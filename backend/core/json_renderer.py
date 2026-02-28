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

STATUS_BAR_BOTTOM_DEFAULT = 36  # Used when screen_h unknown (e.g. dataclass default)


@dataclass
class RenderContext:
    """Mutable state threaded through block renderers."""
    draw: ImageDraw.ImageDraw
    img: Image.Image
    content: dict
    screen_w: int = SCREEN_WIDTH
    screen_h: int = SCREEN_HEIGHT
    y: int = STATUS_BAR_BOTTOM_DEFAULT
    x_offset: int = 0
    available_width: int = SCREEN_WIDTH
    footer_height: int = 30

    @property
    def scale(self) -> float:
        return self.screen_w / 400.0

    @property
    def h_scale(self) -> float:
        return self.screen_h / 300.0

    @property
    def min_scale(self) -> float:
        """Conservative scale factor based on the more constrained dimension."""
        return min(self.scale, self.h_scale)

    def __post_init__(self):
        if self.available_width == SCREEN_WIDTH and self.screen_w != SCREEN_WIDTH:
            self.available_width = self.screen_w

    @property
    def footer_top(self) -> int:
        return self.screen_h - self.footer_height

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

    # Select screen-size-specific layout override if available
    overrides = mode_def.get("layout_overrides", {})
    size_key = f"{screen_w}x{screen_h}"
    if size_key in overrides:
        layout = {**layout, **overrides[size_key]}

    # 1. Status bar
    sb = layout.get("status_bar", {})
    draw_status_bar(
        draw, img, date_str, weather_str, int(battery_pct), weather_code,
        line_width=sb.get("line_width", 1),
        dashed=sb.get("dashed", False),
        time_str=time_str,
        screen_w=screen_w, screen_h=screen_h,
    )

    ft_layout = layout.get("footer", {})
    status_bar_pct = 0.10 if screen_h < 200 else 0.12
    status_bar_bottom = int(screen_h * status_bar_pct)
    scale = screen_w / 400.0
    min_scale = min(scale, screen_h / 300.0)
    footer_height = int(ft_layout.get("height", 30) * min_scale)
    footer_top = screen_h - footer_height

    # 2. Body blocks
    body = layout.get("body", [])
    body_align = layout.get("body_align", "center")
    _has_vcenter = any(
        b.get("type") == "centered_text" and b.get("vertical_center", True)
        for b in body
    )

    if _has_vcenter and len(body) == 1:
        ctx = RenderContext(
            draw=draw, img=img, content=content,
            screen_w=screen_w, screen_h=screen_h,
            y=status_bar_bottom, footer_height=footer_height,
        )
        _render_centered_text(ctx, body[0], use_full_body=True)
    elif body_align == "center" and body:
        measure_img = Image.new("1", (screen_w, screen_h), EINK_BG)
        measure_ctx = RenderContext(
            draw=ImageDraw.Draw(measure_img), img=measure_img, content=content,
            screen_w=screen_w, screen_h=screen_h,
            y=status_bar_bottom, footer_height=footer_height,
        )
        for block in body:
            if measure_ctx.y >= footer_top - 10:
                break
            _render_block(measure_ctx, block)
        content_height = measure_ctx.y - status_bar_bottom
        available_height = footer_top - status_bar_bottom
        offset = max(0, (available_height - content_height) // 2)

        ctx = RenderContext(
            draw=draw, img=img, content=content,
            screen_w=screen_w, screen_h=screen_h,
            y=status_bar_bottom + offset, footer_height=footer_height,
        )
        for block in body:
            if ctx.y >= footer_top - 10:
                break
            _render_block(ctx, block)
    else:
        ctx = RenderContext(
            draw=draw, img=img, content=content,
            screen_w=screen_w, screen_h=screen_h,
            y=status_bar_bottom, footer_height=footer_height,
        )
        for block in body:
            if ctx.y >= footer_top - 10:
                break
            _render_block(ctx, block)

    # 3. Footer
    ft = ft_layout
    label = ft.get("label", mode_def.get("mode_id", ""))
    attribution = ctx.resolve(ft.get("attribution_template", "")) if ft.get("attribution_template") else ""
    _attr_font_size = ft.get("font_size")
    if _attr_font_size is not None:
        _attr_font_size = int(_attr_font_size * scale)
    draw_footer(
        draw, img, label, attribution,
        line_width=ft.get("line_width", 1),
        dashed=ft.get("dashed", False),
        attr_font_size=_attr_font_size,
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

    font_size = int(block.get("font_size", 16) * ctx.scale)
    font_name = block.get("font_name")
    font_key = block.get("font", "noto_serif_light")
    max_ratio = block.get("max_width_ratio", 0.88)
    line_spacing = int(block.get("line_spacing", 8) * ctx.scale)

    body_height = ctx.footer_top - ctx.y
    max_w = int(ctx.available_width * max_ratio)
    while font_size >= 10:
        if font_name:
            if has_cjk(text) and "Noto" not in font_name:
                font_name = "NotoSerifSC-Light.ttf"
            font = load_font_by_name(font_name, font_size)
        else:
            if has_cjk(text):
                font_key = "noto_serif_light"
            font = load_font(font_key, font_size)

        lines = wrap_text(text, font, max_w)
        line_h = font_size + line_spacing
        total_h = len(lines) * line_h

        if use_full_body and block.get("vertical_center", True) and total_h > body_height:
            font_size -= 2
        else:
            break

    if use_full_body and block.get("vertical_center", True):
        y_start = ctx.y + (body_height - total_h) // 2
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

    font_size = int(block.get("font_size", 14) * ctx.scale)
    font_key = block.get("font", "noto_serif_regular")
    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)

    align = block.get("align", "center")
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    max_lines = block.get("max_lines", 3)
    max_w = max(20, ctx.available_width - margin_x * 2)

    lines = wrap_text(text, font, max_w)

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip() + "..."

    for line in lines:
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
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    line_width = block.get("line_width", 1)

    if style == "short":
        w = int(block.get("width", 60) * ctx.scale)
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
    title_font_size = int(block.get("title_font_size", 14) * ctx.scale)

    if has_cjk(title):
        title_font_key = _pick_cjk_font(title_font_key)
    font = load_font(title_font_key, title_font_size)

    margin_x = int(ctx.screen_w * 0.06)
    x = ctx.x_offset + margin_x
    icon_size = int(12 * ctx.scale)
    if icon_name:
        icon_img = load_icon(icon_name, size=(icon_size, icon_size))
        if icon_img:
            ctx.img.paste(icon_img, (x, ctx.y))
            x += int(16 * ctx.scale)

    ctx.draw.text((x, ctx.y), title, fill=EINK_FG, font=font)
    ctx.y += title_font_size + int(6 * ctx.scale)

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
    font_size = int(block.get("font_size", 13) * ctx.scale)
    spacing = int(block.get("item_spacing", 16) * ctx.scale)
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.08)

    align = block.get("align", "left")

    font = load_font(_pick_cjk_font(font_key), font_size)
    item_height = spacing

    rendered_count = 0
    for i, item in enumerate(items[:max_items]):
        if ctx.y + item_height > ctx.footer_top:
            remaining = len(items) - rendered_count
            if remaining > 0:
                more_text = f"+{remaining} more"
                more_font = load_font(_pick_cjk_font(font_key), int(11 * ctx.scale))
                ctx.draw.text((ctx.x_offset + margin_x, ctx.y), more_text, fill=EINK_FG, font=more_font)
            break
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

        right_col_w = int(80 * ctx.scale)
        max_text_w = ctx.available_width - margin_x * 2 if not right_field else ctx.available_width - margin_x - right_col_w
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
                ctx.draw.text((ctx.x_offset + ctx.available_width - right_col_w, ctx.y), rv, fill=EINK_FG, font=font)

        ctx.y += spacing
        rendered_count += 1


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
    ctx.y += int(block.get("height", 12) * ctx.min_scale)


