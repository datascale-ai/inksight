"""
POETRY 模式 - 每日古诗词
展示一首与当前季节、天气相关的中国古诗词
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
    wrap_text,
)


def render_poetry(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    title: str,
    author: str,
    lines: list[str],
    note: str = "",
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """
    渲染 POETRY 模式

    Args:
        title: 诗名
        author: 朝代·作者
        lines: 诗句列表
        note: 一句话赏析
    """
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        dashed=True, time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font_title = load_font("noto_serif_bold", 14)
    font_author = load_font("noto_serif_light", 11)
    font_line = load_font("noto_serif_regular", 16)
    font_note = load_font("noto_serif_light", 10)

    y = 46

    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((screen_w - tw) // 2, y), title, fill=EINK_FG, font=font_title)
    y += 22

    bbox = draw.textbbox((0, 0), author, font=font_author)
    aw = bbox[2] - bbox[0]
    draw.text(((screen_w - aw) // 2, y), author, fill=EINK_FG, font=font_author)
    y += 22

    line_w = 60
    line_x = (screen_w - line_w) // 2
    draw.line([(line_x, y), (line_x + line_w, y)], fill=EINK_FG, width=1)
    y += 16

    max_lines = 8
    for i, verse in enumerate(lines[:max_lines]):
        if y > screen_h - 70:
            break
        verse_lines = wrap_text(verse, font_line, screen_w - 60)
        for vl in verse_lines[:1]:
            bbox = draw.textbbox((0, 0), vl, font=font_line)
            vw = bbox[2] - bbox[0]
            draw.text(((screen_w - vw) // 2, y), vl, fill=EINK_FG, font=font_line)
            y += 24

    if note and y < screen_h - 50:
        y = max(y + 8, screen_h - 60)
        note_lines = wrap_text(note, font_note, screen_w - 60)
        for nl in note_lines[:2]:
            bbox = draw.textbbox((0, 0), nl, font=font_note)
            nw = bbox[2] - bbox[0]
            draw.text(((screen_w - nw) // 2, y), nl, fill=EINK_FG, font=font_note)
            y += 14

    draw_footer(
        draw, img, "POETRY", f"— {author}",
        dashed=True, screen_w=screen_w, screen_h=screen_h,
    )

    return img
