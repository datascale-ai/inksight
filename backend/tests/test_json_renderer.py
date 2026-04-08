"""
测试 JSON 渲染引擎
验证各种布局原语能正确渲染到 1-bit e-ink 图像
"""
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from core.json_renderer import render_json_mode, RenderContext, _localized_footer_label, _localized_footer_attribution, _component_aligned_y
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

