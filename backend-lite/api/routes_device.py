"""固件设备路由：token / heartbeat / config / state / runtime / refresh /
claim-token / alert-bmp / ota-progress。单用户：MAC 任意，token 固定。"""
from __future__ import annotations

import json
import logging
import secrets

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse, Response as RawResponse

from store import config_store

logger = logging.getLogger("backend-lite.device")

router = APIRouter(prefix="/api", tags=["device"])

# 单用户：所有 MAC 共享一个固定 token（首次发放后存 device_state）。
# 不校验 X-Device-Token 内容——局域网信任模型。
DEVICE_TOKEN = "inklite-single-user-token"


def _mac(request: Request, mac: str | None = None) -> str:
    return (mac or request.path_params.get("mac") or "").strip().upper() or "00:00:00:00:00:00:00"


@router.post("/device/{mac}/token")
async def issue_token(mac: str):
    """发放设备 token。单用户固定值，但回写 device_state 以备追溯。"""
    m = mac.strip().upper()
    config_store.upsert_state(m, auth_token=DEVICE_TOKEN)
    return {"token": DEVICE_TOKEN}


@router.post("/device/{mac}/claim-token")
async def claim_token(mac: str, request: Request):
    """回显 pair_code（portal 配对兼容）。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return {"pair_code": body.get("pair_code", "")}


@router.post("/device/{mac}/heartbeat")
async def heartbeat(mac: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    bv = float(body.get("battery_voltage") or 0)
    rssi = int(body.get("wifi_rssi") or 0)
    config_store.add_heartbeat(mac.strip().upper(), bv, rssi)
    return Response(status_code=200)


@router.get("/config/{mac}")
async def get_device_config(mac: str):
    """固件轮询：返回 focus / always_active 开关。"""
    cfg = config_store.get_config()
    return {
        "is_focus_listening": bool(cfg.get("focus_listening")),
        "is_always_active": bool(cfg.get("always_active")),
    }


@router.get("/device/{mac}/state")
async def get_state(mac: str):
    """固件轮询运行状态。OTA 字段非空时附上。"""
    s = config_store.get_state(mac.strip().upper())
    resp = {
        "pending_refresh": int(bool(s.get("pending_refresh"))),
        "pending_mode": s.get("pending_mode") or "",
        "runtime_mode": s.get("runtime_mode") or "interval",
    }
    ota_url = s.get("ota_url") or ""
    ota_ver = s.get("ota_version") or ""
    if ota_url:
        resp["ota_url"] = ota_url
        resp["ota_version"] = ota_ver
    return resp


@router.post("/device/{mac}/runtime")
async def set_runtime(mac: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = (body.get("mode") or "interval").strip()
    config_store.upsert_state(mac.strip().upper(), runtime_mode=mode)
    return Response(status_code=200)


@router.post("/device/{mac}/refresh")
async def trigger_refresh(mac: str):
    config_store.upsert_state(mac.strip().upper(), pending_refresh=1)
    return Response(status_code=200)


@router.post("/config")
async def save_device_config(request: Request):
    """固件 POST /api/config：body 是设备的 cfgConfigJson（含 mac）。
    单用户：把可识别字段写回 config 单行。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    patch: dict = {}
    for k in (
        "modes", "refresh_strategy", "refresh_interval", "city",
        "language", "content_tone", "time_slot_rules", "countdown_events",
        "memo_text", "focus_listening", "always_active",
        "llm_provider", "llm_model", "image_provider", "image_model",
    ):
        if k in body:
            patch[k] = body[k]
    if patch:
        config_store.update_config(patch)
    return Response(status_code=200)


@router.get("/device/{mac}/alert-bmp")
async def alert_bmp(mac: str, w: int = 400, h: int = 300):
    """焦点提醒图。无活跃 alert → 204；有 → 渲染更醒目的居中文字 1-bit BMP。"""
    alert = config_store.get_alert()
    if not alert.get("active"):
        return Response(status_code=204)

    from io import BytesIO
    from PIL import Image, ImageDraw
    from core.patterns.utils import load_font

    width = w or 400
    height = h or 300
    text = (alert.get("text") or "!").strip() or "!"
    img = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(img)

    # 外框，增强“弹窗感”
    draw.rounded_rectangle([8, 8, width - 9, height - 9], radius=16, outline=0, width=2)

    max_width = width - 56
    max_height = height - 56

    def wrap_text(font):
        lines = []
        current = ""
        for ch in text:
            if ch == "\n":
                lines.append(current or " ")
                current = ""
                continue
            candidate = current + ch
            bbox = draw.textbbox((0, 0), candidate, font=font)
            cand_width = bbox[2] - bbox[0]
            if current and cand_width > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or ["!"]

    chosen_font = None
    chosen_lines = [text]
    chosen_metrics = []
    for size in (72, 64, 56, 48, 42, 36, 32, 28, 24):
        try:
            font = load_font("noto_serif_bold", size)
        except Exception:
            font = None
        lines = wrap_text(font)
        metrics = []
        widest = 0
        total_h = 0
        spacing = max(6, size // 5)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            left, top, right, bottom = bbox
            line_w = max(1, right - left)
            line_h = max(1, bottom - top)
            widest = max(widest, line_w)
            total_h += line_h
            metrics.append((line, left, top, line_w, line_h))
        total_h += spacing * max(0, len(metrics) - 1)
        if widest <= max_width and total_h <= max_height:
            chosen_font = font
            chosen_lines = lines
            chosen_metrics = metrics
            break
        chosen_font = font
        chosen_lines = lines
        chosen_metrics = metrics

    total_height = sum(item[4] for item in chosen_metrics)
    total_height += max(6, 24 // 5) * max(0, len(chosen_metrics) - 1)
    # 根据最终字号重新计算行距
    if chosen_metrics:
        avg_height = max(item[4] for item in chosen_metrics)
        line_spacing = max(6, avg_height // 4)
        total_height = sum(item[4] for item in chosen_metrics) + line_spacing * max(0, len(chosen_metrics) - 1)
    else:
        line_spacing = 8

    y = max(18, (height - total_height) // 2)
    for idx, (line, left, top, line_w, line_h) in enumerate(chosen_metrics):
        x = max(16, (width - line_w) // 2)
        draw.text((x - left, y - top), line, fill=0, font=chosen_font)
        y += line_h + (line_spacing if idx < len(chosen_metrics) - 1 else 0)

    buf = BytesIO()
    img.save(buf, format="BMP")
    return RawResponse(content=buf.getvalue(), media_type="image/bmp")


@router.post("/device/{mac}/ota/progress")
async def ota_progress(mac: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    logger.info("[ota] progress %s: %s", mac, body)
    return Response(status_code=200)


# vocab / voice 不实现：固件遇非 200 自动降级
@router.api_route("/device/{mac}/vocab/{rest:path}", methods=["GET", "POST"])
async def vocab_unsupported(rest: str):
    return Response(status_code=404)


@router.api_route("/device/{mac}/voice/{rest:path}", methods=["GET", "POST"])
async def voice_unsupported(rest: str):
    return Response(status_code=404)