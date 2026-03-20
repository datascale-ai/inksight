"""
通用 JSON 模式内容生成器
根据 JSON content 定义调用 LLM 或返回静态数据
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
from json import JSONDecodeError
from typing import Any

import os

import httpx
from httpx import HTTPStatusError
from openai import OpenAIError

from .config import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_IMAGE_PROVIDER, DEFAULT_IMAGE_MODEL
from .content import _build_context_str, _build_style_instructions, _call_llm, _clean_json_response
from .errors import LLMKeyMissingError

logger = logging.getLogger(__name__)

# Experiment switches
DISABLE_FALLBACK = os.environ.get("INKSIGHT_DISABLE_FALLBACK", "").strip().lower() in ("1", "true", "yes")
DISABLE_DEDUP = os.environ.get("INKSIGHT_DISABLE_DEDUP", "").strip().lower() in ("1", "true", "yes")

if DISABLE_FALLBACK:
    logger.warning("[EXP] Fallback is DISABLED via INKSIGHT_DISABLE_FALLBACK")
if DISABLE_DEDUP:
    logger.warning("[EXP] Deduplication is DISABLED via INKSIGHT_DISABLE_DEDUP")

DEDUP_MAX_RETRIES = 2

def _collect_image_fields(blocks: list, fields: set):
    """Recursively collect image field names from layout blocks."""
    for block in blocks:
        if block.get("type") == "image":
            fields.add(block.get("field", "image_url"))
        for child_key in ("children", "left", "right"):
            children = block.get(child_key, [])
            if isinstance(children, list):
                _collect_image_fields(children, fields)


async def _prefetch_images(content: dict, mode_def: dict) -> dict:
    """Pre-fetch any image URLs referenced by the layout into content dict."""
    layout = mode_def.get("layout", {})
    body_blocks = layout.get("body", [])
    image_fields: set = set()
    _collect_image_fields(body_blocks, image_fields)

    if not image_fields:
        return content

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        for field_name in image_fields:
            url = content.get(field_name)
            if url and isinstance(url, str) and url.startswith("http"):
                try:
                    resp = await client.get(url)
                    if resp.status_code < 400:
                        content[f"_prefetched_{field_name}"] = resp.content
                except httpx.HTTPError:
                    logger.warning("[JSONContent] Failed to prefetch image field %s", field_name, exc_info=True)
    return content


def _get_fallback(content_cfg: dict) -> dict:
    """Get fallback content, supporting both single fallback and fallback_pool."""
    pool = content_cfg.get("fallback_pool")
    if pool and isinstance(pool, list) and len(pool) > 0:
        return dict(random.choice(pool))
    return dict(content_cfg.get("fallback", {}))


def _compute_content_hash(result: dict) -> str:
    text = json.dumps(result, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(text.encode()).hexdigest()[:12]


def _is_api_key_error(e: Exception) -> bool:
    """Check if exception indicates API key is invalid/expired (401/403)."""
    if isinstance(e, HTTPStatusError):
        status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
        return status_code in (401, 403)
    
    if isinstance(e, OpenAIError):
        error_message = str(e).lower()
        error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
        if error_code in (401, 403):
            return True
        auth_keywords = ("401", "403", "unauthorized", "invalid", "authentication")
        return any(kw in error_message for kw in auth_keywords)
    
    return False


def _validate_content_quality(result: dict, schema: dict | None = None) -> bool:
    """Validate LLM output quality. Returns True if acceptable."""
    if not result:
        return False
    for key, val in result.items():
        if isinstance(val, str) and len(val) > 500:
            return False
    important_keys = [k for k in result if k in ("quote", "question", "body", "word", "event_title", "challenge", "name_cn", "text")]
    for k in important_keys:
        if not result.get(k):
            return False
    return True


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
    llm_base_url: str | None = None,
    image_provider: str = "",
    image_model: str = "",
    mac: str = "",
    screen_w: int = 400,
    screen_h: int = 300,
    api_key: str = "",
    image_api_key: str = "",
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
    fallback = _get_fallback(content_cfg)
    mode_id = str(mode_def.get("mode_id") or "").upper()

    # Preview-only overrides: backend/api/index.py may inject per-mode overrides into
    # config["mode_overrides"][MODE_ID]. We allow these overrides to fill/replace
    # generated content fields (e.g. custom quote text, image_url for photo modes).
    override = {}
    try:
        cfg = config or {}
        mo = cfg.get("mode_overrides", {})
        if isinstance(mo, dict) and mode_id:
            candidate = mo.get(mode_id, {})
            if isinstance(candidate, dict):
                override = candidate
    except Exception:
        override = {}

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
        llm_base_url=llm_base_url,
        image_provider=image_provider,
        image_model=image_model,
        config=config or {},
        date_ctx=date_ctx or {},
        api_key=api_key,
        image_api_key=image_api_key,
    )

    # If override explicitly provides content fields, short-circuit LLM for llm_json.
    if ctype == "llm_json" and isinstance(override, dict) and override:
        quote = override.get("quote")
        author = override.get("author")
        if isinstance(quote, str) and quote.strip():
            result = dict(fallback)
            result["quote"] = quote.strip()
            if isinstance(author, str) and author.strip():
                result["author"] = author.strip()
            result = await _prefetch_images(result, mode_def)
            return result

    if ctype == "static":
        content = dict(content_cfg.get("static_data", fallback))
        if isinstance(override, dict) and override:
            # Merge overrides into static content (preview-only).
            for k, v in override.items():
                if k in {"city", "llm_provider", "llm_model", "image_provider", "image_model"}:
                    continue
                content[k] = v
        content = await _prefetch_images(content, mode_def)
        return content
    if ctype == "computed":
        content = await _generate_computed_content(mode_def, content_cfg, fallback, **common_args)
        if isinstance(override, dict) and override:
            for k, v in override.items():
                if k in {"city", "llm_provider", "llm_model", "image_provider", "image_model"}:
                    continue
                content[k] = v
        content = await _prefetch_images(content, mode_def)
        return content
    if ctype == "external_data":
        content = await _generate_external_data_content(mode_def, content_cfg, fallback, **common_args)
        if isinstance(override, dict) and override:
            for k, v in override.items():
                if k in {"city", "llm_provider", "llm_model", "image_provider", "image_model"}:
                    continue
                content[k] = v
        content = await _prefetch_images(content, mode_def)
        return content
    if ctype == "image_gen":
        content = await _generate_image_gen_content(mode_def, content_cfg, fallback, **common_args)
        if isinstance(override, dict) and override:
            for k, v in override.items():
                if k in {"city", "llm_provider", "llm_model", "image_provider", "image_model"}:
                    continue
                content[k] = v
        content = await _prefetch_images(content, mode_def)
        return content
    if ctype == "composite":
        content = await _generate_composite_content(mode_def, content_cfg, fallback, **common_args)
        if isinstance(override, dict) and override:
            for k, v in override.items():
                if k in {"city", "llm_provider", "llm_model", "image_provider", "image_model"}:
                    continue
                content[k] = v
        content = await _prefetch_images(content, mode_def)
        return content

    provider = llm_provider or DEFAULT_LLM_PROVIDER
    model = llm_model or DEFAULT_LLM_MODEL
    temperature = content_cfg.get("temperature", 0.8)

    context = _build_context_str(
        date_str, weather_str, festival, daily_word,
        upcoming_holiday, days_until_holiday,
    )
    base_prompt = content_cfg.get("prompt_template", "").replace("{context}", context)

    style = _build_style_instructions(character_tones, language, content_tone)
    if style:
        base_prompt += style

    # Hint for small screens: ask LLM to keep content shorter
    if screen_h < 200:
        base_prompt += "\n注意：内容将显示在极小屏幕上（296×128像素），所有文字请尽量简短。"

    mode_id = mode_def.get("mode_id", "CUSTOM")
    logger.info(f"[JSONContent] Generating content for {mode_id} via {provider}/{model}")

    # Load recent content hashes for dedup
    recent_hashes: list[str] = []
    dedup_hint = ""
    if mac and ctype in ("llm", "llm_json") and not DISABLE_DEDUP:
        try:
            from .stats_store import get_recent_content_hashes, get_recent_content_summaries
            recent_hashes = await get_recent_content_hashes(mac, mode_id, limit=20)
            summaries = await get_recent_content_summaries(mac, mode_id, limit=3)
            if summaries:
                dedup_hint = "\n请避免与以下近期内容重复：" + "；".join(summaries)
        except (OSError, TypeError, ValueError):
            logger.warning("[JSONContent] Failed to load dedup context for %s:%s", mac, mode_id, exc_info=True)

    for attempt in range(1 + DEDUP_MAX_RETRIES):
        prompt = base_prompt
        if attempt > 0 and dedup_hint:
            prompt += dedup_hint

        llm_ok = False
        api_key_invalid = False
        try:
            text = await _call_llm(provider, model, prompt, temperature=temperature, api_key=api_key, base_url=llm_base_url)
            llm_ok = True
        except (LLMKeyMissingError, httpx.HTTPError, HTTPStatusError, OpenAIError, OSError, TypeError, ValueError) as e:
            # 这里捕获所有 LLM 调用异常（包括 OpenAI/DeepSeek 的 BadRequestError 等），
            # 避免将 4xx/5xx 直接抛到上层导致 500，而是统一回退到 fallback 内容。
            logger.error(f"[JSONContent] LLM call failed for {mode_id}: {e}")
            if DISABLE_FALLBACK:
                result = {"text": f"[LLM_ERROR] {e}", "_is_fallback": True, "_llm_used": True, "_llm_ok": False}
                return _apply_post_process(result, content_cfg)
            # 检查是否是 API key 缺失或无效错误（401/403 等），用于给上游返回更明确的 api_key_invalid 标记
            if isinstance(e, LLMKeyMissingError):
                api_key_invalid = True
                logger.warning(f"[JSONContent] API key missing or invalid for {mode_id}: {e}")
            elif isinstance(e, HTTPStatusError):
                status_code = e.response.status_code if hasattr(e, "response") and e.response else None
                if status_code in (401, 403):
                    api_key_invalid = True
                    logger.warning(f"[JSONContent] API key invalid or expired for {mode_id}: HTTP {status_code}")
            elif isinstance(e, OpenAIError):
                # OpenAI/兼容 SDK 的错误可能包含状态码或错误码信息
                # 这里只把「鉴权相关」错误视为 API key 问题，避免把诸如 Model Not Exist 也误判为 key 失效。
                error_message = str(e).lower()
                error_code = getattr(e, "status_code", None) or getattr(e, "code", None)
                if (
                    error_code in (401, 403)
                    or "401" in error_message
                    or "403" in error_message
                    or "unauthorized" in error_message
                    or "auth" in error_message
                    or "api key" in error_message
                    or "apikey" in error_message
                ):
                    api_key_invalid = True
                    logger.warning(f"[JSONContent] API key invalid or expired for {mode_id}: {e}")
            fb = dict(fallback)
            # 标记为使用兜底内容，便于前端/统计判断
            fb["_is_fallback"] = True
            fb["_used_fallback"] = True
            # Mark LLM status for downstream billing/observability.
            fb["_llm_used"] = True
            fb["_llm_ok"] = False
            if api_key_invalid:
                fb["_api_key_invalid"] = True
            return fb

        if ctype == "llm":
            result = _parse_llm_output(text, content_cfg, fallback)
        elif ctype == "llm_json":
            result = _parse_llm_json_output(text, content_cfg, fallback)
        else:
            result = {"text": text}

        if not _validate_content_quality(result, content_cfg.get("output_schema")):
            logger.warning(f"[JSONContent] Quality check failed for {mode_id}, using fallback")
            if DISABLE_FALLBACK:
                result["_is_fallback"] = True
                result["_llm_used"] = True
                result["_llm_ok"] = llm_ok
                return _apply_post_process(result, content_cfg)
            fb = _apply_post_process(dict(fallback), content_cfg)
            fb["_is_fallback"] = True
            fb["_used_fallback"] = True
            fb["_llm_used"] = True
            fb["_llm_ok"] = llm_ok
            return fb

        content_hash = _compute_content_hash(result)
        if content_hash not in recent_hashes:
            break
        logger.info(f"[JSONContent] Dedup retry {attempt + 1} for {mode_id} (hash collision)")

    result = _apply_post_process(result, content_cfg)
    result = await _prefetch_images(result, mode_def)
    # Mark LLM status for downstream billing/observability.
    result["_llm_used"] = True
    result["_llm_ok"] = True
    return result


async def _generate_computed_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    provider = content_cfg.get("provider", "")
    if provider == "countdown":
        from .content import generate_countdown_content
        config = content_cfg.get("config", {})
        cfg = dict(config if config else (kwargs.get("config") or {}))
        mode_settings = (kwargs.get("config") or {}).get("mode_settings", {})
        if isinstance(mode_settings, dict):
            events = mode_settings.get("countdownEvents")
            if isinstance(events, list):
                cfg["countdownEvents"] = events
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
    if provider == "lifebar":
        import calendar
        from datetime import datetime
        now = datetime.now()
        date_ctx = kwargs.get("date_ctx", {}) or {}
        cfg = kwargs.get("config") or {}

        day_of_year = date_ctx.get("day_of_year") or now.timetuple().tm_yday
        days_in_year = date_ctx.get("days_in_year") or 365
        year_pct = round(day_of_year / days_in_year * 100, 1)

        days_in_month = calendar.monthrange(now.year, now.month)[1]
        month_pct = round(now.day / days_in_month * 100, 1)

        weekday_num = now.weekday() + 1
        week_pct = round(weekday_num / 7 * 100, 1)

        birth_year = int(cfg.get("birth_year", 0)) or 1995
        life_expect = int(cfg.get("life_expect", 0)) or 80
        age = now.year - birth_year
        life_pct = min(round(age / life_expect * 100, 1), 100.0)

        return {
            "year_pct": year_pct, "year_label": f"{now.year} 年已过",
            "month_pct": month_pct, "month_label": f"{now.month}月",
            "week_pct": week_pct, "week_label": "本周",
            "life_pct": life_pct, "life_label": "人生",
            "day_of_year": day_of_year, "days_in_year": days_in_year,
            "day": now.day, "days_in_month": days_in_month,
            "weekday_num": weekday_num, "week_total": 7,
            "age": age, "life_expect": life_expect,
        }

    if provider == "memo":
        config = kwargs.get("config") or {}
        mode_settings = config.get("mode_settings", {}) if isinstance(config.get("mode_settings", {}), dict) else {}
        memo_text = mode_settings.get("memo_text", "") if isinstance(mode_settings.get("memo_text", ""), str) else ""
        if not memo_text:
            memo_text = config.get("memo_text", "")
        memo_text = memo_text if isinstance(memo_text, str) else ""
        if not memo_text:
            memo_text = fallback.get("memo_text", "在配置页面设置你的便签内容")
        return {"memo_text": memo_text}

    if provider == "habit":
        config = kwargs.get("config") or {}
        mac = config.get("mac", "")
        try:
            from .stats_store import get_habit_status
            habits = await get_habit_status(mac)
            completed = sum(1 for h in habits if h.get("status") == "✓")
            total = len(habits) if habits else 7
            return {
                "habits": habits,
                "summary": f"本周已完成 {completed}/{total} 项习惯",
                "week_progress": completed,
                "week_total": total,
            }
        except (OSError, TypeError, ValueError):
            logger.warning("[JSONContent] Failed to load habit status for %s", mac, exc_info=True)
            return dict(fallback)

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
    api_key = kwargs.get("api_key")

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
            fb = dict(fallback)
            fb["_is_fallback"] = True
            fb["_used_fallback"] = True
            fb["_llm_used"] = False
            fb["_llm_ok"] = False
            return fb
        
        llm_failed = False
        if summarize:
            summarized_hn, summarized_ph = await summarize_briefing_content(
                hn_items, ph_item, llm_provider, llm_model, api_key=api_key
            )
            # 如果返回 None，说明 summarize 失败了
            if summarized_hn is None or summarized_ph is None:
                llm_failed = True
            else:
                hn_items = summarized_hn
                ph_item = summarized_ph
        
        insight = ""
        if include_insight:
            insight = await generate_briefing_insight(hn_items, ph_item, llm_provider, llm_model, api_key=api_key)
            # 如果返回 None，说明 insight 生成失败了
            if insight is None:
                llm_failed = True
                insight = ""
        
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
        
        # 标记 LLM 使用情况
        if summarize or include_insight:
            result["_llm_used"] = True
            if llm_failed:
                result["_llm_ok"] = False
                result["_used_fallback"] = True
                logger.warning(f"[JSONContent] BRIEFING LLM calls failed, marked as fallback")
            else:
                result["_llm_ok"] = True
        
        return result

    if provider == "weather_forecast":
        from .context import extract_location_settings, get_weather_forecast
        try:
            config = kwargs.get("config") or {}
            mode_settings = config.get("mode_settings", {}) if isinstance(config.get("mode_settings", {}), dict) else {}
            days = mode_settings.get("forecast_days", 4)
            if not isinstance(days, int):
                days = 4
            days = max(1, min(7, days))
            data = await get_weather_forecast(days=days, **extract_location_settings(config))
            if not data:
                return dict(fallback)
            if not data.get("today_temp") or data["today_temp"] == "--":
                return dict(fallback)
            merged = dict(fallback)
            merged.update(data)
            return merged
        except (httpx.HTTPError, TypeError, ValueError, JSONDecodeError) as e:
            logger.warning(f"[JSONContent] Failed to get weather forecast: {e}", exc_info=True)
            return dict(fallback)

    return dict(fallback)


async def _generate_image_gen_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    provider = content_cfg.get("provider", "")
    if provider == "text2image":
        from .content import generate_artwall_content
        mode_id = str(mode_def.get("mode_id", "") or "").upper()
        mode_display_name = str(mode_def.get("display_name", "") or "")
        mode_description = str(mode_def.get("description", "") or "")
        prompt_hint = str(content_cfg.get("prompt_hint", "") or "")
        prompt_template = str(content_cfg.get("prompt_template", "") or "")
        fallback_title = str(fallback.get("artwork_title", "") or "")
        api_key = kwargs.get("api_key")
        llm_provider = kwargs.get("llm_provider") or DEFAULT_LLM_PROVIDER
        llm_model = kwargs.get("llm_model") or DEFAULT_LLM_MODEL
        try:
            result = await generate_artwall_content(
                date_str=kwargs.get("date_str", ""),
                weather_str=kwargs.get("weather_str", ""),
                festival=kwargs.get("festival", ""),
                llm_provider=llm_provider,
                llm_model=llm_model,
                image_provider=kwargs.get("image_provider") or DEFAULT_IMAGE_PROVIDER,
                image_model=kwargs.get("image_model") or DEFAULT_IMAGE_MODEL,
                mode_display_name=mode_display_name,
                mode_description=mode_description,
                prompt_hint=prompt_hint,
                prompt_template=prompt_template,
                fallback_title=fallback_title,
                image_api_key=kwargs.get("image_api_key") or "",
                api_key=api_key,
            )
            # 仅当真正拿到图像地址时才使用生成结果；否则回退到 JSON 中的 fallback/fallback_pool
            if mode_id != "ARTWALL":
                result["artwork_title"] = ""
                result["description"] = ""
            if result.get("image_url"):
                # 成功生成图像
                result["_llm_used"] = True
                result["_llm_ok"] = True
                return result
            else:
                # 没有生成图像，使用 fallback
                logger.warning(f"[JSONContent] image_gen for {mode_id} returned no image_url, using fallback")
                fb = dict(fallback)
                fb["_llm_used"] = True
                fb["_llm_ok"] = False
                fb["_used_fallback"] = True
                return fb
        except Exception as e:
            logger.warning(f"[JSONContent] image_gen failed for {mode_id}: {e}", exc_info=True)
            fb = dict(fallback)
            fb["_llm_used"] = True
            fb["_llm_ok"] = False
            fb["_used_fallback"] = True
            return fb
    return dict(fallback)


async def _generate_composite_content(mode_def: dict, content_cfg: dict, fallback: dict, **kwargs) -> dict:
    steps = content_cfg.get("steps", [])
    result: dict[str, Any] = {}
    any_llm_used = False
    any_llm_failed = False
    
    for step in steps:
        try:
            step_mode_def = {
                "mode_id": mode_def.get("mode_id", "COMPOSITE"),
                "content": step,
            }
            part = await generate_json_mode_content(step_mode_def, **kwargs)
            if isinstance(part, dict):
                # 检查这个 step 是否使用了 LLM
                if part.get("_llm_used"):
                    any_llm_used = True
                    if not part.get("_llm_ok", True):
                        any_llm_failed = True
                # 移除内部标记，避免污染最终结果
                part_clean = {k: v for k, v in part.items() if not k.startswith("_")}
                result.update(part_clean)
        except (LLMKeyMissingError, httpx.HTTPError, OSError, TypeError, ValueError, JSONDecodeError) as e:
            logger.warning(f"[JSONContent] Step failed in composite mode {mode_def.get('mode_id', 'UNKNOWN')}: {e}", exc_info=True)
            any_llm_failed = True
            # Continue with next step instead of failing entirely
            continue
    
    if not result:
        fb = dict(fallback)
        if any_llm_used:
            fb["_llm_used"] = True
            fb["_llm_ok"] = False
            fb["_used_fallback"] = True
        return fb
    
    merged = dict(fallback)
    merged.update(result)
    
    # 设置 LLM 使用标记
    if any_llm_used:
        merged["_llm_used"] = True
        if any_llm_failed:
            merged["_llm_ok"] = False
            merged["_used_fallback"] = True
        else:
            merged["_llm_ok"] = True
    
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
