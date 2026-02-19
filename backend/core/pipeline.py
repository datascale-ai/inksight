"""
统一的内容生成 + 渲染管道
支持内置 Python 模式和 JSON 定义模式的统一分发
"""
from __future__ import annotations

import logging
from PIL import Image

from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_CONTENT_TONE,
)

logger = logging.getLogger(__name__)


async def generate_and_render(
    persona: str,
    config: dict | None,
    date_ctx: dict,
    weather: dict,
    battery_pct: float,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
) -> Image.Image:
    """Generate content for a persona and render to an e-ink image.

    Dispatches to either a builtin Python mode or a JSON-defined mode
    via the mode registry.
    """
    date_str = date_ctx["date_str"]
    time_str = date_ctx.get("time_str", "")
    weather_str = weather["weather_str"]
    weather_code = weather.get("weather_code", -1)
    cfg = config or {}

    content = await _generate_content_for_persona(persona, cfg, date_ctx, weather_str)

    return _render_for_persona(
        persona, content,
        date_str=date_str, weather_str=weather_str, battery_pct=battery_pct,
        weather_code=weather_code, time_str=time_str, date_ctx=date_ctx,
        screen_w=screen_w, screen_h=screen_h,
    )


async def _generate_content_for_persona(
    persona: str,
    cfg: dict,
    date_ctx: dict,
    weather_str: str,
) -> dict:
    """Dispatch content generation to the appropriate handler."""
    from .mode_registry import get_registry

    registry = get_registry()
    date_str = date_ctx["date_str"]

    # JSON-defined mode
    if registry.is_json_mode(persona):
        from .json_content import generate_json_mode_content
        jm = registry.get_json_mode(persona)
        return await generate_json_mode_content(
            jm.definition,
            date_str=date_str,
            weather_str=weather_str,
            festival=date_ctx.get("festival", ""),
            daily_word=date_ctx.get("daily_word", ""),
            upcoming_holiday=date_ctx.get("upcoming_holiday", ""),
            days_until_holiday=date_ctx.get("days_until_holiday", 0),
            character_tones=cfg.get("character_tones", []),
            language=cfg.get("language", DEFAULT_LANGUAGE),
            content_tone=cfg.get("content_tone", DEFAULT_CONTENT_TONE),
            llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
        )

    # Builtin Python mode - use specialized content functions
    bm = registry.get_builtin(persona)
    if bm:
        return await _call_builtin_content(persona, bm, cfg, date_ctx, weather_str)

    # Fallback: treat as standard LLM mode
    from .content import generate_content
    return await generate_content(
        persona=persona,
        date_str=date_str,
        weather_str=weather_str,
        character_tones=cfg.get("character_tones", []),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        content_tone=cfg.get("content_tone", DEFAULT_CONTENT_TONE),
        festival=date_ctx.get("festival", ""),
        daily_word=date_ctx.get("daily_word", ""),
        upcoming_holiday=date_ctx.get("upcoming_holiday", ""),
        days_until_holiday=date_ctx.get("days_until_holiday", 0),
        llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
        llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
    )


async def _call_builtin_content(
    persona: str,
    bm,
    cfg: dict,
    date_ctx: dict,
    weather_str: str,
) -> dict:
    """Call builtin mode's content function with the correct arguments."""
    from .content import (
        generate_artwall_content,
        generate_briefing_content,
        generate_countdown_content,
        generate_recipe_content,
    )

    date_str = date_ctx["date_str"]

    if persona == "ARTWALL":
        return await generate_artwall_content(
            date_str=date_str,
            weather_str=weather_str,
            festival=date_ctx.get("festival", ""),
            llm_provider=cfg.get("llm_provider", "aliyun"),
            llm_model=cfg.get("llm_model", "qwen-image-max"),
        )

    if persona == "BRIEFING":
        return await generate_briefing_content(
            llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
        )

    if persona == "RECIPE":
        return await generate_recipe_content(
            llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
        )

    if persona == "COUNTDOWN":
        return await generate_countdown_content(config=cfg)

    # DAILY and other builtins that use the standard generate_content path
    from .content import generate_content
    return await generate_content(
        persona=persona,
        date_str=date_str,
        weather_str=weather_str,
        character_tones=cfg.get("character_tones", []),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        content_tone=cfg.get("content_tone", DEFAULT_CONTENT_TONE),
        festival=date_ctx.get("festival", ""),
        daily_word=date_ctx.get("daily_word", ""),
        upcoming_holiday=date_ctx.get("upcoming_holiday", ""),
        days_until_holiday=date_ctx.get("days_until_holiday", 0),
        llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
        llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
    )


def _render_for_persona(
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
    """Dispatch rendering to the appropriate handler."""
    from .mode_registry import get_registry
    from .renderer import render_mode
    from .json_renderer import render_json_mode

    registry = get_registry()

    # JSON-defined mode
    if registry.is_json_mode(persona):
        jm = registry.get_json_mode(persona)
        return render_json_mode(
            jm.definition, content,
            date_str=date_str, weather_str=weather_str, battery_pct=battery_pct,
            weather_code=weather_code, time_str=time_str,
            screen_w=screen_w, screen_h=screen_h,
        )

    # Builtin Python mode - use original render_mode dispatcher
    return render_mode(
        persona, content,
        date_str=date_str, weather_str=weather_str, battery_pct=battery_pct,
        weather_code=weather_code, time_str=time_str, date_ctx=date_ctx,
        screen_w=screen_w, screen_h=screen_h,
    )
