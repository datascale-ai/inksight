"""
BRIEFING 模式 - 科技简报
展示 Hacker News 热榜、Product Hunt 新品和行业洞察
"""
from __future__ import annotations

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
    load_icon,
)


def render_briefing(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    hn_items: list[dict],
    ph_item: dict,
    insight: str = "",
    v2ex_items: list[dict] | None = None,
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """
    渲染 BRIEFING 模式

    Args:
        hn_items: Hacker News 热榜列表 [{"title": str, "score": int, "summary": str}, ...]
        ph_item: Product Hunt 产品 {"name": str, "tagline": str}
        insight: 行业洞察
        v2ex_items: V2EX 热帖列表 [{"title": str, "node": str}, ...]
    """
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font_cn = load_font("noto_serif_regular", 12)
    font_en = load_font("inter_medium", 12)

    y = 40

    draw.text((24, y), "AI简报", fill=EINK_FG, font=font_cn)
    y += 16
    draw.line([(24, y), (screen_w - 24, y)], fill=EINK_FG, width=1)
    y += 20

    # ── Hacker News TOP 2 ──
    star_icon = load_icon("star", size=(20, 20))
    if star_icon:
        img.paste(star_icon, (20, y - 2))
    draw.text((40, y), "Hacker News TOP 2", fill=EINK_FG, font=font_en)
    y += 18

    for i, item in enumerate(hn_items[:2], 1):
        title = item.get("summary") or item.get("title", "")
        title_lines = wrap_text(f"{i}. {title}", font_cn, screen_w - 56)
        for line in title_lines[:2]:
            draw.text((32, y), line, fill=EINK_FG, font=font_cn)
            y += 15

    # ── V2EX Hot ──
    if v2ex_items:
        y += 6
        for x in range(24, screen_w - 24, 6):
            draw.line([(x, y), (min(x + 3, screen_w - 24), y)], fill=EINK_FG, width=1)
        y += 10

        draw.text((24, y), "V2EX 热议", fill=EINK_FG, font=font_cn)
        y += 18
        for item in v2ex_items[:1]:
            v_title = item.get("title", "")
            node = item.get("node", "")
            prefix = f"[{node}] " if node else ""
            v_lines = wrap_text(f"{prefix}{v_title}", font_cn, screen_w - 56)
            for line in v_lines[:2]:
                draw.text((32, y), line, fill=EINK_FG, font=font_cn)
                y += 15

    y += 6
    for x in range(24, screen_w - 24, 6):
        draw.line([(x, y), (min(x + 3, screen_w - 24), y)], fill=EINK_FG, width=1)
    y += 10

    # ── Product Hunt ──
    flag_icon = load_icon("flag", size=(20, 20))
    if flag_icon:
        img.paste(flag_icon, (20, y - 2))
    draw.text((40, y), "Product Hunt 今日推荐", fill=EINK_FG, font=font_cn)
    y += 22

    if ph_item:
        name = ph_item.get("name", "N/A")
        tagline = ph_item.get("tagline", "")
        content = f"{name}: {tagline}" if tagline else name
        content_lines = wrap_text(content, font_cn, screen_w - 56)
        for line in content_lines[:2]:
            draw.text((32, y), line, fill=EINK_FG, font=font_cn)
            y += 15

    y += 12

    # ── AI Insight ──
    if insight:
        draw.text((24, y), "AI Insight", fill=EINK_FG, font=font_en)
        y += 18
        insight_lines = wrap_text(insight, font_cn, screen_w - 56)
        for line in insight_lines:
            if y > screen_h - 35:
                break
            draw.text((32, y), line, fill=EINK_FG, font=font_cn)
            y += 15

    draw_footer(
        draw, img, "BRIEFING", "via HN / V2EX / PH",
        screen_w=screen_w, screen_h=screen_h,
    )

    return img
