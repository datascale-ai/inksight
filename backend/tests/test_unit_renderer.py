"""
Unit tests for renderer helpers (image conversion, mode dispatch).
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
        # BMP magic number
        assert data[:2] == b"BM"

    def test_png_bytes(self):
        img = _make_1bit_image()
        data = image_to_png_bytes(img)
        assert isinstance(data, bytes)
        assert len(data) > 0
        # PNG magic number
        assert data[:4] == b"\x89PNG"

    def test_png_from_1bit_converts(self):
        img = Image.new("1", (100, 100), 0)
        data = image_to_png_bytes(img)
        assert data[:4] == b"\x89PNG"


class TestRenderMode:
    """Smoke tests for render_mode dispatcher — verifies all modes return an Image."""

    COMMON_KWARGS = dict(
        date_str="2月16日 周一",
        weather_str="12°C",
        battery_pct=85,
        weather_code=1,
        time_str="09:30",
    )

    def test_stoic(self):
        img = render_mode(
            "STOIC",
            {"quote": "Test quote", "author": "Test Author"},
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)
        assert img.size == (400, 300)

    def test_roast(self):
        img = render_mode(
            "ROAST",
            {"quote": "Test roast"},
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_zen(self):
        img = render_mode(
            "ZEN",
            {"word": "静"},
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_daily(self):
        date_ctx = {
            "year": 2026, "day": 16, "month_cn": "二月",
            "weekday_cn": "周一", "day_of_year": 47, "days_in_year": 365,
        }
        img = render_mode(
            "DAILY",
            {
                "quote": "Test", "author": "Author",
                "book_title": "Book", "book_author": "Writer",
                "book_desc": "Desc", "tip": "Tip", "season_text": "Spring",
            },
            date_ctx=date_ctx,
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_briefing(self):
        img = render_mode(
            "BRIEFING",
            {
                "hn_items": [{"title": "Story", "score": 100}],
                "ph_item": {"name": "Product", "tagline": "Tagline"},
                "insight": "Insight text",
            },
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_recipe(self):
        img = render_mode(
            "RECIPE",
            {
                "season": "立春·二月",
                "breakfast": "粥·蛋",
                "lunch": {"meat": "鸡", "veg": "菜", "staple": "饭"},
                "dinner": {"meat": "鱼", "veg": "菜", "staple": "汤"},
                "nutrition": "蛋白质✓",
            },
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_fitness(self):
        img = render_mode(
            "FITNESS",
            {
                "workout_name": "Test",
                "duration": "15min",
                "exercises": [{"name": "Push-up", "reps": "10"}],
                "tip": "Stay hydrated",
            },
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)

    def test_unknown_falls_back_to_stoic(self):
        img = render_mode(
            "UNKNOWN_MODE",
            {"quote": "Fallback", "author": ""},
            **self.COMMON_KWARGS,
        )
        assert isinstance(img, Image.Image)
