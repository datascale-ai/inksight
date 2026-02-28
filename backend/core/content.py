from __future__ import annotations

import datetime
import json
import os
import re
import traceback
import xml.etree.ElementTree as ET

import logging
import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .errors import LLMKeyMissingError

logger = logging.getLogger(__name__)

try:
    import dashscope
    from dashscope import MultiModalConversation
except ImportError:
    dashscope = None
    MultiModalConversation = None

# LLM Provider configurations
LLM_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": {"deepseek-chat": {"name": "DeepSeek Chat", "max_tokens": 1024}},
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": {
            "qwen-max": {"name": "通义千问 Max", "max_tokens": 1024},
            "qwen-plus": {"name": "通义千问 Plus", "max_tokens": 1024},
            "qwen-turbo": {"name": "通义千问 Turbo", "max_tokens": 1024},
            "deepseek-v3": {"name": "DeepSeek V3", "max_tokens": 1024},
            "kimi-2.5": {"name": "Kimi 2.5", "max_tokens": 1024},
            "glm-4-plus": {"name": "智谱 GLM-4 Plus", "max_tokens": 1024},
        },
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": {
            "moonshot-v1-8k": {"name": "Kimi K1.5", "max_tokens": 1024},
            "moonshot-v1-32k": {"name": "Kimi K1.5 32K", "max_tokens": 1024},
            "kimi-k2-turbo-preview": {"name": "Kimi K2 Turbo", "max_tokens": 1024},
        },
    },
}

PROMPTS = {
    "DAILY": (
        "你是一位博学的每日推荐助手。根据以下环境信息，生成一份每日推荐内容，用 JSON 格式输出，包含：\n"
        "1. quote: 一句语录（中文，20字以内，来源不限：哲学、文学、科学、历史、电影等均可）\n"
        "2. author: 语录作者\n"
        "3. book_title: 推荐一本书（书名用书名号，领域不限，每次推荐不同的书）\n"
        '4. book_author: 书的作者 + " 著"\n'
        "5. book_desc: 一句话描述这本书（25字以内）\n"
        "6. tip: 一条有趣的冷知识或实用小贴士（30字以内，话题不限）\n"
        "7. season_text: 当前节气或季节的一句话描述（10字以内）\n"
        "要求：内容丰富多样，每次推荐不同的内容，避免重复。只输出 JSON，不要其他内容。\n"
        "环境：{context}"
    ),
}


# ── Shared helpers ───────────────────────────────────────────


def _clean_json_response(text: str) -> str:
    """Remove markdown code fences and extract JSON from LLM responses."""
    cleaned = text.strip()
    # Remove markdown code fences (```json, ```JSON, ``` etc.)
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        cleaned = cleaned.rsplit("```", 1)[0]
    # Try to extract a JSON object if surrounded by other text
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        cleaned = match.group(0)
    return cleaned.strip()


def _build_context_str(
    date_str: str,
    weather_str: str,
    festival: str = "",
    daily_word: str = "",
    upcoming_holiday: str = "",
    days_until: int = 0,
) -> str:
    parts = [f"日期: {date_str}", f"天气: {weather_str}"]
    if festival:
        parts.append(f"节日: {festival}")
    if upcoming_holiday and days_until > 0:
        parts.append(f"{days_until}天后是{upcoming_holiday}")
    if daily_word:
        parts.append(f"每日一词: {daily_word}")
    return ", ".join(parts)


def _build_style_instructions(
    character_tones: list[str] | None, language: str | None, content_tone: str | None
) -> str:
    parts = []

    if character_tones:
        # Defense in depth: strip any prompt-like patterns even if schema missed them
        safe_tones = [t for t in character_tones if len(t) <= 20 and "\n" not in t]
        if safe_tones:
            names = "、".join(safe_tones)
            parts.append(f"请模仿「{names}」的说话风格和语气来表达")

    lang_map = {"zh": "中文", "en": "英文", "mixed": "中英混合"}
    if language and language != "zh":
        parts.append(f"请使用{lang_map.get(language, '中文')}为主要语言")

    tone_map = {
        "positive": "积极鼓励、温暖向上",
        "neutral": "中性克制、理性平和",
        "deep": "深沉内省、富有哲理",
        "humor": "轻松幽默、诙谐有趣",
    }
    if content_tone and content_tone != "neutral":
        parts.append(f"整体调性要{tone_map.get(content_tone, '中性克制')}")

    if not parts:
        return ""
    return "\n额外风格要求：" + "；".join(parts) + "。"


