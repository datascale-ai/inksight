"""
测试 JSON 内容生成器
测试输出解析逻辑（不需要 LLM API 调用）
"""
import os
import sys

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


if __name__ == "__main__":
    test_parse_text_split_basic()
    test_parse_text_split_missing_fields()
    test_parse_text_split_strips_quotes()
    test_parse_json_output_basic()
    test_parse_json_output_with_markdown_fence()
    test_parse_json_output_missing_fields_use_fallback()
    test_parse_json_output_invalid_json_returns_fallback()
    test_parse_llm_json_output_with_schema()
    test_parse_llm_json_output_uses_schema_defaults()
    test_parse_llm_json_output_invalid_returns_fallback()
    test_parse_llm_output_raw()
    test_parse_llm_output_dispatches_text_split()
    test_parse_llm_output_dispatches_json()
    test_apply_post_process_first_char()
    test_apply_post_process_first_char_empty()
    test_apply_post_process_strip_quotes()
    test_apply_post_process_no_rules()
    test_apply_post_process_skips_non_string()
    print("✓ All JSON content tests passed")
