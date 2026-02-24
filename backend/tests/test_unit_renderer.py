"""
Unit tests for renderer helpers (image conversion, mode dispatch).

STOIC, ROAST, ZEN, FITNESS, POETRY are now JSON-defined modes rendered by
json_renderer.py. Tests for those live in test_json_renderer.py.
This file tests only the Python builtin modes still dispatched by render_mode().
"""
import pytest
from PIL import Image

from core.renderer import image_to_bmp_bytes, image_to_png_bytes, render_mode


def _make_1bit_image() -> Image.Image:
    return Image.new("1", (400, 300), 1)


class TestImageConversion:
    def test_bmp_bytes(self):
        img = _make_1bit_image()
        data = image_to_bmp_bytes(img)
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data[:2] == b"BM"

    def test_png_bytes(self):
        img = _make_1bit_image()
        data = image_to_png_bytes(img)
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data[:4] == b"\x89PNG"

    def test_png_from_1bit_converts(self):
        img = Image.new("1", (100, 100), 0)
        data = image_to_png_bytes(img)
        assert data[:4] == b"\x89PNG"


class TestRenderMode:
    """render_mode is legacy; all modes are JSON-defined."""

    COMMON_KWARGS = dict(
        date_str="2月16日 周一",
        weather_str="12°C",
        battery_pct=85,
        weather_code=1,
        time_str="09:30",
    )

    def test_all_personas_raise_value_error(self):
        with pytest.raises(ValueError):
            render_mode(
                "STOIC",
                {"quote": "Test", "author": "Author"},
                **self.COMMON_KWARGS,
            )
        with pytest.raises(ValueError):
            render_mode(
                "DAILY",
                {"quote": "Test", "author": "Author"},
                **self.COMMON_KWARGS,
            )
