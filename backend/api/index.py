from __future__ import annotations

import asyncio
import copy
import io
import json
import logging
import os
import random
import time
import mimetypes
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response, Depends, Header, HTTPException, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# slowapi (rate limiting) is optional at runtime. In environments where it is
# not installed, we fall back to lightweight no-op shims so the API can still
# start normally (just without rate limiting).
try:  # pragma: no cover - exercised implicitly at import time
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
except ImportError:  # pragma: no cover
    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
            """Dummy limiter that accepts any arguments but does nothing."""
            pass
        
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def get_remote_address(request: Request) -> str:
        client = getattr(request, "client", None)
        return getattr(client, "host", "unknown") if client else "unknown"

    class RateLimitExceeded(Exception):
        """Fallback rate limit exception (never actually raised without slowapi)."""

    async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_unavailable", "message": "Rate limiting is not enabled on this server."},
        )

    Limiter = _DummyLimiter  # type: ignore

import httpx
from PIL import Image
from PIL import ImageDraw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
DISCOVERY_WINDOW_MINUTES = 15
ONLINE_WINDOW_MINUTES = 15

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _build_claim_url(request: Request, token: str) -> str:
    override = os.environ.get("INKSIGHT_WEB_BASE_URL", "").rstrip("/")
    if override:
        return f"{override}/claim?token={token}"
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc or "").strip()
    if "inksight.site" not in host.lower():
        return ""
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip()
    return f"{scheme}://{host}/claim?token={token}"

from core.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    DEFAULT_CITY,
    DEFAULT_MODES,
    DEFAULT_REFRESH_INTERVAL,
)
from core.mode_registry import get_registry
from core.context import get_date_context, get_weather, calc_battery_pct
from core.config_store import (
    init_db,
    save_config,
    get_active_config,
    get_config_history,
    activate_config,
    get_cycle_index,
    set_cycle_index,
    update_device_state,
    get_device_state,
    set_pending_refresh,
    consume_pending_refresh,
    generate_device_token,
    validate_device_token,
    create_user,
    authenticate_user,
    bind_device,
    unbind_device,
    get_user_devices,
    get_device_membership,
    get_device_owner,
    get_device_members,
    get_pending_requests_for_owner,
    approve_access_request,
    reject_access_request,
    share_device_with_user,
    revoke_device_member,
    get_user_by_username,
    create_claim_token,
    consume_claim_token,
)
from core.cache import content_cache
from core.schemas import ConfigRequest
from core.pipeline import generate_and_render, get_effective_mode_config
from core.renderer import (
    render_error,
    image_to_bmp_bytes,
    image_to_png_bytes,
)
from core.stats_store import (
    init_stats_db,
    log_render,
    log_heartbeat,
    get_latest_battery_voltage,
    get_latest_heartbeat,
    get_device_stats,
    get_stats_overview,
    get_render_history,
    save_render_content,
    get_content_history,
    add_favorite,
    get_favorites,
    get_latest_render_content,
    check_habit,
    get_habit_status,
    delete_habit,
)
from core.auth import (
    validate_mac_param,
    require_device_token,
    require_admin,
    require_user,
    optional_user,
    create_session_token,
    decode_session_token,
    set_session_cookie,
    clear_session_cookie,
    is_admin_authorized,
)
from core.i18n import detect_lang_from_request, msg


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_stats_db()
    from core.cache import init_cache_db
    await init_cache_db()
    yield
    from core.db import close_all
    await close_all()


app = FastAPI(title="InkSight API", version="1.0.0", lifespan=lifespan)


async def _resolve_user_id(request: Request, ink_session: Optional[str]) -> int | None:
    return await optional_user(request, ink_session)


async def _require_membership_access(
    request: Request,
    mac: str,
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
) -> dict:
    lang = detect_lang_from_request(request)
    mac = validate_mac_param(mac, lang)
    user_id = await _resolve_user_id(request, ink_session)
    if user_id is None:
        raise HTTPException(status_code=401, detail=msg("auth.login_required", lang))
    membership = await get_device_membership(mac, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail=msg("auth.no_device_access", lang))
    if owner_only and membership.get("role") != "owner":
        raise HTTPException(status_code=403, detail=msg("auth.owner_only", lang))
    return membership


async def _ensure_web_or_device_access(
    request: Request,
    mac: str,
    x_device_token: Optional[str],
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
    allow_device_token: bool = True,
) -> dict:
    lang = detect_lang_from_request(request)
    mac = validate_mac_param(mac, lang)
    if allow_device_token and x_device_token:
        await require_device_token(mac, x_device_token)
        return {"mode": "device", "role": "device"}
    membership = await _require_membership_access(request, mac, ink_session, owner_only=owner_only)
    return {"mode": "user", **membership}

# ── Rate limiting ────────────────────────────────────────────


class _NoopLimiter:
    """A shunt limiter for downgrading, which implements the same interface but does not impose any restrictions."""
    def __init__(self, *args, **kwargs):
        pass
    def limit(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator


def _rate_limit_key(request: Request) -> str:
    """Use MAC query param if present, otherwise fall back to client IP."""
    mac = request.query_params.get("mac")
    if mac:
        return f"mac:{mac}"
    return get_remote_address(request)


try:
    limiter = Limiter(key_func=_rate_limit_key)
except Exception as e:
    logging.warning("Rate limiter disabled due to init error: %s", e)
    limiter = _NoopLimiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global error handler for InkSightError hierarchy ─────────
from core.errors import InkSightError


@app.exception_handler(InkSightError)
async def inksight_error_handler(request: Request, exc: InkSightError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.message},
    )


FIRMWARE_CHIP_FAMILY = "ESP32-C3"
FIRMWARE_RELEASE_CACHE_TTL = int(os.getenv("FIRMWARE_RELEASE_CACHE_TTL", "120"))
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "datascale-ai")
GITHUB_REPO = os.getenv("GITHUB_REPO", "inksight")
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
_firmware_release_cache = {
    "expires_at": 0.0,
    "payload": None,
}
_firmware_release_cache_lock = asyncio.Lock()
_preview_push_queue: dict[str, dict] = {}
_preview_push_queue_lock = asyncio.Lock()

# Debug mode: used by firmware to enable fast refresh (1 min) for testing
# Backend cache is always enabled regardless of this flag
DEBUG_MODE = False  # Set to False in production

# Smart mode default time-slot mapping
_SMART_TIME_SLOTS = [
    (6, 9, ["RECIPE", "DAILY"]),
    (9, 12, ["BRIEFING", "STOIC"]),
    (12, 14, ["ZEN", "POETRY"]),
    (14, 18, ["STOIC", "ROAST"]),
    (18, 21, ["FITNESS", "RECIPE"]),
    (21, 24, ["ZEN", "POETRY"]),
    (0, 6, ["ZEN", "POETRY"]),
]


# ── Mode resolution ──────────────────────────────────────────


