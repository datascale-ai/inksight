from datetime import datetime as real_datetime

import pytest
from PIL import Image, ImageDraw

import core.patterns.utils as utils


@pytest.mark.parametrize(
    ("raw", "expected", "hour"),
    [
        ("09:30:45", "09:30", 9),
        ("9:03", "09:03", 9),
        ("23:59:59", "23:59", 23),
        ("00:00", "00:00", 0),
    ],
)
def test_resolve_status_bar_time_formats_hh_mm(raw, expected, hour):
    assert utils._resolve_status_bar_time(raw) == (expected, hour)


def test_resolve_status_bar_time_falls_back_to_current_minute(monkeypatch):
    class FrozenDatetime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 8, 11, 14, 37, 59)

    monkeypatch.setattr(utils, "datetime", FrozenDatetime)
    assert utils._resolve_status_bar_time("") == ("14:37", 14)
    assert utils._resolve_status_bar_time("not-a-time") == ("14:37", 14)
    assert utils._resolve_status_bar_time("24:80:00") == ("14:37", 14)


def test_draw_status_bar_uses_normalized_time_without_parentheses(monkeypatch):
    captured = {}

    def capture_group(draw, time_text, battery_pct, font_en, screen_w, screen_h, colors):
        captured["time_text"] = time_text
        captured["battery_pct"] = battery_pct
        return {}

    monkeypatch.setattr(utils, "_draw_status_bar_dynamic_group", capture_group)
    image = Image.new("1", (400, 300), 1)
    utils.draw_status_bar(
        ImageDraw.Draw(image),
        image,
        date_str="8月11日 周二",
        weather_str="晴",
        battery_pct=85,
        time_str="9:03:45",
        screen_w=400,
        screen_h=300,
    )
    assert captured == {"time_text": "09:03", "battery_pct": 85}
    assert "(" not in captured["time_text"]
    assert ")" not in captured["time_text"]


@pytest.mark.parametrize("screen_w, screen_h", [(296, 128), (400, 300), (800, 480)])
@pytest.mark.parametrize("battery_pct", [0, 85, 100])
def test_dynamic_group_fits_screen(screen_w, screen_h, battery_pct):
    image = Image.new("1", (screen_w, screen_h), 1)
    draw = ImageDraw.Draw(image)
    scale = screen_w / 400.0
    font = utils.load_font(
        "inter_medium",
        int(utils.FONT_SIZES["status_bar"]["en"] * scale),
    )
    layout = utils._status_bar_dynamic_group_layout(
        draw,
        "23:59",
        battery_pct,
        font,
        screen_w,
        screen_h,
    )
    assert layout["group_left"] >= 0
    assert layout["time_left"] >= 0
    assert layout["time_right"] <= layout["battery_x"]
    assert layout["battery_x"] + layout["battery_box_w"] + int(2 * scale) <= screen_w
    assert layout["battery_text_right"] <= layout["group_right"]


def test_refresh_dynamic_group_does_not_mutate_cached_image():
    original = Image.new("1", (400, 300), 1)
    original_bytes = original.tobytes()
    updated = utils.refresh_status_bar_dynamic_right(
        original,
        85,
        time_str="14:37:59",
        screen_w=400,
        screen_h=300,
    )
    assert updated is not original
    assert original.tobytes() == original_bytes
    assert updated.tobytes() != original_bytes


def test_refresh_dynamic_group_supports_four_color_image():
    image = Image.new("P", (400, 300), utils.EINK_BG)
    image.putpalette(utils.EINK_COLOR_NAME_MAP.get("white", 1).to_bytes(1, "big") * 3 + bytes(765))
    updated = utils.refresh_status_bar_dynamic_right(
        image,
        20,
        time_str="02:00:00",
        screen_w=400,
        screen_h=300,
        colors=4,
    )
    assert updated.mode == "P"
    assert updated.size == (400, 300)
