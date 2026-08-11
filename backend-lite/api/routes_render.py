"""固件渲染路由：/api/render, /api/preview。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import Response as RawResponse

from adaptee.render import encode_image, encode_png, render_for_device, render_for_preview
from store import config_store

logger = logging.getLogger("backend-lite.render")

router = APIRouter(prefix="/api", tags=["render"])

# 固件协议默认尺寸 400×300、2bpp、4 色
SCREEN_W = 400
SCREEN_H = 300
COLORS = 4


@router.get("/render")
async def render(
    request: Request,
    mac: str = Query(default=""),
    v: float = Query(default=0.0),
    rssi: int = Query(default=0),
    refresh_min: int = Query(default=0),
    w: int = Query(default=SCREEN_W),
    h: int = Query(default=SCREEN_H),
    bpp: int = Query(default=2),
    colors: int = Query(default=COLORS),
    next: int = Query(default=0, alias="next"),
):
    """固件核心刷图端点。返回 raw 2bpp（4 色）或 BMP。"""
    mac_clean = mac.strip().upper() or "00:00:00:00:00:00"
    result = await render_for_device(
        mac_clean,
        battery_voltage=v,
        screen_w=w or SCREEN_W,
        screen_h=h or SCREEN_H,
        colors=colors if colors >= 2 else COLORS,
    )
    # 渲染成功后清除 pending_refresh
    config_store.upsert_state(mac_clean, pending_refresh=0)

    body = encode_image(result["image"], result["colors"] if "colors" in result else colors)
    headers = {
        "X-Mode-Id": result["persona"],
        "X-Refresh-Minutes": str(result["refresh_minutes"]),
        "Cache-Control": "no-store",
        "Connection": "close",
    }
    if result["fallback"]:
        headers["X-Content-Fallback"] = "1"
    return RawResponse(content=body, media_type="application/octet-stream", headers=headers)


@router.get("/preview")
async def preview(
    mode: str = Query(default=""),
    colors: int = Query(default=COLORS),
    as_png: int = Query(default=0),
):
    """管理页预览：固定 400×300/4 色。默认 PNG 便于浏览器内联显示。"""
    persona = (mode or "").strip().upper() or "STOIC"
    img = await render_for_preview(persona, colors=colors if colors >= 2 else COLORS)
    if as_png:
        return RawResponse(content=encode_png(img), media_type="image/png")
    return RawResponse(content=encode_image(img, colors), media_type="application/octet-stream")