def _get_client(
    provider: str = "deepseek", model: str = "deepseek-chat"
) -> tuple[AsyncOpenAI, int]:
    """Get OpenAI client for specified provider and return max_tokens"""
    api_key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "aliyun": "DASHSCOPE_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
    }

    env_key = api_key_map.get(provider, "DEEPSEEK_API_KEY")
    api_key = os.getenv(env_key, "")

    if not api_key or api_key.startswith("sk-your-"):
        raise LLMKeyMissingError(
            f"Missing or invalid API key for {provider}. Please set {env_key} in .env file."
        )

    config = LLM_CONFIGS.get(provider, LLM_CONFIGS["deepseek"])
    base_url = config["base_url"]
    model_config = config["models"].get(model, {"max_tokens": 120})
    max_tokens = model_config["max_tokens"]

    return AsyncOpenAI(api_key=api_key, base_url=base_url), max_tokens


class LLMClient:
    """Unified LLM client with retry, timeout, and logging."""

    def __init__(self, provider: str = "deepseek", model: str = "deepseek-chat"):
        self.provider = provider
        self.model = model
        self._client, self._max_tokens = _get_client(provider, model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            httpx.ConnectError,
            httpx.ReadTimeout,
        )),
        before_sleep=lambda rs: logger.warning(
            f"[LLM] Retry {rs.attempt_number}/3 after {type(rs.outcome.exception()).__name__}..."
        ),
        reraise=True,
    )
    async def call(
        self, prompt: str, temperature: float = 0.8, max_tokens: int | None = None,
    ) -> str:
        """Call the LLM with retry logic. Returns response text."""
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content.strip()
        finish_reason = response.choices[0].finish_reason
        usage = response.usage
        logger.info(
            f"[LLM] {self.provider}/{self.model} tokens={usage.total_tokens}, finish={finish_reason}"
        )
        if finish_reason == "length":
            logger.warning("[LLM] Content truncated due to max_tokens limit")
        return text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((
        ConnectionError,
        TimeoutError,
        httpx.ConnectError,
        httpx.ReadTimeout,
    )),
    before_sleep=lambda rs: logger.warning(
        f"[LLM] Retry {rs.attempt_number}/3 after {type(rs.outcome.exception()).__name__}..."
    ),
    reraise=True,
)
async def _call_llm(
    provider: str,
    model: str,
    prompt: str,
    temperature: float = 0.8,
    max_tokens: int | None = None,
) -> str:
    """Unified LLM call: create client, call API, return response text.

    Retries up to 3 times with exponential backoff for transient errors.
    Raises ValueError when the API key is missing (no retry).
    """
    client, default_max_tokens = _get_client(provider, model)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens or default_max_tokens,
        temperature=temperature,
    )
    text = response.choices[0].message.content.strip()

    finish_reason = response.choices[0].finish_reason
    usage = response.usage
    logger.info(
        f"[LLM] {provider}/{model} tokens={usage.total_tokens}, finish={finish_reason}"
    )
    if finish_reason == "length":
        logger.warning("[LLM] Content truncated due to max_tokens limit")

    return text


# ── Core content generation ──────────────────────────────────