async def _choose_persona_from_config(config: dict, peek_next: bool = False) -> str:
    """Choose persona based on refresh strategy (async for DB-backed cycle_index).

    Args:
        config: User configuration
        peek_next: If True, return the NEXT persona without incrementing counter (for pre-generation)
    """
    modes = config.get("modes", DEFAULT_MODES)
    if not modes:
        modes = DEFAULT_MODES

    strategy = config.get("refresh_strategy", "random")
    logger.debug(
        f"[STRATEGY] refresh_strategy={strategy}, modes={modes}, peek_next={peek_next}"
    )

    if strategy == "cycle":
        mac = config.get("mac", "default")
        idx = await get_cycle_index(mac)
        persona = modes[idx % len(modes)]
        if not peek_next:
            await set_cycle_index(mac, idx + 1)
            logger.debug(
                f"[CYCLE] {mac}: index {idx} → {idx + 1}, persona={persona}, modes={modes}"
            )
        return persona

    elif strategy == "time_slot":
        hour = datetime.now().hour
        rules = config.get("time_slot_rules", [])
        for rule in rules:
            start_h = rule.get("startHour", 0)
            end_h = rule.get("endHour", 24)
            rule_modes = rule.get("modes", [])
            if start_h <= hour < end_h and rule_modes:
                available = [m for m in rule_modes if m in modes]
                if available:
                    persona = random.choice(available)
                    logger.debug(f"[TIME_SLOT] hour={hour}, matched {start_h}-{end_h}, persona={persona}")
                    return persona
        logger.debug(f"[TIME_SLOT] hour={hour}, no rule matched, falling back to random")
        return random.choice(modes)

    elif strategy == "smart":
        hour = datetime.now().hour
        for start_h, end_h, candidates in _SMART_TIME_SLOTS:
            if start_h <= hour < end_h:
                available = [m for m in candidates if m in modes]
                if available:
                    persona = random.choice(available)
                    logger.debug(f"[SMART] hour={hour}, candidates={candidates}, persona={persona}")
                    return persona
        return random.choice(modes)

    else:
        return random.choice(modes)


async def _resolve_mode(
    mac: Optional[str], config: Optional[dict], persona_override: Optional[str],
    force_next: bool = False,
) -> str:
    """Determine which persona to use for this request.

    Args:
        force_next: If True, advance to the next mode in the enabled list
                    (triggered by device double-click).
    """
    registry = get_registry()

    # Check for pending_mode (remote switch via API)
    if mac and not persona_override:
        pending = await _consume_pending_mode(mac)
        if pending and registry.is_supported(pending.upper()):
            logger.debug(f"[REQUEST] Using pending_mode: {pending}")
            return pending.upper()

    if persona_override and registry.is_supported(persona_override.upper()):
        persona = persona_override.upper()
        logger.debug(f"[REQUEST] Using override persona: {persona}")
    elif config:
        if force_next:
            persona = await _advance_to_next_mode(mac, config)
        else:
            persona = await _choose_persona_from_config(config)
        mac_key = config.get("mac", "default")
        logger.debug(
            f"[REQUEST] Chosen persona: {persona}, mac_key={mac_key}, force_next={force_next}"
        )
    else:
        persona = random.choice(["STOIC", "ROAST", "ZEN", "DAILY"])
        logger.debug(f"[REQUEST] No config, random persona: {persona}")
    return persona


async def _advance_to_next_mode(mac: Optional[str], config: dict) -> str:
    """Pick the next mode after the current one in the enabled list."""
    modes = config.get("modes", DEFAULT_MODES)
    if not modes:
        return "STOIC"

    state = await get_device_state(mac) if mac else None
    current = state.get("last_persona", "") if state else ""

    if current in modes:
        idx = (modes.index(current) + 1) % len(modes)
    else:
        idx = 0

    persona = modes[idx]

    # Also update cycle_index to keep in sync
    if mac:
        await set_cycle_index(mac, idx + 1)

    return persona


async def _consume_pending_mode(mac: str) -> Optional[str]:
    """Check and clear pending_mode. Returns mode name or None."""
    try:
        state = await get_device_state(mac)
        if state and state.get("pending_mode"):
            mode = state["pending_mode"]
            await update_device_state(mac, pending_mode="")
            return mode
    except Exception:
        logger.warning(f"[PENDING_MODE] Failed to consume for {mac}", exc_info=True)
    return None


# ── Main orchestrator ────────────────────────────────────────


async def _build_image(
    v: float, mac: Optional[str], persona_override: Optional[str] = None,
    rssi: Optional[int] = None,
    screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    force_next: bool = False,
    skip_cache: bool = False,
    preview_city_override: Optional[str] = None,
    preview_mode_override: Optional[dict] = None,
    preview_memo_text: Optional[str] = None,
):
    battery_pct = calc_battery_pct(v)

    config = None
    if mac:
        config = await get_active_config(mac)

    persona = await _resolve_mode(mac, config, persona_override, force_next=force_next)
    mode_info = get_registry().get_mode_info(persona)
    is_mode_cacheable = bool(mode_info.cacheable) if mode_info else True
    if preview_city_override or preview_mode_override or preview_memo_text:
        config = copy.deepcopy(config or {})
        mode_overrides = dict(config.get("mode_overrides") or {})
        current_mode_override = dict(mode_overrides.get(persona) or {})
        if preview_city_override:
            config["city"] = preview_city_override
            current_mode_override["city"] = preview_city_override
        if isinstance(preview_mode_override, dict) and preview_mode_override:
            current_mode_override.update(preview_mode_override)
        mode_overrides[persona] = current_mode_override
        config["mode_overrides"] = mode_overrides
        config["modeOverrides"] = mode_overrides
        if (persona or "").upper() == "MEMO":
            memo_text = current_mode_override.get("memo_text")
            if isinstance(memo_text, str) and memo_text.strip():
                config["memo_text"] = memo_text.strip()
                config["memoText"] = memo_text.strip()
            if isinstance(preview_memo_text, str) and preview_memo_text.strip():
                memo_clean = preview_memo_text.strip()
                current_mode_override["memo_text"] = memo_clean
                mode_overrides[persona] = current_mode_override
                config["mode_overrides"] = mode_overrides
                config["modeOverrides"] = mode_overrides
                config["memo_text"] = memo_clean
                config["memoText"] = memo_clean

    # Try cache first
    cache_hit = False
    if mac and config and is_mode_cacheable and not skip_cache:
        await content_cache.check_and_regenerate_all(mac, config, v, screen_w, screen_h)
        cached_img = await content_cache.get(mac, persona, config, screen_w=screen_w, screen_h=screen_h)
        if cached_img:
            logger.info(f"[CACHE HIT] {mac}:{persona} - Returning cached image")
            cache_hit = True
            img = cached_img
        else:
            logger.info(f"[CACHE MISS] {mac}:{persona} - Generating fallback content")
    elif skip_cache:
        logger.info(f"[PREVIEW] Skip cache for {mac}:{persona}")

    content_data = None
    content_fallback = False
    if not cache_hit:
        effective_cfg = get_effective_mode_config(config, persona)
        city = effective_cfg.get("city", DEFAULT_CITY) if effective_cfg else None
        date_ctx, weather = await asyncio.gather(
            get_date_context(),
            get_weather(city=city),
        )
        img, content_data = await generate_and_render(
            persona, config, date_ctx, weather, battery_pct,
            screen_w=screen_w, screen_h=screen_h,
            mac=mac or "",
        )
        if isinstance(content_data, dict):
            if content_data.get("_is_fallback") is True:
                content_fallback = True
            else:
                jm = get_registry().get_json_mode(persona)
                if jm and (jm.definition.get("content", {}).get("type") == "image_gen"):
                    content_fallback = not bool(content_data.get("image_url"))

        if mac and config and is_mode_cacheable:
            await content_cache.set(mac, persona, img, screen_w, screen_h)

    if mac:
        await update_device_state(
            mac,
            last_persona=persona,
            last_refresh_at=datetime.now().isoformat(),
        )

    # Save content history
    if mac and content_data:
        try:
            await save_render_content(mac, persona, content_data)
        except Exception:
            logger.warning(f"[CONTENT] Failed to save content for {mac}:{persona}", exc_info=True)

    return img, persona, cache_hit, content_fallback


