"""
测试 JSON 内容生成器
测试输出解析逻辑（不需要 LLM API 调用）
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.errors import LLMKeyMissingError
from core.json_content import (
    _parse_llm_output,
    _parse_text_split,
    _parse_json_output,
    _parse_llm_json_output,
    _apply_post_process,
    generate_json_mode_content,
)


def test_parse_text_split_basic():
    cfg = {
        "output_separator": "|",
        "output_fields": ["quote", "author"],
    }
    fallback = {"quote": "default", "author": "unknown"}

    result = _parse_text_split("行路难 | 李白", cfg, fallback)
    assert result["quote"] == "行路难"
    assert result["author"] == "李白"


def test_parse_text_split_missing_fields():
    cfg = {
        "output_separator": "|",
        "output_fields": ["quote", "author"],
    }
    fallback = {"quote": "default", "author": "佚名"}

    result = _parse_text_split("只有一段文本", cfg, fallback)
    assert result["quote"] == "只有一段文本"
    assert result["author"] == "佚名"


def test_parse_text_split_strips_quotes():
    cfg = {
        "output_separator": "|",
        "output_fields": ["quote", "author"],
    }
    fallback = {}

    result = _parse_text_split('"Hello World" | Author', cfg, fallback)
    assert result["quote"] == "Hello World"


def test_parse_json_output_basic():
    cfg = {
        "output_fields": ["title", "author"],
    }
    fallback = {"title": "默认", "author": "未知"}

    result = _parse_json_output('{"title": "静夜思", "author": "李白"}', cfg, fallback)
    assert result["title"] == "静夜思"
    assert result["author"] == "李白"


def test_parse_json_output_with_markdown_fence():
    cfg = {
        "output_fields": ["title", "note"],
    }
    fallback = {"title": "默认", "note": "无"}

    text = '```json\n{"title": "春晓", "note": "经典名篇"}\n```'
    result = _parse_json_output(text, cfg, fallback)
    assert result["title"] == "春晓"
    assert result["note"] == "经典名篇"


def test_parse_json_output_missing_fields_use_fallback():
    cfg = {
        "output_fields": ["a", "b", "c"],
    }
    fallback = {"a": "1", "b": "2", "c": "3"}

    result = _parse_json_output('{"a": "hello"}', cfg, fallback)
    assert result["a"] == "hello"
    assert result["b"] == "2"
    assert result["c"] == "3"


def test_parse_json_output_invalid_json_returns_fallback():
    cfg = {"output_fields": ["text"]}
    fallback = {"text": "默认内容"}

    result = _parse_json_output("not json at all {{{", cfg, fallback)
    assert result["text"] == "默认内容"


def test_parse_llm_json_output_with_schema():
    cfg = {
        "output_schema": {
            "workout_name": {"type": "string", "default": "默认训练"},
            "duration": {"type": "string", "default": "15分钟"},
            "exercises": {"type": "array", "default": []},
        },
    }
    fallback = {"workout_name": "fallback", "duration": "0", "exercises": []}

    text = '{"workout_name": "核心训练", "duration": "20分钟", "exercises": [{"name": "深蹲"}]}'
    result = _parse_llm_json_output(text, cfg, fallback)
    assert result["workout_name"] == "核心训练"
    assert result["duration"] == "20分钟"
    assert len(result["exercises"]) == 1


def test_parse_llm_json_output_uses_schema_defaults():
    cfg = {
        "output_schema": {
            "title": {"type": "string", "default": "默认标题"},
            "items": {"type": "array", "default": ["a", "b"]},
        },
    }
    fallback = {}

    text = '{"title": "自定义标题"}'
    result = _parse_llm_json_output(text, cfg, fallback)
    assert result["title"] == "自定义标题"
    assert result["items"] == ["a", "b"]


def test_parse_llm_json_output_invalid_returns_fallback():
    cfg = {"output_schema": {"x": {"type": "string", "default": ""}}}
    fallback = {"x": "fallback_value"}

    result = _parse_llm_json_output("broken json {{{", cfg, fallback)
    assert result["x"] == "fallback_value"


def test_parse_llm_output_raw():
    cfg = {
        "output_format": "raw",
        "output_fields": ["word"],
    }
    fallback = {"word": "静"}

    result = _parse_llm_output("悟", cfg, fallback)
    assert result["word"] == "悟"


def test_parse_llm_output_dispatches_text_split():
    cfg = {
        "output_format": "text_split",
        "output_separator": "|",
        "output_fields": ["a", "b"],
    }
    fallback = {"a": "", "b": ""}

    result = _parse_llm_output("hello|world", cfg, fallback)
    assert result["a"] == "hello"
    assert result["b"] == "world"


def test_parse_llm_output_dispatches_json():
    cfg = {
        "output_format": "json",
        "output_fields": ["name"],
    }
    fallback = {"name": "default"}

    result = _parse_llm_output('{"name": "test"}', cfg, fallback)
    assert result["name"] == "test"


def test_apply_post_process_first_char():
    cfg = {"post_process": {"word": "first_char"}}
    result = _apply_post_process({"word": "悟道"}, cfg)
    assert result["word"] == "悟"


def test_apply_post_process_first_char_empty():
    cfg = {"post_process": {"word": "first_char"}}
    result = _apply_post_process({"word": ""}, cfg)
    assert result["word"] == ""


def test_apply_post_process_strip_quotes():
    cfg = {"post_process": {"text": "strip_quotes"}}
    result = _apply_post_process({"text": '"Hello World"'}, cfg)
    assert result["text"] == "Hello World"


def test_apply_post_process_no_rules():
    cfg = {}
    result = _apply_post_process({"text": "unchanged"}, cfg)
    assert result["text"] == "unchanged"


def test_apply_post_process_skips_non_string():
    cfg = {"post_process": {"items": "first_char"}}
    result = _apply_post_process({"items": [1, 2, 3]}, cfg)
    assert result["items"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_llm_key_missing_returns_fallback():
    """当 LLM API key 缺失时，应返回 fallback 内容而非抛出异常"""
    mode_def = {
        "mode_id": "STOIC",
        "content": {
            "type": "llm_json",
            "prompt_template": "test {context}",
            "output_schema": {"quote": {"default": "fallback quote"}, "author": {"default": "fallback author"}},
            "fallback": {"quote": "fallback quote", "author": "fallback author"},
        },
        "layout": {"body": []},
    }
    with patch("core.json_content._call_llm", new_callable=AsyncMock, side_effect=LLMKeyMissingError("Missing API key")):
        result = await generate_json_mode_content(
            mode_def,
            date_str="2025-03-12",
            weather_str="晴 15°C",
        )
    assert "quote" in result
    assert "author" in result
    assert result["quote"] == "fallback quote"
    assert result["author"] == "fallback author"


@pytest.mark.asyncio
async def test_daily_first_attempt_includes_recent_history_dedup_hint():
    mode_def = {
        "mode_id": "DAILY",
        "content": {
            "type": "llm_json",
            "prompt_template": "test {context}",
            "output_schema": {
                "quote": {"default": "fallback quote"},
                "author": {"default": "fallback author"},
                "book_title": {"default": "fallback book"},
                "book_author": {"default": "fallback book author"},
                "book_desc": {"default": "fallback desc"},
                "tip": {"default": "fallback tip"},
                "season_text": {"default": "fallback season"},
            },
            "fallback": {
                "quote": "fallback quote",
                "author": "fallback author",
                "book_title": "fallback book",
                "book_author": "fallback book author",
                "book_desc": "fallback desc",
                "tip": "fallback tip",
                "season_text": "fallback season",
            },
        },
        "layout": {"body": []},
    }
    with (
        patch("core.json_content._call_llm", new_callable=AsyncMock) as mock_llm,
        patch("core.stats_store.get_recent_content_hashes", new_callable=AsyncMock) as mock_hashes,
        patch("core.stats_store.get_recent_content_summaries", new_callable=AsyncMock) as mock_summaries,
        patch("core.stats_store.get_content_history", new_callable=AsyncMock) as mock_history,
    ):
        mock_hashes.return_value = []
        mock_summaries.return_value = ["旧主题"]
        mock_history.return_value = [
            {
                "content": {
                    "quote": "知止而后有定",
                    "book_title": "《人间值得》",
                    "tip": "午睡20分钟最佳",
                    "season_text": "春寒料峭",
                }
            }
        ]
        mock_llm.return_value = (
            '{"quote":"新的语录","author":"作者","book_title":"《新书》","book_author":"某人 著",'
            '"book_desc":"新的描述","tip":"新的提示","season_text":"新的时令"}'
        )

        await generate_json_mode_content(
            mode_def,
            date_str="2025-03-12",
            weather_str="晴 15°C",
            language="zh",
            mac="AA:BB:CC:DD:EE:FF",
        )

    prompt = mock_llm.await_args.args[2]
    assert "请避免与这些最近的 DAILY 内容重复" in prompt
    assert "《人间值得》" in prompt
    assert "午睡20分钟最佳" in prompt


@pytest.mark.asyncio
async def test_weather_external_data_does_not_mark_llm_used():
    mode_def = {
        "mode_id": "WEATHER",
        "content": {
            "type": "external_data",
            "provider": "weather_forecast",
            "fallback": {
                "city": "",
                "today_temp": "--",
                "today_desc": "暂无数据",
                "today_code": -1,
                "today_low": "--",
                "today_high": "--",
                "today_range": "-- / --",
                "advice": "注意根据天气添减衣物",
                "forecast": [],
            },
        },
        "layout": {"body": []},
    }
    weather_payload = {
        "city": "上海",
        "today_temp": 16,
        "today_desc": "多云",
        "today_code": 2,
        "today_low": 12,
        "today_high": 19,
        "today_range": "12°C / 19°C",
        "advice": "早晚微凉，带件薄外套",
        "forecast": [],
    }

    with patch("core.json_content._generate_external_data_content", new_callable=AsyncMock) as mock_external:
        mock_external.return_value = weather_payload
        result = await generate_json_mode_content(
            mode_def,
            date_str="2025-03-12",
            weather_str="多云 16°C",
        )

    assert result["city"] == "上海"
    assert result["advice"] == "早晚微凉，带件薄外套"
    assert "_llm_used" not in result


@pytest.mark.asyncio
async def test_briefing_external_data_translates_with_deepl_for_zh():
    mode_def = {
        "mode_id": "BRIEFING",
        "content": {
            "type": "external_data",
            "provider": "briefing",
            "hn_limit": 2,
            "devto_limit": 2,
            "fallback": {
                "hn_items": [],
                "ph_item": {},
                "devto_items": [],
                "ph_name": "",
                "ph_tagline": "",
                "devto_title": "",
            },
        },
        "layout": {"body": []},
    }
    with (
        patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
        patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
        patch("core.content.fetch_devto_top", new_callable=AsyncMock) as mock_devto,
        patch("core.json_content._translate_with_aliyun_mt", new_callable=AsyncMock) as mock_translate,
    ):
        mock_hn.return_value = [{"title": "Project Glasswing: Securing critical software for the AI era", "score": 100}]
        mock_ph.return_value = {"name": "LookAway 2", "tagline": "Protect your eyes and improve your posture"}
        mock_devto.return_value = [
            {"title": "Component-based CSS", "score": 10},
            {"title": "Forem is slow, so I optimized it.", "score": 28},
        ]
        mock_translate.return_value = [
            "项目 Glasswing：保护 AI 时代关键软件",
            "组件化 CSS",
            "Forem 很慢，所以我把它优化了",
            "保护你的眼睛并改善坐姿",
        ]

        result = await generate_json_mode_content(
            mode_def,
            date_str="2025-03-12",
            weather_str="晴 15°C",
            language="zh",
        )

    assert result["hn_items"][0]["title"] == "项目 Glasswing：保护 AI 时代关键软件"
    assert result["devto_items"][0]["title"] == "组件化 CSS"
    assert result["devto_items"][1]["title"] == "Forem 很慢，所以我把它优化了"
    assert result["ph_name"] == "LookAway 2"
    assert result["ph_tagline"] == "保护你的眼睛并改善坐姿"
    assert result["devto_title"] == "组件化 CSS"


@pytest.mark.asyncio
async def test_briefing_external_data_keeps_original_without_deepl_key():
    mode_def = {
        "mode_id": "BRIEFING",
        "content": {
            "type": "external_data",
            "provider": "briefing",
            "fallback": {
                "hn_items": [],
                "ph_item": {},
                "devto_items": [],
                "ph_name": "",
                "ph_tagline": "",
                "devto_title": "",
            },
        },
        "layout": {"body": []},
    }
    with (
        patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
        patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
        patch("core.content.fetch_devto_top", new_callable=AsyncMock) as mock_devto,
        patch("core.json_content._translate_with_aliyun_mt", new_callable=AsyncMock) as mock_translate,
    ):
        mock_hn.return_value = [{"title": "Project Glasswing", "score": 100}]
        mock_ph.return_value = {"name": "LookAway 2", "tagline": "Protect your eyes"}
        mock_devto.return_value = [{"title": "Component-based CSS", "score": 10}]
        mock_translate.return_value = None

        result = await generate_json_mode_content(
            mode_def,
            date_str="2025-03-12",
            weather_str="晴 15°C",
            language="zh",
        )

    assert result["hn_items"][0]["title"] == "Project Glasswing"
    assert result["devto_title"] == "Component-based CSS"
    assert result["ph_tagline"] == "Protect your eyes"


@pytest.mark.asyncio
async def test_countdown_preview_override_keeps_message_and_event_in_sync():
    mode_def = {
        "mode_id": "COUNTDOWN",
        "content": {
            "type": "computed",
            "provider": "countdown",
            "fallback": {"events": []},
        },
        "layout": {"body": []},
    }

    result = await generate_json_mode_content(
        mode_def,
        config={
            "mode_overrides": {
                "COUNTDOWN": {
                    "events": [
                        {"name": "测试1", "date": "2099-01-01", "type": "countdown", "days": 123},
                    ]
                }
            },
            "content_tone": "positive",
        },
        date_str="2025-03-12",
        weather_str="晴 15°C",
    )

    assert result["events"][0]["name"] == "测试1"
    assert "测试1" in result["message"]


@pytest.mark.asyncio
async def test_habit_computed_content_ignores_stale_derived_override_fields():
    mode_def = {
        "mode_id": "HABIT",
        "content": {
            "type": "computed",
            "provider": "habit",
            "fallback": {"habits": [], "summary": "", "week_progress": 0, "week_total": 7},
        },
        "layout": {"body": []},
    }

    result = await generate_json_mode_content(
        mode_def,
        config={
            "mode_overrides": {
                "HABIT": {
                    "habitItems": [
                        {"name": "早起", "done": True},
                        {"name": "阅读", "done": False},
                    ],
                    "habits": [{"name": "脏数据", "done": False, "status": "○"}],
                    "summary": "旧 summary",
                    "week_progress": 99,
                    "week_total": 99,
                }
            }
        },
        date_str="2025-03-12",
        weather_str="晴 15°C",
        language="zh",
    )

    assert result["habits"] == [
        {"name": "早起", "done": True, "status": "●"},
        {"name": "阅读", "done": False, "status": "○"},
    ]
    assert "旧 summary" not in result["summary"]
    assert "今日已完成 1/2 项" in result["summary"]
    assert result["week_progress"] == 1
    assert result["week_total"] == 2


@pytest.mark.asyncio
async def test_almanac_api_uses_cache_db_across_calls(tmp_path):
    from core import db as db_mod
    from core.cache import init_cache_db

    cache_db = str(Path(tmp_path) / "almanac_cache.db")
    mode_def = {
        "mode_id": "ALMANAC",
        "content": {
            "type": "computed",
            "provider": "almanac_api",
            "fallback": {
                "solar_term": "",
                "lunar_date_display": "",
                "yi": "",
                "ji": "",
                "shenwei": "",
                "xingsu": "",
                "suisha": "",
                "chongsha": "",
                "health_tip": "默认提示",
            },
        },
        "layout": {"body": []},
    }
    raw_payload = {
        "jieqi": "谷雨",
        "fitness": "祭祀.沐浴.扫舍",
        "taboo": "嫁娶.安葬",
        "shenwei": "喜神东南 福神东北 财神正北",
        "lubarmonth": "三月",
        "lunarday": "初八",
        "xingsu": "角木蛟",
        "suisha": "东",
        "chongsha": "冲牛(辛丑)煞西",
        "pengzu": "辛不合酱",
    }

    await db_mod.close_all()
    try:
        with (
            patch.object(db_mod, "_CACHE_DB_PATH", cache_db),
            patch("core.cache._CACHE_DB_PATH", cache_db),
        ):
            await init_cache_db()
            with (
                patch("core.json_content._fetch_tianapi_almanac_payload", new_callable=AsyncMock) as mock_fetch,
                patch("core.json_content._generate_almanac_health_tip", new_callable=AsyncMock, return_value="宜早睡早起") as mock_tip,
            ):
                mock_fetch.return_value = raw_payload

                first = await generate_json_mode_content(
                    mode_def,
                    date_ctx={"year": 2026, "month": 4, "day": 13},
                    date_str="2026-04-13",
                    weather_str="晴 15°C",
                    language="zh",
                )
                second = await generate_json_mode_content(
                    mode_def,
                    date_ctx={"year": 2026, "month": 4, "day": 13},
                    date_str="2026-04-13",
                    weather_str="晴 15°C",
                    language="zh",
                )

            assert first["solar_term"] == "谷雨"
            assert first["health_tip"] == "宜早睡早起"
            assert second["solar_term"] == "谷雨"
            assert second["health_tip"] == "宜早睡早起"
            assert mock_fetch.await_count == 1
            assert mock_tip.await_count == 1
    finally:
        await db_mod.close_all()