def _render_icon_text(ctx: RenderContext, block: dict) -> None:
    icon_name = block.get("icon")
    field_name = block.get("field")
    text = str(ctx.get_field(field_name)) if field_name else block.get("text", "")
    text = ctx.resolve(text)
    if not text:
        return

    font_key = block.get("font", "noto_serif_regular")
    font_size = int(block.get("font_size", 14) * ctx.scale)
    icon_size = int(block.get("icon_size", 12) * ctx.scale)
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)

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
    if not text or text == "--":
        return
    
    # 支持单位后缀
    unit = block.get("unit", "")
    if unit:
        text = f"{text}{unit}"
    
    font_size = int(block.get("font_size", 42) * ctx.scale)
    font_key = block.get("font", "lora_bold")
    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    align = block.get("align", "center")
    _raw_margin = block.get("margin_x")
    if _raw_margin is not None:
        margin_x = int(_raw_margin * ctx.scale)
    else:
        margin_x = int(ctx.available_width * 0.06)
    if align == "left":
        x = ctx.x_offset + margin_x
    elif align == "right":
        x = ctx.x_offset + ctx.available_width - margin_x - tw
    else:
        x = ctx.x_offset + (ctx.available_width - tw) // 2
    ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
    ctx.y += font_size + 6


def _render_progress_bar(ctx: RenderContext, block: dict) -> None:
    value = _num(ctx.get_field(block.get("field", "")))
    max_value = max(_num(ctx.get_field(block.get("max_field", ""))), 1)
    ratio = max(0.0, min(1.0, value / max_value))
    width = int(block.get("width", 80) * ctx.scale)
    height = int(block.get("height", 6) * ctx.scale)
    _raw_margin = block.get("margin_x")
    if _raw_margin is not None:
        margin_x = int(_raw_margin * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    x = ctx.x_offset + margin_x
    y = ctx.y
    ctx.draw.rectangle([x, y, x + width, y + height], outline=EINK_FG, width=1)
    fill_w = int((width - 2) * ratio)
    if fill_w > 0:
        ctx.draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + height - 1], fill=EINK_FG)
    ctx.y += height + 6


