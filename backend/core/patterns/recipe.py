"""
RECIPE 模式 - 每日食谱
展示早中晚三餐方案
"""

from PIL import Image, ImageDraw
from .utils import (
    SCREEN_W,
    SCREEN_H,
    EINK_BG,
    EINK_FG,
    draw_status_bar,
    load_font,
    wrap_text,
    load_icon,
)


def render_recipe(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    season: str,
    breakfast: str,
    lunch: dict,
    dinner: dict,
    nutrition: str,
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """
    渲染 RECIPE 模式 - 早中晚三餐方案

    Args:
        season: 时令（如：立春·二月）
        breakfast: 早餐内容
        lunch: 午餐 {meat, veg, staple}
        dinner: 晚餐 {meat, veg, staple}
        nutrition: 营养标注
    """
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font_all = load_font("noto_serif_regular", 13)
    font_label = load_font("inter_medium", 8)

    y = 38

    food_icon = load_icon("food", size=(16, 16))
    if food_icon:
        img.paste(food_icon, (12, y - 1))

    draw.text((32, y), "今日食谱", fill=EINK_FG, font=font_all)

    season_text = f"时令: {season}"
    bbox = draw.textbbox((0, 0), season_text, font=font_all)
    draw.text((screen_w - 12 - (bbox[2] - bbox[0]), y), season_text, fill=EINK_FG, font=font_all)

    y += 28

    breakfast_icon = load_icon("breakfast", size=(16, 16))
    if breakfast_icon:
        img.paste(breakfast_icon, (12, y - 1))
    draw.text((32, y), "早餐", fill=EINK_FG, font=font_all)
    y += 18

    parts = breakfast.split("·")
    x = 12
    for i, part in enumerate(parts):
        part = part.strip()

        if i == 0:
            cookie_icon = load_icon("cookie", size=(12, 12))
            if cookie_icon:
                img.paste(cookie_icon, (x, y + 1))
                x += 16

        draw.text((x, y), part, fill=EINK_FG, font=font_all)
        bbox = draw.textbbox((0, 0), part, font=font_all)
        x += (bbox[2] - bbox[0]) + 4

        if i == 2:
            cookie_icon = load_icon("cookie", size=(12, 12))
            if cookie_icon:
                img.paste(cookie_icon, (x, y + 1))
                x += 16

        if i < len(parts) - 1:
            draw.text((x, y), "·", fill=EINK_FG, font=font_all)
            x += 12

    y += 28

    lunch_icon = load_icon("lunch", size=(16, 16))
    if lunch_icon:
        img.paste(lunch_icon, (12, y - 1))
    draw.text((32, y), "午餐", fill=EINK_FG, font=font_all)
    y += 18

    x = 12
    meat_icon = load_icon("meat", size=(16, 16))
    if meat_icon:
        img.paste(meat_icon, (x, y - 1))
    x += 20
    draw.text((x, y), lunch["meat"], fill=EINK_FG, font=font_all)
    bbox = draw.textbbox((0, 0), lunch["meat"], font=font_all)
    x += (bbox[2] - bbox[0]) + 16

    veg_icon = load_icon("vegetable", size=(16, 16))
    if veg_icon:
        img.paste(veg_icon, (x, y - 1))
    x += 20
    draw.text((x, y), lunch["veg"], fill=EINK_FG, font=font_all)
    bbox = draw.textbbox((0, 0), lunch["veg"], font=font_all)
    x += (bbox[2] - bbox[0]) + 16

    rice_icon = load_icon("rice", size=(16, 16))
    if rice_icon:
        img.paste(rice_icon, (x, y - 1))
    x += 20
    draw.text((x, y), lunch["staple"], fill=EINK_FG, font=font_all)

    y += 28

    dinner_icon = load_icon("dinner", size=(16, 16))
    if dinner_icon:
        img.paste(dinner_icon, (12, y - 1))
    draw.text((32, y), "晚餐", fill=EINK_FG, font=font_all)
    y += 18

    x = 12
    meat_icon = load_icon("meat", size=(16, 16))
    if meat_icon:
        img.paste(meat_icon, (x, y - 1))
    x += 20
    draw.text((x, y), dinner["meat"], fill=EINK_FG, font=font_all)
    bbox = draw.textbbox((0, 0), dinner["meat"], font=font_all)
    x += (bbox[2] - bbox[0]) + 16

    veg_icon = load_icon("vegetable", size=(16, 16))
    if veg_icon:
        img.paste(veg_icon, (x, y - 1))
    x += 20
    draw.text((x, y), dinner["veg"], fill=EINK_FG, font=font_all)
    bbox = draw.textbbox((0, 0), dinner["veg"], font=font_all)
    x += (bbox[2] - bbox[0]) + 16

    is_soup = "汤" in dinner["staple"]
    staple_icon = load_icon("soup" if is_soup else "rice", size=(16, 16))
    if staple_icon:
        img.paste(staple_icon, (x, y - 1))
    x += 20
    draw.text((x, y), dinner["staple"], fill=EINK_FG, font=font_all)

    y += 28

    vital_icon = load_icon("vital", size=(16, 16))
    if vital_icon:
        img.paste(vital_icon, (12, y - 1))

    draw.text((32, y), "营养:", fill=EINK_FG, font=font_all)
    y += 18

    nutrition_items = nutrition.split()
    x = 12
    for item in nutrition_items:
        draw.text((x, y), item, fill=EINK_FG, font=font_all)
        bbox = draw.textbbox((0, 0), item, font=font_all)
        x += (bbox[2] - bbox[0]) + 12

        if x > screen_w - 60:
            y += 16
            x = 12

    y_line = screen_h - 30
    draw.line([(0, y_line), (screen_w, y_line)], fill=EINK_FG, width=1)

    food_icon_footer = load_icon("food", size=(12, 12))
    if food_icon_footer:
        img.paste(food_icon_footer, (12, y_line + 9))

    draw.text((27, y_line + 9), "RECIPE", fill=EINK_FG, font=font_label)

    attr_text = "荤素搭配 · 营养均衡"
    bbox = draw.textbbox((0, 0), attr_text, font=font_all)
    draw.text((screen_w - 12 - (bbox[2] - bbox[0]), y_line + 9), attr_text, fill=EINK_FG, font=font_all)

    return img
