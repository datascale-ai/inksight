from __future__ import annotations

import asyncio
import copy
import io
import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image

try:  # pragma: no cover - exercised implicitly at import time
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover
    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
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
            content={
                "error": "rate_limit_unavailable",
                "message": "Rate limiting is not enabled on this server.",
            },
        )

    Limiter = _DummyLimiter  # type: ignore

from core.auth import (
    optional_user,
    require_device_token,
    validate_mac_param,
)
from core.cache import content_cache
from core.config import (
    DEFAULT_CITY,
    DEFAULT_MODES,
    DEFAULT_REFRESH_INTERVAL,
)
from core.config_store import (
    get_active_config,
    get_cycle_index,
    get_device_membership,
    get_device_state,
    init_db,
    set_cycle_index,
    update_device_state,
)
from core.context import calc_battery_pct, get_date_context, get_weather
from core.pipeline import generate_and_render, get_effective_mode_config
from core.renderer import image_to_bmp_bytes
from core.stats_store import (
    get_latest_battery_voltage,
    init_stats_db,
    log_heartbeat,
    log_render,
    save_render_content,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DISCOVERY_WINDOW_MINUTES = 15
ONLINE_WINDOW_MINUTES = 15

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@asynccontextmanager
async def lifespan(app):
    await init_db()
    await init_stats_db()
    from core.cache import init_cache_db
    from core.db import close_all

    await init_cache_db()
    yield
    await close_all()


def _rate_limit_key(request: Request) -> str:
    mac = request.query_params.get("mac")
    if mac:
        return f"mac:{mac}"
    return get_remote_address(request)


class _NoopLimiter:
    def __init__(self, *args, **kwargs):
        pass

    def limit(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


try:
    limiter = Limiter(key_func=_rate_limit_key)
except Exception as exc:  # pragma: no cover - depends on optional runtime dependency
    logger.warning("Rate limiter disabled due to init error: %s", exc)
    limiter = _NoopLimiter()


async def inksight_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.message},
    )


def build_claim_url(request: Request, token: str) -> str:
    override = os.environ.get("INKSIGHT_WEB_BASE_URL", "").rstrip("/")
    if override:
        return f"{override}/claim?token={token}"
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
        or ""
    ).strip()
    if "inksight.site" not in host.lower():
        return ""
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip()
    return f"{scheme}://{host}/claim?token={token}"


async def resolve_user_id(request: Request, ink_session: Optional[str]) -> int | None:
    return await optional_user(request, ink_session)


async def require_membership_access(
    request: Request,
    mac: str,
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
) -> dict:
    from core.i18n import detect_lang_from_request, msg

    lang = detect_lang_from_request(request)
    mac = validate_mac_param(mac, lang)
    user_id = await resolve_user_id(request, ink_session)
    if user_id is None:
        raise HTTPException(status_code=401, detail=msg("auth.login_required", lang))
    membership = await get_device_membership(mac, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail=msg("auth.no_device_access", lang))
    if owner_only and membership.get("role") != "owner":
        raise HTTPException(status_code=403, detail=msg("auth.owner_only", lang))
    return membership


async def ensure_web_or_device_access(
    request: Request,
    mac: str,
    x_device_token: Optional[str],
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
    allow_device_token: bool = True,
) -> dict:
    mac = validate_mac_param(mac)
    if allow_device_token and x_device_token:
        await require_device_token(mac, x_device_token)
        return {"mode": "device", "role": "device"}
    membership = await require_membership_access(request, mac, ink_session, owner_only=owner_only)
    return {"mode": "user", **membership}


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

_SMART_TIME_SLOTS = [
    (6, 9, ["RECIPE", "DAILY"]),
    (9, 12, ["BRIEFING", "STOIC"]),
    (12, 14, ["ZEN", "POETRY"]),
    (14, 18, ["STOIC", "ROAST"]),
    (18, 21, ["FITNESS", "RECIPE"]),
    (21, 24, ["ZEN", "POETRY"]),
    (0, 6, ["ZEN", "POETRY"]),
]