def _render_temp_chart(ctx: RenderContext, block: dict) -> None:
    """Render a temperature chart with optional high/low lines for multi-day forecast."""
    field_name = block.get("field", "forecast")
    items = ctx.get_field(field_name)
    if not isinstance(items, list) or not items:
        return

    max_points = int(block.get("max_points", 4))
    # 默认使用 temp_max / temp_min 作为高低温字段
    high_field = block.get("high_field", block.get("temp_field", "temp_max"))
    low_field = block.get("low_field", "temp_min")
    label_field = block.get("label_field", "day")

    highs: list[float] = []
    lows: list[float] = []
    labels = []

    for item in items[:max_points]:
        if not isinstance(item, dict):
            continue
        h_raw = item.get(high_field)
        l_raw = item.get(low_field)
        if h_raw is None or l_raw is None:
            continue
        h_val = _num(h_raw)
        l_val = _num(l_raw)
        highs.append(h_val)
        lows.append(l_val)
        labels.append(str(item.get(label_field, "")))

    if not highs:
        return

    # 全局取 min / max，保证两条折线在同一坐标系内
    all_temps = highs + lows
    min_t = min(all_temps)
    max_t = max(all_temps)
    if max_t == min_t:
        max_t = min_t + 1  # avoid divide-by-zero, draw a flat line

    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.08)

    chart_height = int(block.get("height", 40) * ctx.scale)
    # 在右侧预留一点空白，避免折线紧贴屏幕边缘被“截断”的视觉效果
    extra_right_margin = int(block.get("right_margin", 8) * ctx.scale)
    width = ctx.available_width - margin_x * 2 - extra_right_margin
    if width <= 0:
        return

    x0 = ctx.x_offset + margin_x

    # 通过 bottom_pad 将整个折线图（含数字和标签）整体上移一段距离
    bottom_pad = int(block.get("bottom_pad", 0) * ctx.scale)
    y_bottom = ctx.y + chart_height - bottom_pad
    y_top = y_bottom - chart_height

    n = len(highs)
    if n == 1:
        step = 0
    else:
        step = width / (n - 1)

    high_coords: list[tuple[float, float]] = []
    low_coords: list[tuple[float, float]] = []
    for idx, (h_temp, l_temp) in enumerate(zip(highs, lows)):
        x = x0 + step * idx
        ratio_h = (h_temp - min_t) / (max_t - min_t)
        ratio_l = (l_temp - min_t) / (max_t - min_t)
        y_h = y_bottom - ratio_h * (chart_height - 8)
        y_l = y_bottom - ratio_l * (chart_height - 8)
        high_coords.append((x, y_h))
        low_coords.append((x, y_l))

    # Draw connecting lines
    for i in range(1, len(high_coords)):
        ctx.draw.line([high_coords[i - 1], high_coords[i]], fill=EINK_FG, width=1)
    for i in range(1, len(low_coords)):
        ctx.draw.line([low_coords[i - 1], low_coords[i]], fill=EINK_FG, width=1)

    # Draw points and labels（只标注最高温数字，最低温仅用空心点表示）
    font = load_font("noto_serif_light", int(10 * ctx.scale))
    for (xh, yh), (xl, yl), h_temp, l_temp, label in zip(
        high_coords, low_coords, highs, lows, labels
    ):
        r = int(2 * ctx.scale) or 1
        # 最高温：实心圆点
        ctx.draw.ellipse([xh - r, yh - r, xh + r, yh + r], fill=EINK_FG)
        # 最低温：空心圆点
        ctx.draw.ellipse([xl - r, yl - r, xl + r, yl + r], fill=EINK_BG)
        ctx.draw.ellipse([xl - r, yl - r, xl + r, yl + r], outline=EINK_FG, width=1)

        # 最高温数字（在图顶上方）
        temp_text_high = str(int(round(h_temp)))
        hbbox = font.getbbox(temp_text_high)
        htw = hbbox[2] - hbbox[0]
        hth = hbbox[3] - hbbox[1]
        ctx.draw.text(
            (xh - htw / 2, y_top - hth - 2),
            temp_text_high,
            fill=EINK_FG,
            font=font,
        )

        if label:
            lbbox = font.getbbox(label)
            lw = lbbox[2] - lbbox[0]
            ctx.draw.text((xh - lw / 2, y_bottom + 2), label, fill=EINK_FG, font=font)

    ctx.y = y_bottom + int(18 * ctx.scale)