async def generate_content(
    persona: str,
    date_str: str,
    weather_str: str,
    character_tones: list[str] | None = None,
    language: str | None = None,
    content_tone: str | None = None,
    festival: str = "",
    daily_word: str = "",
    upcoming_holiday: str = "",
    days_until_holiday: int = 0,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
) -> dict:
    context = _build_context_str(
        date_str,
        weather_str,
        festival,
        daily_word,
        upcoming_holiday,
        days_until_holiday,
    )
    prompt_template = PROMPTS.get(persona)
    if not prompt_template:
        logger.warning(f"[LLM] No prompt template for persona={persona}, returning fallback")
        return _fallback_content(persona)
    prompt = prompt_template.format(context=context)

    style = _build_style_instructions(character_tones, language, content_tone)
    if style:
        prompt += style

    logger.info(f"[LLM] Calling {llm_provider}/{llm_model} for persona={persona}")

    try:
        text = await _call_llm(llm_provider, llm_model, prompt, temperature=0.8)
    except ValueError as e:
        logger.error(f"[LLM] ✗ FAILED - ValueError: {e}")
        return _fallback_content(persona)
    except Exception as e:
        logger.error(f"[LLM] ✗ FAILED - {type(e).__name__}: {e}")
        return _fallback_content(persona)

    if persona == "DAILY":
        try:
            cleaned = _clean_json_response(text)
            data = json.loads(cleaned)
            return {
                "quote": data.get("quote", ""),
                "author": data.get("author", ""),
                "book_title": data.get("book_title", ""),
                "book_author": data.get("book_author", ""),
                "book_desc": data.get("book_desc", ""),
                "tip": data.get("tip", ""),
                "season_text": data.get("season_text", ""),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[LLM] ✗ FAILED to parse DAILY JSON: {e}")
            logger.info(f"[LLM] Raw response: {text[:200]}...")
            return _fallback_content("DAILY")

    return {"quote": text, "author": ""}


def _fallback_content(persona: str) -> dict:
    """Fallback content for Python builtin modes when LLM calls fail.

    JSON-defined modes (STOIC, ROAST, ZEN, FITNESS, POETRY) have their own
    fallback data in their JSON definitions — see core/modes/builtin/*.json.
    """
    if persona == "DAILY":
        return {
            "quote": "阻碍行动的障碍，本身就是行动的路。",
            "author": "马可·奥勒留",
            "book_title": "《沉思录》",
            "book_author": "马可·奥勒留 著",
            "book_desc": "罗马帝王的自省笔记，斯多葛哲学的经典之作。",
            "tip": "冬季干燥，记得多喝水，保持室内适当湿度。",
            "season_text": "立春已过，万物生长。",
        }
    if persona == "BRIEFING":
        return {
            "hn_items": [
                {"title": "Hacker News API 暂时不可用", "score": 0},
                {"title": "请稍后重试", "score": 0},
                {"title": "或检查网络连接", "score": 0},
            ],
            "ph_item": {"name": "Product Hunt", "tagline": "数据获取失败"},
            "v2ex_items": [],
            "insight": "今日科技动态暂时无法获取，请稍后刷新。",
        }
    if persona == "COUNTDOWN":
        return {"events": []}
    return {"quote": "...", "author": ""}


# ── Hacker News & Product Hunt ───────────────────────────────


async def fetch_hn_top_stories(limit: int = 3) -> list[dict]:
    """获取 Hacker News 热榜 Top N（并发请求各 story）"""
    import asyncio as _asyncio

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            if resp.status_code != 200:
                logger.error(f"[HN] Failed to fetch top stories: {resp.status_code}")
                return []

            story_ids = resp.json()[:limit]

            async def _fetch_one(sid: int) -> dict | None:
                r = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                )
                if r.status_code == 200:
                    s = r.json()
                    return {
                        "title": s.get("title", "No title"),
                        "score": s.get("score", 0),
                        "url": s.get("url", ""),
                    }
                return None

            results = await _asyncio.gather(*[_fetch_one(sid) for sid in story_ids])
            stories = [s for s in results if s is not None]

            logger.info(f"[HN] Fetched {len(stories)} stories (concurrent)")
            return stories

    except Exception as e:
        logger.error(f"[HN] Error: {e}")
        return []


async def fetch_ph_top_product() -> dict:
    """获取 Product Hunt 今日 #1 产品（通过 RSS）"""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get("https://www.producthunt.com/feed")
            if resp.status_code != 200:
                logger.error(f"[PH] Failed to fetch RSS: {resp.status_code}")
                return {}

            root = ET.fromstring(resp.content)

            namespaces = {
                "atom": "http://www.w3.org/2005/Atom",
                "media": "http://search.yahoo.com/mrss/",
            }

            items = (
                root.findall(".//item")
                or root.findall(".//entry", namespaces)
                or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            )

            if not items:
                logger.warning(f"[PH] No items found in RSS. Root tag: {root.tag}")
                return {}

            first_item = items[0]

            title = first_item.find("title") or first_item.find(
                "{http://www.w3.org/2005/Atom}title"
            )
            description = (
                first_item.find("description")
                or first_item.find("summary")
                or first_item.find("{http://www.w3.org/2005/Atom}summary")
                or first_item.find("content")
                or first_item.find("{http://www.w3.org/2005/Atom}content")
            )

            tagline_text = ""
            if description is not None and description.text:
                tagline_text = re.sub(r"<[^>]+>", "", description.text).strip()
                tagline_text = tagline_text[:100]

            product = {
                "name": title.text if title is not None else "Unknown Product",
                "tagline": tagline_text,
            }

            logger.info(f"[PH] Fetched product: {product['name']}")
            return product

    except Exception as e:
        logger.exception("[PH] Error fetching Product Hunt product")
        return {}


