"""
统一的内容生成 + 渲染管道
消除 index.py._render_for_persona 和 cache.py._generate_single_mode 的重复逻辑
"""
from __future__ import annotations

import logging
from PIL import Image

from .config import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_CONTENT_TONE,
)
from .content import (
    generate_content,
    generate_briefing_content,
    generate_artwall_content,
    generate_recipe_content,
    generate_fitness_content,
)
from .renderer import render_mode

logger = logging.getLogger(__name__)


async def generate_and_render(
    persona: str,
    config: dict | None,
    date_ctx: dict,
    weather: dict,
    battery_pct: float,
) -> Image.Image:
    """Generate content for a persona and render to an e-ink image.

    This is the single entry point for all modes, replacing the duplicated
    logic in index.py._render_for_persona and cache.py._generate_single_mode.
    """
    date_str = date_ctx["date_str"]
    time_str = date_ctx.get("time_str", "")
    weather_str = weather["weather_str"]
    weather_code = weather.get("weather_code", -1)
    cfg = config or {}

    content = await _generate_content_for_persona(persona, cfg, date_ctx, weather_str)

    return render_mode(
        persona,
        content,
        date_str=date_str,
        weather_str=weather_str,
        battery_pct=battery_pct,
        weather_code=weather_code,
        time_str=time_str,
        date_ctx=date_ctx,
    )


async def _generate_content_for_persona(
    persona: str,
    cfg: dict,
    date_ctx: dict,
    weather_str: str,
) -> dict:
    """Dispatch content generation to the appropriate mode handler."""
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

    if persona == "FITNESS":
        return await generate_fitness_content(
            llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
        )

    # Standard modes: STOIC, ROAST, ZEN, DAILY (+ fallback)
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
