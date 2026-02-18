"""
通用 JSON 模式内容生成器
根据 JSON content 定义调用 LLM 或返回静态数据
"""
from __future__ import annotations

import json
import logging
import re

from .config import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
from .content import _build_context_str, _build_style_instructions, _call_llm, _clean_json_response

logger = logging.getLogger(__name__)


async def generate_json_mode_content(
    mode_def: dict,
    *,
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

    Supports three content types:
    - static: returns static_data from the definition
    - llm: calls LLM with prompt template, parses output per output_format
    - llm_json: calls LLM, parses JSON response using output_schema
    """
    content_cfg = mode_def.get("content", {})
    ctype = content_cfg.get("type", "static")
    fallback = content_cfg.get("fallback", {})

    if ctype == "static":
        return dict(content_cfg.get("static_data", fallback))

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
