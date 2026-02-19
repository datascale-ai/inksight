"""
ZEN 模式 - 禅意
显示极简的汉字（如"静"、"空"）
"""

from PIL import Image, ImageDraw
from .utils import (
    SCREEN_W,
    SCREEN_H,
    EINK_BG,
    EINK_FG,
    draw_status_bar,
    draw_footer,
    load_font,
)
from ..config import FONT_SIZES


def render_zen(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    word: str,
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """渲染 ZEN 模式"""
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        dashed=True, time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font = load_font("noto_serif_regular", FONT_SIZES["zen"]["word"])
    bbox = font.getbbox(word)
    char_w = bbox[2] - bbox[0]
    char_h = bbox[3] - bbox[1]
    x = (screen_w - char_w) // 2
    y = (screen_h - char_h) // 2 - 10
    draw.text((x, y), word, fill=EINK_FG, font=font)

    draw_footer(
        draw, img, "ZEN", "— ...",
        dashed=True, screen_w=screen_w, screen_h=screen_h,
    )

    return img