async def choose_persona_from_config(config: dict, peek_next: bool = False) -> str:
    modes = config.get("modes", DEFAULT_MODES) or DEFAULT_MODES
    strategy = config.get("refresh_strategy", "random")

    if strategy == "cycle":
        mac = config.get("mac", "default")
        idx = await get_cycle_index(mac)
        persona = modes[idx % len(modes)]
        if not peek_next:
            await set_cycle_index(mac, idx + 1)
        return persona

    if strategy == "time_slot":
        hour = datetime.now().hour
        rules = config.get("time_slot_rules", [])
        for rule in rules:
            start_h = rule.get("startHour", 0)
            end_h = rule.get("endHour", 24)
            rule_modes = rule.get("modes", [])
            if start_h <= hour < end_h and rule_modes:
                available = [mode for mode in rule_modes if mode in modes]
                if available:
                    return random.choice(available)
        return random.choice(modes)

    if strategy == "smart":
        hour = datetime.now().hour
        for start_h, end_h, candidates in _SMART_TIME_SLOTS:
            if start_h <= hour < end_h:
                available = [mode for mode in candidates if mode in modes]
                if available:
                    return random.choice(available)
        return random.choice(modes)

    return random.choice(modes)


async def advance_to_next_mode(mac: Optional[str], config: dict) -> str:
    modes = config.get("modes", DEFAULT_MODES)
    if not modes:
        return "STOIC"

    state = await get_device_state(mac) if mac else None
    current = state.get("last_persona", "") if state else ""
    idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
    persona = modes[idx]
    if mac:
        await set_cycle_index(mac, idx + 1)
    return persona


async def consume_pending_mode(mac: str) -> Optional[str]:
    try:
        state = await get_device_state(mac)
        if state and state.get("pending_mode"):
            mode = state["pending_mode"]
            await update_device_state(mac, pending_mode="")
            return mode
    except (OSError, ValueError, TypeError):
        logger.warning("[PENDING_MODE] Failed to consume for %s", mac, exc_info=True)
    return None


async def resolve_mode(
    mac: Optional[str],
    config: Optional[dict],
    persona_override: Optional[str],
    *,
    force_next: bool = False,
) -> str:
    from core.mode_registry import get_registry

    registry = get_registry()
    if mac and not persona_override:
        pending = await consume_pending_mode(mac)
        if pending and registry.is_supported(pending.upper()):
            return pending.upper()

    if persona_override and registry.is_supported(persona_override.upper()):
        return persona_override.upper()

    if config:
        if force_next:
            return await advance_to_next_mode(mac, config)
        return await choose_persona_from_config(config)

    return random.choice(["STOIC", "ROAST", "ZEN", "DAILY"])


async def build_image(
    v: float,
    mac: Optional[str],
    persona_override: Optional[str] = None,
    *,
    screen_w: int,
    screen_h: int,
    force_next: bool = False,
    skip_cache: bool = False,
    preview_city_override: Optional[str] = None,
    preview_mode_override: Optional[dict] = None,
    preview_memo_text: Optional[str] = None,
):
    from core.mode_registry import get_registry

    battery_pct = calc_battery_pct(v)
    config = await get_active_config(mac) if mac else None
    persona = await resolve_mode(mac, config, persona_override, force_next=force_next)
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
        if persona == "MEMO":
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

    cache_hit = False
    if mac and config and is_mode_cacheable and not skip_cache:
        await content_cache.check_and_regenerate_all(mac, config, v, screen_w, screen_h)
        cached_img = await content_cache.get(
            mac,
            persona,
            config,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        if cached_img:
            cache_hit = True
            img = cached_img
        else:
            logger.info("[CACHE MISS] %s:%s - Generating fallback content", mac, persona)
    else:
        if skip_cache:
            logger.info("[PREVIEW] Skip cache for %s:%s", mac, persona)
        img = None

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
            persona,
            config,
            date_ctx,
            weather,
            battery_pct,
            screen_w=screen_w,
            screen_h=screen_h,
            mac=mac or "",
        )
        if isinstance(content_data, dict):
            if content_data.get("_is_fallback") is True:
                content_fallback = True
            else:
                jm = get_registry().get_json_mode(persona)
                if jm and jm.definition.get("content", {}).get("type") == "image_gen":
                    content_fallback = not bool(content_data.get("image_url"))

        if mac and config and is_mode_cacheable:
            await content_cache.set(mac, persona, img, screen_w, screen_h)

    if mac:
        await update_device_state(
            mac,
            last_persona=persona,
            last_refresh_at=datetime.now().isoformat(),
        )

    if mac and content_data:
        try:
            await save_render_content(mac, persona, content_data)
        except (OSError, ValueError, TypeError):
            logger.warning("[CONTENT] Failed to save content for %s:%s", mac, persona, exc_info=True)

    return img, persona, cache_hit, content_fallback


async def log_render_stats(
    mac: str,
    persona: str,
    cache_hit: bool,
    elapsed_ms: int,
    *,
    voltage: float = 3.3,
    rssi: Optional[int] = None,
    status: str = "success",
):
    try:
        await log_render(mac, persona, cache_hit, elapsed_ms, status)
        await log_heartbeat(mac, voltage, rssi)
    except (OSError, ValueError, TypeError):
        logger.warning("[STATS] Failed to log render stats for %s", mac, exc_info=True)


