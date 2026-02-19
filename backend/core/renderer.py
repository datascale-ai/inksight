"""
渲染器模块
负责将内容渲染为墨水屏图像，并提供统一的模式分发接口
"""

from __future__ import annotations

import io
from PIL import Image

from .config import SCREEN_WIDTH, SCREEN_HEIGHT
from .patterns import (
    render_stoic,
    render_roast,
    render_zen,
    render_daily,
    render_error,
    render_briefing,
    render_artwall,
    render_recipe,
    render_fitness,
    render_poetry,
    render_countdown,
)

__all__ = [
    "render_stoic",
    "render_roast",
    "render_zen",
    "render_daily",
    "render_error",
    "render_briefing",
    "render_artwall",
    "render_recipe",
    "render_fitness",
    "render_poetry",
    "render_countdown",
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
    """Unified mode rendering dispatcher.

    Maps persona to the corresponding render function, extracts
    mode-specific fields from *content*, and passes common display
    parameters automatically.

    Args:
        persona: Mode name (STOIC, ROAST, ZEN, DAILY, BRIEFING, …)
        content: Content dict returned by generate_content() or
                 a mode-specific content generator.
        date_str / weather_str / battery_pct / weather_code / time_str:
            Common status-bar parameters shared by all renderers.
        date_ctx: Full date context dict (needed by DAILY mode for
                  year, month_cn, weekday_cn, etc.).
        screen_w / screen_h: Target resolution (default 400x300).
    """
    common = dict(
        date_str=date_str,
        weather_str=weather_str,
        battery_pct=battery_pct,
        weather_code=weather_code,
        time_str=time_str,
        screen_w=screen_w,
        screen_h=screen_h,
    )

    if persona == "STOIC":
        return render_stoic(
            **common,
            quote=content["quote"],
            author=content.get("author", ""),
        )

    if persona == "ROAST":
        return render_roast(**common, quote=content["quote"])

    if persona == "ZEN":
        return render_zen(**common, word=content["word"])

    if persona == "DAILY":
        ctx = date_ctx or {}
        return render_daily(
            **common,
            year=ctx["year"],
            day=ctx["day"],
            month_cn=ctx["month_cn"],
            weekday_cn=ctx["weekday_cn"],
            day_of_year=ctx["day_of_year"],
            days_in_year=ctx["days_in_year"],
            quote=content.get("quote", ""),
            author=content.get("author", ""),
            book_title=content.get("book_title", ""),
            book_author=content.get("book_author", ""),
            book_desc=content.get("book_desc", ""),
            tip_label="小知识",
            tip=content.get("tip", ""),
            season_text=content.get("season_text", ""),
        )

    if persona == "BRIEFING":
        return render_briefing(
            **common,
            hn_items=content["hn_items"],
            ph_item=content["ph_item"],
            insight=content["insight"],
            v2ex_items=content.get("v2ex_items"),
        )

    if persona == "ARTWALL":
        return render_artwall(
            **common,
            artwork_title=content["artwork_title"],
            image_url=content.get("image_url", ""),
            description=content.get("description", ""),
        )

    if persona == "RECIPE":
        return render_recipe(
            **common,
            season=content["season"],
            breakfast=content["breakfast"],
            lunch=content["lunch"],
            dinner=content["dinner"],
            nutrition=content["nutrition"],
        )

    if persona == "FITNESS":
        return render_fitness(
            **common,
            workout_name=content["workout_name"],
            duration=content["duration"],
            exercises=content["exercises"],
            tip=content["tip"],
        )

    if persona == "POETRY":
        return render_poetry(
            **common,
            title=content.get("title", ""),
            author=content.get("author", ""),
            lines=content.get("lines", []),
            note=content.get("note", ""),
        )

    if persona == "COUNTDOWN":
        return render_countdown(
            **common,
            events=content.get("events", []),
        )

    # Fallback: treat as STOIC
    return render_stoic(
        **common,
        quote=content.get("quote", "..."),
        author=content.get("author", ""),
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
