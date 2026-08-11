"""
测试 JSON 渲染引擎
验证各种布局原语能正确渲染到 1-bit e-ink 图像
"""
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from copy import deepcopy

from core.json_renderer import (
    render_json_mode,
    RenderContext,
    _localized_footer_label,
    _localized_footer_attribution,
    _component_aligned_y,
    _auto_fit_component_scale,
    _merge_layout_dict,
    _build_component_node,
    _component_has_auto_pair,
    _measure_component_node,
)
from core.layout_presets import expand_layout_presets
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


def _make_component_tree_mode_def(body_tree, footer=None):
    return {
        "mode_id": "TREE_TEST",
        "display_name": "Tree Test",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "component_theme": {
                "body_font_size": 12,
                "body_line_gap": 4,
                "section_title_font_size": 12,
                "section_icon_size": 12,
                "section_icon_gap": 16,
                "section_title_gap": 6,
                "section_content_indent": 36,
                "section_content_gap": 4,
            },
            "body": body_tree,
            "footer": footer or {"label": "TREE", "attribution_template": ""},
        },
    }


def _load_builtin_poetry_mode():
    path = Path(__file__).resolve().parents[1] / "core" / "modes" / "builtin" / "poetry.json"
    return json.loads(path.read_text())


def _find_component_def(node, predicate):
    if not isinstance(node, dict):
        return None
    if predicate(node):
        return node
    for child in node.get("children", []):
        found = _find_component_def(child, predicate)
        if found is not None:
            return found
    item = node.get("item")
    if isinstance(item, dict):
        found = _find_component_def(item, predicate)
        if found is not None:
            return found
    return None