# ── V2EX ─────────────────────────────────────────────────────


async def fetch_v2ex_hot(limit: int = 3) -> list[dict]:
    """获取 V2EX 热门话题"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://www.v2ex.com/api/topics/hot.json")
            if resp.status_code == 200:
                topics = resp.json()[:limit]
                return [
                    {
                        "title": t.get("title", ""),
                        "node": t.get("node", {}).get("title", ""),
                    }
                    for t in topics
                ]
            logger.error(f"[V2EX] Failed to fetch hot topics: {resp.status_code}")
    except Exception as e:
        logger.error(f"[V2EX] Error: {e}")
    return []


# ── Briefing mode ────────────────────────────────────────────


async def generate_briefing_insight(
    hn_stories: list[dict],
    ph_product: dict,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
) -> str:
    """使用 LLM 生成行业洞察"""
    hn_summary = "\n".join(
        [f"- {s['title']} ({s['score']} points)" for s in hn_stories[:3]]
    )
    ph_summary = f"Product Hunt #1: {ph_product.get('name', 'N/A')}"

    prompt = f"""你是一位科技行业分析师。根据今日 Hacker News 热榜和 Product Hunt 新品，生成一句简短的行业洞察（30字以内）。

Hacker News Top 3:
{hn_summary}

{ph_summary}

