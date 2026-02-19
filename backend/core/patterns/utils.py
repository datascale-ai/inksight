"""
渲染工具函数
提供所有模式共用的基础渲染功能
"""
from __future__ import annotations

import logging
import os
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)
from ..config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    EINK_BACKGROUND,
    EINK_FOREGROUND,
    WEATHER_ICON_MAP,
    MODE_ICON_MAP,
    ICON_SIZES,
    FONTS,
    FONT_SIZES,
)

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
ICONS_DIR = os.path.join(FONTS_DIR, "icons")

SCREEN_W = SCREEN_WIDTH
SCREEN_H = SCREEN_HEIGHT
EINK_BG = EINK_BACKGROUND
EINK_FG = EINK_FOREGROUND

_font_warned: set[str] = set()


def load_font(font_key: str, size: int) -> ImageFont.FreeTypeFont:
    """从配置加载字体"""
    font_name = FONTS.get(font_key)
    if not font_name:
        return ImageFont.load_default()
    path = os.path.join(FONTS_DIR, font_name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    if font_key not in _font_warned:
        _font_warned.add(font_key)
        logger.warning(f"[FONT] Missing {font_name}, run: python scripts/setup_fonts.py")
    return ImageFont.load_default()


def load_font_by_name(name: str, size: int) -> ImageFont.FreeTypeFont:
    """直接通过文件名加载字体（兼容旧代码）"""
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    if name not in _font_warned:
        _font_warned.add(name)
        logger.warning(f"[FONT] Missing {name}, run: python scripts/setup_fonts.py")
    return ImageFont.load_default()


def rgba_to_mono(
    img: Image.Image, target_size: tuple[int, int] | None = None
) -> Image.Image:
    """Convert an RGBA icon to monochrome (mode '1'), optionally resizing."""
    if target_size:
        img = img.resize(target_size, Image.LANCZOS)
    img = img.convert("RGBA")
    mono = Image.new("1", img.size, 1)
    for x in range(img.width):
        for y in range(img.height):
            _, _, _, a = img.getpixel((x, y))
            if a > 128:
                mono.putpixel((x, y), 0)
    return mono


def load_icon(name: str, size: tuple[int, int] | None = None) -> Image.Image | None:
    """Load a PNG icon from ICONS_DIR, convert to monochrome, optionally resize."""
    path = os.path.join(ICONS_DIR, f"{name}.png")
    if os.path.exists(path):
        img = Image.open(path)
        if img.mode == "1":
            if size:
                img = img.resize(size, Image.LANCZOS)
            return img
        return rgba_to_mono(img, size)
    return None


def get_weather_icon(weather_code: int) -> Image.Image | None:
    """Get weather icon image by WMO weather code."""
    icon_name = WEATHER_ICON_MAP.get(weather_code, "cloud")
    return load_icon(icon_name, size=ICON_SIZES["weather"])


def get_mode_icon(mode: str) -> Image.Image | None:
    """Get footer mode icon (book, electric_bolt, etc.)."""
    icon_name = MODE_ICON_MAP.get(mode.upper())
    if icon_name:
        return load_icon(icon_name, size=ICON_SIZES["mode"])
    return None


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple,
    end: tuple,
    fill=0,
    width: int = 1,
    dash_len: int = 4,
    gap_len: int = 4,
):
    """Draw a horizontal dashed line (for zen/faded style)."""
    x0, y0 = start
    x1, _ = end
    x = x0
    while x < x1:
        seg_end = min(x + dash_len, x1)
        draw.line([(x, y0), (seg_end, y0)], fill=fill, width=width)
        x += dash_len + gap_len


