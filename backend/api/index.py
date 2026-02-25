from __future__ import annotations

import asyncio
import io
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import httpx
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from core.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    DEFAULT_CITY,
    DEFAULT_MODES,
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
)
from core.cache import content_cache
from core.schemas import ConfigRequest
from core.pipeline import generate_and_render
from core.renderer import (
    render_error,
    image_to_bmp_bytes,
    image_to_png_bytes,
)
from core.stats_store import (
    init_stats_db,
    log_render,
    log_heartbeat,
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
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_stats_db()
    from core.cache import init_cache_db
    await init_cache_db()
    yield


app = FastAPI(title="InkSight API", version="1.0.0", lifespan=lifespan)

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
):
    battery_pct = calc_battery_pct(v)

    config = None
    if mac:
        config = await get_active_config(mac)

    persona = await _resolve_mode(mac, config, persona_override, force_next=force_next)

    # Try cache first
    cache_hit = False
    if mac and config:
        await content_cache.check_and_regenerate_all(mac, config, v, screen_w, screen_h)
        cached_img = await content_cache.get(mac, persona, config, screen_w=screen_w, screen_h=screen_h)
        if cached_img:
            logger.info(f"[CACHE HIT] {mac}:{persona} - Returning cached image")
            cache_hit = True
            img = cached_img
        else:
            logger.info(f"[CACHE MISS] {mac}:{persona} - Generating fallback content")

    content_data = None
    if not cache_hit:
        city = config.get("city", DEFAULT_CITY) if config else None
        date_ctx, weather = await asyncio.gather(
            get_date_context(),
            get_weather(city=city),
        )
        img, content_data = await generate_and_render(
            persona, config, date_ctx, weather, battery_pct,
            screen_w=screen_w, screen_h=screen_h,
            mac=mac or "",
        )

        if mac and config:
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

    return img, persona, cache_hit


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
async def render(
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: Optional[str] = Query(default=None, description="Device MAC address"),
    persona: Optional[str] = Query(default=None, description="Force persona"),
    rssi: Optional[int] = Query(default=None, description="WiFi RSSI (dBm)"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600, description="Screen width in pixels"),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200, description="Screen height in pixels"),
    next_mode: Optional[int] = Query(default=None, alias="next", description="1 = advance to next mode (double-click)"),
):
    start_time = time.time()
    force_next = (next_mode == 1)
    logger.debug(f"[RENDER] Request started: mac={mac}, v={v}, persona={persona}, next={force_next}, size={w}x{h}")

    try:
        img, resolved_persona, cache_hit = await _build_image(
            v, mac, persona, rssi, screen_w=w, screen_h=h, force_next=force_next,
        )
        bmp_bytes = image_to_bmp_bytes(img)
        elapsed = time.time() - start_time
        elapsed_ms = int(elapsed * 1000)
        logger.info(
            f"[RENDER] ✓ Success in {elapsed:.2f}s - Generated BMP: {len(bmp_bytes)} bytes for {mac}:{resolved_persona} ({w}x{h})"
        )

        if mac:
            await _log_render(mac, resolved_persona, cache_hit, elapsed_ms, v, rssi)

        headers = {}
        if mac:
            was_pending = await consume_pending_refresh(mac)
            if was_pending:
                headers["X-Pending-Refresh"] = "1"

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
):
    """Read-only widget endpoint for embedding InkSight content.
    Does NOT update device state or trigger refreshes.
    """
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
async def preview(
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: Optional[str] = Query(default=None, description="Device MAC address"),
    persona: Optional[str] = Query(default=None, description="Force persona"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600, description="Screen width in pixels"),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200, description="Screen height in pixels"),
):
    try:
        img, resolved_persona, cache_hit = await _build_image(
            v, mac, persona, screen_w=w, screen_h=h,
        )
        png_bytes = image_to_png_bytes(img)
        logger.info(f"[PREVIEW] Generated PNG: {len(png_bytes)} bytes, persona={resolved_persona} ({w}x{h})")
        return Response(content=png_bytes, media_type="image/png")
    except Exception:
        logger.exception("Exception occurred during preview")
        err_img = render_error(mac=mac or "unknown", screen_w=w, screen_h=h)
        return Response(
            content=image_to_png_bytes(err_img), media_type="image/png", status_code=500
        )


# ── Config endpoints ─────────────────────────────────────────


@app.post("/api/config")
async def post_config(body: ConfigRequest):
    data = body.model_dump()
    mac = data["mac"]
    config_id = await save_config(mac, data)

    saved_config = await get_active_config(mac)
    if saved_config:
        logger.info(
            f"[CONFIG VERIFY] Saved config id={saved_config.get('id')}, "
            f"refresh_strategy={saved_config.get('refresh_strategy')}"
        )

    return {"ok": True, "config_id": config_id}


@app.get("/api/config/{mac}")
async def get_config(mac: str):
    config = await get_active_config(mac)
    if not config:
        return JSONResponse({"error": "no config found"}, status_code=404)
    return config


@app.get("/api/config/{mac}/history")
async def get_config_hist(mac: str):
    history = await get_config_history(mac)
    return {"mac": mac, "configs": history}


