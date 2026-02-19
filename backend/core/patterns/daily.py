"""
DAILY 模式 - 每日推荐
显示包含语录、书籍推荐、冷知识、节气信息的丰富排版内容
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
from ..config import FONT_SIZES, DAILY_LAYOUT


def render_daily(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    year: int,
    day: int,
    month_cn: str,
    weekday_cn: str,
    day_of_year: int,
    days_in_year: int,
    quote: str,
    author: str,
    book_title: str,
    book_author: str,
    book_desc: str,
    tip_label: str,
    tip: str,
    season_text: str = "",
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """渲染 DAILY 模式：左侧日期列 + 右侧内容区"""
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    TOP = 33
    BOT = screen_h - 30
    LEFT_W = DAILY_LAYOUT["left_column_width"]
    RIGHT_X = LEFT_W + 1

    draw.line([(LEFT_W, TOP), (LEFT_W, BOT)], fill=EINK_FG, width=1)

    # ==================== LEFT COLUMN ====================
    cx = LEFT_W // 2

    font_year = load_font("inter_medium", FONT_SIZES["daily"]["year"])
    font_day = load_font("lora_bold", FONT_SIZES["daily"]["day"])
    font_month = load_font("noto_serif_regular", FONT_SIZES["daily"]["month"])
    font_weekday = load_font("noto_serif_regular", FONT_SIZES["daily"]["weekday"])
    font_progress = load_font("noto_serif_light", FONT_SIZES["daily"]["progress"])

    year_str = str(year)
    day_str = str(day)

    bbox_year = font_year.getbbox(year_str)
    h_year = bbox_year[3] - bbox_year[1]
    bbox_day = font_day.getbbox(day_str)
    h_day = bbox_day[3] - bbox_day[1]
    bbox_month = font_month.getbbox(month_cn)
    h_month = bbox_month[3] - bbox_month[1]
    bbox_wk = font_weekday.getbbox(weekday_cn)
    h_wk = bbox_wk[3] - bbox_wk[1]

    gaps = DAILY_LAYOUT["gaps"]
    h_bar = 3
    progress_text = f"第{day_of_year}天 / {days_in_year}"
    bbox_pt = font_progress.getbbox(progress_text)
    h_pt = bbox_pt[3] - bbox_pt[1]

    total_h = (
        h_year
        + gaps["year_to_day"]
        + h_day
        + gaps["day_to_month"]
        + h_month
        + gaps["month_to_weekday"]
        + h_wk
        + gaps["weekday_to_progress"]
        + h_bar
        + gaps["bar_to_text"]
        + h_pt
    )
    y = TOP + (BOT - TOP - total_h) // 2

    w = bbox_year[2] - bbox_year[0]
    draw.text((cx - w // 2, y), year_str, fill=EINK_FG, font=font_year)
    y += h_year + gaps["year_to_day"]

    w = bbox_day[2] - bbox_day[0]
    draw.text((cx - w // 2, y), day_str, fill=EINK_FG, font=font_day)
    y += h_day + gaps["day_to_month"]

    w = bbox_month[2] - bbox_month[0]
    draw.text((cx - w // 2, y), month_cn, fill=EINK_FG, font=font_month)
    y += h_month + gaps["month_to_weekday"]

    w = bbox_wk[2] - bbox_wk[0]
    draw.text((cx - w // 2, y), weekday_cn, fill=EINK_FG, font=font_weekday)
    y += h_wk + gaps["weekday_to_progress"]

    bar_w = DAILY_LAYOUT["progress_bar_width"]
    bar_x = cx - bar_w // 2
    draw.rectangle([bar_x, y, bar_x + bar_w, y + h_bar], outline=EINK_FG, width=1)
    fill_w = int(bar_w * day_of_year / max(days_in_year, 1))
    if fill_w > 0:
        draw.rectangle([bar_x, y, bar_x + fill_w, y + h_bar], fill=EINK_FG)
    y += h_bar + gaps["bar_to_text"]

    w = bbox_pt[2] - bbox_pt[0]
    draw.text((cx - w // 2, y), progress_text, fill=EINK_FG, font=font_progress)

    # ==================== RIGHT COLUMN ====================
    rx = RIGHT_X + DAILY_LAYOUT["right_column_padding"]
    rw = screen_w - rx - 12
    ry = TOP + 8

    font_sec_title = load_font("noto_serif_bold", FONT_SIZES["daily"]["section_title"])
    font_quote = load_font("noto_serif_light", FONT_SIZES["daily"]["quote"])
    font_author = load_font("noto_serif_light", FONT_SIZES["daily"]["author"])
    font_book_title = load_font("noto_serif_bold", FONT_SIZES["daily"]["book_title"])
    font_book_info = load_font("noto_serif_light", FONT_SIZES["daily"]["book_info"])
    font_tip = load_font("noto_serif_light", FONT_SIZES["daily"]["tip"])

    draw.text((rx, ry), "/ 今日语录", fill=EINK_FG, font=font_sec_title)
    ry += 17

    q_lines = wrap_text(quote, font_quote, rw)
    for line in q_lines:
        draw.text((rx, ry), line, fill=EINK_FG, font=font_quote)
        ry += 20
    if author:
        author_text = f"— {author}"
        bbox_a = font_author.getbbox(author_text)
        aw = bbox_a[2] - bbox_a[0]
        draw.text((screen_w - 12 - aw, ry), author_text, fill=EINK_FG, font=font_author)
        ry += 17

    ry += 2
    draw.line([(rx, ry), (screen_w - 12, ry)], fill=EINK_FG, width=1)
    ry += 6

    draw.text((rx, ry), "/ 推荐阅读", fill=EINK_FG, font=font_sec_title)
    ry += 17

    bt_lines = wrap_text(book_title, font_book_title, rw)
    for line in bt_lines:
        draw.text((rx, ry), line, fill=EINK_FG, font=font_book_title)
        ry += 20
    draw.text((rx, ry), book_author, fill=EINK_FG, font=font_book_info)
    ry += 16
    bd_lines = wrap_text(book_desc, font_tip, rw)
    for line in bd_lines:
        draw.text((rx, ry), line, fill=EINK_FG, font=font_tip)
        ry += 16

    ry += 2
    draw.line([(rx, ry), (screen_w - 12, ry)], fill=EINK_FG, width=1)
    ry += 6

    draw.text((rx, ry), f"/ {tip_label}", fill=EINK_FG, font=font_sec_title)
    ry += 17

    tip_lines = wrap_text(tip, font_tip, rw)
    for line in tip_lines:
        if ry > BOT - 17:
            break
        draw.text((rx, ry), line, fill=EINK_FG, font=font_tip)
        ry += 16

    draw_footer(draw, img, "DAILY", season_text, screen_w=screen_w, screen_h=screen_h)

    return img
