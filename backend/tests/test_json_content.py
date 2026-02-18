"""
测试 JSON 内容生成器
测试输出解析逻辑（不需要 LLM API 调用）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.json_content import (
    _parse_llm_output,
    _parse_text_split,
    _parse_json_output,
    _parse_llm_json_output,
    _apply_post_process,
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
