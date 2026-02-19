"""
测试 JSON 渲染引擎
验证各种布局原语能正确渲染到 1-bit e-ink 图像
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from core.json_renderer import render_json_mode, RenderContext
from core.config import SCREEN_WIDTH as SCREEN_W, SCREEN_HEIGHT as SCREEN_H


def _make_mode_def(body_blocks, content_type="static", footer=None):
    return {
        "mode_id": "TEST",
        "display_name": "Test",
        "content": {"type": content_type},
        "layout": {
            "status_bar": {"line_width": 1, "dashed": False},
            "body": body_blocks,
            "footer": footer or {"label": "TEST", "attribution_template": ""},
        },
    }


def test_render_produces_correct_size_image():
    mode_def = _make_mode_def([
        {"type": "centered_text", "field": "text", "font_size": 16, "vertical_center": True}
    ])
    content = {"text": "Hello World"}
    img = render_json_mode(
        mode_def, content,
        date_str="1月1日", weather_str="晴 20°C", battery_pct=85,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (SCREEN_W, SCREEN_H)
    assert img.mode == "1"


def test_render_centered_text():
    mode_def = _make_mode_def([
        {"type": "centered_text", "field": "quote", "font_size": 14, "vertical_center": True}
    ])
    content = {"quote": "测试居中文本"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="多云 15°C", battery_pct=90,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_text_block():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 20},
        {"type": "text", "field": "title", "font_size": 16, "align": "center"},
        {"type": "text", "template": "作者: {author}", "font_size": 12, "align": "center"},
    ])
    content = {"title": "静夜思", "author": "李白"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=75,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_separator():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 50},
        {"type": "separator", "style": "solid", "margin_x": 24},
        {"type": "spacer", "height": 10},
        {"type": "separator", "style": "dashed", "margin_x": 24},
        {"type": "spacer", "height": 10},
        {"type": "separator", "style": "short", "width": 60},
    ])
    img = render_json_mode(
        _make_mode_def([
            {"type": "spacer", "height": 50},
            {"type": "separator", "style": "solid"},
            {"type": "separator", "style": "dashed"},
            {"type": "separator", "style": "short", "width": 60},
        ]), {},
        date_str="1月1日", weather_str="晴", battery_pct=100,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_list_with_dicts():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 14},
        {
            "type": "list",
            "field": "exercises",
            "max_items": 5,
            "item_template": "{name}",
            "right_field": "reps",
            "font_size": 13,
            "margin_x": 32,
            "numbered": True,
            "item_spacing": 16,
        },
    ])
    content = {
        "exercises": [
            {"name": "深蹲", "reps": "20次"},
            {"name": "俯卧撑", "reps": "15次"},
            {"name": "平板支撑", "reps": "30秒"},
        ]
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_list_with_strings():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 14},
        {
            "type": "list",
            "field": "lines",
            "max_items": 4,
            "item_template": "{_value}",
            "font_size": 16,
            "item_spacing": 24,
            "margin_x": 30,
            "align": "center",
        },
    ])
    content = {"lines": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"]}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_section_with_icon():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 14},
        {
            "type": "section",
            "title": "训练动作",
            "icon": "exercise",
            "children": [
                {"type": "text", "field": "tip", "font_size": 13, "align": "left", "margin_x": 40},
            ],
        },
    ])
    content = {"tip": "运动前记得热身"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_vertical_stack():
    mode_def = _make_mode_def([
        {
            "type": "vertical_stack",
            "spacing": 4,
            "children": [
                {"type": "spacer", "height": 14},
                {"type": "text", "field": "a", "font_size": 14, "align": "center"},
                {"type": "separator", "style": "solid"},
                {"type": "text", "field": "b", "font_size": 14, "align": "center"},
            ],
        },
    ])
    content = {"a": "第一段", "b": "第二段"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_conditional():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 14},
        {
            "type": "conditional",
            "field": "count",
            "conditions": [
                {
                    "op": "gt",
                    "value": 5,
                    "children": [
                        {"type": "text", "template": "很多: {count}", "font_size": 14, "align": "center"},
                    ],
                },
            ],
            "fallback_children": [
                {"type": "text", "template": "少量: {count}", "font_size": 14, "align": "center"},
            ],
        },
    ])

    # count = 10 -> "很多"
    img1 = render_json_mode(
        mode_def, {"count": 10},
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img1.size == (SCREEN_W, SCREEN_H)

    # count = 3 -> fallback "少量"
    img2 = render_json_mode(
        mode_def, {"count": 3},
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img2.size == (SCREEN_W, SCREEN_H)


def test_render_icon_text():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 40},
        {"type": "icon_text", "icon": "book", "text": "推荐阅读", "font_size": 14, "margin_x": 24},
    ])
    img = render_json_mode(
        mode_def, {},
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_with_footer_template():
    mode_def = _make_mode_def(
        [{"type": "centered_text", "field": "quote", "font_size": 16}],
        footer={"label": "CUSTOM", "attribution_template": "— {author}", "dashed": True},
    )
    content = {"quote": "Test", "author": "Author"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_with_dashed_status_bar():
    mode_def = {
        "mode_id": "ZEN_TEST",
        "display_name": "Zen Test",
        "content": {"type": "static"},
        "layout": {
            "status_bar": {"line_width": 1, "dashed": True},
            "body": [
                {"type": "centered_text", "field": "word", "font": "noto_serif_regular", "font_size": 48, "vertical_center": True}
            ],
            "footer": {"label": "ZEN", "attribution_template": "— ...", "dashed": True},
        },
    }
    content = {"word": "静"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_context_resolve():
    """Test RenderContext.resolve template substitution."""
    from PIL import ImageDraw
    img = Image.new("1", (100, 100), 1)
    draw = ImageDraw.Draw(img)
    ctx = RenderContext(draw=draw, img=img, content={"name": "Alice", "count": 42})

    assert ctx.resolve("Hello {name}!") == "Hello Alice!"
    assert ctx.resolve("{count} items") == "42 items"
    assert ctx.resolve("no placeholders") == "no placeholders"
    assert ctx.resolve("{missing}") == ""


def test_render_stoic_json():
    """End-to-end: render using the builtin STOIC JSON definition."""
    stoic_path = os.path.join(
        os.path.dirname(__file__), "..", "core", "modes", "builtin", "stoic.json"
    )
    with open(stoic_path, "r", encoding="utf-8") as f:
        mode_def = json.load(f)

    content = {
        "quote": "The impediment to action advances action.",
        "author": "Marcus Aurelius",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日 周二", weather_str="晴 15°C", battery_pct=85,
        weather_code=0, time_str="14:30",
    )
    assert img.size == (SCREEN_W, SCREEN_H)
    assert img.mode == "1"


def test_render_fitness_json():
    """End-to-end: render using the builtin FITNESS JSON definition."""
    fitness_path = os.path.join(
        os.path.dirname(__file__), "..", "core", "modes", "builtin", "fitness.json"
    )
    with open(fitness_path, "r", encoding="utf-8") as f:
        mode_def = json.load(f)

    content = {
        "workout_name": "晨间拉伸",
        "duration": "15分钟",
        "exercises": [
            {"name": "颈部拉伸", "reps": "10次"},
            {"name": "肩部环绕", "reps": "15次"},
            {"name": "腰部扭转", "reps": "20次"},
        ],
        "tip": "运动前充分热身，避免受伤。",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日 周二", weather_str="多云 12°C", battery_pct=70,
        weather_code=3, time_str="07:00",
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_poetry_json():
    """End-to-end: render using the builtin POETRY JSON definition."""
    poetry_path = os.path.join(
        os.path.dirname(__file__), "..", "core", "modes", "builtin", "poetry.json"
    )
    with open(poetry_path, "r", encoding="utf-8") as f:
        mode_def = json.load(f)

    content = {
        "title": "静夜思",
        "author": "唐·李白",
        "lines": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
        "note": "千古思乡名篇",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日 周二", weather_str="晴", battery_pct=90,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


if __name__ == "__main__":
    test_render_produces_correct_size_image()
    test_render_centered_text()
    test_render_text_block()
    test_render_separator()
    test_render_list_with_dicts()
    test_render_list_with_strings()
    test_render_section_with_icon()
    test_render_vertical_stack()
    test_render_conditional()
    test_render_icon_text()
    test_render_with_footer_template()
    test_render_with_dashed_status_bar()
    test_render_context_resolve()
    test_render_stoic_json()
    test_render_fitness_json()
    test_render_poetry_json()
    print("✓ All JSON renderer tests passed")
