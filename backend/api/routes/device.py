from __future__ import annotations

import asyncio
import io
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from api.shared import (
    DISCOVERY_WINDOW_MINUTES,
    ONLINE_WINDOW_MINUTES,
    _preview_push_queue,
    _preview_push_queue_lock,
    build_claim_url,
    ensure_web_or_device_access,
    logger,
    resolve_refresh_minutes_for_device_state,
)
from core.auth import require_admin, require_device_token, require_user, validate_mac_param
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.config_store import (
    consume_claim_token,
    create_claim_token,
    generate_device_token,
    get_active_config,
    get_device_state,
    get_or_create_alert_token,
    is_device_owner,
    set_pending_refresh,
    update_device_state,
    validate_alert_token,
)
from core.patterns.utils import apply_text_fontmode, load_font
from core.renderer import image_to_bmp_bytes, image_to_png_bytes
from core.schemas import DeviceHeartbeatRequest, OkResponse
from core.stats_store import (
    add_favorite,
    check_habit,
    delete_habit,
    get_content_history,
    get_favorites,
    get_habit_status,
    get_latest_heartbeat,
    get_latest_render_content,
)

router = APIRouter(tags=["device"])

_ALERT_TTL_SECONDS = 60
_device_alerts: dict[str, dict] = {}
_device_alerts_lock = asyncio.Lock()