# ── Stats helper ─────────────────────────────────────────────


async def _log_render(
    mac: str, persona: str, cache_hit: bool, elapsed_ms: int,
    voltage: float = 3.3, rssi: Optional[int] = None, status: str = "success",
):
    """Log render stats and device heartbeat (fire-and-forget)."""
    try:
        await log_render(mac, persona, cache_hit, elapsed_ms, status)
        await log_heartbeat(mac, voltage, rssi)
    except Exception:
        logger.warning(f"[STATS] Failed to log render stats for {mac}", exc_info=True)


async def _resolve_preview_voltage(v: Optional[float], mac: Optional[str]) -> float:
    if v is not None:
        return v
    if mac:
        latest_voltage = await get_latest_battery_voltage(mac)
        if latest_voltage is not None:
            return latest_voltage
    return 3.3


def _resolve_refresh_minutes_for_device_state(config: Optional[dict], state: Optional[dict]) -> int:
    refresh_minutes_raw = config.get("refresh_interval") if config else DEFAULT_REFRESH_INTERVAL
    try:
        refresh_minutes = int(refresh_minutes_raw)
    except Exception:
        refresh_minutes = DEFAULT_REFRESH_INTERVAL
    if refresh_minutes <= 0:
        refresh_minutes = DEFAULT_REFRESH_INTERVAL
    expected_refresh_raw = state.get("expected_refresh_min", 0) if state else 0
    try:
        expected_refresh = int(expected_refresh_raw)
    except Exception:
        expected_refresh = 0
    if expected_refresh > 0:
        refresh_minutes = expected_refresh
    return refresh_minutes


def _reconnect_threshold_seconds(refresh_minutes: int) -> int:
    base_seconds = max(1, int(refresh_minutes)) * 60
    return max(base_seconds + 30, int(base_seconds * 1.5))


def _build_firmware_manifest(version: str, download_url: str) -> dict:
    return {
        "name": "InkSight",
        "version": version,
        "builds": [
            {
                "chipFamily": FIRMWARE_CHIP_FAMILY,
                "parts": [
                    {
                        "path": download_url,
                        "offset": 0,
                    }
                ],
            }
        ],
    }


def _pick_firmware_asset(assets: list[dict]) -> Optional[dict]:
    preferred = [
        a for a in assets
        if a.get("name", "").endswith(".bin") and "inksight-firmware-" in a.get("name", "")
    ]
    if preferred:
        return preferred[0]
    fallback = [a for a in assets if a.get("name", "").endswith(".bin")]
    return fallback[0] if fallback else None


async def _load_firmware_releases(force_refresh: bool = False) -> dict:
    now = time.time()
    async with _firmware_release_cache_lock:
        if (
            not force_refresh
            and _firmware_release_cache["payload"] is not None
            and _firmware_release_cache["expires_at"] > now
        ):
            cached_payload = dict(_firmware_release_cache["payload"])
            cached_payload["cached"] = True
            return cached_payload

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "inksight-firmware-api",
        }
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(GITHUB_RELEASES_API, headers=headers)
            if resp.status_code >= 400:
                message = f"GitHub releases API error: {resp.status_code}"
                try:
                    details = resp.json().get("message")
                    if details:
                        message = f"{message} - {details}"
                except Exception:
                    pass
                raise RuntimeError(message)

            releases = []
            for rel in resp.json():
                if rel.get("draft"):
                    continue
                asset = _pick_firmware_asset(rel.get("assets", []))
                if not asset:
                    continue

                tag_name = rel.get("tag_name", "")
                version = tag_name.lstrip("v") if tag_name else "unknown"
                download_url = asset.get("browser_download_url")
                if not download_url:
                    continue

                releases.append({
                    "version": version,
                    "tag": tag_name,
                    "published_at": rel.get("published_at"),
                    "download_url": download_url,
                    "size_bytes": asset.get("size"),
                    "chip_family": FIRMWARE_CHIP_FAMILY,
                    "asset_name": asset.get("name"),
                    "manifest": _build_firmware_manifest(version, download_url),
                })

            payload = {
                "source": "github_releases",
                "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
                "cached": False,
                "count": len(releases),
                "releases": releases,
            }
        except Exception as exc:
            logger.warning(f"[FIRMWARE] Failed to load releases: {exc}")
            raise

        _firmware_release_cache["payload"] = payload
        _firmware_release_cache["expires_at"] = now + FIRMWARE_RELEASE_CACHE_TTL
        return payload


async def _validate_firmware_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("firmware URL must start with http:// or https://")

    if not parsed.netloc:
        raise ValueError("firmware URL host is missing")

    if not parsed.path.lower().endswith(".bin"):
        raise ValueError("firmware URL should point to a .bin file")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            resp = await client.head(url)
            status_code = resp.status_code
            headers = resp.headers
            final_url = str(resp.url)
        except Exception:
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
            status_code = resp.status_code
            headers = resp.headers
            final_url = str(resp.url)

    if status_code >= 400:
        raise RuntimeError(f"firmware URL is not reachable: {status_code}")

    return {
        "ok": True,
        "reachable": True,
        "status_code": status_code,
        "final_url": final_url,
        "content_type": headers.get("content-type"),
        "content_length": headers.get("content-length"),
    }


# ── Render endpoints ─────────────────────────────────────────


