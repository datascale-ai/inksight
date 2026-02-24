"""
通用 JSON 模式内容生成器
根据 JSON content 定义调用 LLM 或返回静态数据
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from .config import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
from .content import _build_context_str, _build_style_instructions, _call_llm, _clean_json_response

logger = logging.getLogger(__name__)


async def generate_json_mode_content(
    mode_def: dict,
    *,
    config: dict | None = None,
    date_ctx: dict | None = None,
    date_str: str = "",
    weather_str: str = "",
    festival: str = "",
    daily_word: str = "",
    upcoming_holiday: str = "",
    days_until_holiday: int = 0,
    character_tones: list[str] | None = None,
    language: str | None = None,
    content_tone: str | None = None,
    llm_provider: str = "",
    llm_model: str = "",
) -> dict:
    """Generate content for a JSON-defined mode.

    Supports content types:
    - static: returns static_data from the definition
    - llm: calls LLM with prompt template, parses output per output_format
    - llm_json: calls LLM, parses JSON response using output_schema
    - external_data: fetches data from built-in providers (HN/PH/V2EX)
    - image_gen: generates image data payload (ARTWALL provider)
    - computed: computes content from config/date without LLM
    - composite: merges results from multiple nested content steps
    """
    content_cfg = mode_def.get("content", {})
    ctype = content_cfg.get("type", "static")
    fallback = content_cfg.get("fallback", {})

    common_args = dict(
        date_str=date_str,
        weather_str=weather_str,
        festival=festival,
        daily_word=daily_word,
        upcoming_holiday=upcoming_holiday,
        days_until_holiday=days_until_holiday,
        character_tones=character_tones,
        language=language,
        content_tone=content_tone,
        llm_provider=llm_provider,
        llm_model=llm_model,
        config=config or {},
        date_ctx=date_ctx or {},
    )

    if ctype == "static":
        return dict(content_cfg.get("static_data", fallback))
    if ctype == "computed":
        return await _generate_computed_content(mode_def, content_cfg, fallback, **common_args)
    if ctype == "external_data":
        return await _generate_external_data_content(mode_def, content_cfg, fallback, **common_args)
    if ctype == "image_gen":
        return await _generate_image_gen_content(mode_def, content_cfg, fallback, **common_args)
    if ctype == "composite":
        return await _generate_composite_content(mode_def, content_cfg, fallback, **common_args)

    provider = llm_provider or DEFAULT_LLM_PROVIDER
    model = llm_model or DEFAULT_LLM_MODEL
    temperature = content_cfg.get("temperature", 0.8)

    context = _build_context_str(
        date_str, weather_str, festival, daily_word,
        upcoming_holiday, days_until_holiday,
    )
    prompt = content_cfg.get("prompt_template", "").format(context=context)

    style = _build_style_instructions(character_tones, language, content_tone)
    if style:
        prompt += style

    mode_id = mode_def.get("mode_id", "CUSTOM")
    logger.info(f"[JSONContent] Generating content for {mode_id} via {provider}/{model}")

    try:
        text = await _call_llm(provider, model, prompt, temperature=temperature)
    except Exception as e:
        logger.error(f"[JSONContent] LLM call failed for {mode_id}: {e}")
        return dict(fallback)

    if ctype == "llm":
        result = _parse_llm_output(text, content_cfg, fallback)
    elif ctype == "llm_json":
        result = _parse_llm_json_output(text, content_cfg, fallback)
    else:
        result = {"text": text}

    return _apply_post_process(result, content_cfg)


async def _generate_computed_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    provider = content_cfg.get("provider", "")
    if provider == "countdown":
        from .content import generate_countdown_content
        config = content_cfg.get("config", {})
        cfg = config if config else (kwargs.get("config") or {})
        return await generate_countdown_content(config=cfg)
    if provider == "daily_meta":
        date_ctx = kwargs.get("date_ctx", {}) or {}
        result = dict(fallback)
        result.update({
            "year": date_ctx.get("year"),
            "day": date_ctx.get("day"),
            "month_cn": date_ctx.get("month_cn"),
            "weekday_cn": date_ctx.get("weekday_cn"),
            "day_of_year": date_ctx.get("day_of_year"),
            "days_in_year": date_ctx.get("days_in_year"),
        })
        return result
    return dict(fallback)


async def _generate_external_data_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    from .content import (
        fetch_hn_top_stories,
        fetch_ph_top_product,
        fetch_v2ex_hot,
        summarize_briefing_content,
        generate_briefing_insight,
    )

    provider = content_cfg.get("provider", "")
    llm_provider = kwargs.get("llm_provider") or DEFAULT_LLM_PROVIDER
    llm_model = kwargs.get("llm_model") or DEFAULT_LLM_MODEL

    if provider == "briefing":
        hn_limit = int(content_cfg.get("hn_limit", 2))
        v2ex_limit = int(content_cfg.get("v2ex_limit", 1))
        summarize = bool(content_cfg.get("summarize", True))
        include_insight = bool(content_cfg.get("include_insight", True))

        import asyncio as _asyncio
        hn_items, ph_item, v2ex_items = await _asyncio.gather(
            fetch_hn_top_stories(limit=hn_limit),
            fetch_ph_top_product(),
            fetch_v2ex_hot(limit=v2ex_limit),
        )
        if not hn_items and not ph_item and not v2ex_items:
            return dict(fallback)
        if summarize:
            hn_items, ph_item = await summarize_briefing_content(
                hn_items, ph_item, llm_provider, llm_model
            )
        insight = ""
        if include_insight:
            insight = await generate_briefing_insight(hn_items, ph_item, llm_provider, llm_model)
        result = dict(fallback)
        ph_name = ""
        ph_tagline = ""
        if isinstance(ph_item, dict):
            ph_name = str(ph_item.get("name", ""))
            ph_tagline = str(ph_item.get("tagline", ""))
        result.update({
            "hn_items": hn_items or result.get("hn_items", []),
            "ph_item": ph_item or result.get("ph_item", {}),
            "v2ex_items": v2ex_items or result.get("v2ex_items", []),
            "insight": insight or result.get("insight", ""),
            "ph_name": ph_name,
            "ph_tagline": ph_tagline,
        })
        return result

    return dict(fallback)


async def _generate_image_gen_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    provider = content_cfg.get("provider", "")
    if provider == "artwall":
        from .content import generate_artwall_content
        return await generate_artwall_content(
            date_str=kwargs.get("date_str", ""),
            weather_str=kwargs.get("weather_str", ""),
            festival=kwargs.get("festival", ""),
            llm_provider=kwargs.get("llm_provider") or "aliyun",
            llm_model=kwargs.get("llm_model") or "qwen-image-max",
        )
    return dict(fallback)


async def _generate_composite_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    steps = content_cfg.get("steps", [])
    result: dict[str, Any] = {}
    for step in steps:
        step_mode_def = {
            "mode_id": mode_def.get("mode_id", "COMPOSITE"),
            "content": step,
        }
        part = await generate_json_mode_content(step_mode_def, **kwargs)
        if isinstance(part, dict):
            result.update(part)
    if not result:
        return dict(fallback)
    merged = dict(fallback)
    merged.update(result)
    return merged


def _apply_post_process(result: dict, content_cfg: dict) -> dict:
    """Apply optional post-processing rules to content fields."""
    rules = content_cfg.get("post_process", {})
    for field_name, rule in rules.items():
        val = result.get(field_name, "")
        if not isinstance(val, str):
            continue
        if rule == "first_char":
            result[field_name] = val[:1] if val else ""
        elif rule == "strip_quotes":
            result[field_name] = val.strip('""\u201c\u201d\u300c\u300d')
    return result


def _parse_llm_output(text: str, content_cfg: dict, fallback: dict) -> dict:
    """Parse LLM text output according to output_format."""
    fmt = content_cfg.get("output_format", "raw")

    if fmt == "text_split":
        return _parse_text_split(text, content_cfg, fallback)
    elif fmt == "json":
        return _parse_json_output(text, content_cfg, fallback)
    else:
        fields = content_cfg.get("output_fields", ["text"])
        return {fields[0]: text}


def _parse_text_split(text: str, content_cfg: dict, fallback: dict) -> dict:
    """Split text by separator and map to output_fields."""
    sep = content_cfg.get("output_separator", "|")
    fields = content_cfg.get("output_fields", ["text"])
    parts = text.split(sep)

    result = {}
    for i, field_name in enumerate(fields):
        if i < len(parts):
            result[field_name] = parts[i].strip().strip('""\u201c\u201d')
        else:
            result[field_name] = fallback.get(field_name, "")
    return result


def _parse_json_output(text: str, content_cfg: dict, fallback: dict) -> dict:
    """Parse JSON from LLM response."""
    try:
        cleaned = _clean_json_response(text)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return dict(fallback)

        fields = content_cfg.get("output_fields")
        if fields:
            return {f: data.get(f, fallback.get(f, "")) for f in fields}
        return data
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"[JSONContent] JSON parse failed: {e}")
        return dict(fallback)


def _parse_llm_json_output(text: str, content_cfg: dict, fallback: dict) -> dict:
    """Parse JSON from LLM response using output_schema for defaults."""
    schema = content_cfg.get("output_schema", {})
    try:
        cleaned = _clean_json_response(text)
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return dict(fallback)

        result = {}
        for field_name, field_def in schema.items():
            default = field_def.get("default", "")
            result[field_name] = data.get(field_name, default)
        return result
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"[JSONContent] JSON parse failed: {e}")
        return dict(fallback)