def _render_two_column(ctx: RenderContext, block: dict) -> None:
    # Auto-downgrade to single column on very short screens
    if ctx.screen_h < 200:
        for child in block.get("left", []):
            if ctx.y >= ctx.footer_top - 10:
                break
            _render_block(ctx, child)
        for child in block.get("right", []):
            if ctx.y >= ctx.footer_top - 10:
                break
            _render_block(ctx, child)
        return

    left_width = int(block.get("left_width", 120) * ctx.scale)
    gap = int(block.get("gap", 8) * ctx.scale)
    left_x = int(block.get("left_x", 0) * ctx.scale) + ctx.x_offset
    right_x = left_x + left_width + gap
    left_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=ctx.y,
        x_offset=left_x, available_width=left_width,
        footer_height=ctx.footer_height,
    )
    right_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=ctx.y,
        x_offset=right_x, available_width=max(0, ctx.screen_w - right_x),
        footer_height=ctx.footer_height,
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
    font_size = int(block.get("font_size", 12) * ctx.scale)
    font = load_font("noto_serif_light", font_size)
    _raw_margin = block.get("margin_x")
    if _raw_margin is not None:
        margin_x = int(_raw_margin * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    ctx.draw.text((ctx.x_offset + margin_x, ctx.y), text, fill=EINK_FG, font=font)
    ctx.y += font_size + 4


def _render_group(ctx: RenderContext, block: dict) -> None:
    title = block.get("title", "")
    if title:
        title_font_size = int(block.get("title_font_size", 12) * ctx.scale)
        title_font = load_font("noto_serif_bold", title_font_size)
        _raw_margin = block.get("margin_x")
        if _raw_margin is not None:
            margin_x = int(_raw_margin * ctx.scale)
        else:
            margin_x = int(ctx.available_width * 0.06)
        ctx.draw.text((ctx.x_offset + margin_x, ctx.y), title, fill=EINK_FG, font=title_font)
        ctx.y += title_font_size + int(4 * ctx.scale)
    for child in block.get("children", []):
        _render_block(ctx, child)


def _render_weather_icon(ctx: RenderContext, block: dict) -> None:
    """Render weather icon based on weather_code field."""
    from .patterns.utils import get_weather_icon
    
    field_name = block.get("field", "code")
    weather_code = ctx.get_field(field_name)
    
    # 支持从数字字符串转换
    try:
        if isinstance(weather_code, str):
            weather_code = int(weather_code)
        elif not isinstance(weather_code, int):
            weather_code = -1
    except (ValueError, TypeError):
        weather_code = -1
    
    if weather_code < 0:
        return
    
    icon_size = int(block.get("icon_size", 48) * ctx.scale)
    align = block.get("align", "left")
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    
    weather_icon = get_weather_icon(weather_code)
    if weather_icon:
        # 调整图标大小
        if weather_icon.size[0] != icon_size:
            weather_icon = weather_icon.resize((icon_size, icon_size), Image.LANCZOS)
        
        x = ctx.x_offset + margin_x
        if align == "center":
            x = ctx.x_offset + (ctx.available_width - icon_size) // 2
        elif align == "right":
            x = ctx.x_offset + ctx.available_width - margin_x - icon_size
        
        ctx.img.paste(weather_icon, (x, ctx.y))
        ctx.y += icon_size + int(block.get("margin_bottom", 6) * ctx.scale)


def _render_icon_list(ctx: RenderContext, block: dict) -> None:
    items = ctx.get_field(block.get("field", ""))
    if not isinstance(items, list):
        return
    icon_field = block.get("icon_field", "icon")
    text_field = block.get("text_field", "text")
    max_items = int(block.get("max_items", 6))
    font_size = int(block.get("font_size", 12) * ctx.scale)
    font = load_font("noto_serif_regular", font_size)
    _raw_margin = block.get("margin_x")
    if _raw_margin is not None:
        margin_x = int(_raw_margin * ctx.scale)
    else:
        margin_x = int(ctx.available_width * 0.06)
    line_h = int(block.get("line_height", 16) * ctx.scale)
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        icon_name = item.get(icon_field)
        text = str(item.get(text_field, ""))
        x = ctx.x_offset + margin_x
        icon_size = int(12 * ctx.scale)
        if icon_name:
            icon_img = load_icon(icon_name, size=(icon_size, icon_size))
            if icon_img:
                ctx.img.paste(icon_img, (x, ctx.y))
                x += int(16 * ctx.scale)
        ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
        ctx.y += line_h


def _render_image(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "image_url")
    image_url = str(ctx.get_field(field_name) or "")
    if not image_url:
        return
    width = int(block.get("width", 220) * ctx.scale)
    height = int(block.get("height", 140) * ctx.scale)
    x = int(block.get("x", (ctx.screen_w - width) // 2))
    y = int(block.get("y", ctx.y))
    # Try pre-fetched data first (async download from json_content.py)
    prefetched = ctx.content.get(f"_prefetched_{field_name}")
    if prefetched:
        from io import BytesIO
        img = Image.open(BytesIO(prefetched)).convert("L").resize((width, height))
        mono = img.convert("1")
        ctx.img.paste(mono, (x, y))
        ctx.y = y + height + int(block.get("margin_bottom", 6))
        return
    try:
        resp = None
        last_error = None
        attempts = [
            {"trust_env": True, "timeout": httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=8.0)},
            {"trust_env": False, "timeout": httpx.Timeout(connect=12.0, read=18.0, write=10.0, pool=10.0)},
        ]
        for opts in attempts:
            try:
                with httpx.Client(
                    timeout=opts["timeout"],
                    follow_redirects=True,
                    trust_env=opts["trust_env"],
                ) as client:
                    resp = client.get(image_url)
                if resp.status_code >= 400:
                    raise ValueError(f"HTTP {resp.status_code}")
                break
            except Exception as e:
                last_error = e
                resp = None
        if resp is None:
            raise last_error if last_error else ValueError("image fetch failed")
        from io import BytesIO
        img = Image.open(BytesIO(resp.content)).convert("L").resize((width, height))
        mono = img.convert("1")
        ctx.img.paste(mono, (x, y))
        ctx.y = y + height + int(block.get("margin_bottom", 6))
    except Exception:
        logger.warning("[JSONRenderer] Failed to render image block", exc_info=True)
        ctx.draw.rectangle([x, y, x + width, y + height], outline=EINK_FG, width=1)
        placeholder_font = load_font("noto_serif_light", int(12 * ctx.scale))
        placeholder_text = "Image unavailable"
        bbox = placeholder_font.getbbox(placeholder_text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = x + (width - tw) // 2
        ty = y + (height - th) // 2
        ctx.draw.text((tx, ty), placeholder_text, fill=EINK_FG, font=placeholder_font)
        ctx.y = y + height + int(block.get("margin_bottom", 6) * ctx.scale)


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
_BLOCK_RENDERERS["temp_chart"] = _render_temp_chart
_BLOCK_RENDERERS["big_number"] = _render_big_number
_BLOCK_RENDERERS["icon_list"] = _render_icon_list
_BLOCK_RENDERERS["key_value"] = _render_key_value
_BLOCK_RENDERERS["group"] = _render_group
_BLOCK_RENDERERS["weather_icon"] = _render_weather_icon