@app.get("/api/render")
@limiter.limit("10/minute")
async def render(
    request: Request,
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: Optional[str] = Query(default=None, description="Device MAC address"),
    persona: Optional[str] = Query(default=None, description="Force persona"),
    rssi: Optional[int] = Query(default=None, description="WiFi RSSI (dBm)"),
    refresh_min: Optional[int] = Query(default=None, ge=1, le=1440, description="Device effective refresh interval in minutes"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600, description="Screen width in pixels"),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200, description="Screen height in pixels"),
    next_mode: Optional[int] = Query(default=None, alias="next", description="1 = advance to next mode (double-click)"),
    x_device_token: Optional[str] = Header(default=None),
):
    if mac:
        mac = validate_mac_param(mac)
        await require_device_token(mac, x_device_token)
    start_time = time.time()
    force_next = (next_mode == 1)
    logger.debug(f"[RENDER] Request started: mac={mac}, v={v}, persona={persona}, next={force_next}, size={w}x{h}")

    try:
        if mac:
            pushed_payload = None
            async with _preview_push_queue_lock:
                pushed_payload = _preview_push_queue.pop(mac, None)
            if pushed_payload and pushed_payload.get("image"):
                try:
                    with Image.open(io.BytesIO(pushed_payload["image"])) as pushed_img:
                        img = pushed_img.convert("1")
                        if img.size != (w, h):
                            img = img.resize((w, h), Image.NEAREST)
                    bmp_bytes = image_to_bmp_bytes(img)
                    elapsed = time.time() - start_time
                    elapsed_ms = int(elapsed * 1000)
                    resolved_persona = pushed_payload.get("mode") or persona or "PUSH_PREVIEW"
                    await _log_render(mac, resolved_persona, False, elapsed_ms, v, rssi)
                    if refresh_min is not None:
                        await update_device_state(mac, expected_refresh_min=refresh_min)
                    logger.info(
                        f"[RENDER] ✓ Preview push delivered in {elapsed:.2f}s - {mac}:{resolved_persona} ({w}x{h})"
                    )
                    headers = {"X-Preview-Push": "1"}
                    was_pending = await consume_pending_refresh(mac)
                    if was_pending:
                        headers["X-Pending-Refresh"] = "1"
                    return Response(content=bmp_bytes, media_type="image/bmp", headers=headers)
                except Exception as push_err:
                    logger.warning(f"[RENDER] Failed to deliver pushed preview for {mac}: {push_err}")

        skip_cache_for_this_render = False
        if mac:
            cfg_for_online_check = await get_active_config(mac)
            if cfg_for_online_check:
                state_for_online_check = await get_device_state(mac)
                refresh_minutes_for_online_check = _resolve_refresh_minutes_for_device_state(
                    cfg_for_online_check, state_for_online_check
                )
                latest_heartbeat = await get_latest_heartbeat(mac)
                if latest_heartbeat and latest_heartbeat.get("created_at"):
                    try:
                        now_dt = datetime.now()
                        delta_seconds = (
                            now_dt - datetime.fromisoformat(latest_heartbeat["created_at"])
                        ).total_seconds()
                        threshold_seconds = _reconnect_threshold_seconds(refresh_minutes_for_online_check)
                        last_regen_raw = (
                            state_for_online_check.get("last_reconnect_regen_at", "")
                            if state_for_online_check
                            else ""
                        )
                        regen_cooldown_ok = True
                        if isinstance(last_regen_raw, str) and last_regen_raw:
                            try:
                                since_last_regen = (
                                    now_dt - datetime.fromisoformat(last_regen_raw)
                                ).total_seconds()
                                regen_cooldown_ok = since_last_regen > threshold_seconds
                            except Exception:
                                regen_cooldown_ok = True
                        if delta_seconds > threshold_seconds and regen_cooldown_ok:
                            skip_cache_for_this_render = True
                            await update_device_state(
                                mac, last_reconnect_regen_at=now_dt.isoformat()
                            )
                            await content_cache.force_regenerate_all(
                                mac, cfg_for_online_check, v, w, h
                            )
                            logger.info(
                                f"[RECONNECT] {mac} offline {int(delta_seconds)}s "
                                f"(threshold={threshold_seconds}s), forcing fresh render"
                            )
                    except Exception:
                        pass
        img, resolved_persona, cache_hit, content_fallback = await _build_image(
            v, mac, persona, rssi, screen_w=w, screen_h=h, force_next=force_next,
            skip_cache=skip_cache_for_this_render,
        )
        # 确保返回给固件的图像尺寸严格等于设备请求的 w×h。
        # 如果某个模式或配置导致渲染尺寸与固件编译时的分辨率不一致，
        # 固件在按固定字节数读取 BMP 时就会出现 "Failed to read row" -> Server error。
        if img.size != (w, h):
            logger.warning(
                f"[RENDER] Image size mismatch for {mac}:{resolved_persona}: "
                f"got {img.size[0]}x{img.size[1]}, expected {w}x{h}. Resizing to match."
            )
            img = img.resize((w, h), Image.NEAREST)

        bmp_bytes = image_to_bmp_bytes(img)
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(
            f"[RENDER] ✓ Success in {elapsed:.2f}s - Generated BMP: {len(bmp_bytes)} bytes for {mac}:{resolved_persona} ({w}x{h})"
        )

        if mac:
            await _log_render(mac, resolved_persona, cache_hit, elapsed_ms, v, rssi)
            if refresh_min is not None:
                await update_device_state(mac, expected_refresh_min=refresh_min)

        headers = {}
        if mac:
            was_pending = await consume_pending_refresh(mac)
            if was_pending:
                headers["X-Pending-Refresh"] = "1"
        if content_fallback:
            headers["X-Content-Fallback"] = "1"

        return Response(content=bmp_bytes, media_type="image/bmp", headers=headers)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[RENDER] ✗ Failed in {elapsed:.2f}s - Error: {e}")
        logger.exception("Exception occurred during render")
        if mac:
            await _log_render(mac, persona or "unknown", False, int(elapsed * 1000), v, rssi, status="error")
        err_img = render_error(mac=mac or "unknown", screen_w=w, screen_h=h)
        return Response(
            content=image_to_bmp_bytes(err_img), media_type="image/bmp", status_code=500
        )


@app.get("/api/widget/{mac}")
async def get_widget(
    mac: str,
    mode: str = "",
    w: int = 400,
    h: int = 300,
    size: str = "",
    x_device_token: Optional[str] = Header(default=None),
):
    """Read-only widget endpoint for embedding InkSight content.
    Does NOT update device state or trigger refreshes.
    """
    await require_device_token(mac, x_device_token)
    # Size presets
    if size == "small":
        w, h = 200, 150
    elif size == "medium":
        w, h = 400, 300
    elif size == "large":
        w, h = 800, 480

    config = await get_active_config(mac)
    if not config:
        config = {}

    persona = mode.upper() if mode else config.get("modes", ["STOIC"])[0] if config.get("modes") else "STOIC"
    city = config.get("city") if config else None

    date_ctx = await get_date_context()
    weather = await get_weather(city=city)

    img, _ = await generate_and_render(
        persona, config, date_ctx, weather, 100.0,
        screen_w=w, screen_h=h,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-InkSight-Mode": persona,
        },
    )


@app.get("/api/preview")
@limiter.limit("20/minute")
async def preview(
    request: Request,
    v: Optional[float] = Query(default=None, description="Battery voltage"),
    mac: Optional[str] = Query(default=None, description="Device MAC address"),
    persona: Optional[str] = Query(default=None, description="Force persona"),
    city_override: Optional[str] = Query(default=None, description="Override city for preview"),
    mode_override: Optional[str] = Query(default=None, description="JSON object override for current mode in preview only"),
    memo_text: Optional[str] = Query(default=None, description="Memo text override for MEMO preview"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600, description="Screen width in pixels"),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200, description="Screen height in pixels"),
    no_cache: Optional[int] = Query(default=None, description="1 = bypass cache for this preview"),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    if mac:
        mac = validate_mac_param(mac)
        await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    try:
        effective_v = await _resolve_preview_voltage(v, mac)
        parsed_mode_override = None
        if mode_override:
            try:
                candidate = json.loads(mode_override)
                if isinstance(candidate, dict):
                    parsed_mode_override = candidate
            except Exception:
                parsed_mode_override = None
        img, resolved_persona, cache_hit, _content_fallback = await _build_image(
            effective_v, mac, persona, screen_w=w, screen_h=h,
            skip_cache=(no_cache == 1),
            preview_city_override=(city_override.strip() if city_override else None),
            preview_mode_override=parsed_mode_override,
            preview_memo_text=(memo_text if isinstance(memo_text, str) else None),
        )
        png_bytes = image_to_png_bytes(img)
        logger.info(f"[PREVIEW] Generated PNG: {len(png_bytes)} bytes, persona={resolved_persona} ({w}x{h})")
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "X-Cache-Hit": "1" if cache_hit else "0",
                "X-Preview-Bypass": "1" if no_cache == 1 else "0",
            },
        )
    except Exception:
        logger.exception("Exception occurred during preview")
        err_img = render_error(mac=mac or "unknown", screen_w=w, screen_h=h)
        return Response(
            content=image_to_png_bytes(err_img), media_type="image/png", status_code=500
        )


# ── Config endpoints ─────────────────────────────────────────


