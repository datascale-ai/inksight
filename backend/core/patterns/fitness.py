"""
FITNESS 模式 - 健身计划
展示一套简单的健身训练计划
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
    load_icon,
)


def render_fitness(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    workout_name: str,
    duration: str,
    exercises: list[dict],
    tip: str = "",
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """
    渲染 FITNESS 模式

    Args:
        workout_name: 训练名称
        duration: 总时长
        exercises: 动作列表 [{"name": str, "reps": str}, ...]
        tip: 健康提示
    """
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code,
        time_str=time_str, screen_w=screen_w, screen_h=screen_h,
    )

    font_title = load_font("noto_serif_bold", 16)
    font_subtitle = load_font("noto_serif_regular", 14)
    font_content = load_font("noto_serif_regular", 13)
    font_tip = load_font("noto_serif_light", 14)

    y = 50

    bbox = draw.textbbox((0, 0), workout_name, font=font_title)
    x = (screen_w - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), workout_name, fill=EINK_FG, font=font_title)
    y += 22

    bbox = draw.textbbox((0, 0), duration, font=font_subtitle)
    x = (screen_w - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), duration, fill=EINK_FG, font=font_subtitle)
    y += 20

    draw.line([(24, y), (screen_w - 24, y)], fill=EINK_FG, width=1)
    y += 12

    exercise_icon = load_icon("exercise", size=(12, 12))
    if exercise_icon:
        img.paste(exercise_icon, (24, y))

    draw.text((40, y), "训练动作", fill=EINK_FG, font=font_subtitle)
    y += 16

    for i, exercise in enumerate(exercises[:8], 1):
        name = exercise.get("name", "")
        reps = exercise.get("reps", "")

        text = f"{i}. {name}"
        lines = wrap_text(text, font_content, screen_w - 120)
        for line in lines[:1]:
            draw.text((32, y), line, fill=EINK_FG, font=font_content)

        draw.text((screen_w - 80, y), reps, fill=EINK_FG, font=font_content)
        y += 16

    if tip:
        y += 12
        draw.line([(24, y), (screen_w - 24, y)], fill=EINK_FG, width=1)
        y += 10

        tips_icon = load_icon("tips", size=(12, 12))
        if tips_icon:
            img.paste(tips_icon, (24, y))

        tip_lines = wrap_text(tip, font_tip, screen_w - 48)
        for line in tip_lines[:3]:
            if y > screen_h - 60:
                break
            draw.text((40, y), line, fill=EINK_FG, font=font_tip)
            y += 13

    y_line = screen_h - 30
    draw.line([(0, y_line), (screen_w, y_line)], fill=EINK_FG, width=1)

    body_icon = load_icon("body", size=(12, 12))
    if body_icon:
        img.paste(body_icon, (12, y_line + 9))

    font_label = load_font("inter_medium", 8)
    draw.text((27, y_line + 9), "FITNESS", fill=EINK_FG, font=font_label)

    font_attr = load_font("noto_serif_light", 12)
    attr_text = "Stay Healthy"
    bbox = draw.textbbox((0, 0), attr_text, font=font_attr)
    draw.text((screen_w - 12 - (bbox[2] - bbox[0]), y_line + 9), attr_text, fill=EINK_FG, font=font_attr)

    return img
