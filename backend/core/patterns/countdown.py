"""
COUNTDOWN 模式 - 重要日倒计时 / 正计日
纯日期计算，无需 LLM 调用
"""

import datetime
import logging
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

logger = logging.getLogger(__name__)


def render_countdown(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    events: list[dict],
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """
    渲染 COUNTDOWN 模式

    Args:
        events: 事件列表 [{"name": str, "date": "YYYY-MM-DD", "type": "countdown"|"countup", "days": int}, ...]
                events should be pre-processed with "days" field computed.
    """
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font_label = load_font("noto_serif_regular", 12)
    font_name = load_font("noto_serif_regular", 14)
    font_days_big = load_font("noto_serif_bold", 48)
    font_days_unit = load_font("noto_serif_regular", 14)
    font_small = load_font("noto_serif_light", 10)

    if not events:
        msg = "暂无倒计时事件"
        bbox = draw.textbbox((0, 0), msg, font=font_label)
        mw = bbox[2] - bbox[0]
        draw.text(((screen_w - mw) // 2, screen_h // 2 - 10), msg, fill=EINK_FG, font=font_label)
        draw_footer(draw, img, "COUNTDOWN", "", screen_w=screen_w, screen_h=screen_h)
        return img

    y = 42

    display_events = events[:3]

    if len(display_events) == 1:
        evt = display_events[0]
        name = evt.get("name", "")
        days = evt.get("days", 0)
        evt_type = evt.get("type", "countdown")
        target_date = evt.get("date", "")

        y = 60

        bbox = draw.textbbox((0, 0), name, font=font_name)
        nw = bbox[2] - bbox[0]
        draw.text(((screen_w - nw) // 2, y), name, fill=EINK_FG, font=font_name)
        y += 28

        if evt_type == "countdown":
            prefix = "还有"
            suffix = "天"
        else:
            prefix = "已经"
            suffix = "天"

        bbox_p = draw.textbbox((0, 0), prefix, font=font_label)
        pw = bbox_p[2] - bbox_p[0]
        draw.text(((screen_w - pw) // 2, y), prefix, fill=EINK_FG, font=font_label)
        y += 20

        days_str = str(abs(days))
        bbox_d = draw.textbbox((0, 0), days_str, font=font_days_big)
        dw = bbox_d[2] - bbox_d[0]
        dh = bbox_d[3] - bbox_d[1]
        dx = (screen_w - dw) // 2
        draw.text((dx, y), days_str, fill=EINK_FG, font=font_days_big)

        draw.text((dx + dw + 4, y + dh - 20), suffix, fill=EINK_FG, font=font_days_unit)
        y += dh + 16

        if target_date:
            bbox_t = draw.textbbox((0, 0), target_date, font=font_small)
            tw = bbox_t[2] - bbox_t[0]
            draw.text(((screen_w - tw) // 2, y), target_date, fill=EINK_FG, font=font_small)

    else:
        y = 48

        draw.text((24, y), "重要日子", fill=EINK_FG, font=font_label)
        y += 18
        draw.line([(24, y), (screen_w - 24, y)], fill=EINK_FG, width=1)
        y += 14

        font_evt_name = load_font("noto_serif_regular", 13)
        font_evt_days = load_font("noto_serif_bold", 28)
        font_evt_unit = load_font("noto_serif_regular", 11)

        for evt in display_events:
            if y > screen_h - 55:
                break

            name = evt.get("name", "")
            days = evt.get("days", 0)
            evt_type = evt.get("type", "countdown")
            target_date = evt.get("date", "")

            draw.text((32, y), name, fill=EINK_FG, font=font_evt_name)

            days_str = str(abs(days))
            label = "还有" if evt_type == "countdown" else "已经"
            unit = "天"

            bbox_d = draw.textbbox((0, 0), days_str, font=font_evt_days)
            dw = bbox_d[2] - bbox_d[0]
            bbox_u = draw.textbbox((0, 0), unit, font=font_evt_unit)
            uw = bbox_u[2] - bbox_u[0]

            right_x = screen_w - 32
            draw.text((right_x - dw - uw - 4, y - 4), days_str, fill=EINK_FG, font=font_evt_days)
            draw.text((right_x - uw, y + 10), unit, fill=EINK_FG, font=font_evt_unit)

            y += 18

            meta = f"{label} · {target_date}"
            draw.text((32, y), meta, fill=EINK_FG, font=font_small)

            y += 24

            if evt != display_events[-1]:
                for x in range(32, screen_w - 32, 6):
                    draw.line([(x, y), (min(x + 3, screen_w - 32), y)], fill=EINK_FG, width=1)
                y += 10

    draw_footer(draw, img, "COUNTDOWN", "", screen_w=screen_w, screen_h=screen_h)

    return img
