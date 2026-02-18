"""
测试 ModeRegistry 模式注册中心
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.mode_registry import ModeRegistry, _validate_mode_def, JsonMode


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


if __name__ == "__main__":
    test_validate_valid_mode()
    test_validate_missing_mode_id()
    test_validate_missing_content()
    test_validate_invalid_content_type()
    test_validate_llm_without_prompt()
    test_validate_missing_layout()
    test_validate_empty_body()
    test_validate_static_mode()
    test_registry_register_and_query()
    test_registry_load_json_mode()
    test_registry_load_directory()
    test_registry_unregister_custom()
    test_registry_builtin_shadows_json()
    test_registry_list_modes()
    test_registry_cacheable()
    test_registry_mode_icon_map()
    print("✓ All ModeRegistry tests passed")