async def resolve_preview_voltage(v: Optional[float], mac: Optional[str]) -> float:
    if v is not None:
        return v
    if mac:
        latest_voltage = await get_latest_battery_voltage(mac)
        if latest_voltage is not None:
            return latest_voltage
    return 3.3


def resolve_refresh_minutes_for_device_state(config: Optional[dict], state: Optional[dict]) -> int:
    refresh_minutes_raw = config.get("refresh_interval") if config else DEFAULT_REFRESH_INTERVAL
    try:
        refresh_minutes = int(refresh_minutes_raw)
    except (TypeError, ValueError):
        refresh_minutes = DEFAULT_REFRESH_INTERVAL
    if refresh_minutes <= 0:
        refresh_minutes = DEFAULT_REFRESH_INTERVAL

    expected_refresh_raw = state.get("expected_refresh_min", 0) if state else 0
    try:
        expected_refresh = int(expected_refresh_raw)
    except (TypeError, ValueError):
        expected_refresh = 0
    if expected_refresh > 0:
        refresh_minutes = expected_refresh
    return refresh_minutes


def reconnect_threshold_seconds(refresh_minutes: int) -> int:
    base_seconds = max(1, int(refresh_minutes)) * 60
    return max(base_seconds + 30, int(base_seconds * 1.5))


def build_firmware_manifest(version: str, download_url: str) -> dict:
    return {
        "name": "InkSight",
        "version": version,
        "builds": [
            {
                "chipFamily": FIRMWARE_CHIP_FAMILY,
                "parts": [{"path": download_url, "offset": 0}],
            }
        ],
    }


def pick_firmware_asset(assets: list[dict]) -> Optional[dict]:
    preferred = [
        asset
        for asset in assets
        if asset.get("name", "").endswith(".bin")
        and "inksight-firmware-" in asset.get("name", "")
    ]
    if preferred:
        return preferred[0]
    fallback = [asset for asset in assets if asset.get("name", "").endswith(".bin")]
    return fallback[0] if fallback else None


async def load_firmware_releases(force_refresh: bool = False) -> dict:
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

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GITHUB_RELEASES_API, headers=headers)
        if resp.status_code >= 400:
            message = f"GitHub releases API error: {resp.status_code}"
            try:
                details = resp.json().get("message")
                if details:
                    message = f"{message} - {details}"
            except (ValueError, TypeError, json.JSONDecodeError):
                logger.warning("[FIRMWARE] Failed to parse GitHub error payload", exc_info=True)
            raise RuntimeError(message)

        releases = []
        for release in resp.json():
            if release.get("draft"):
                continue
            asset = pick_firmware_asset(release.get("assets", []))
            if not asset:
                continue
            tag_name = release.get("tag_name", "")
            version = tag_name.lstrip("v") if tag_name else "unknown"
            download_url = asset.get("browser_download_url")
            if not download_url:
                continue
            releases.append(
                {
                    "version": version,
                    "tag": tag_name,
                    "published_at": release.get("published_at"),
                    "download_url": download_url,
                    "size_bytes": asset.get("size"),
                    "chip_family": FIRMWARE_CHIP_FAMILY,
                    "asset_name": asset.get("name"),
                    "manifest": build_firmware_manifest(version, download_url),
                }
            )

        payload = {
            "source": "github_releases",
            "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            "cached": False,
            "count": len(releases),
            "releases": releases,
        }
        _firmware_release_cache["payload"] = payload
        _firmware_release_cache["expires_at"] = now + FIRMWARE_RELEASE_CACHE_TTL
        return payload


async def validate_firmware_url(url: str) -> dict:
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
        except httpx.HTTPError:
            logger.warning("[FIRMWARE] HEAD failed for %s, falling back to ranged GET", url, exc_info=True)
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
    if resp.status_code >= 400:
        raise RuntimeError(f"firmware URL is not reachable: {resp.status_code}")

    return {
        "ok": True,
        "reachable": True,
        "status_code": resp.status_code,
        "final_url": str(resp.url),
        "content_type": resp.headers.get("content-type"),
        "content_length": resp.headers.get("content-length"),
    }


def normalize_pushed_preview(image_bytes: bytes, *, width: int, height: int) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as incoming:
        img = incoming.convert("1")
        if img.size != (width, height):
            img = img.resize((width, height), Image.NEAREST)
        return image_to_bmp_bytes(img)