def draw_status_bar(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    date_str: str,
    weather_str: str,
    battery_pct: int,
    weather_code: int = -1,
    line_width: int = 1,
    dashed: bool = False,
    time_str: str = "",
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
):
    """绘制顶部状态栏"""
    font_cn = load_font("noto_serif_extralight", FONT_SIZES["status_bar"]["cn"])
    font_en = load_font("inter_medium", FONT_SIZES["status_bar"]["en"])

    y = 10
    x = 12
    if time_str:
        draw.text((x, y), time_str, fill=EINK_FG, font=font_cn)
        bbox_time = draw.textbbox((0, 0), time_str, font=font_cn)
        x += (bbox_time[2] - bbox_time[0]) + 8
    draw.text((x, y), date_str, fill=EINK_FG, font=font_cn)

    wx = screen_w // 2 - 28
    weather_icon = get_weather_icon(weather_code) if weather_code >= 0 else None
    if weather_icon:
        img.paste(weather_icon, (wx, y - 1))
        draw.text((wx + 18, y), weather_str, fill=EINK_FG, font=font_cn)
    else:
        draw.text((wx, y), weather_str, fill=EINK_FG, font=font_cn)

    batt_text = f"{battery_pct}%"
    bbox = draw.textbbox((0, 0), batt_text, font=font_en)
    batt_text_w = bbox[2] - bbox[0]

    bx = screen_w - 12 - batt_text_w - 6 - 26
    by = y + 1
    draw.rectangle([bx, by, bx + 22, by + 11], outline=EINK_FG, width=1)
    draw.rectangle([bx + 22, by + 3, bx + 24, by + 8], fill=EINK_FG)
    fill_w = int(18 * battery_pct / 100)
    if fill_w > 0:
        draw.rectangle([bx + 2, by + 2, bx + 2 + fill_w, by + 9], fill=EINK_FG)

    draw.text((bx + 28, y), batt_text, fill=EINK_FG, font=font_en)

    if dashed:
        draw_dashed_line(draw, (0, 32), (screen_w, 32), fill=EINK_FG, width=line_width)
    else:
        draw.line([(0, 32), (screen_w, 32)], fill=EINK_FG, width=line_width)


def has_cjk(text: str) -> bool:
    """Check if text contains CJK (Chinese/Japanese/Korean) characters."""
    return any("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" for ch in text)


def draw_footer(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    mode: str,
    attribution: str,
    line_width: int = 1,
    dashed: bool = False,
    attr_font: str | None = None,
    attr_font_size: int | None = None,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
):
    """绘制底部页脚"""
    if attr_font_size is None:
        attr_font_size = FONT_SIZES["footer"]["attribution"]

    y_line = screen_h - 30
    if dashed:
        draw_dashed_line(
            draw, (0, y_line), (screen_w, y_line), fill=EINK_FG, width=line_width
        )
    else:
        draw.line([(0, y_line), (screen_w, y_line)], fill=EINK_FG, width=line_width)

    font_label = load_font("inter_medium", FONT_SIZES["footer"]["label"])
    if attr_font:
        font_attr = load_font_by_name(attr_font, attr_font_size)
    elif attribution and has_cjk(attribution):
        font_attr = load_font("noto_serif_light", attr_font_size)
    else:
        font_attr = load_font("lora_regular", attr_font_size)

    icon_x = 12
    icon_y = y_line + 9
    mode_icon = get_mode_icon(mode)
    if mode_icon:
        img.paste(mode_icon, (icon_x, icon_y))
        label_x = icon_x + 15
    else:
        label_x = icon_x
    draw.text((label_x, y_line + 9), mode.upper(), fill=EINK_FG, font=font_label)

    if attribution:
        bbox = draw.textbbox((0, 0), attribution, font=font_attr)
        draw.text(
            (screen_w - 12 - (bbox[2] - bbox[0]), y_line + 9),
            attribution,
            fill=EINK_FG,
            font=font_attr,
        )


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """文本换行"""
    lines = []
    for paragraph in text.split("\n"):
        words = list(paragraph)
        current = ""
        for ch in words:
            test = current + ch
            bbox = font.getbbox(test)
            if bbox[2] > max_width:
                if current:
                    lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
    return lines


def render_quote_body(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    font_size: int,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
):
    """渲染居中的引用文本"""
    if has_cjk(text) and "Noto" not in font_name:
        font_name = "NotoSerifSC-Light.ttf"
    font = load_font_by_name(font_name, font_size)
    lines = wrap_text(text, font, screen_w - 48)
    line_h = font_size + 8
    total_h = len(lines) * line_h
    y_start = 32 + (screen_h - 32 - 30 - total_h) // 2

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        x = (screen_w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_start + i * line_h), line, fill=EINK_FG, font=font)
