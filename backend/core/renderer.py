"""
渲染器模块
负责将内容渲染为墨水屏图像，并提供统一的模式分发接口

STOIC, ROAST, ZEN, FITNESS, POETRY 已迁移至 JSON 渲染引擎 (json_renderer.py)。
此处仅分发尚未迁移的 Python 内置模式。
"""

from __future__ import annotations

import io
from PIL import Image

from .config import SCREEN_WIDTH, SCREEN_HEIGHT
from .patterns import render_error

__all__ = [
    "render_error",
    "render_mode",
    "image_to_bmp_bytes",
    "image_to_png_bytes",
]


def render_mode(
    persona: str,
    content: dict,
    *,
    date_str: str,
    weather_str: str,
    battery_pct: float,
    weather_code: int = -1,
    time_str: str = "",
    date_ctx: dict | None = None,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
) -> Image.Image:
    """Legacy dispatcher retained for backward compatibility.

    All production modes are JSON-defined and rendered by json_renderer.
    """
    raise ValueError(
        f"Unknown builtin persona '{persona}'. "
        "JSON-defined modes should be routed through json_renderer."
    )


def image_to_bmp_bytes(img: Image.Image) -> bytes:
    """将图像转换为 BMP 字节流"""
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def image_to_png_bytes(img: Image.Image) -> bytes:
    """将图像转换为 PNG 字节流"""
    if img.mode == "1":
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
