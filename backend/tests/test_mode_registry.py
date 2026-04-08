"""
测试 ModeRegistry 模式注册中心
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.layout_presets import get_public_layout_dsl_catalog
from core.mode_registry import ModeRegistry, _validate_mode_def, _validate_mode_def_with_error, JsonMode


SAMPLE_MODE_DEF = {
    "mode_id": "TEST_MODE",
    "display_name": "测试模式",
    "icon": "star",
    "cacheable": True,
    "description": "A test mode",
    "content": {
        "type": "llm",
        "prompt_template": "Test prompt: {context}",
        "output_format": "raw",
        "output_fields": ["text"],
        "fallback": {"text": "fallback"},
    },
    "layout": {
        "status_bar": {"line_width": 1},
        "body": [
            {
                "type": "centered_text",
                "field": "text",
                "font_size": 16,
                "vertical_center": True,
            }
        ],
        "footer": {"label": "TEST"},
    },
}


def test_validate_valid_mode():
    assert _validate_mode_def(SAMPLE_MODE_DEF) is True


def test_validate_missing_mode_id():
    bad = {**SAMPLE_MODE_DEF, "mode_id": ""}
    assert _validate_mode_def(bad) is False


def test_validate_missing_content():
    bad = {**SAMPLE_MODE_DEF}
    del bad["content"]
    assert _validate_mode_def(bad) is False


def test_validate_invalid_content_type():
    bad = {**SAMPLE_MODE_DEF, "content": {"type": "invalid"}}
    assert _validate_mode_def(bad) is False


def test_validate_llm_without_prompt():
    bad = {
        **SAMPLE_MODE_DEF,
        "content": {"type": "llm", "fallback": {"text": "x"}},
    }
    assert _validate_mode_def(bad) is False


def test_validate_missing_layout():
    bad = {**SAMPLE_MODE_DEF}
    del bad["layout"]
    assert _validate_mode_def(bad) is False


def test_validate_empty_body():
    bad = {**SAMPLE_MODE_DEF, "layout": {"body": []}}
    assert _validate_mode_def(bad) is False


def test_validate_static_mode():
    static_def = {
        "mode_id": "STATIC_TEST",
        "display_name": "Static",
        "content": {"type": "static", "static_data": {"msg": "hello"}},
        "layout": {"body": [{"type": "centered_text", "field": "msg"}]},
    }
    assert _validate_mode_def(static_def) is True


def test_validate_component_tree_mode():
    component_tree_def = {
        "mode_id": "TREE_TEST",
        "display_name": "Tree Test",
        "content": {"type": "static", "static_data": {"msg": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body": {
                "type": "column",
                "children": [
                    {"type": "text", "field": "msg"}
                ],
            },
        },
    }
    assert _validate_mode_def(component_tree_def) is True


def test_validate_component_tree_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_PRESET",
        "display_name": "Tree Preset",
        "content": {"type": "static", "static_data": {"title": "hello", "opening": "a", "twist": "b", "ending": "c"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "story_card",
            "preset_props": {
                "title_field": "title",
                "sections": [
                    {"field": "opening"},
                    {"field": "twist"},
                    {"field": "ending"},
                ],
            },
        },
    }
    assert _validate_mode_def(component_tree_def) is True


def test_validate_component_tree_fragment_mode():
    component_tree_def = {
        "mode_id": "TREE_FRAGMENT",
        "display_name": "Tree Fragment",
        "content": {"type": "static", "static_data": {"title": "hello", "body": "world"}},
        "layout": {
            "layout_engine": "component_tree",
            "fragment_stack": {"padding_x": 18, "gap": 6},
            "fragments": [
                {"fragment": "title_with_rule", "title_field": "title", "separator_width": 50},
                {"fragment": "inset_body_text", "field": "body", "inset_x": 24},
            ],
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_prompt_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_PROMPT",
        "display_name": "Tree Prompt",
        "content": {"type": "static", "static_data": {"question": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "prompt_card",
            "preset_props": {
                "hero_field": "question",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_letter_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_LETTER",
        "display_name": "Tree Letter",
        "content": {"type": "static", "static_data": {"body": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "letter_card",
            "preset_props": {
                "body_field": "body",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_bias_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_BIAS",
        "display_name": "Tree Bias",
        "content": {"type": "static", "static_data": {"name": "bias", "definition": "desc"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "bias_card",
            "preset_props": {
                "title_field": "name",
                "definition_field": "definition",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_riddle_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_RIDDLE",
        "display_name": "Tree Riddle",
        "content": {"type": "static", "static_data": {"question": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "riddle_card",
            "preset_props": {
                "question_field": "question",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_recipe_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_RECIPE",
        "display_name": "Tree Recipe",
        "content": {"type": "static", "static_data": {"season": "spring"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "recipe_card",
            "preset_props": {
                "season_field": "season",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_poetry_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_POETRY",
        "display_name": "Tree Poetry",
        "content": {"type": "static", "static_data": {"title": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "poetry_card",
            "preset_props": {
                "title_field": "title",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_lifebar_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_LIFEBAR",
        "display_name": "Tree Lifebar",
        "content": {"type": "static", "static_data": {"year_label": "2026"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "lifebar_card",
            "preset_props": {
                "primary_metric": {
                    "label_field": "year_label",
                    "value_template": "{year_pct}%",
                    "bar_field": "day_of_year",
                    "bar_max_field": "days_in_year",
                },
                "bottom_metric": {
                    "label_field": "life_label",
                    "value_template": "{life_pct}%",
                    "bar_field": "age",
                    "bar_max_field": "life_expect",
                },
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_countdown_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_COUNTDOWN",
        "display_name": "Tree Countdown",
        "content": {"type": "static", "static_data": {"message": "Soon", "events": []}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "countdown_card",
            "preset_props": {
                "days_label_template": "days left",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_component_tree_fitness_preset_mode():
    component_tree_def = {
        "mode_id": "TREE_FITNESS",
        "display_name": "Tree Fitness",
        "content": {"type": "static", "static_data": {"workout_name": "Stretch"}},
        "layout": {
            "layout_engine": "component_tree",
            "body_preset": "fitness_card",
            "preset_props": {
                "exercise_title": "Exercises",
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is True


def test_validate_custom_mode_rejects_raw_component_tree():
    component_tree_def = {
        "mode_id": "TREE_RAW",
        "display_name": "Tree Raw",
        "content": {"type": "static", "static_data": {"msg": "hello"}},
        "layout": {
            "layout_engine": "component_tree",
            "body": {
                "type": "column",
                "children": [
                    {"type": "text", "field": "msg"}
                ],
            },
        },
    }
    assert _validate_mode_def(component_tree_def, allow_raw_component_tree=False) is False


def test_validate_mode_def_with_error_message():
    bad = {
        **SAMPLE_MODE_DEF,
        "layout": {
            "layout_engine": "component_tree",
            "body": {
                "type": "column",
                "children": [{"type": "text", "field": "text"}],
            },
        },
    }
    ok, error = _validate_mode_def_with_error(bad, allow_raw_component_tree=False)
    assert ok is False
    assert error == "raw component_tree body is not allowed here"


def test_public_layout_dsl_catalog_is_curated():
    catalog = get_public_layout_dsl_catalog()
    fragment_names = [item["name"] for item in catalog["fragments"]]
    preset_names = [item["name"] for item in catalog["presets"]]
    assert "plain_text" in fragment_names
    assert "quote_focus_card" in preset_names
    assert "fitness_card" not in preset_names


def test_registry_register_and_query():
    reg = ModeRegistry()

    async def dummy_content(**kw):
        return {"text": "hello"}

    def dummy_render(**kw):
        pass

    reg.register_builtin(
        "TEST_BUILTIN",
        dummy_content,
        dummy_render,
        display_name="Test",
        icon="star",
    )

    assert reg.is_supported("TEST_BUILTIN")
    assert reg.is_supported("test_builtin")
    assert reg.is_builtin("TEST_BUILTIN")
    assert not reg.is_json_mode("TEST_BUILTIN")
    assert "TEST_BUILTIN" in reg.get_supported_ids()

    info = reg.get_mode_info("TEST_BUILTIN")
    assert info is not None
    assert info.display_name == "Test"
    assert info.icon == "star"


def test_registry_load_json_mode():
    reg = ModeRegistry()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(SAMPLE_MODE_DEF, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        mode_id = reg.load_json_mode(tmp_path, source="custom")
        assert mode_id == "TEST_MODE"
        assert reg.is_supported("TEST_MODE")
        assert reg.is_json_mode("TEST_MODE")
        assert not reg.is_builtin("TEST_MODE")

        jm = reg.get_json_mode("TEST_MODE")
        assert jm is not None
        assert jm.info.display_name == "测试模式"
        assert jm.definition["content"]["type"] == "llm"
    finally:
        os.unlink(tmp_path)


def test_registry_load_directory():
    reg = ModeRegistry()

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(3):
            mode_def = {
                **SAMPLE_MODE_DEF,
                "mode_id": f"DIR_TEST_{i}",
                "display_name": f"Dir Test {i}",
            }
            path = os.path.join(tmpdir, f"test_{i}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mode_def, f, ensure_ascii=False)

        loaded = reg.load_directory(tmpdir, source="custom")
        assert len(loaded) == 3
        for i in range(3):
            assert reg.is_supported(f"DIR_TEST_{i}")


def test_registry_unregister_custom():
    reg = ModeRegistry()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(SAMPLE_MODE_DEF, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        reg.load_json_mode(tmp_path, source="custom")
        assert reg.is_supported("TEST_MODE")

        result = reg.unregister_custom("TEST_MODE")
        assert result is True
        assert not reg.is_supported("TEST_MODE")

        result = reg.unregister_custom("NONEXISTENT")
        assert result is False
    finally:
        os.unlink(tmp_path)


def test_registry_builtin_shadows_json():
    reg = ModeRegistry()

    async def dummy_content(**kw):
        return {}

    def dummy_render(**kw):
        pass

    reg.register_builtin("SHADOW_TEST", dummy_content, dummy_render)

    shadow_def = {**SAMPLE_MODE_DEF, "mode_id": "SHADOW_TEST"}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(shadow_def, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        result = reg.load_json_mode(tmp_path)
        assert result is None
        assert reg.is_builtin("SHADOW_TEST")
    finally:
        os.unlink(tmp_path)


def test_registry_list_modes():
    reg = ModeRegistry()

    async def dummy_content(**kw):
        return {}

    def dummy_render(**kw):
        pass

    reg.register_builtin("A_MODE", dummy_content, dummy_render, display_name="A")
    reg.register_builtin("B_MODE", dummy_content, dummy_render, display_name="B")

    modes = reg.list_modes()
    assert len(modes) == 2
    assert modes[0].mode_id == "A_MODE"
    assert modes[1].mode_id == "B_MODE"


def test_registry_cacheable():
    reg = ModeRegistry()

    async def dummy_content(**kw):
        return {}

    def dummy_render(**kw):
        pass

    reg.register_builtin("CACHE_YES", dummy_content, dummy_render, cacheable=True)
    reg.register_builtin("CACHE_NO", dummy_content, dummy_render, cacheable=False)

    cacheable = reg.get_cacheable_ids()
    assert "CACHE_YES" in cacheable
    assert "CACHE_NO" not in cacheable


def test_registry_mode_icon_map():
    reg = ModeRegistry()

    async def dummy_content(**kw):
        return {}

    def dummy_render(**kw):
        pass

    reg.register_builtin("ICON_TEST", dummy_content, dummy_render, icon="book")

    icon_map = reg.get_mode_icon_map()
    assert icon_map["ICON_TEST"] == "book"

