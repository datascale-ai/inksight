from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse

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
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_stats_db()
    yield


app = FastAPI(title="InkSight API", version="1.0.0", lifespan=lifespan)

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
    mac: str | None, config: dict | None, persona_override: str | None
) -> str:
    """Determine which persona to use for this request."""
    registry = get_registry()
    if persona_override and registry.is_supported(persona_override.upper()):
        persona = persona_override.upper()
        logger.debug(f"[REQUEST] Using override persona: {persona}")
    elif config:
        persona = await _choose_persona_from_config(config)
        mac_key = config.get("mac", "default")
        logger.debug(
            f"[REQUEST] Chosen persona: {persona}, mac_key={mac_key}"
        )
    else:
        persona = random.choice(["STOIC", "ROAST", "ZEN", "DAILY"])
        logger.debug(f"[REQUEST] No config, random persona: {persona}")
    return persona


# ── Main orchestrator ────────────────────────────────────────


async def _build_image(
    v: float, mac: str | None, persona_override: str | None = None,
    rssi: int | None = None,
    screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
):
    battery_pct = calc_battery_pct(v)

    config = None
    if mac:
        config = await get_active_config(mac)

    persona = await _resolve_mode(mac, config, persona_override)

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

    if not cache_hit:
        city = config.get("city", DEFAULT_CITY) if config else None
        date_ctx, weather = await asyncio.gather(
            get_date_context(),
            get_weather(city=city),
        )
        img = await generate_and_render(
            persona, config, date_ctx, weather, battery_pct,
            screen_w=screen_w, screen_h=screen_h,
        )

        if mac and config:
            await content_cache.set(mac, persona, img, screen_w, screen_h)

    if mac:
        await update_device_state(
            mac,
            last_persona=persona,
            last_refresh_at=datetime.now().isoformat(),
        )

    return img, persona, cache_hit


# ── Stats helper ─────────────────────────────────────────────


async def _log_render(
    mac: str, persona: str, cache_hit: bool, elapsed_ms: int,
    voltage: float = 3.3, rssi: int | None = None, status: str = "success",
):
    """Log render stats and device heartbeat (fire-and-forget)."""
    try:
        await log_render(mac, persona, cache_hit, elapsed_ms, status)
        await log_heartbeat(mac, voltage, rssi)
    except Exception:
        logger.warning(f"[STATS] Failed to log render stats for {mac}", exc_info=True)


# ── Render endpoints ─────────────────────────────────────────


@app.get("/api/render")
async def render(
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: str | None = Query(default=None, description="Device MAC address"),
    persona: str | None = Query(default=None, description="Force persona"),
    rssi: int | None = Query(default=None, description="WiFi RSSI (dBm)"),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600, description="Screen width in pixels"),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200, description="Screen height in pixels"),
):
    start_time = time.time()
    logger.debug(f"[RENDER] Request started: mac={mac}, v={v}, persona={persona}, size={w}x{h}")

    try:
        img, resolved_persona, cache_hit = await _build_image(
            v, mac, persona, rssi, screen_w=w, screen_h=h,
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


@app.get("/api/preview")
async def preview(
    v: float = Query(default=3.3, description="Battery voltage"),
    mac: str | None = Query(default=None, description="Device MAC address"),
    persona: str | None = Query(default=None, description="Force persona"),
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


@app.get("/", response_class=HTMLResponse)
async def preview_page():
    html_path = Path(__file__).resolve().parent.parent.parent / "web" / "preview.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    html_path = Path(__file__).resolve().parent.parent.parent / "web" / "config.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    html_path = Path(__file__).resolve().parent.parent.parent / "web" / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


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
