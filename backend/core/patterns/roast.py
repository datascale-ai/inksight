"""
ROAST 模式 - 毒舌吐槽
显示犀利的中文吐槽，缓解压力
"""

from PIL import Image, ImageDraw
from .utils import (
    SCREEN_W,
    SCREEN_H,
    EINK_BG,
    EINK_FG,
    draw_status_bar,
    draw_footer,
    render_quote_body,
)
from ..config import FONT_SIZES


def render_roast(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    quote: str,
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """渲染 ROAST 模式"""
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        line_width=2, time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )
    render_quote_body(
        draw, quote, "NotoSerifSC-Bold.ttf", FONT_SIZES["roast"]["quote"],
        screen_w=screen_w, screen_h=screen_h,
    )
    draw_footer(
        draw, img, "ROAST", "— InkSight AI",
        line_width=2, screen_w=screen_w, screen_h=screen_h,
    )

    return img