@app.post("/api/config")
async def post_config(
    request: Request,
    body: ConfigRequest,
    x_inksight_client: Optional[str] = Header(default=None),
    x_device_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    data = body.model_dump()
    mac = data["mac"]
    if not is_admin_authorized(authorization):
        await _ensure_web_or_device_access(
            request,
            mac,
            x_device_token,
            ink_session,
            allow_device_token=True,
        )
    modes = data.get("modes", [])
    logger.info(
        f"[CONFIG SAVE REQUEST] source={x_inksight_client or 'unknown'} "
        f"mac={mac} modes={len(modes) if isinstance(modes, list) else 0} "
        f"refresh_strategy={data.get('refresh_strategy')}"
    )
    config_id = await save_config(mac, data)
    await update_device_state(mac, runtime_mode="interval")

    saved_config = await get_active_config(mac)
    if saved_config:
        logger.info(
            f"[CONFIG VERIFY] Saved config id={saved_config.get('id')}, "
            f"refresh_strategy={saved_config.get('refresh_strategy')}"
        )

    return {"ok": True, "config_id": config_id}


@app.get("/api/config/{mac}")
async def get_config(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    config = await get_active_config(mac)
    if not config:
        return JSONResponse({"error": "no config found"}, status_code=404)
    # Strip encrypted key from API response (keep has_api_key flag)
    config.pop("llm_api_key", None)
    config.pop("image_api_key", None)
    return config


@app.get("/api/config/{mac}/history")
async def get_config_hist(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    history = await get_config_history(mac)
    # Strip encrypted keys from API response
    for cfg in history:
        cfg.pop("llm_api_key", None)
        cfg.pop("image_api_key", None)
    return {"mac": mac, "configs": history}


@app.put("/api/config/{mac}/activate/{config_id}")
async def put_activate(mac: str, config_id: int, admin_auth: None = Depends(require_admin)):
    ok = await activate_config(mac, config_id)
    if not ok:
        return JSONResponse({"error": "config not found"}, status_code=404)
    return {"ok": True}


# ── Custom mode endpoints ────────────────────────────────────


@app.get("/api/modes")
async def list_modes():
    """List all available modes (builtin + custom)."""
    registry = get_registry()
    modes = []
    for info in registry.list_modes():
        modes.append({
            "mode_id": info.mode_id,
            "display_name": info.display_name,
            "icon": info.icon,
            "cacheable": info.cacheable,
            "description": info.description,
            "source": info.source,
            "settings_schema": info.settings_schema,
        })
    return {"modes": modes}


@app.post("/api/modes/custom/preview")
async def custom_mode_preview(body: dict, admin_auth: None = Depends(require_admin)):
    """Render a preview for a custom mode definition without saving."""
    mode_def = body.get("mode_def", body)
    if not mode_def.get("mode_id"):
        mode_def = dict(mode_def, mode_id="PREVIEW")
    screen_w = body.get("w", SCREEN_WIDTH)
    screen_h = body.get("h", SCREEN_HEIGHT)
    try:
        from core.json_content import generate_json_mode_content
        from core.json_renderer import render_json_mode

        date_ctx = await get_date_context()
        weather = await get_weather()
        content = await generate_json_mode_content(
            mode_def,
            date_ctx=date_ctx,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            screen_w=screen_w,
            screen_h=screen_h,
        )
        img = render_json_mode(
            mode_def, content,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            battery_pct=100.0,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="image/png")
    except Exception as e:
        logger.exception("[CUSTOM_PREVIEW] Preview failed")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )


@app.post("/api/modes/custom")
async def create_custom_mode(body: dict, admin_auth: None = Depends(require_admin)):
    """Upload a JSON mode definition."""
    import json as _json
    from core.mode_registry import CUSTOM_JSON_DIR, _validate_mode_def

    mode_id = body.get("mode_id", "").upper()
    if not mode_id:
        return JSONResponse({"error": "mode_id is required"}, status_code=400)

    if not _validate_mode_def(body):
        return JSONResponse({"error": "Invalid mode definition"}, status_code=400)

    body["mode_id"] = mode_id

    registry = get_registry()
    if registry.is_builtin(mode_id):
        return JSONResponse(
            {"error": f"Cannot override builtin mode: {mode_id}"}, status_code=409
        )

    file_path = Path(CUSTOM_JSON_DIR) / f"{mode_id.lower()}.json"
    file_path.write_text(_json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    registry.unregister_custom(mode_id)
    loaded = registry.load_json_mode(str(file_path), source="custom")
    if not loaded:
        file_path.unlink(missing_ok=True)
        return JSONResponse({"error": "Failed to load mode definition"}, status_code=400)

    logger.info(f"[MODES] Created custom mode: {mode_id}")
    return {"ok": True, "mode_id": mode_id}


@app.get("/api/modes/custom/{mode_id}")
async def get_custom_mode(mode_id: str):
    """Get a custom mode's JSON definition."""
    registry = get_registry()
    jm = registry.get_json_mode(mode_id.upper())
    if not jm or jm.info.source != "custom":
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)
    return jm.definition


@app.delete("/api/modes/custom/{mode_id}")
async def delete_custom_mode(mode_id: str, admin_auth: None = Depends(require_admin)):
    """Delete a custom mode."""
    mode_id = mode_id.upper()
    registry = get_registry()

    jm = registry.get_json_mode(mode_id)
    if not jm or jm.info.source != "custom":
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)

    file_path = jm.file_path
    registry.unregister_custom(mode_id)

    if file_path:
        Path(file_path).unlink(missing_ok=True)

    logger.info(f"[MODES] Deleted custom mode: {mode_id}")
    return {"ok": True, "mode_id": mode_id}


@app.post("/api/modes/generate")
async def generate_mode(body: dict, admin_auth: None = Depends(require_admin)):
    """Use AI to generate a mode definition from natural language description."""
    description = body.get("description", "").strip()
    if not description:
        return JSONResponse({"error": "description is required"}, status_code=400)
    if len(description) > 2000:
        return JSONResponse(
            {"error": "description too long (max 2000 chars)"}, status_code=400
        )

    image_base64 = body.get("image_base64")
    if image_base64 and len(image_base64) > 5 * 1024 * 1024:
        return JSONResponse(
            {"error": "image too large (max 4MB)"}, status_code=400
        )

    provider = body.get("provider", "deepseek")
    model = body.get("model", "deepseek-chat")

    from core.mode_generator import generate_mode_definition

    try:
        result = await generate_mode_definition(
            description=description,
            image_base64=image_base64,
            provider=provider,
            model=model,
        )
        return result
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.exception("[MODE_GEN] Failed to generate mode")
        return JSONResponse(
            {"error": f"生成失败: {type(e).__name__}: {str(e)[:200]}"},
            status_code=500,
        )


# ── Misc endpoints ───────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/firmware/releases")
async def firmware_releases(refresh: bool = Query(default=False)):
    """List available firmware releases from GitHub Releases."""
    try:
        data = await _load_firmware_releases(force_refresh=refresh)
        return data
    except Exception as exc:
        return JSONResponse(
            {
                "error": "firmware_release_fetch_failed",
                "message": str(exc),
                "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            },
            status_code=503,
        )


@app.get("/api/firmware/releases/latest")
async def firmware_releases_latest(refresh: bool = Query(default=False)):
    """Get the latest recommended firmware release."""
    try:
        data = await _load_firmware_releases(force_refresh=refresh)
        releases = data.get("releases", [])
        if not releases:
            return JSONResponse(
                {
                    "error": "firmware_release_not_found",
                    "message": "No published firmware release with .bin asset found",
                    "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
                },
                status_code=404,
            )
        return {
            "source": data.get("source"),
            "repo": data.get("repo"),
            "cached": data.get("cached", False),
            "latest": releases[0],
        }
    except Exception as exc:
        return JSONResponse(
            {
                "error": "firmware_release_fetch_failed",
                "message": str(exc),
                "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            },
            status_code=503,
        )


@app.get("/api/firmware/validate-url")
async def firmware_validate_url(url: str = Query(..., description="Firmware .bin URL")):
    """Validate manual firmware URL format and reachability."""
    try:
        result = await _validate_firmware_url(url)
        return result
    except ValueError as exc:
        return JSONResponse(
            {
                "error": "invalid_firmware_url",
                "message": str(exc),
                "url": url,
            },
            status_code=400,
        )
    except Exception as exc:
        return JSONResponse(
            {
                "error": "firmware_url_unreachable",
                "message": str(exc),
                "url": url,
            },
            status_code=503,
        )


@app.get("/", response_class=HTMLResponse)
async def preview_page():
    return HTMLResponse(content=_load_web_page_html("preview.html"))


@app.get("/preview", response_class=HTMLResponse)
async def preview_page_alias():
    return HTMLResponse(content=_load_web_page_html("preview.html"))


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    return HTMLResponse(content=_load_web_page_html("config.html"))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return HTMLResponse(content=_load_web_page_html("dashboard.html"))


@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    return HTMLResponse(content=_load_web_page_html("editor.html"))


@app.get("/webconfig/{asset_path:path}")
async def webconfig_asset(asset_path: str):
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = (project_root / "webconfig" / asset_path).resolve()
    webconfig_root = (project_root / "webconfig").resolve()
    if not str(file_path).startswith(str(webconfig_root)) or not file_path.exists() or not file_path.is_file():
        return JSONResponse({"error": "asset_not_found", "message": "Webconfig asset not found"}, status_code=404)
    media_type, _ = mimetypes.guess_type(str(file_path))
    return Response(content=file_path.read_bytes(), media_type=media_type or "application/octet-stream")


@app.get("/thumbs/{filename}")
async def get_thumb(filename: str):
    project_root = Path(__file__).resolve().parent.parent.parent
    thumb_path = project_root / "webconfig" / "thumbs" / filename
    if thumb_path.exists() and thumb_path.is_file():
        return Response(content=thumb_path.read_bytes(), media_type="image/png")

    mode_name = Path(filename).stem.upper() if filename else "MODE"
    img = Image.new("L", (400, 300), 248)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(18, 18), (382, 282)], outline=180, width=1)
    draw.text((170, 130), mode_name[:16], fill=40)
    draw.text((110, 165), "No static thumbnail", fill=110)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def _load_web_page_html(filename: str) -> str:
    """Load static page from webconfig directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    html_path = project_root / "webconfig" / filename
    if not html_path.exists():
        raise FileNotFoundError(f"Static page not found in webconfig: {filename}")
    html = html_path.read_text(encoding="utf-8")
    if "/webconfig/i18n.js" not in html:
        html = html.replace("</body>", '<script src="/webconfig/i18n.js"></script></body>')
    return html


# ── Device control endpoints ─────────────────────────────────


@app.post("/api/device/{mac}/refresh")
async def trigger_refresh(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Mark a device for immediate refresh on next wake-up."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    await set_pending_refresh(mac, True)
    logger.info(f"[DEVICE] Pending refresh set for {mac}")
    return {"ok": True, "message": "Refresh queued for next wake-up"}


@app.get("/api/device/{mac}/state")
async def device_state(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Get device runtime state."""
    access = await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    if access["mode"] == "device":
        await update_device_state(mac, last_state_poll_at=datetime.now().isoformat())
    state = await get_device_state(mac)
    if not state:
        return JSONResponse({"error": "no device state found"}, status_code=404)

    cfg = await get_active_config(mac, log_load=False)
    refresh_minutes = _resolve_refresh_minutes_for_device_state(cfg, state)
    latest_heartbeat = await get_latest_heartbeat(mac)
    last_seen = latest_heartbeat.get("created_at") if latest_heartbeat else None
    is_online = False
    if isinstance(last_seen, str) and last_seen:
        try:
            delta_seconds = (datetime.now() - datetime.fromisoformat(last_seen)).total_seconds()
            is_online = delta_seconds <= (ONLINE_WINDOW_MINUTES * 60)
        except Exception:
            is_online = False
    state["last_seen"] = last_seen
    state["is_online"] = is_online
    state["refresh_minutes"] = refresh_minutes

    # Prefer explicit device-reported runtime_mode when available.
    # Firmware toggles this via /api/device/{mac}/runtime on BOOT key action.
    explicit_mode = str(state.get("runtime_mode") or "").lower()
    if explicit_mode in ("active", "interval"):
        state["runtime_mode"] = explicit_mode
        return state

    runtime_mode = ""
    last_poll = state.get("last_state_poll_at", "")
    if isinstance(last_poll, str) and last_poll:
        try:
            delta = (datetime.now() - datetime.fromisoformat(last_poll)).total_seconds()
            runtime_mode = "active" if delta <= 8 else "interval"
        except Exception:
            pass

    if runtime_mode not in ("active", "interval"):
        runtime_mode = "interval"

    state["runtime_mode"] = runtime_mode
    return state


@app.post("/api/device/{mac}/runtime")
async def set_runtime_mode(mac: str, body: dict, x_device_token: Optional[str] = Header(default=None)):
    """Update device runtime mode (active/interval)."""
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    mode = str(body.get("mode", "")).strip().lower()
    if mode not in ("active", "interval"):
        return JSONResponse({"error": "mode must be active or interval"}, status_code=400)
    await update_device_state(mac, runtime_mode=mode)
    return {"ok": True, "runtime_mode": mode}


@app.post("/api/device/{mac}/heartbeat")
async def post_device_heartbeat(mac: str, body: dict, x_device_token: Optional[str] = Header(default=None)):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    battery_voltage = body.get("battery_voltage")
    wifi_rssi = body.get("wifi_rssi")
    try:
        voltage = float(battery_voltage) if battery_voltage is not None else 3.3
    except Exception:
        voltage = 3.3
    try:
        rssi = int(wifi_rssi) if wifi_rssi is not None else None
    except Exception:
        rssi = None
    await log_heartbeat(mac, voltage, rssi)
    return {"ok": True}


@app.post("/api/device/{mac}/apply-preview")
async def apply_preview_to_device(
    mac: str,
    request: Request,
    mode: str = Query(default="", description="Optional mode hint for logs/state"),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Queue a one-shot preview image to be sent by /api/render."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    body = await request.body()
    if not body:
        return JSONResponse({"error": "empty image payload"}, status_code=400)
    if len(body) > 4 * 1024 * 1024:
        return JSONResponse({"error": "image payload too large"}, status_code=413)

    try:
        with Image.open(io.BytesIO(body)) as incoming:
            normalized = io.BytesIO()
            incoming.convert("L").save(normalized, format="PNG")
            normalized_bytes = normalized.getvalue()
    except Exception:
        return JSONResponse({"error": "invalid image payload"}, status_code=400)

    mode_hint = mode.strip().upper()
    async with _preview_push_queue_lock:
        _preview_push_queue[mac] = {"image": normalized_bytes, "mode": mode_hint}
    await set_pending_refresh(mac, True)
    logger.info(
        f"[DEVICE] Queued preview push for {mac}, bytes={len(normalized_bytes)}, mode={mode_hint or '-'}"
    )
    return {"ok": True, "message": "Preview queued"}


@app.post("/api/device/{mac}/switch")
async def switch_mode(
    mac: str,
    body: dict,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Set a pending mode for the device to use on next refresh."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    mode = body.get("mode", "").upper()
    registry = get_registry()
    if not mode or not registry.is_supported(mode):
        return JSONResponse({"error": f"unsupported mode: {mode}"}, status_code=400)
    await update_device_state(mac, pending_mode=mode, pending_refresh=1)
    logger.info(f"[DEVICE] Pending mode switch to {mode} for {mac}")
    return {"ok": True, "message": f"Mode switch to {mode} queued"}


@app.post("/api/device/{mac}/favorite")
async def favorite_content(
    mac: str,
    request: Request,
    body: Optional[dict] = None,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Favorite the most recently rendered content for this device."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    mode = ""
    if isinstance(body, dict):
        mode = str(body.get("mode", "")).strip().upper()
    if mode:
        registry = get_registry()
        if not registry.is_supported(mode):
            return JSONResponse({"error": f"unsupported mode: {mode}"}, status_code=400)
        latest = await get_latest_render_content(mac)
        if latest and latest.get("mode_id", "").upper() == mode:
            import json
            await add_favorite(mac, mode, json.dumps(latest["content"], ensure_ascii=False))
        else:
            await add_favorite(mac, mode, None)
        logger.info(f"[DEVICE] Mode favorited for {mac}: {mode}")
        return {"ok": True, "message": "Mode favorited", "mode_id": mode}

    latest = await get_latest_render_content(mac)
    if not latest:
        state = await get_device_state(mac)
        mode_id = state.get("last_persona", "UNKNOWN") if state else "UNKNOWN"
        await add_favorite(mac, mode_id, None)
    else:
        import json
        await add_favorite(mac, latest["mode_id"], json.dumps(latest["content"], ensure_ascii=False))
    logger.info(f"[DEVICE] Content favorited for {mac}")
    return {"ok": True, "message": "Content favorited"}


@app.get("/api/device/{mac}/favorites")
async def list_favorites(
    mac: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Get favorites for a device."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    favorites = await get_favorites(mac, limit)
    return {"mac": mac, "favorites": favorites}


@app.get("/api/device/{mac}/history")
async def content_history(
    mac: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mode: Optional[str] = Query(default=None, description="Filter by mode"),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Get content history for a device."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    history = await get_content_history(mac, limit, offset, mode)
    return {"mac": mac, "history": history}


@app.post("/api/device/{mac}/habit/check")
async def habit_check(
    mac: str,
    body: dict,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Record a habit check."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    habit_name = body.get("habit", "").strip()
    if not habit_name:
        return JSONResponse({"error": "habit name is required"}, status_code=400)
    date = body.get("date")
    await check_habit(mac, habit_name, date)
    return {"ok": True, "message": f"Habit '{habit_name}' checked"}


@app.get("/api/device/{mac}/habit/status")
async def habit_status(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Get habit status for the current week."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    habits = await get_habit_status(mac)
    return {"mac": mac, "habits": habits}


@app.delete("/api/device/{mac}/habit/{habit_name}")
async def habit_delete(
    mac: str,
    habit_name: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Delete a habit and all its records."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    deleted = await delete_habit(mac, habit_name)
    if not deleted:
        return JSONResponse({"error": "Habit not found"}, status_code=404)
    return {"ok": True, "message": f"Habit '{habit_name}' deleted"}


@app.post("/api/device/{mac}/token")
async def provision_device_token(mac: str):
    mac = validate_mac_param(mac)
    """分发或获取设备 Token。

    - 新设备（无状态）：生成并返回新 Token
    - 已有设备：返回已有 Token
    """
    state = await get_device_state(mac)
    if state and state.get("auth_token"):
        return {"token": state["auth_token"], "new": False}

    token = await generate_device_token(mac)
    logger.info(f"[AUTH] 为设备 {mac} 分发了新 Token")
    return {"token": token, "new": True}


@app.post("/api/device/{mac}/claim-token")
async def provision_claim_token(
    mac: str,
    request: Request,
    body: Optional[dict] = None,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    preferred_pair_code = str((body or {}).get("pair_code") or "").strip()
    created = await create_claim_token(
        mac,
        source="portal",
        preferred_pair_code=preferred_pair_code,
    )
    if created is None:
        return JSONResponse({"error": "pair_code_conflict"}, status_code=409)
    return {
        "ok": True,
        "token": created["token"],
        "pair_code": created["pair_code"],
        "claim_url": _build_claim_url(request, created["token"]),
        "expires_at": created["expires_at"],
    }


@app.post("/api/claim/consume")
async def claim_consume(body: dict, user_id: int = Depends(require_user)):
    token = str(body.get("token") or "").strip()
    pair_code = str(body.get("pair_code") or "").strip()
    if not token and not pair_code:
        return JSONResponse({"error": "token 或 pair_code 不能为空"}, status_code=400)
    result = await consume_claim_token(user_id=user_id, token=token, pair_code=pair_code)
    if result["status"] == "invalid":
        return JSONResponse({"error": "配对码或 claim token 无效"}, status_code=404)
    if result["status"] == "expired":
        return JSONResponse({"error": "配对码或 claim token 已失效"}, status_code=410)
    return {"ok": True, **result}

# ── Device discovery ──────────────────────────────────────────


@app.get("/api/devices/recent")
async def recent_devices(
    minutes: int = Query(default=DISCOVERY_WINDOW_MINUTES, ge=1, le=60),
    admin_auth: None = Depends(require_admin),
):
    """Return recently online devices for admin diagnostics."""
    from datetime import datetime, timedelta
    from core.db import get_main_db
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    logger.info(f"[DISCOVERY] recent_devices requested: minutes={minutes}, cutoff={cutoff}")
    db = await get_main_db()
    cursor = await db.execute(
        """WITH recent AS (
               SELECT mac, MAX(created_at) AS last_seen
               FROM device_heartbeats
               WHERE created_at > ?
               GROUP BY mac
           )
           SELECT recent.mac,
                  recent.last_seen,
                  CASE WHEN owner.user_id IS NULL THEN 0 ELSE 1 END AS has_owner
           FROM recent
           LEFT JOIN device_memberships owner
             ON owner.mac = recent.mac AND owner.role = 'owner' AND owner.status = 'active'
           ORDER BY recent.last_seen DESC""",
        (cutoff,),
    )
    rows = await cursor.fetchall()
    devices = [{"mac": r[0], "last_seen": r[1], "has_owner": bool(r[2])} for r in rows if r and r[0]]
    macs = [d["mac"] for d in devices]
    logger.info(f"[DISCOVERY] recent_devices result: count={len(devices)}, macs={macs}")
    return {"devices": devices}


# ── User auth endpoints ───────────────────────────────────────


@app.post("/api/auth/register")
async def auth_register(body: dict, response: Response):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or len(username) < 2 or len(username) > 30:
        return JSONResponse({"error": "用户名长度须为 2-30 字符"}, status_code=400)
    if len(password) < 4:
        return JSONResponse({"error": "密码至少 4 位"}, status_code=400)
    user_id = await create_user(username, password)
    if user_id is None:
        return JSONResponse({"error": "用户名已存在"}, status_code=409)
    token = create_session_token(user_id, username)
    set_session_cookie(response, token)
    return {"ok": True, "user_id": user_id, "username": username, "token": token}


@app.post("/api/auth/login")
async def auth_login(body: dict, response: Response):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = await authenticate_user(username, password)
    if not user:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    token = create_session_token(user["id"], user["username"])
    set_session_cookie(response, token)
    return {"ok": True, "user_id": user["id"], "username": user["username"], "token": token}


@app.get("/api/auth/me")
async def auth_me(user_id: int = Depends(require_user)):
    from core.db import get_main_db
    db = await get_main_db()
    cursor = await db.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return {"user_id": row[0], "username": row[1], "created_at": row[2]}


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


# ── User device endpoints ─────────────────────────────────────


@app.get("/api/user/devices")
async def list_user_devices(user_id: int = Depends(require_user)):
    devices = await get_user_devices(user_id)
    return {"devices": devices}


@app.post("/api/user/devices")
async def bind_user_device(body: dict, user_id: int = Depends(require_user)):
    mac = validate_mac_param((body.get("mac") or "").strip().upper())
    nickname = (body.get("nickname") or "").strip()
    if not mac:
        return JSONResponse({"error": "MAC 地址不能为空"}, status_code=400)
    result = await bind_device(user_id, mac, nickname)
    if result["status"] == "pending_approval":
        return {"ok": True, **result}
    return {"ok": True, **result}


@app.delete("/api/user/devices/{mac:path}")
async def unbind_user_device(mac: str, user_id: int = Depends(require_user)):
    result = await unbind_device(user_id, mac.upper())
    if result == "not_found":
        return JSONResponse({"error": "设备未绑定"}, status_code=404)
    if result == "owner_has_members":
        return JSONResponse({"error": "owner 仍有共享成员，无法解绑"}, status_code=409)
    return {"ok": True}


@app.get("/api/user/devices/requests")
async def list_device_requests(user_id: int = Depends(require_user)):
    requests = await get_pending_requests_for_owner(user_id)
    return {"requests": requests}


@app.post("/api/user/devices/requests/{request_id}/approve")
async def approve_device_request(request_id: int, user_id: int = Depends(require_user)):
    membership = await approve_access_request(request_id, user_id)
    if not membership:
        return JSONResponse({"error": "请求不存在或无法批准"}, status_code=404)
    return {"ok": True, "membership": membership}


@app.post("/api/user/devices/requests/{request_id}/reject")
async def reject_device_request(request_id: int, user_id: int = Depends(require_user)):
    ok = await reject_access_request(request_id, user_id)
    if not ok:
        return JSONResponse({"error": "请求不存在或无法拒绝"}, status_code=404)
    return {"ok": True}


@app.get("/api/user/devices/{mac:path}/members")
async def list_device_members(mac: str, request: Request, ink_session: Optional[str] = Cookie(default=None)):
    await _require_membership_access(request, mac.upper(), ink_session)
    members = await get_device_members(mac.upper())
    owner = await get_device_owner(mac.upper())
    return {"mac": mac.upper(), "members": members, "owner_user_id": owner["user_id"] if owner else None}


@app.post("/api/user/devices/{mac:path}/share")
async def share_device_access(
    mac: str,
    body: dict,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    owner = await _require_membership_access(request, mac.upper(), ink_session, owner_only=True)
    username = str(body.get("username") or "").strip()
    if not username:
        return JSONResponse({"error": "用户名不能为空"}, status_code=400)
    target_user = await get_user_by_username(username)
    if not target_user:
        return JSONResponse({"error": "目标用户不存在"}, status_code=404)
    result = await share_device_with_user(owner["user_id"], mac.upper(), target_user["id"])
    return {"ok": True, **result}


@app.delete("/api/user/devices/{mac:path}/members/{target_user_id}")
async def remove_device_member(
    mac: str,
    target_user_id: int,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    owner = await _require_membership_access(request, mac.upper(), ink_session, owner_only=True)
    ok = await revoke_device_member(owner["user_id"], mac.upper(), target_user_id)
    if not ok:
        return JSONResponse({"error": "成员不存在或无法移除"}, status_code=404)
    return {"ok": True}


# ── Stats endpoints ──────────────────────────────────────────


@app.get("/api/stats/overview")
async def stats_overview(admin_auth: None = Depends(require_admin)):
    """Global statistics overview."""
    return await get_stats_overview()


@app.get("/api/stats/{mac}")
async def stats_device(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Device-specific statistics."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return await get_device_stats(mac)


@app.get("/api/stats/{mac}/renders")
async def stats_renders(
    mac: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Render history for a device with pagination."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    renders = await get_render_history(mac, limit, offset)
    return {"mac": mac, "renders": renders}


# ── QR code and share endpoints ──────────────────────────────


@app.get("/api/device/{mac}/qr")
async def device_qr(
    mac: str,
    request: Request,
    base_url: Optional[str] = Query(default=None, description="Override base URL for remote page"),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Generate a QR code BMP for device binding (scan to open remote control)."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    import qrcode
    from io import BytesIO

    remote_base = base_url or "https://www.inksight.site"
    url = f"{remote_base}/remote?mac={mac}"

    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("1")

    qr_w, qr_h = qr_img.size
    canvas = Image.new("1", (SCREEN_WIDTH, SCREEN_HEIGHT), 1)

    x_offset = (SCREEN_WIDTH - qr_w) // 2
    y_offset = (SCREEN_HEIGHT - qr_h) // 2 - 20
    canvas.paste(qr_img, (x_offset, max(y_offset, 30)))

    bmp_bytes = image_to_bmp_bytes(canvas)
    return Response(content=bmp_bytes, media_type="image/bmp")


@app.get("/api/device/{mac}/share")
async def share_image(
    mac: str,
    request: Request,
    w: int = Query(default=800, ge=400, le=1600),
    h: int = Query(default=450, ge=300, le=900),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """Generate a shareable image (16:9) with InkSight watermark."""
    await _ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    latest = await get_latest_render_content(mac)
    if not latest:
        return JSONResponse({"error": "no content to share"}, status_code=404)

    state = await get_device_state(mac)
    persona = latest["mode_id"]
    content = latest["content"]

    from PIL import ImageDraw, ImageFont
    import os

    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)

    font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
    try:
        title_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Bold.ttf"), 24)
        body_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Regular.ttf"), 18)
        small_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Regular.ttf"), 12)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (w - 1, h - 1)], outline=0, width=2)

    draw.text((40, 30), persona, fill=0, font=title_font)

    y = 80
    main_text = ""
    for key in ("quote", "question", "challenge", "body", "word", "opening", "event_title", "name_cn"):
        if key in content:
            main_text = str(content[key])
            break
    if not main_text:
        main_text = str(list(content.values())[0]) if content else "InkSight"

    for line in main_text[:200].split("\n"):
        draw.text((40, y), line, fill=0, font=body_font)
        y += 28

    draw.line([(40, h - 50), (w - 40, h - 50)], fill=180, width=1)
    draw.text((40, h - 40), "InkSight | inco", fill=128, font=small_font)
    draw.text((w - 180, h - 40), "www.inksight.site", fill=128, font=small_font)

    img_1bit = img.convert("1")
    png_bytes = image_to_png_bytes(img_1bit)
    return Response(content=png_bytes, media_type="image/png")