要求：
1. 只输出洞察本身，不要前缀或引号
2. 聚焦技术趋势或行业动态
3. 语言简洁有力，适合晨间阅读"""

    try:
        insight = await _call_llm(llm_provider, llm_model, prompt, temperature=0.7)
        logger.info(f"[BRIEFING] Generated insight: {insight[:50]}...")
        return insight
    except Exception as e:
        logger.error(f"[BRIEFING] Failed to generate insight: {e}")
        return "今日科技圈依然精彩，开发者们在不断探索新的可能性。"


async def summarize_briefing_content(
    stories: list[dict],
    ph_product: dict,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
) -> tuple[list[dict], dict]:
    """使用单次 LLM 调用批量总结 HN stories 和 PH tagline（原先需 3-4 次调用）"""
    try:
        titles_to_summarize = []
        for i, story in enumerate(stories):
            title = story.get("title", "")
            if title and len(title) >= 20:
                titles_to_summarize.append((i, title))

        ph_tagline = ""
        ph_name = ""
        if ph_product and ph_product.get("tagline") and len(ph_product["tagline"]) > 30:
            ph_name = ph_product.get("name", "")
            ph_tagline = ph_product["tagline"]

        # Build a single batch prompt for all summaries
        if not titles_to_summarize and not ph_tagline:
            return stories, ph_product

        prompt_parts = [
            "# Role",
            "你是一个科技内容编辑，擅长用精练中文总结技术新闻。",
            "",
            "# Tasks",
            "请按顺序完成以下总结任务，用 JSON 格式输出结果。",
            "",
        ]

        if titles_to_summarize:
            prompt_parts.append("## HN Stories 总结")
            prompt_parts.append("为每条标题生成 30 字以内的中文简介：")
            for idx, (_, title) in enumerate(titles_to_summarize):
                prompt_parts.append(f"  {idx + 1}. {title}")
            prompt_parts.append("")

        if ph_tagline:
            prompt_parts.append("## Product Hunt 产品总结")
            prompt_parts.append(f"产品名称：{ph_name}")
            prompt_parts.append(f"英文Slogan：{ph_tagline}")
            prompt_parts.append("重写为 30 字以内的中文介绍。")
            prompt_parts.append("")

        prompt_parts.append("# Output (仅输出 JSON)")
        prompt_parts.append('{')
        if titles_to_summarize:
            prompt_parts.append('  "hn_summaries": ["简介1", "简介2", ...],')
        if ph_tagline:
            prompt_parts.append('  "ph_summary": "中文介绍"')
        prompt_parts.append('}')

        batch_prompt = "\n".join(prompt_parts)

        text = await _call_llm(
            llm_provider, llm_model, batch_prompt,
            max_tokens=300, temperature=0.5,
        )
        cleaned = _clean_json_response(text)
        data = json.loads(cleaned)

        # Apply HN summaries
        hn_summaries = data.get("hn_summaries", [])
        summarized_stories = list(stories)
        for summary_idx, (story_idx, _) in enumerate(titles_to_summarize):
            if summary_idx < len(hn_summaries):
                summary = str(hn_summaries[summary_idx]).strip('"').strip("「」")
                summarized_stories[story_idx] = {**stories[story_idx], "summary": summary}

        logger.info(f"[BRIEFING] Batch-summarized {len(titles_to_summarize)} HN stories in 1 LLM call")

        # Apply PH summary
        summarized_ph = ph_product.copy() if ph_product else {}
        if ph_tagline and data.get("ph_summary"):
            summary = str(data["ph_summary"]).strip('"').strip("「」")
            summarized_ph["tagline_original"] = ph_tagline
            summarized_ph["tagline"] = summary
            logger.info("[BRIEFING] Batch-summarized PH tagline")

        return summarized_stories, summarized_ph

    except Exception as e:
        logger.error(f"[BRIEFING] Batch summarize failed, returning originals: {e}")
        return stories, ph_product


async def generate_briefing_content(
    ctx=None,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
    summarize: bool = True,
) -> dict:
    """生成 BRIEFING 模式的完整内容"""
    if ctx is not None:
        llm_provider = ctx.llm_provider
        llm_model = ctx.llm_model
    import asyncio as _asyncio

    logger.info("[BRIEFING] Starting content generation...")

    # Fetch HN, PH, and V2EX concurrently
    hn_stories, ph_product, v2ex_topics = await _asyncio.gather(
        fetch_hn_top_stories(limit=2),
        fetch_ph_top_product(),
        fetch_v2ex_hot(limit=1),
    )

    if not hn_stories and not ph_product and not v2ex_topics:
        logger.error("[BRIEFING] All data sources failed, using fallback")
        return _fallback_content("BRIEFING")

    if summarize:
        (hn_stories, ph_product), insight = await _asyncio.gather(
            summarize_briefing_content(
                hn_stories, ph_product, llm_provider, llm_model
            ),
            generate_briefing_insight(
                hn_stories, ph_product, llm_provider, llm_model
            ),
        )
    else:
        insight = await generate_briefing_insight(
            hn_stories, ph_product, llm_provider, llm_model
        )

    result = {
        "hn_items": hn_stories if hn_stories else [{"title": "数据获取失败", "score": 0}],
        "ph_item": ph_product if ph_product else {"name": "N/A", "tagline": ""},
        "v2ex_items": v2ex_topics if v2ex_topics else [],
        "insight": insight,
    }

    logger.info("[BRIEFING] Content generation complete")
    return result


# ── Countdown mode ───────────────────────────────────────────


async def generate_countdown_content(
    ctx=None,
    config: dict | None = None,
    **kwargs,
) -> dict:
    """生成 COUNTDOWN 模式的内容 — 纯日期计算，无需 LLM"""
    if ctx is not None:
        config = ctx.config
    logger.info("[COUNTDOWN] Computing countdown events...")

    cfg = config or {}
    raw_events = cfg.get("countdownEvents", [])

    today = datetime.date.today()
    computed_events = []

    for evt in raw_events:
        name = evt.get("name", "")
        date_str = evt.get("date", "")
        evt_type = evt.get("type", "countdown")

        if not name or not date_str:
            continue

        try:
            target = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue

        delta = (target - today).days

        if evt_type == "countdown" and delta < 0:
            continue
        if evt_type == "countup":
            delta = abs(delta)

        computed_events.append({
            "name": name,
            "date": date_str,
            "type": evt_type,
            "days": abs(delta) if evt_type == "countdown" else delta,
        })

    # Sort: countdown events by nearest first, then countup
    computed_events.sort(key=lambda e: (0 if e["type"] == "countdown" else 1, e["days"]))

    if not computed_events:
        # Provide default countdown events
        new_year = datetime.date(today.year + 1, 1, 1)
        days_to_ny = (new_year - today).days
        computed_events = [
            {"name": "元旦", "date": str(new_year), "type": "countdown", "days": days_to_ny},
        ]

    logger.info(f"[COUNTDOWN] Computed {len(computed_events)} events")
    return {"events": computed_events}


# ── Artwall mode ─────────────────────────────────────────────


async def generate_artwall_content(
    ctx=None,
    date_str: str = "",
    weather_str: str = "",
    festival: str = "",
    llm_provider: str = "aliyun",
    llm_model: str = "qwen-image-max",
) -> dict:
    """生成 ARTWALL 模式的内容 - 使用文生图模型"""
    if ctx is not None:
        date_str = ctx.date_str
        weather_str = ctx.weather_str
        festival = ctx.festival
        llm_provider = ctx.llm_provider
        llm_model = ctx.llm_model
    logger.info("[ARTWALL] Starting content generation...")

    context_parts = []
    if weather_str:
        context_parts.append(f"天气：{weather_str}")
    if festival:
        context_parts.append(f"节日：{festival}")
    if date_str:
        context_parts.append(f"日期：{date_str}")

    context = "，".join(context_parts) if context_parts else "今日"

    title_prompt = f"""根据以下信息，生成一个富有诗意和意境的艺术作品标题（8字以内）：