def test_render_list_wraps_to_multiple_lines():
    mode_def = _make_mode_def([
        {"type": "spacer", "height": 14},
        {
            "type": "list",
            "field": "items",
            "max_items": 1,
            "item_template": "{title}",
            "font_size": 14,
            "item_spacing": 18,
            "margin_x": 24,
        },
    ])
    content = {
        "items": [
            {
                "title": "This is a very long Hacker News headline that should wrap onto a second line in the list renderer"
            }
        ]
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    second_line_band = img.crop((24, 32, SCREEN_W - 24, 52))
    assert min(second_line_band.getdata()) < 255


def test_component_tree_repeat_wraps_text():
    mode_def = _make_component_tree_mode_def(
        {
            "type": "column",
            "padding_x": 18,
            "padding_y": 8,
            "children": [
                {
                    "type": "section_box",
                    "title": "HN",
                    "icon": "global",
                    "children": [
                        {
                            "type": "repeat",
                            "field": "items",
                            "limit": 1,
                            "item": {
                                "type": "row",
                                "gap": 8,
                                "align": "end",
                                "children": [
                                    {"type": "text", "field": "title", "grow": 1, "max_lines": 2},
                                    {"type": "text", "field": "score", "align": "right", "max_lines": 1},
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    )
    content = {
        "items": [
            {"title": "This is a very long story title that should wrap inside the component tree layout row", "score": 321}
        ]
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    second_line_band = img.crop((54, 52, SCREEN_W - 60, 76))
    assert min(second_line_band.getdata()) < 255


def test_render_component_tree_preset_mode():
    mode_def = {
        "mode_id": "STORY_PRESET",
        "display_name": "Story Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": True},
            "component_theme": {
                "body_font": "noto_serif_regular",
                "body_font_size": 13,
                "body_line_gap": 5,
            },
            "body_preset": "story_card",
            "preset_props": {
                "padding_x": 18,
                "padding_y": 6,
                "justify": "center",
                "gap": 6,
                "meta_field": "genre",
                "meta_font_size": 9,
                "title_field": "title",
                "title_font": "noto_serif_bold",
                "title_font_size": 16,
                "title_max_lines": 2,
                "separator_width": 50,
                "sections": [
                    {"field": "opening", "font_size": 13, "inset_x": 28, "max_lines": 3},
                    {"field": "twist", "font_size": 13, "inset_x": 28, "max_lines": 3},
                    {"field": "ending", "font": "noto_serif_light", "font_size": 13, "inset_x": 28, "max_lines": 3},
                ],
            },
            "footer": {"label": "STORY", "attribution_template": "— Micro Fiction", "dashed": True},
        },
    }
    content = {
        "genre": "温情",
        "title": "末班车",
        "opening": "她每天都坐末班地铁，座位对面总是同一个男人在看书。",
        "twist": "有一天她终于鼓起勇气搭话，男人抬头，手里的书封面是她写的小说。",
        "ending": "小说的最后一章写的是：她从未搭话。",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_fragment_stack_mode():
    mode_def = {
        "mode_id": "FRAGMENT_STACK",
        "display_name": "Fragment Stack",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "component_theme": {
                "body_font": "noto_serif_regular",
                "body_font_size": 13,
                "body_line_gap": 5,
            },
            "fragment_stack": {"padding_x": 18, "gap": 6},
            "fragments": [
                {"fragment": "title_with_rule", "title_field": "title", "separator_width": 50},
                {"fragment": "inset_body_text", "field": "body", "font_size": 13, "inset_x": 24, "max_lines": 3},
            ],
            "footer": {"label": "STACK", "attribution_template": ""},
        },
    }
    content = {
        "title": "Hello",
        "body": "This fragment-based layout compiles into a component tree before rendering.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_prompt_preset_mode():
    mode_def = {
        "mode_id": "PROMPT_PRESET",
        "display_name": "Prompt Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "prompt_card",
            "preset_props": {
                "title_template": "Daily Question",
                "meta_template": "{category}",
                "hero_field": "question",
                "hero_font": "noto_serif_bold",
                "note_field": "context_note",
            },
            "footer": {"label": "QUESTION", "attribution_template": ""},
        },
    }
    content = {
        "category": "Self",
        "question": "What are you avoiding because it might matter?",
        "context_note": "The answer often points at the next real step.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_word_preset_mode():
    mode_def = {
        "mode_id": "WORD_PRESET",
        "display_name": "Word Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "word_card",
            "preset_props": {
                "word_field": "word",
                "word_font": "noto_serif_bold",
                "definition_field": "definition",
                "example_field": "example",
            },
            "footer": {"label": "WORD", "attribution_template": ""},
        },
    }
    content = {
        "word": "Serendipity",
        "definition": "意外发现美好事物的能力",
        "example": "Traveling is full of serendipity.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_letter_preset_mode():
    mode_def = {
        "mode_id": "LETTER_PRESET",
        "display_name": "Letter Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": True},
            "body_preset": "letter_card",
            "preset_props": {
                "greeting_field": "greeting",
                "body_field": "body",
                "closing_field": "closing",
                "postscript_field": "postscript",
            },
            "footer": {"label": "LETTER", "attribution_template": "— {sender}"},
        },
    }
    content = {
        "sender": "A traveler",
        "greeting": "Dear friend",
        "body": "I found a quiet cafe where the rain sounds louder than the city. It made me think of slower days.",
        "closing": "Yours",
        "postscript": "The tea was excellent.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_bias_preset_mode():
    mode_def = {
        "mode_id": "BIAS_PRESET",
        "display_name": "Bias Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "bias_card",
            "preset_props": {
                "title_field": "name",
                "definition_field": "definition",
                "example_field": "example",
                "antidote_field": "antidote",
            },
            "footer": {"label": "BIAS", "attribution_template": ""},
        },
    }
    content = {
        "name": "Survivorship Bias",
        "definition": "Looking at wins while ignoring losses.",
        "example": "You hear startup success stories and forget the many silent failures.",
        "antidote": "Look for the missing denominator.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_riddle_preset_mode():
    mode_def = {
        "mode_id": "RIDDLE_PRESET",
        "display_name": "Riddle Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "riddle_card",
            "preset_props": {
                "question_field": "question",
                "hint_template": "Hint: {hint}",
            },
            "footer": {"label": "RIDDLE", "attribution_template": ""},
        },
    }
    content = {
        "category": "Riddle",
        "question": "What has keys but can't open locks?",
        "hint": "You play it.",
        "answer": "A piano",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_recipe_preset_mode():
    mode_def = {
        "mode_id": "RECIPE_PRESET",
        "display_name": "Recipe Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "recipe_card",
            "preset_props": {
                "season_field": "season",
                "breakfast_title": "Breakfast",
                "lunch_title": "Lunch",
                "dinner_title": "Dinner",
            },
            "footer": {"label": "RECIPE", "attribution_template": ""},
        },
    }
    content = {
        "season": "Spring",
        "breakfast": "Oatmeal and fruit",
        "lunch": "Chicken salad",
        "dinner": "Soup and bread",
        "tip": "Eat light today.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_poetry_preset_mode():
    mode_def = {
        "mode_id": "POETRY_PRESET",
        "display_name": "Poetry Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": True},
            "body_preset": "poetry_card",
            "preset_props": {
                "title_field": "title",
                "author_field": "author",
                "lines_field": "lines",
                "note_field": "note",
            },
            "footer": {"label": "POETRY", "attribution_template": "— {author}"},
        },
    }
    content = {
        "title": "Stopping by Woods",
        "author": "Robert Frost",
        "lines": [
            "Whose woods these are I think I know,",
            "His house is in the village though,",
            "He will not see me stopping here",
            "To watch his woods fill up with snow.",
        ],
        "note": "A quiet pause before the miles ahead.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_poetry_auto_pair_on_overflow():
    """8-line poems auto-pair two-per-row; 4-line poems stay single-column."""
    mode_def = {
        "mode_id": "POETRY_PRESET",
        "display_name": "Poetry Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": True},
            "body_preset": "poetry_card",
            "preset_props": {
                "title_field": "title",
                "author_field": "author",
                "lines_field": "lines",
                "note_field": "note",
            },
            "footer": {"label": "POETRY", "attribution_template": "— {author}"},
        },
    }
    status_bar_bottom = int(SCREEN_H * 0.12)
    footer_top = SCREEN_H - 30
    available = footer_top - status_bar_bottom

    eight_line = {
        "title": "春江花月夜",
        "author": "唐·张若虚",
        "lines": [
            "春江潮水连海平", "海上明月共潮生",
            "滟滟随波千万里", "何处春江无月明",
            "江流宛转绕芳甸", "月照花林皆似霰",
            "空里流霜不觉飞", "汀上白沙看不见",
        ],
        "note": "孤篇压全唐",
    }
    four_line = {
        "title": "静夜思",
        "author": "唐·李白",
        "lines": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
        "note": "千古思乡名篇",
    }

    layout = expand_layout_presets(mode_def["layout"])
    body = layout["body"]

    # 8-line overflows without pairing, then auto-pairs and fits.
    base_root = _build_component_node(deepcopy(body), eight_line)
    _measure_component_node(base_root, SCREEN_W, {}, 1.0)
    assert base_root.measured_height > available

    body_8 = deepcopy(body)
    scale_8 = _auto_fit_component_scale(
        body_8, eight_line, SCREEN_W, {}, 1.0, status_bar_bottom, footer_top,
    )
    root_8 = _build_component_node(body_8, eight_line)
    _measure_component_node(root_8, SCREEN_W, {}, scale_8)
    assert _component_has_auto_pair(root_8)
    assert root_8.measured_height <= available
    assert scale_8 == 1.0

    # 4-line already fits — no pairing, no scale-down.
    body_4 = deepcopy(body)
    scale_4 = _auto_fit_component_scale(
        body_4, four_line, SCREEN_W, {}, 1.0, status_bar_bottom, footer_top,
    )
    root_4 = _build_component_node(body_4, four_line)
    _measure_component_node(root_4, SCREEN_W, {}, scale_4)
    assert not _component_has_auto_pair(root_4)
    assert root_4.measured_height <= available
    assert scale_4 == 1.0

    # End-to-end render still succeeds for both.
    for content in (eight_line, four_line):
        img = render_json_mode(
            mode_def, content,
            date_str="2月18日", weather_str="晴", battery_pct=80,
        )
        assert img.size == (SCREEN_W, SCREEN_H)


def test_poetry_adaptive_typography_compacts_long_ci_only():
    """Long ci uses a larger title and smaller verse text on 400x300."""
    mode_def = _load_builtin_poetry_mode()
    layout = expand_layout_presets(mode_def["layout"])
    body = layout["body"]
    long_ci = {
        "title": "水调歌头·明月几时有",
        "author": "宋·苏轼",
        "lines": [
            "明月几时有？把酒问青天。",
            "不知天上宫阙，今夕是何年。",
            "我欲乘风归去，又恐琼楼玉宇，高处不胜寒。",
            "起舞弄清影，何似在人间。",
            "转朱阁，低绮户，照无眠。",
            "不应有恨，何事长向别时圆？",
        ],
        "note": "此事古难全·宋苏轼",
    }
    status_bar_bottom = 36
    footer_top = 270
    available = footer_top - status_bar_bottom

    normal_root = _build_component_node(deepcopy(body), long_ci)
    _measure_component_node(normal_root, SCREEN_W, {}, 1.0)
    assert normal_root.measured_height >= available - 8

    compact_body = deepcopy(body)
    scale = _auto_fit_component_scale(
        compact_body,
        long_ci,
        SCREEN_W,
        {},
        1.0,
        status_bar_bottom,
        footer_top,
        screen_h=SCREEN_H,
    )
    compact_root = _build_component_node(compact_body, long_ci)
    _measure_component_node(compact_root, SCREEN_W, {}, scale)

    title = _find_component_def(
        compact_body,
        lambda node: node.get("type") == "text" and node.get("field") == "title",
    )
    verse = _find_component_def(
        compact_body,
        lambda node: node.get("type") == "text" and node.get("field") == "_value",
    )
    repeat = _find_component_def(
        compact_body,
        lambda node: node.get("type") == "repeat" and node.get("field") == "lines",
    )
    note = _find_component_def(
        compact_body,
        lambda node: node.get("type") == "text" and node.get("field") == "note",
    )
    assert title is not None and verse is not None and repeat is not None and note is not None
    assert title["font_size"] == 16
    assert verse["font_size"] == 14
    assert title["font_size"] > verse["font_size"]
    assert repeat["gap"] == 4
    assert compact_body["gap"] == 4
    assert compact_body["padding_y"] == 6
    assert compact_body["children"][0]["height"] == 8
    assert note["max_lines"] == 1
    assert not _component_has_auto_pair(compact_root)
    assert scale == 1.0
    assert compact_root.measured_height <= available

    image = render_json_mode(
        mode_def,
        long_ci,
        date_str="8月10日",
        weather_str="晴",
        battery_pct=80,
        screen_w=SCREEN_W,
        screen_h=SCREEN_H,
    )
    assert image.size == (SCREEN_W, SCREEN_H)


def test_poetry_short_ci_keeps_normal_typography():
    mode_def = _load_builtin_poetry_mode()
    layout = expand_layout_presets(mode_def["layout"])
    body = deepcopy(layout["body"])
    short_ci = {
        "title": "静夜思",
        "author": "唐·李白",
        "lines": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
        "note": "千古思乡名篇",
    }
    scale = _auto_fit_component_scale(
        body, short_ci, SCREEN_W, {}, 1.0, 36, 270, screen_h=SCREEN_H,
    )
    title = _find_component_def(
        body,
        lambda node: node.get("type") == "text" and node.get("field") == "title",
    )
    verse = _find_component_def(
        body,
        lambda node: node.get("type") == "text" and node.get("field") == "_value",
    )
    root = _build_component_node(body, short_ci)
    _measure_component_node(root, SCREEN_W, {}, scale)
    assert title is not None and verse is not None
    assert title["font_size"] == 14
    assert verse["font_size"] == 16
    assert not _component_has_auto_pair(root)
    assert scale == 1.0


def test_poetry_adaptive_typography_is_scoped_to_400x300():
    mode_def = _load_builtin_poetry_mode()
    content = {
        "title": "水调歌头·明月几时有",
        "author": "宋·苏轼",
        "lines": ["明月几时有？把酒问青天。"] * 8,
        "note": "此事古难全",
    }
    expected = {
        "296x128": (11, 10),
        "648x480": (18, 18),
        "800x480": (22, 24),
    }
    for size_key, (title_size, verse_size) in expected.items():
        width, height = (int(value) for value in size_key.split("x"))
        layout = _merge_layout_dict(mode_def["layout"], mode_def["layout_overrides"][size_key])
        body = expand_layout_presets(layout)["body"]
        title = _find_component_def(
            body,
            lambda node: node.get("type") == "text" and node.get("field") == "title",
        )
        verse = _find_component_def(
            body,
            lambda node: node.get("type") == "text" and node.get("field") == "_value",
        )
        assert title is not None and verse is not None
        assert title["font_size"] == title_size
        assert verse["font_size"] == verse_size

        _auto_fit_component_scale(
            body,
            content,
            width,
            {},
            0.92 if width < 400 else 1.35,
            int(height * (0.11 if height <= 128 else 0.12)) + (2 if height <= 128 else 0),
            height - (24 if height <= 128 else int(30 * min(width / 400, height / 300))),
            screen_h=height,
        )
        assert title["font_size"] == title_size
        assert verse["font_size"] == verse_size


def test_component_tree_scale_down_when_pairing_unavailable():
    """Without auto_pair, overflowing content shrinks via binary-search scale."""
    body_tree = {
        "type": "column",
        "padding_x": 12,
        "gap": 6,
        "children": [
            {
                "type": "repeat",
                "field": "lines",
                "gap": 10,
                "item": {
                    "type": "text",
                    "field": "_value",
                    "font": "noto_serif_regular",
                    "font_size": 20,
                    "align": "center",
                    "max_lines": 1,
                },
            }
        ],
    }
    content = {
        "lines": [
            "第一行内容足够长一些",
            "第二行内容足够长一些",
            "第三行内容足够长一些",
            "第四行内容足够长一些",
            "第五行内容足够长一些",
            "第六行内容足够长一些",
            "第七行内容足够长一些",
            "第八行内容足够长一些",
            "第九行内容足够长一些",
            "第十行内容足够长一些",
        ]
    }
    status_bar_bottom = 36
    footer_top = 270
    available = footer_top - status_bar_bottom

    base_root = _build_component_node(deepcopy(body_tree), content)
    _measure_component_node(base_root, SCREEN_W, {}, 1.0)
    assert base_root.measured_height > available

    body = deepcopy(body_tree)
    fit_scale = _auto_fit_component_scale(
        body, content, SCREEN_W, {}, 1.0, status_bar_bottom, footer_top,
    )
    assert fit_scale is not None
    assert fit_scale < 1.0
    assert fit_scale >= 0.72
    assert not _component_has_auto_pair(_build_component_node(body, content))

    fitted = _build_component_node(body, content)
    _measure_component_node(fitted, SCREEN_W, {}, fit_scale)
    assert fitted.measured_height <= available


def test_render_component_tree_lifebar_preset_mode():
    mode_def = {
        "mode_id": "LIFEBAR_PRESET",
        "display_name": "Lifebar Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "lifebar_card",
            "preset_props": {
                "primary_metric": {
                    "label_field": "year_label",
                    "value_template": "{year_pct}%",
                    "bar_field": "day_of_year",
                    "bar_max_field": "days_in_year",
                    "bar_width": 220,
                },
                "left_metric": {
                    "label_field": "month_label",
                    "value_template": "{month_pct}%",
                    "bar_field": "day",
                    "bar_max_field": "days_in_month",
                    "bar_width": 100,
                },
                "right_metric": {
                    "label_field": "week_label",
                    "value_template": "{week_pct}%",
                    "bar_field": "weekday_num",
                    "bar_max_field": "week_total",
                    "bar_width": 100,
                },
                "bottom_metric": {
                    "label_field": "life_label",
                    "value_template": "{life_pct}%",
                    "bar_field": "age",
                    "bar_max_field": "life_expect",
                    "bar_width": 220,
                },
            },
            "footer": {"label": "LIFEBAR", "attribution_template": ""},
        },
    }
    content = {
        "year_label": "2026",
        "year_pct": 32.1,
        "day_of_year": 117,
        "days_in_year": 365,
        "month_label": "April",
        "month_pct": 30.0,
        "day": 9,
        "days_in_month": 30,
        "week_label": "Week",
        "week_pct": 57.0,
        "weekday_num": 4,
        "week_total": 7,
        "life_label": "Life",
        "life_pct": 40.0,
        "age": 32,
        "life_expect": 80,
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_countdown_preset_mode():
    mode_def = {
        "mode_id": "COUNTDOWN_PRESET",
        "display_name": "Countdown Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "countdown_card",
            "preset_props": {
                "days_label_template": "days left",
            },
            "footer": {"label": "COUNTDOWN", "attribution_template": ""},
        },
    }
    content = {
        "message": "A milestone is getting close.",
        "events": [{"name": "Launch Day", "date": "2026-05-01", "days": 22}],
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_fitness_preset_mode():
    mode_def = {
        "mode_id": "FITNESS_PRESET",
        "display_name": "Fitness Preset",
        "content": {"type": "static"},
        "layout": {
            "layout_engine": "component_tree",
            "status_bar": {"line_width": 1, "dashed": False},
            "body_preset": "fitness_card",
            "preset_props": {
                "exercise_title": "Exercises",
                "tip_title": "Tip",
            },
            "footer": {"label": "FITNESS", "attribution_template": ""},
        },
    }
    content = {
        "workout_name": "Morning Stretch",
        "duration": "15 min",
        "exercises": [
            {"name": "Jumping Jacks", "reps": "30 sec"},
            {"name": "Push-ups", "reps": "10"},
            {"name": "Plank", "reps": "30 sec"},
        ],
        "tip": "Keep breathing steadily.",
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_render_component_tree_inline_quote_mode():
    mode_def = _make_component_tree_mode_def(
        {
            "type": "column",
            "padding_x": 18,
            "justify": "center",
            "children": [
                {
                    "type": "box",
                    "padding_x": 6,
                    "children": [
                        {
                            "type": "text",
                            "field": "quote",
                            "font": "noto_serif_bold",
                            "font_size": 18,
                            "align": "center",
                            "max_lines": 4,
                        }
                    ],
                }
            ],
        }
    )
    mode_def["layout"]["component_theme"] = {"body_line_gap": 8}
    content = {"quote": "A sharp line that still needs wrapping in the inline component tree layout."}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.size == (SCREEN_W, SCREEN_H)


def test_component_aligned_y_positions_content():
    assert _component_aligned_y(10, 40, 12, "top") == 10
    assert _component_aligned_y(10, 40, 12, "center") == 24
    assert _component_aligned_y(10, 40, 12, "bottom") == 38


def test_render_component_tree_debug_overlay_draws_bounds():
    mode_def = _make_component_tree_mode_def(
        {
            "type": "column",
            "padding_x": 18,
            "padding_y": 8,
            "children": [
                {"type": "text", "field": "title", "font_size": 14},
            ],
        }
    )
    mode_def["layout"]["debug_overlay"] = True
    content = {"title": "Debug"}
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    )
    assert img.getpixel((0, 36)) == 0


def test_render_image_block_preserves_palette_colors():
    src = Image.new("RGB", (4, 2), "white")
    src.putpixel((0, 0), (200, 0, 0))
    src.putpixel((1, 0), (232, 176, 0))
    src.putpixel((2, 0), (0, 0, 0))
    buf = BytesIO()
    src.save(buf, format="PNG")
    mode_def = _make_mode_def([
        {"type": "image", "field": "image_url", "width": 40, "height": 20, "x": 100, "y": 80}
    ])
    content = {
        "image_url": "prefetched://artwall",
        "_prefetched_image_url": buf.getvalue(),
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
        colors=4,
    )
    assert img.mode == "P"
    palette_indexes = set(img.crop((100, 80, 140, 100)).getdata())
    assert 3 in palette_indexes
    assert 2 in palette_indexes


def test_render_image_block_contain_fit_keeps_padding():
    src = Image.new("RGB", (4, 2), "black")
    buf = BytesIO()
    src.save(buf, format="PNG")
    mode_def = _make_mode_def([
        {"type": "image", "field": "image_url", "width": 20, "height": 20, "x": 100, "y": 80, "fit": "contain"}
    ])
    content = {
        "image_url": "prefetched://artwall",
        "_prefetched_image_url": buf.getvalue(),
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    assert img.getpixel((100, 80)) == 255
    assert img.getpixel((110, 90)) < 255


def test_render_image_block_cover_fit_fills_frame():
    src = Image.new("RGB", (2, 4), "white")
    for y in range(4):
        src.putpixel((0, y), (0, 0, 0))
        src.putpixel((1, y), (255, 255, 255))
    buf = BytesIO()
    src.save(buf, format="PNG")
    mode_def = _make_mode_def([
        {"type": "image", "field": "image_url", "width": 20, "height": 20, "x": 100, "y": 80, "fit": "cover"}
    ])
    content = {
        "image_url": "prefetched://frame",
        "_prefetched_image_url": buf.getvalue(),
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    assert img.getpixel((100, 80)) < 255
    assert img.getpixel((119, 99)) == 255


def test_render_missing_uploaded_image_does_not_fetch_remote():
    mode_def = _make_mode_def([
        {"type": "image", "field": "image_url", "width": 120, "height": 36, "x": 100, "y": 80}
    ])
    content = {
        "image_url": "https://www.inksight.site/api/uploads/00000000-0000-4000-8000-000000000000",
    }

    with patch("core.json_renderer.httpx.Client") as mock_client:
        img = render_json_mode(
            mode_def, content,
            date_str="2月18日", weather_str="晴", battery_pct=80,
        ).convert("L")

    mock_client.assert_not_called()
    assert img.getpixel((100, 80)) == 0


def test_render_forecast_cards_supports_custom_fields():
    mode_def = _make_mode_def([
        {
            "type": "forecast_cards",
            "field": "cards",
            "day_field": "label",
            "date_field": "when",
            "desc_field": "summary",
            "code_field": "weather_code",
            "temp_min_field": "low",
            "temp_max_field": "high",
            "show_desc": False,
            "margin_x": 16,
        }
    ])
    content = {
        "cards": [
            {"label": "Mon", "when": "4/8", "summary": "Sunny", "weather_code": 0, "low": 12, "high": 22},
            {"label": "Tue", "when": "4/9", "summary": "Rain", "weather_code": 3, "low": 10, "high": 18},
        ]
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    assert min(img.crop((40, 34, SCREEN_W - 40, 120)).getdata()) < 255


def test_slice_calendar_rows_around_day():
    from core.json_renderer import slice_calendar_rows_around_day

    rows = [
        ["", "", "", "", "1", "2", "3"],
        ["4", "5", "6", "7", "8", "9", "10"],
        ["11", "12", "13", "14", "15", "16", "17"],
        ["28", "29", "30", "31", "", "", ""],
    ]
    assert slice_calendar_rows_around_day(rows, "1", max_rows=2) == [rows[0], rows[1]]
    assert slice_calendar_rows_around_day(rows, "9", max_rows=2) == [rows[1], rows[2]]
    assert slice_calendar_rows_around_day(rows, "31", max_rows=2) == [rows[2], rows[3]]
    # Cell "19" must not satisfy today "9" (exact match per cell)
    tail = [["18", "19", "20", "21", "22", "23", "24"]]
    assert slice_calendar_rows_around_day(tail + rows, "9", max_rows=2) == [rows[0], rows[1]]


def test_render_calendar_grid_supports_custom_fields():
    mode_def = _make_mode_def([
        {
            "type": "calendar_grid",
            "rows_field": "rows",
            "headers_field": "headers",
            "today_field": "today",
            "labels_field": "labels",
            "label_types_field": "types",
            "today_style": "outline",
        }
    ])
    mode_def["layout"]["body_align"] = "top"
    content = {
        "headers": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "rows": [["1", "2", "3", "4", "5", "6", "7"]],
        "today": "3",
        "labels": {"3": "Today", "6": "Trip"},
        "types": {"6": "reminder"},
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    assert min(img.crop((20, 34, SCREEN_W - 20, 110)).getdata()) < 255


def test_render_timetable_grid_supports_custom_fields():
    mode_def = _make_mode_def([
        {
            "type": "timetable_grid",
            "field": "agenda",
            "time_field": "start",
            "name_field": "course",
            "location_field": "room",
            "current_field": "is_now",
            "show_location": False,
            "time_col_ratio": 0.3,
            "row_height": 24,
        }
    ])
    mode_def["layout"]["body_align"] = "top"
    content = {
        "style": "daily",
        "agenda": [
            {"start": "09:00", "course": "Math", "room": "A101", "is_now": True},
            {"start": "10:30", "course": "Literature", "room": "B202", "is_now": False},
        ],
    }
    img = render_json_mode(
        mode_def, content,
        date_str="2月18日", weather_str="晴", battery_pct=80,
    ).convert("L")
    assert min(img.crop((10, 34, SCREEN_W - 10, 110)).getdata()) < 255


def test_builtin_footer_localization():
    assert _localized_footer_label("COUNTDOWN", "COUNTDOWN", "zh") == "倒计时"
    assert _localized_footer_label("COUNTDOWN", "Countdown", "en") == "Countdown"
    assert _localized_footer_attribution("COUNTDOWN", "— Remember", "zh") == "— 静待那天"
    assert _localized_footer_attribution("COUNTDOWN", "— Remember", "en") == "— Remember"


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