@router.post("/device/{mac}/refresh")
async def trigger_refresh(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    await set_pending_refresh(mac, True)
    logger.info("[DEVICE] Pending refresh set for %s", mac)
    return {"ok": True, "message": "Refresh queued for next wake-up"}


@router.get("/device/{mac}/state")
async def device_state(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    access = await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    if access["mode"] == "device":
        await update_device_state(mac, last_state_poll_at=datetime.now().isoformat())
    state = await get_device_state(mac)
    if not state:
        return JSONResponse({"error": "no device state found"}, status_code=404)

    cfg = await get_active_config(mac, log_load=False)
    refresh_minutes = resolve_refresh_minutes_for_device_state(cfg, state)
    latest_heartbeat = await get_latest_heartbeat(mac)
    last_seen = latest_heartbeat.get("created_at") if latest_heartbeat else None
    is_online = False
    if isinstance(last_seen, str) and last_seen:
        try:
            delta_seconds = (datetime.now() - datetime.fromisoformat(last_seen)).total_seconds()
            is_online = delta_seconds <= (ONLINE_WINDOW_MINUTES * 60)
        except ValueError:
            logger.warning("[DEVICE] Invalid last_seen timestamp for %s: %s", mac, last_seen, exc_info=True)
            is_online = False
    state["last_seen"] = last_seen
    state["is_online"] = is_online
    state["refresh_minutes"] = refresh_minutes

    explicit_mode = str(state.get("runtime_mode") or "").lower()
    if explicit_mode in ("active", "interval"):
        state["runtime_mode"] = explicit_mode
        return state

    runtime_mode = "interval"
    last_poll = state.get("last_state_poll_at", "")
    if isinstance(last_poll, str) and last_poll:
        try:
            delta = (datetime.now() - datetime.fromisoformat(last_poll)).total_seconds()
            runtime_mode = "active" if delta <= 8 else "interval"
        except ValueError:
            logger.warning("[DEVICE] Invalid last_state_poll_at for %s: %s", mac, last_poll, exc_info=True)
            runtime_mode = "interval"
    state["runtime_mode"] = runtime_mode
    return state


@router.post("/device/{mac}/runtime")
async def set_runtime_mode(
    mac: str,
    body: dict,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    mode = str(body.get("mode", "")).strip().lower()
    if mode not in ("active", "interval"):
        return JSONResponse({"error": "mode must be active or interval"}, status_code=400)
    await update_device_state(mac, runtime_mode=mode)
    return {"ok": True, "runtime_mode": mode}


@router.post("/device/{mac}/heartbeat", response_model=OkResponse)
async def post_device_heartbeat(
    mac: str,
    body: DeviceHeartbeatRequest,
    x_device_token: Optional[str] = Header(default=None),
):
    from core.stats_store import log_heartbeat

    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    await log_heartbeat(mac, body.battery_voltage or 3.3, body.wifi_rssi)
    return OkResponse(ok=True)


@router.post("/device/{mac}/alert-token")
async def provision_device_alert_token(
    mac: str,
    regenerate: bool = Query(default=False, description="是否强制重新生成 token"),
    user_id: int = Depends(require_user),
):
    mac = validate_mac_param(mac)
    if not await is_device_owner(mac, user_id):
        return JSONResponse({"error": "owner_required"}, status_code=403)
    token = await get_or_create_alert_token(mac, regenerate=regenerate)
    return {"ok": True, "token": token, "regenerated": regenerate}


@router.post("/device/{mac}/alert")
async def push_device_alert(
    mac: str,
    request: Request,
    x_agent_token: Optional[str] = Header(default=None, alias="X-Agent-Token"),
):
    mac = validate_mac_param(mac)
    token = (x_agent_token or "").strip()
    if not token:
        return JSONResponse({"error": "missing_agent_token"}, status_code=401)
    if not await validate_alert_token(mac, token):
        return JSONResponse({"error": "invalid_agent_token"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid_payload"}, status_code=400)

    sender = str(payload.get("sender") or "").strip()
    message = str(payload.get("message") or "").strip()
    level = str(payload.get("level") or "info").strip()
    if not sender or not message:
        return JSONResponse({"error": "sender_and_message_required"}, status_code=400)

    now = datetime.now()
    async with _device_alerts_lock:
        _device_alerts[mac] = {
            "sender": sender,
            "message": message,
            "level": level or "info",
            "expires_at": now + timedelta(seconds=_ALERT_TTL_SECONDS),
        }

    logger.info("[ALERT] Stored alert for %s (level=%s, ttl=%ss)", mac, level or "info", _ALERT_TTL_SECONDS)
    return {"ok": True}


@router.get("/device/{mac}/check_alert")
async def check_device_alert(
    mac: str,
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)

    now = datetime.now()
    alert_payload: Optional[dict] = None
    async with _device_alerts_lock:
        existing = _device_alerts.get(mac)
        if existing:
            expires_at = existing.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at < now:
                _device_alerts.pop(mac, None)
            else:
                alert_payload = {
                    "sender": existing.get("sender") or "",
                    "message": existing.get("message") or "",
                    "level": existing.get("level") or "info",
                }
                _device_alerts.pop(mac, None)
    if not alert_payload:
        return {"has_alert": False}
    return {"has_alert": True, "alert": alert_payload}


def _wrap_text_by_pixels(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    if not text:
        return lines
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        test = cur + ch
        try:
            w = draw.textlength(test, font=font)
        except Exception:
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
        if w <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


@router.get("/device/{mac}/alert-bmp")
async def alert_bmp(
    mac: str,
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200),
    x_device_token: Optional[str] = Header(default=None, alias="X-Device-Token"),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)

    now = datetime.now()
    alert_payload: Optional[dict] = None
    async with _device_alerts_lock:
        existing = _device_alerts.get(mac)
        if existing:
            expires_at = existing.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at < now:
                _device_alerts.pop(mac, None)
            else:
                alert_payload = {
                    "sender": existing.get("sender") or "",
                    "message": existing.get("message") or "",
                    "level": existing.get("level") or "info",
                }
                _device_alerts.pop(mac, None)

    if not alert_payload:
        return Response(status_code=204)

    sender = str(alert_payload.get("sender") or "").strip()
    message = str(alert_payload.get("message") or "").strip()
    level = str(alert_payload.get("level") or "info").strip().lower()

    img = Image.new("1", (w, h), 1)
    draw = ImageDraw.Draw(img)
    apply_text_fontmode(draw)

    scale = min(w / float(SCREEN_WIDTH), h / float(SCREEN_HEIGHT))
    title_font = load_font("noto_serif_bold", max(14, int(26 * scale)))
    sender_font = load_font("noto_serif_regular", max(12, int(20 * scale)))
    body_font = load_font("noto_serif_regular", max(10, int(18 * scale)))

    margin_x = max(8, int(w * 0.06))
    top_pad = max(8, int(h * 0.08))
    max_width = w - 2 * margin_x

    label = "FOCUS ALERT" if level != "critical" else "紧急告警"
    title_w = draw.textlength(label, font=title_font)
    draw.text((max(margin_x, int((w - title_w) / 2)), top_pad), label, fill=0, font=title_font)

    y = top_pad + int((title_font.size if hasattr(title_font, "size") else 20) * 1.3) + 4
    if sender:
        draw.text((margin_x, y), f"[{sender}]", fill=0, font=sender_font)
        y += int((sender_font.size if hasattr(sender_font, "size") else 16) * 1.3) + 6

    line_height = int((body_font.size if hasattr(body_font, "size") else 14) * 1.3) + 2
    lines = _wrap_text_by_pixels(draw, message, body_font, max_width)
    max_lines = max(1, (h - y - 10) // max(line_height, 1))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1][: max(0, len(lines[-1]) - 1)] + "…"
    for i, line in enumerate(lines):
        yy = y + i * line_height
        if yy > h - 6:
            break
        if line:
            draw.text((margin_x, yy), line, fill=0, font=body_font)

    return Response(content=image_to_bmp_bytes(img), media_type="image/bmp")


@router.post("/device/{mac}/apply-preview")
async def apply_preview_to_device(
    mac: str,
    request: Request,
    mode: str = Query(default="", description="Optional mode hint for logs/state"),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
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
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("[DEVICE] Invalid preview payload for %s", mac, exc_info=True)
        return JSONResponse({"error": "invalid image payload"}, status_code=400)

    mode_hint = mode.strip().upper()
    async with _preview_push_queue_lock:
        _preview_push_queue[mac] = {"image": normalized_bytes, "mode": mode_hint}
    await set_pending_refresh(mac, True)
    logger.info("[DEVICE] Queued preview push for %s, mode=%s", mac, mode_hint or "-")
    return {"ok": True, "message": "Preview queued"}


@router.post("/device/{mac}/switch")
async def switch_mode(
    mac: str,
    body: dict,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    from core.mode_registry import get_registry

    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    mode = body.get("mode", "").upper()
    registry = get_registry()
    if not mode or not registry.is_supported(mode, mac):
        return JSONResponse({"error": f"unsupported mode: {mode}"}, status_code=400)
    await update_device_state(mac, pending_mode=mode, pending_refresh=1)
    logger.info("[DEVICE] Pending mode switch to %s for %s", mode, mac)
    return {"ok": True, "message": f"Mode switch to {mode} queued"}


@router.post("/device/{mac}/favorite")
async def favorite_content(
    mac: str,
    request: Request,
    body: Optional[dict] = None,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    from core.mode_registry import get_registry

    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    mode = str((body or {}).get("mode", "")).strip().upper()
    if mode:
        registry = get_registry()
        if not registry.is_supported(mode, mac):
            return JSONResponse({"error": f"unsupported mode: {mode}"}, status_code=400)
        latest = await get_latest_render_content(mac)
        if latest and latest.get("mode_id", "").upper() == mode:
            await add_favorite(mac, mode, json.dumps(latest["content"], ensure_ascii=False))
        else:
            await add_favorite(mac, mode, None)
        return {"ok": True, "message": "Mode favorited", "mode_id": mode}

    latest = await get_latest_render_content(mac)
    if not latest:
        state = await get_device_state(mac)
        mode_id = state.get("last_persona", "UNKNOWN") if state else "UNKNOWN"
        await add_favorite(mac, mode_id, None)
    else:
        await add_favorite(mac, latest["mode_id"], json.dumps(latest["content"], ensure_ascii=False))
    return {"ok": True, "message": "Content favorited"}


@router.get("/device/{mac}/favorites")
async def list_favorites(
    mac: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return {"mac": mac, "favorites": await get_favorites(mac, limit)}


@router.get("/device/{mac}/history")
async def content_history(
    mac: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mode: Optional[str] = Query(default=None),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return {"mac": mac, "history": await get_content_history(mac, limit, offset, mode)}


@router.post("/device/{mac}/habit/check")
async def habit_check(
    mac: str,
    body: dict,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    habit_name = body.get("habit", "").strip()
    if not habit_name:
        return JSONResponse({"error": "habit name is required"}, status_code=400)
    await check_habit(mac, habit_name, body.get("date"))
    return {"ok": True, "message": f"Habit '{habit_name}' checked"}


@router.get("/device/{mac}/habit/status")
async def habit_status(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return {"mac": mac, "habits": await get_habit_status(mac)}


@router.delete("/device/{mac}/habit/{habit_name}")
async def habit_delete(
    mac: str,
    habit_name: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    deleted = await delete_habit(mac, habit_name)
    if not deleted:
        return JSONResponse({"error": "Habit not found"}, status_code=404)
    return {"ok": True, "message": f"Habit '{habit_name}' deleted"}


@router.post("/device/{mac}/token")
async def provision_device_token(mac: str):
    mac = validate_mac_param(mac)
    state = await get_device_state(mac)
    if state and state.get("auth_token"):
        return {"token": state["auth_token"], "new": False}
    token = await generate_device_token(mac)
    logger.info("[AUTH] Provisioned new device token for %s", mac)
    return {"token": token, "new": True}


@router.post("/device/{mac}/claim-token")
async def provision_claim_token(
    mac: str,
    request: Request,
    body: Optional[dict] = None,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    preferred_pair_code = str((body or {}).get("pair_code") or "").strip()
    created = await create_claim_token(mac, source="portal", preferred_pair_code=preferred_pair_code)
    if created is None:
        return JSONResponse({"error": "pair_code_conflict"}, status_code=409)
    return {
        "ok": True,
        "token": created["token"],
        "pair_code": created["pair_code"],
        "claim_url": build_claim_url(request, created["token"]),
        "expires_at": created["expires_at"],
    }


@router.post("/claim/consume")
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


@router.get("/devices/recent")
async def recent_devices(
    minutes: int = Query(default=DISCOVERY_WINDOW_MINUTES, ge=1, le=60),
    admin_auth: None = Depends(require_admin),
):
    from core.db import get_main_db

    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
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
    devices = [{"mac": row[0], "last_seen": row[1], "has_owner": bool(row[2])} for row in rows if row and row[0]]
    return {"devices": devices}


@router.get("/device/{mac}/qr")
async def device_qr(
    mac: str,
    request: Request,
    base_url: Optional[str] = Query(default=None),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    import qrcode

    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
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
    return Response(content=image_to_bmp_bytes(canvas), media_type="image/bmp")


@router.get("/device/{mac}/share")
async def share_image(
    mac: str,
    request: Request,
    w: int = Query(default=800, ge=400, le=1600),
    h: int = Query(default=450, ge=300, le=900),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    latest = await get_latest_render_content(mac)
    if not latest:
        return JSONResponse({"error": "no content to share"}, status_code=404)

    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
    try:
        title_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Bold.ttf"), 24)
        body_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Regular.ttf"), 18)
        small_font = ImageFont.truetype(os.path.join(font_dir, "NotoSerifSC-Regular.ttf"), 12)
    except OSError:
        logger.warning("[DEVICE] Falling back to default fonts for share image", exc_info=True)
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (w - 1, h - 1)], outline=0, width=2)
    draw.text((40, 30), latest["mode_id"], fill=0, font=title_font)

    y = 80
    content = latest["content"]
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
    return Response(content=image_to_png_bytes(img.convert("1")), media_type="image/png")