@app.put("/api/config/{mac}/activate/{config_id}")
async def put_activate(mac: str, config_id: int):
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
        })
    return {"modes": modes}


@app.post("/api/modes/custom/preview")
async def custom_mode_preview(body: dict):
    """Render a preview for a custom mode definition without saving."""
    mode_def = body.get("mode_def", body)
    if not mode_def.get("mode_id"):
        mode_def = dict(mode_def, mode_id="PREVIEW")
    from core.json_content import generate_json_mode_content
    from core.json_renderer import render_json_mode

    date_ctx = await get_date_context()
    weather = await get_weather()
    content = await generate_json_mode_content(
        mode_def,
        date_ctx=date_ctx,
        date_str=date_ctx["date_str"],
        weather_str=weather["weather_str"],
    )
    img = render_json_mode(
        mode_def, content,
        date_str=date_ctx["date_str"],
        weather_str=weather["weather_str"],
        battery_pct=100.0,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="image/png")


@app.post("/api/modes/custom")
async def create_custom_mode(body: dict):
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
async def delete_custom_mode(mode_id: str):
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


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    return HTMLResponse(content=_load_web_page_html("config.html"))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return HTMLResponse(content=_load_web_page_html("dashboard.html"))


@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    return HTMLResponse(content=_load_web_page_html("editor.html"))


def _load_web_page_html(filename: str) -> str:
    """Load static page from webconfig directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    html_path = project_root / "webconfig" / filename
    if not html_path.exists():
        raise FileNotFoundError(f"Static page not found in webconfig: {filename}")
    return html_path.read_text(encoding="utf-8")


# ── Device control endpoints ─────────────────────────────────


@app.post("/api/device/{mac}/refresh")
async def trigger_refresh(mac: str):
    """Mark a device for immediate refresh on next wake-up."""
    await set_pending_refresh(mac, True)
    logger.info(f"[DEVICE] Pending refresh set for {mac}")
    return {"ok": True, "message": "Refresh queued for next wake-up"}


@app.get("/api/device/{mac}/state")
async def device_state(mac: str):
    """Get device runtime state."""
    state = await get_device_state(mac)
    if not state:
        return JSONResponse({"error": "no device state found"}, status_code=404)
    return state


@app.post("/api/device/{mac}/switch")
async def switch_mode(mac: str, body: dict):
    """Set a pending mode for the device to use on next refresh."""
    mode = body.get("mode", "").upper()
    registry = get_registry()
    if not mode or not registry.is_supported(mode):
        return JSONResponse({"error": f"unsupported mode: {mode}"}, status_code=400)
    await update_device_state(mac, pending_mode=mode, pending_refresh=1)
    logger.info(f"[DEVICE] Pending mode switch to {mode} for {mac}")
    return {"ok": True, "message": f"Mode switch to {mode} queued"}


@app.post("/api/device/{mac}/favorite")
async def favorite_content(mac: str):
    """Favorite the most recently rendered content for this device."""
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
    limit: int = Query(default=30, ge=1, le=100),
):
    """Get favorites for a device."""
    favorites = await get_favorites(mac, limit)
    return {"mac": mac, "favorites": favorites}


@app.get("/api/device/{mac}/history")
async def content_history(
    mac: str,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mode: Optional[str] = Query(default=None, description="Filter by mode"),
):
    """Get content history for a device."""
    history = await get_content_history(mac, limit, offset, mode)
    return {"mac": mac, "history": history}


@app.post("/api/device/{mac}/habit/check")
async def habit_check(mac: str, body: dict):
    """Record a habit check."""
    habit_name = body.get("habit", "").strip()
    if not habit_name:
        return JSONResponse({"error": "habit name is required"}, status_code=400)
    date = body.get("date")
    await check_habit(mac, habit_name, date)
    return {"ok": True, "message": f"Habit '{habit_name}' checked"}


@app.get("/api/device/{mac}/habit/status")
async def habit_status(mac: str):
    """Get habit status for the current week."""
    habits = await get_habit_status(mac)
    return {"mac": mac, "habits": habits}


# ── Stats endpoints ──────────────────────────────────────────


@app.get("/api/stats/overview")
async def stats_overview():
    """Global statistics overview."""
    return await get_stats_overview()


@app.get("/api/stats/{mac}")
async def stats_device(mac: str):
    """Device-specific statistics."""
    return await get_device_stats(mac)


@app.get("/api/stats/{mac}/renders")
async def stats_renders(
    mac: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Render history for a device with pagination."""
    renders = await get_render_history(mac, limit, offset)
    return {"mac": mac, "renders": renders}


# ── QR code and share endpoints ──────────────────────────────


@app.get("/api/device/{mac}/qr")
async def device_qr(
    mac: str,
    base_url: Optional[str] = Query(default=None, description="Override base URL for remote page"),
):
    """Generate a QR code BMP for device binding (scan to open remote control)."""
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
    w: int = Query(default=800, ge=400, le=1600),
    h: int = Query(default=450, ge=300, le=900),
):
    """Generate a shareable image (16:9) with InkSight watermark."""
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