{context}

要求：
1. 富有诗意和意境，如山水画的题名
2. 8字以内
3. 意境深远，留有想象空间
4. 只输出标题，不要其他内容"""

    artwork_title = "墨韵天成"
    try:
        title_text = await _call_llm("deepseek", "deepseek-chat", title_prompt)
        artwork_title = title_text.strip('"').strip("「」") or artwork_title
        logger.info(f"[ARTWALL] Generated title: {artwork_title}")
    except Exception as e:
        # 标题模型失败时继续执行文生图，避免整条 ARTWALL 流程直接降级为空图
        logger.warning(f"[ARTWALL] Title generation failed, use fallback title: {e}")

    try:
        image_prompt = f"""
绘画风格：极简黑白线条艺术，现代矢量简笔画，墨水屏二值化风格。
核心要求：线条干净流畅肯定，禁止任何水墨晕染、毛笔笔触、焦墨枯笔。
强制约束：画面中绝对禁止出现任何汉字、英文、印章或签名，纯图像表达。
构图：极度空灵，大量留白(Negative Space)，用最少的线条表达最多的含义，马一角构图。
背景：纯净绝对白色(#FFFFFF)，无纸张纹理。
意境：宁静、孤独、禅意(Zen minimalism)。
画面内容：用几根简单的黑色线条勾勒出{artwork_title}的神韵。环境：{context}（极简暗示或留白）。
"""

        logger.info(f"[ARTWALL] Image prompt: {image_prompt[:100]}...")

        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key or api_key.startswith("sk-your-"):
            logger.warning("[ARTWALL] No valid DASHSCOPE_API_KEY, using fallback")
            return {
                "artwork_title": artwork_title,
                "image_url": "",
                "description": f"基于{context}创作的黑白版画",
                "prompt": image_prompt,
            }

        if MultiModalConversation is None:
            logger.warning("[ARTWALL] dashscope not installed, using fallback")
            return {
                "artwork_title": artwork_title,
                "image_url": "",
                "description": f"基于{context}创作的黑白版画",
                "prompt": image_prompt,
            }

        import asyncio as _asyncio

        dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

        messages = [{"role": "user", "content": [{"text": image_prompt}]}]

        # Wrap synchronous DashScope SDK call to avoid blocking the event loop
        response = await _asyncio.to_thread(
            MultiModalConversation.call,
            api_key=api_key,
            model="qwen-image-max",
            messages=messages,
            result_format="message",
            stream=False,
            watermark=False,
            prompt_extend=True,
            negative_prompt="低分辨率，彩色，复杂细节，文字，标签，过度装饰，花哨元素，浓墨重彩，密集笔触",
            size="512*512",
        )

        if response.status_code == 200:
            image_url = response.output.choices[0].message.content[0].get("image", "")
            logger.info(f"[ARTWALL] Image generated: {image_url[:50]}...")

            return {
                "artwork_title": artwork_title,
                "image_url": image_url,
                "description": f"基于{context}创作的黑白版画",
                "prompt": image_prompt,
                "model_name": "qwen-image-max",
            }
        else:
            logger.error(f"[ARTWALL] Image generation failed: {response.status_code}")
            logger.error(f"Error: {response.code} - {response.message}")
            return {
                "artwork_title": artwork_title,
                "image_url": "",
                "description": f"基于{context}创作的黑白版画",
                "prompt": image_prompt,
            }

    except Exception as e:
        logger.exception("[ARTWALL] Failed to generate artwall content")
        return {
            "artwork_title": artwork_title,
            "image_url": "",
            "description": "今日艺术作品",
            "prompt": "",
        }


# ── Recipe mode ──────────────────────────────────────────────


async def generate_recipe_content(
    ctx=None,
    llm_provider: str = "deepseek",
    llm_model: str = "deepseek-chat",
) -> dict:
    """生成 RECIPE 模式的内容 - 早中晚三餐方案"""
    if ctx is not None:
        llm_provider = ctx.llm_provider
        llm_model = ctx.llm_model
    logger.info("[RECIPE] Starting content generation...")

    month = datetime.datetime.now().month

    season_map = {
        1: "大寒·一月",
        2: "立春·二月",
        3: "惊蛰·三月",
        4: "清明·四月",
        5: "立夏·五月",
        6: "芒种·六月",
        7: "小暑·七月",
        8: "立秋·八月",
        9: "白露·九月",
        10: "寒露·十月",
        11: "立冬·十一月",
        12: "大雪·十二月",
    }

    prompt = f"""你是一位营养师。根据当前月份（{month}月），推荐一套荤素搭配的早中晚三餐方案。

要求：
1. 早餐：简单清淡，如粥+蛋+小菜
2. 午餐：1荤+1素+主食
3. 晚餐：1荤+1素+汤/主食
4. 营养均衡标注（如：蛋白质✓ 膳食纤维✓ 维生素C✓）

用 JSON 格式输出：
{{
  "breakfast": "早餐内容（如：小米南瓜粥·水煮蛋·凉拌菠菜）",
  "lunch": {{
    "meat": "荤菜名",
    "veg": "素菜名",
    "staple": "主食名"
  }},
  "dinner": {{
    "meat": "荤菜名",
    "veg": "素菜名",
    "staple": "汤/主食名"
  }},
  "nutrition": "营养标注（如：蛋白质✓ 膳食纤维✓ 维生素C✓ 铁✓）"
}}

只输出 JSON，不要其他内容。"""

    try:
        text = await _call_llm(llm_provider, llm_model, prompt)
        cleaned = _clean_json_response(text)
        data = json.loads(cleaned)
        logger.info("[RECIPE] Generated meal plan")

        return {
            "season": season_map.get(month, f"{month}月"),
            "breakfast": data.get("breakfast", "燕麦牛奶粥·茶叶蛋·凉拌黑木耳"),
            "lunch": data.get(
                "lunch",
                {"meat": "番茄炖牛腩", "veg": "清炒芥兰", "staple": "白米饭"},
            ),
            "dinner": data.get(
                "dinner",
                {"meat": "清蒸鲈鱼", "veg": "蒜蓉西兰花", "staple": "紫菜蛋花汤"},
            ),
            "nutrition": data.get("nutrition", "蛋白质✓ 膳食纤维✓ 维生素C✓ 铁✓"),
        }

    except Exception as e:
        logger.exception("[RECIPE] Failed to generate recipe content")
        return {
            "season": season_map.get(month, f"{month}月"),
            "breakfast": "燕麦牛奶粥·茶叶蛋·凉拌黑木耳",
            "lunch": {"meat": "番茄炖牛腩", "veg": "清炒芥兰", "staple": "白米饭"},
            "dinner": {"meat": "清蒸鲈鱼", "veg": "蒜蓉西兰花", "staple": "紫菜蛋花汤"},
            "nutrition": "蛋白质✓ 膳食纤维✓ 维生素C✓ 铁✓",
        }


