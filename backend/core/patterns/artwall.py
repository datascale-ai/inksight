"""
ARTWALL 模式 - AI 艺术画廊
使用文生图模型生成黑白版画风格的艺术作品
"""

import logging
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

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
import httpx
import io


def render_artwall(
    date_str: str,
    weather_str: str,
    battery_pct: int,
    artwork_title: str,
    image_url: str = "",
    description: str = "",
    model_name: str = "qwen-image-max",
    weather_code: int = -1,
    time_str: str = "",
) -> Image.Image:
    """
    渲染 ARTWALL 模式

    Args:
        artwork_title: 作品标题
        image_url: 生成的图像 URL
        description: 作品描述
        model_name: 生成图像的模型名称
    """
    img = Image.new("1", (SCREEN_W, SCREEN_H), EINK_BG)
    draw = ImageDraw.Draw(img)

    draw_status_bar(
        draw, img, date_str, weather_str, battery_pct, weather_code, time_str=time_str
    )

    font_title = load_font("noto_serif_regular", 12)
    font_source = load_font("noto_serif_light", 11)

    if image_url:
        try:
            import httpx
            response = httpx.get(image_url, timeout=30.0)
            if response.status_code == 200:
                artwork_img = Image.open(io.BytesIO(response.content))
                
                artwork_img = artwork_img.convert("L")
                
                target_size_w = 400
                target_size_h = 220
                artwork_img = artwork_img.resize((target_size_w, target_size_h), Image.LANCZOS)
                
                threshold = 128
                artwork_img = artwork_img.point(lambda x: 0 if x < threshold else 255, '1')
                
                img_x = (SCREEN_W - target_size_w) // 2
                img_y = (SCREEN_H - target_size_h) // 2
                img.paste(artwork_img, (img_x, img_y))
                
                y_line = SCREEN_H - 30
                draw.line([(0, y_line), (SCREEN_W, y_line)], fill=EINK_FG, width=1)
                
                art_icon = load_icon("art", size=(12, 12))
                if art_icon:
                    img.paste(art_icon, (12, y_line + 9))
                
                font_label = load_font("inter_medium", 8)
                draw.text((27, y_line + 9), "ARTWALL", fill=EINK_FG, font=font_label)
                
                title_lines = wrap_text(artwork_title, font_title, SCREEN_W - 120)
                if title_lines:
                    draw.text((SCREEN_W - 12 - font_title.getbbox(title_lines[0])[2], y_line + 9), title_lines[0], fill=EINK_FG, font=font_title)
                
                return img
        except Exception as e:
            logger.error(f"[ARTWALL] Failed to load image: {e}")
    
    y = 80
    
    title_lines = wrap_text(artwork_title, font_title, SCREEN_W - 48)
    for line in title_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x = (SCREEN_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=EINK_FG, font=font_title)
        y += 20

    y += 20

    if description:
        font_desc = load_font("noto_serif_light", 10)
        desc_lines = wrap_text(description, font_desc, SCREEN_W - 48)
        for line in desc_lines[:5]:
            if y > SCREEN_H - 60:
                break
            bbox = draw.textbbox((0, 0), line, font=font_desc)
            x = (SCREEN_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill=EINK_FG, font=font_desc)
            y += 16

    draw_footer(draw, img, "ARTWALL", "AI Art")

    return img

