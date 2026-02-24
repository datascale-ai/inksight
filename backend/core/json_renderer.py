"""
通用 JSON 模式渲染引擎
根据 JSON layout 定义将内容渲染为墨水屏图像
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from PIL import Image, ImageDraw

from .config import SCREEN_WIDTH, SCREEN_HEIGHT
from .patterns.utils import (
    EINK_BG,
    EINK_FG,
    draw_status_bar,
    draw_footer,
    draw_dashed_line,
    load_font,
    load_font_by_name,
    load_icon,
    wrap_text,
    has_cjk,
)

logger = logging.getLogger(__name__)

STATUS_BAR_BOTTOM = 36


@dataclass
class RenderContext:
    """Mutable state threaded through block renderers."""
    draw: ImageDraw.ImageDraw
    img: Image.Image
    content: dict
    screen_w: int = SCREEN_WIDTH
    screen_h: int = SCREEN_HEIGHT
    y: int = STATUS_BAR_BOTTOM
    x_offset: int = 0
    available_width: int = SCREEN_WIDTH

    def __post_init__(self):
        if self.available_width == SCREEN_WIDTH and self.screen_w != SCREEN_WIDTH:
            self.available_width = self.screen_w

    @property
    def footer_top(self) -> int:
        return self.screen_h - 30

    def resolve(self, template: str) -> str:
        """Resolve {field} placeholders against content dict."""
        def _replace(m: re.Match) -> str:
            key = m.group(1)
            val = self.content.get(key, "")
            if isinstance(val, list):
                return ", ".join(str(v) for v in val)
            return str(val)
        return re.sub(r"\{(\w+)\}", _replace, template)

    def get_field(self, name: str) -> Any:
        return self.content.get(name, "")

    @property
    def remaining_height(self) -> int:
        return self.footer_top - self.y


# ── Public API ───────────────────────────────────────────────


def render_json_mode(
    mode_def: dict,
    content: dict,
    *,
    date_str: str,
    weather_str: str,
    battery_pct: float,
    weather_code: int = -1,
    time_str: str = "",
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
) -> Image.Image:
    """Render a JSON-defined mode to a 1-bit e-ink image."""
    img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)
    layout = mode_def.get("layout", {})

    # 1. Status bar
    sb = layout.get("status_bar", {})
    draw_status_bar(
        draw, img, date_str, weather_str, int(battery_pct), weather_code,
        line_width=sb.get("line_width", 1),
        dashed=sb.get("dashed", False),
        time_str=time_str,
        screen_w=screen_w, screen_h=screen_h,
    )

    footer_top = screen_h - 30

    # 2. Body blocks
    ctx = RenderContext(
        draw=draw, img=img, content=content,
        screen_w=screen_w, screen_h=screen_h,
        y=STATUS_BAR_BOTTOM,
    )

    body = layout.get("body", [])
    _has_vcenter = any(
        b.get("type") == "centered_text" and b.get("vertical_center", True)
        for b in body
    )
    if _has_vcenter and len(body) == 1:
        _render_centered_text(ctx, body[0], use_full_body=True)
    else:
        for block in body:
            if ctx.y >= footer_top - 10:
                break
            _render_block(ctx, block)

    # 3. Footer
    ft = layout.get("footer", {})
    label = ft.get("label", mode_def.get("mode_id", ""))
    attribution = ctx.resolve(ft.get("attribution_template", "")) if ft.get("attribution_template") else ""
    draw_footer(
        draw, img, label, attribution,
        line_width=ft.get("line_width", 1),
        dashed=ft.get("dashed", False),
        attr_font_size=ft.get("font_size"),
        screen_w=screen_w, screen_h=screen_h,
    )

    return img


# ── Block dispatcher ─────────────────────────────────────────


_BLOCK_RENDERERS: dict[str, Any] = {}


def _render_block(ctx: RenderContext, block: dict) -> None:
    btype = block.get("type", "")
    renderer = _BLOCK_RENDERERS.get(btype)
    if renderer:
        renderer(ctx, block)
    else:
        logger.warning(f"[JSONRenderer] Unknown block type: {btype}")


# ── Block implementations ────────────────────────────────────


def _render_centered_text(ctx: RenderContext, block: dict, *, use_full_body: bool = False) -> None:
    field_name = block.get("field", "text")
    text = str(ctx.get_field(field_name))
    if not text:
        return

    font_size = block.get("font_size", 16)
    font_name = block.get("font_name")
    font_key = block.get("font", "noto_serif_light")
    max_ratio = block.get("max_width_ratio", 0.88)
    line_spacing = block.get("line_spacing", 8)

    if font_name:
        if has_cjk(text) and "Noto" not in font_name:
            font_name = "NotoSerifSC-Light.ttf"
        font = load_font_by_name(font_name, font_size)
    else:
        if has_cjk(text):
            font_key = "noto_serif_light"
        font = load_font(font_key, font_size)

    max_w = int(ctx.available_width * max_ratio)
    lines = wrap_text(text, font, max_w)
    line_h = font_size + line_spacing
    total_h = len(lines) * line_h

    if use_full_body and block.get("vertical_center", True):
        body_height = ctx.footer_top - STATUS_BAR_BOTTOM
        y_start = STATUS_BAR_BOTTOM + (body_height - total_h) // 2
    else:
        y_start = ctx.y

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        x = ctx.x_offset + (ctx.available_width - lw) // 2
        ctx.draw.text((x, y_start + i * line_h), line, fill=EINK_FG, font=font)

    ctx.y = y_start + total_h + 4


def _render_text(ctx: RenderContext, block: dict) -> None:
    template = block.get("template", "")
    field_name = block.get("field")
    if field_name:
        text = str(ctx.get_field(field_name))
    elif template:
        text = ctx.resolve(template)
    else:
        return

    if not text:
        return

    font_size = block.get("font_size", 14)
    font_key = block.get("font", "noto_serif_regular")
    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)

    align = block.get("align", "center")
    margin_x = block.get("margin_x", 24)
    max_lines = block.get("max_lines", 3)
    max_w = max(20, ctx.available_width - margin_x * 2)

    lines = wrap_text(text, font, max_w)

    for line in lines[:max_lines]:
        if ctx.y >= ctx.footer_top - 10:
            break
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        if align == "center":
            x = ctx.x_offset + (ctx.available_width - lw) // 2
        elif align == "right":
            x = ctx.x_offset + ctx.available_width - margin_x - lw
        else:
            x = ctx.x_offset + margin_x
        ctx.draw.text((x, ctx.y), line, fill=EINK_FG, font=font)
        ctx.y += font_size + 6


def _render_separator(ctx: RenderContext, block: dict) -> None:
    style = block.get("style", "solid")
    margin_x = block.get("margin_x", 24)
    line_width = block.get("line_width", 1)

    if style == "short":
        w = block.get("width", 60)
        x0 = ctx.x_offset + (ctx.available_width - w) // 2
        ctx.draw.line([(x0, ctx.y), (x0 + w, ctx.y)], fill=EINK_FG, width=line_width)
    elif style == "dashed":
        draw_dashed_line(ctx.draw, (ctx.x_offset + margin_x, ctx.y), (ctx.x_offset + ctx.available_width - margin_x, ctx.y),
                         fill=EINK_FG, width=line_width)
    else:
        ctx.draw.line([(ctx.x_offset + margin_x, ctx.y), (ctx.x_offset + ctx.available_width - margin_x, ctx.y)],
                      fill=EINK_FG, width=line_width)
    ctx.y += 8 + line_width


def _render_section(ctx: RenderContext, block: dict) -> None:
    title = block.get("title", "")
    icon_name = block.get("icon")
    title_font_key = block.get("title_font", "noto_serif_regular")
    title_font_size = block.get("title_font_size", 14)

    if has_cjk(title):
        title_font_key = _pick_cjk_font(title_font_key)
    font = load_font(title_font_key, title_font_size)

    x = ctx.x_offset + 24
    if icon_name:
        icon_img = load_icon(icon_name, size=(12, 12))
        if icon_img:
            ctx.img.paste(icon_img, (x, ctx.y))
            x += 16

    ctx.draw.text((x, ctx.y), title, fill=EINK_FG, font=font)
    ctx.y += title_font_size + 6

    for child in block.get("children", []):
        if ctx.y >= ctx.footer_top - 10:
            break
        _render_block(ctx, child)


def _render_list(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "")
    items = ctx.get_field(field_name)
    if not isinstance(items, list):
        return

    max_items = block.get("max_items", 8)
    template = block.get("item_template", "{name}")
    right_field = block.get("right_field")
    numbered = block.get("numbered", False)
    font_key = block.get("font", "noto_serif_regular")
    font_size = block.get("font_size", 13)
    spacing = block.get("item_spacing", 16)
    margin_x = block.get("margin_x", 32)

    align = block.get("align", "left")

    font = load_font(_pick_cjk_font(font_key), font_size)

    for i, item in enumerate(items[:max_items]):
        if ctx.y >= ctx.footer_top - 10:
            break

        if isinstance(item, dict):
            text = template
            for k, v in item.items():
                text = text.replace("{" + k + "}", str(v))
            text = text.replace("{_value}", str(item))
        else:
            text = str(item)
            if template and "{_value}" in template:
                text = template.replace("{_value}", str(item))

        if numbered:
            text = f"{i + 1}. {text}"
        text = text.replace("{index}", str(i + 1))

        max_text_w = ctx.available_width - margin_x * 2 if not right_field else ctx.available_width - margin_x - 80
        lines = wrap_text(text, font, max_text_w)

        if align == "center":
            for ln in lines[:1]:
                bbox = font.getbbox(ln)
                lw = bbox[2] - bbox[0]
                ctx.draw.text((ctx.x_offset + (ctx.available_width - lw) // 2, ctx.y), ln, fill=EINK_FG, font=font)
        else:
            for ln in lines[:1]:
                ctx.draw.text((ctx.x_offset + margin_x, ctx.y), ln, fill=EINK_FG, font=font)

        if right_field and isinstance(item, dict):
            rv = str(item.get(right_field, ""))
            if rv:
                ctx.draw.text((ctx.x_offset + ctx.available_width - 80, ctx.y), rv, fill=EINK_FG, font=font)

        ctx.y += spacing


def _render_vertical_stack(ctx: RenderContext, block: dict) -> None:
    spacing = block.get("spacing", 0)
    for child in block.get("children", []):
        if ctx.y >= ctx.footer_top - 10:
            break
        _render_block(ctx, child)
        ctx.y += spacing


def _render_conditional(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "")
    value = ctx.get_field(field_name)
    conditions = block.get("conditions", [])

    for cond in conditions:
        op = cond.get("op", "exists")
        cmp_val = cond.get("value")
        matched = False

        if op == "exists":
            matched = bool(value)
        elif op == "eq":
            matched = value == cmp_val
        elif op == "gt":
            matched = _num(value) > _num(cmp_val)
        elif op == "lt":
            matched = _num(value) < _num(cmp_val)
        elif op == "gte":
            matched = _num(value) >= _num(cmp_val)
        elif op == "lte":
            matched = _num(value) <= _num(cmp_val)
        elif op == "len_eq":
            matched = isinstance(value, (list, str)) and len(value) == _num(cmp_val)
        elif op == "len_gt":
            matched = isinstance(value, (list, str)) and len(value) > _num(cmp_val)

        if matched:
            for child in cond.get("children", []):
                _render_block(ctx, child)
            return

    for child in block.get("fallback_children", []):
        _render_block(ctx, child)


def _render_spacer(ctx: RenderContext, block: dict) -> None:
    ctx.y += block.get("height", 12)


def _render_icon_text(ctx: RenderContext, block: dict) -> None:
    icon_name = block.get("icon")
    field_name = block.get("field")
    text = str(ctx.get_field(field_name)) if field_name else block.get("text", "")
    text = ctx.resolve(text)
    if not text:
        return

    font_key = block.get("font", "noto_serif_regular")
    font_size = block.get("font_size", 14)
    icon_size = block.get("icon_size", 12)
    margin_x = block.get("margin_x", 24)

    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)

    x = ctx.x_offset + margin_x
    if icon_name:
        icon_img = load_icon(icon_name, size=(icon_size, icon_size))
        if icon_img:
            ctx.img.paste(icon_img, (x, ctx.y))
            x += icon_size + 4

    ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
    ctx.y += font_size + 6


def _render_big_number(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "")
    text = str(ctx.get_field(field_name))
    if not text:
        return
    font_size = block.get("font_size", 42)
    font_key = block.get("font", "lora_bold")
    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    align = block.get("align", "center")
    if align == "left":
        x = block.get("margin_x", 24)
    elif align == "right":
        x = ctx.screen_w - block.get("margin_x", 24) - tw
    else:
        x = (ctx.screen_w - tw) // 2
    ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
    ctx.y += font_size + 6


def _render_progress_bar(ctx: RenderContext, block: dict) -> None:
    value = _num(ctx.get_field(block.get("field", "")))
    max_value = max(_num(ctx.get_field(block.get("max_field", ""))), 1)
    ratio = max(0.0, min(1.0, value / max_value))
    width = int(block.get("width", 80))
    height = int(block.get("height", 6))
    margin_x = int(block.get("margin_x", 24))
    x = margin_x
    y = ctx.y
    ctx.draw.rectangle([x, y, x + width, y + height], outline=EINK_FG, width=1)
    fill_w = int((width - 2) * ratio)
    if fill_w > 0:
        ctx.draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + height - 1], fill=EINK_FG)
    ctx.y += height + 6


def _render_two_column(ctx: RenderContext, block: dict) -> None:
    left_width = int(block.get("left_width", 120))
    gap = int(block.get("gap", 8))
    left_x = int(block.get("left_x", 0))
    right_x = left_x + left_width + gap
    left_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=ctx.y,
        x_offset=left_x, available_width=left_width,
    )
    right_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=ctx.y,
        x_offset=right_x, available_width=max(0, ctx.screen_w - right_x),
    )
    for child in block.get("left", []):
        _render_block(left_ctx, child)
    for child in block.get("right", []):
        _render_block(right_ctx, child)
    ctx.y = max(left_ctx.y, right_ctx.y)


def _render_key_value(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "")
    label = block.get("label", "")
    value = ctx.get_field(field_name)
    if isinstance(value, dict):
        ordered = [value.get("meat"), value.get("veg"), value.get("staple")]
        parts = [str(v) for v in ordered if v]
        if not parts:
            parts = [f"{k}:{v}" for k, v in value.items()]
        value_text = " · ".join(parts)
    else:
        value_text = str(value)
    text = f"{label}: {value_text}" if label else value_text
    font_size = block.get("font_size", 12)
    font = load_font("noto_serif_light", font_size)
    margin_x = block.get("margin_x", 24)
    ctx.draw.text((margin_x, ctx.y), text, fill=EINK_FG, font=font)
    ctx.y += font_size + 4


def _render_group(ctx: RenderContext, block: dict) -> None:
    title = block.get("title", "")
    if title:
        title_font = load_font("noto_serif_bold", block.get("title_font_size", 12))
        margin_x = block.get("margin_x", 24)
        ctx.draw.text((margin_x, ctx.y), title, fill=EINK_FG, font=title_font)
        ctx.y += block.get("title_font_size", 12) + 4
    for child in block.get("children", []):
        _render_block(ctx, child)


def _render_icon_list(ctx: RenderContext, block: dict) -> None:
    items = ctx.get_field(block.get("field", ""))
    if not isinstance(items, list):
        return
    icon_field = block.get("icon_field", "icon")
    text_field = block.get("text_field", "text")
    max_items = int(block.get("max_items", 6))
    font = load_font("noto_serif_regular", block.get("font_size", 12))
    margin_x = int(block.get("margin_x", 24))
    line_h = int(block.get("line_height", 16))
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        icon_name = item.get(icon_field)
        text = str(item.get(text_field, ""))
        x = margin_x
        if icon_name:
            icon_img = load_icon(icon_name, size=(12, 12))
            if icon_img:
                ctx.img.paste(icon_img, (x, ctx.y))
                x += 16
        ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
        ctx.y += line_h


def _render_image(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "image_url")
    image_url = str(ctx.get_field(field_name) or "")
    if not image_url:
        return
    width = int(block.get("width", 220))
    height = int(block.get("height", 140))
    x = int(block.get("x", (ctx.screen_w - width) // 2))
    y = int(block.get("y", ctx.y))
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(image_url)
        if resp.status_code >= 400:
            return
        from io import BytesIO
        img = Image.open(BytesIO(resp.content)).convert("L").resize((width, height))
        mono = img.convert("1")
        ctx.img.paste(mono, (x, y))
        ctx.y = y + height + int(block.get("margin_bottom", 6))
    except Exception:
        logger.warning("[JSONRenderer] Failed to render image block", exc_info=True)


# ── Helpers ──────────────────────────────────────────────────


def _pick_cjk_font(font_key: str) -> str:
    """Ensure CJK text gets a Noto Serif font variant."""
    if font_key.startswith("noto_serif"):
        return font_key
    if font_key in ("lora_regular", "lora_bold", "inter_medium"):
        return "noto_serif_light"
    return font_key


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ── Register block types ─────────────────────────────────────

_BLOCK_RENDERERS["centered_text"] = _render_centered_text
_BLOCK_RENDERERS["text"] = _render_text
_BLOCK_RENDERERS["separator"] = _render_separator
_BLOCK_RENDERERS["section"] = _render_section
_BLOCK_RENDERERS["list"] = _render_list
_BLOCK_RENDERERS["vertical_stack"] = _render_vertical_stack
_BLOCK_RENDERERS["conditional"] = _render_conditional
_BLOCK_RENDERERS["spacer"] = _render_spacer
_BLOCK_RENDERERS["icon_text"] = _render_icon_text
_BLOCK_RENDERERS["two_column"] = _render_two_column
_BLOCK_RENDERERS["image"] = _render_image
_BLOCK_RENDERERS["progress_bar"] = _render_progress_bar
_BLOCK_RENDERERS["big_number"] = _render_big_number
_BLOCK_RENDERERS["icon_list"] = _render_icon_list
_BLOCK_RENDERERS["key_value"] = _render_key_value
_BLOCK_RENDERERS["group"] = _render_group
