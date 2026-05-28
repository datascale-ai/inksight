"""
通用 JSON 模式渲染引擎
根据 JSON layout 定义将内容渲染为墨水屏图像
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, UnidentifiedImageError

from .config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    EINK_4COLOR_PALETTE, EINK_COLOR_NAME_MAP, EINK_COLOR_AVAILABILITY,
)
from .patterns.utils import (
    EINK_BG,
    EINK_FG,
    apply_text_fontmode,
    draw_status_bar,
    draw_footer,
    draw_dashed_line,
    load_font,
    load_font_by_name,
    paste_icon_onto,
    load_icon,
    wrap_text,
    wrap_text_fill_sidebar,
    has_cjk,
    safe_font_bbox,
)
from .layout_presets import expand_layout_presets
from .mode_catalog import builtin_catalog_map
from .image_processing import convert_image_block

logger = logging.getLogger(__name__)

# Cap component-tree scaling on wide panels so preset pt sizes stay near the bitmap PCF grid
# (see patterns.utils INKSIGHT_BITMAP_MAX_REQUEST_SIZE). width >= LARGE_PANEL_MIN_W covers
# 583-inch class (648 px) and 7.5-inch class (800 px) bodies.
_COMPONENT_TREE_SCALE_CAP = float(
    os.getenv(
        "INKSIGHT_COMPONENT_TREE_SCALE_MAX",
        os.getenv("INKSIGHT_648_COMPONENT_SCALE_MAX", "1.35"),
    )
)
_LARGE_PANEL_MIN_W = int(os.getenv("INKSIGHT_LARGE_PANEL_MIN_WIDTH", "648"))

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_UPLOAD_DIR = _BACKEND_ROOT / "runtime_uploads"

STATUS_BAR_BOTTOM_DEFAULT = 36  # Used when screen_h unknown (e.g. dataclass default)

_EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]+", re.UNICODE
)


def _strip_emoji(s: str) -> str:
    """Remove emoji/symbols that typical CJK fonts don't render."""
    if not s:
        return s
    return _EMOJI_PATTERN.sub("", s).strip()


_LABEL_EMOJI_TO_ICON = {
    "\U0001f4d6": "book",
    "\U0001f4a1": "tips",
    "\U0001f31f": "star",
}

_BUILTIN_STATIC_ATTRIBUTIONS = {
    "zh": {
        "ARTWALL": "— 墨上观形",
        "BIAS": "— 见自己",
        "BRIEFING": "— 科技改变生活",
        "CALENDAR": "— 日有其序",
        "CHALLENGE": "— 试试看",
        "COUNTDOWN": "— 静待那天",
        "DAILY": "— 活在当下",
        "FITNESS": "— 动起来",
        "LIFEBAR": "— 此刻即刻度",
        "QUESTION": "— 想一想",
        "RECIPE": "— 好好吃饭",
        "RIDDLE": "— 且猜且想",
        "ROAST": "— 一笑了之",
        "STORY": "— 微光成篇",
        "THISDAY": "— 以史为镜",
        "TIMETABLE": "— 按表前行",
        "WEATHER": "— 阴晴有时",
        "WORD_OF_THE_DAY": "— 每日精进",
    },
    "en": {
        "ARTWALL": "— Ink Art",
        "BIAS": "— Think Clearly",
        "BRIEFING": "— Tech Brief",
        "CALENDAR": "— InkSight",
        "CHALLENGE": "— Just Do It",
        "COUNTDOWN": "— Remember",
        "DAILY": "— Carpe Diem",
        "FITNESS": "— Stay Healthy",
        "LIFEBAR": "— Time Flies",
        "QUESTION": "— Take a Moment",
        "RECIPE": "— Eat Well",
        "RIDDLE": "— Think About It",
        "ROAST": "— InkSight AI",
        "STORY": "— Micro Fiction",
        "THISDAY": "— History",
        "TIMETABLE": "— InkSight",
        "WEATHER": "— Open-Meteo",
        "WORD_OF_THE_DAY": "— Expand Your Lexicon",
    },
}


def _section_icon_from_label(label: str) -> str | None:
    """If label starts with a known emoji, return the corresponding icon name."""
    for emoji, icon_name in _LABEL_EMOJI_TO_ICON.items():
        if label.startswith(emoji) or emoji in label:
            return icon_name
    return None


def _localized_footer_label(mode_id: str, fallback_label: str, language: str) -> str:
    item = builtin_catalog_map().get((mode_id or "").upper())
    if not item:
        return fallback_label
    return item.en.name if language == "en" else item.zh.name


def _localized_footer_attribution(mode_id: str, attribution: str, language: str) -> str:
    if not attribution or "{" in attribution:
        return attribution
    localized = _BUILTIN_STATIC_ATTRIBUTIONS.get(language, {}).get((mode_id or "").upper())
    return localized or attribution


def _resolve_template(content: dict, template: str) -> str:
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        val = content.get(key, "")
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val)
    return re.sub(r"\{(\w+)\}", _replace, template)


def _resolve_named_color(ctx: RenderContext, color_name: Any, default: int = EINK_FG) -> int:
    if not isinstance(color_name, str) or not color_name:
        return default
    return ctx.color_index(color_name, default)


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
    colors: int = 2
    footer_top_offset: int = 0

    @property
    def scale(self) -> float:
        return max(0.92, self.screen_w / 400.0)

    @property
    def h_scale(self) -> float:
        return self.screen_h / 300.0

    @property
    def min_scale(self) -> float:
        """Conservative scale factor based on the more constrained dimension."""
        return max(0.65, min(self.scale, self.h_scale))

    def __post_init__(self):
        if self.available_width == SCREEN_WIDTH and self.screen_w != SCREEN_WIDTH:
            self.available_width = self.screen_w

    @property
    def footer_top(self) -> int:
        return self.screen_h - self.footer_height + self.footer_top_offset

    def resolve(self, template: str) -> str:
        """Resolve {field} placeholders against content dict."""
        return _resolve_template(self.content, template)

    def get_field(self, name: str) -> Any:
        return self.content.get(name, "")

    @property
    def remaining_height(self) -> int:
        return self.footer_top - self.y

    def color_index(self, name: str, default: int = EINK_FG) -> int:
        """Return palette index for a named color if the device supports it."""
        available = EINK_COLOR_AVAILABILITY.get(self.colors, frozenset())
        if name not in available:
            return default
        return EINK_COLOR_NAME_MAP.get(name, default)

    def resolve_color(self, block: dict, default: int = EINK_FG) -> int:
        """Resolve block 'color' property to a fill value."""
        name = block.get("color")
        if not name:
            return default
        return self.color_index(name, default)

    def paste_icon(self, icon: Image.Image, pos: tuple[int, int], fill: int = EINK_FG) -> None:
        """Paste a 1-bit icon onto the canvas, handling palette mode transparency."""
        paste_icon_onto(self.img, icon, pos, fill)


@dataclass
class ComponentBox:
    x: int
    y: int
    width: int
    height: int


@dataclass
class ComponentNode:
    kind: str
    props: dict
    content: dict
    children: list["ComponentNode"] = field(default_factory=list)
    box: ComponentBox | None = None
    measured_width: int = 0
    measured_height: int = 0
    draw_data: dict[str, Any] = field(default_factory=dict)


def _component_aligned_y(box_y: int, box_height: int, content_height: int, align_y: str) -> int:
    extra = max(0, box_height - content_height)
    if align_y == "center":
        return box_y + extra // 2
    if align_y in {"bottom", "end"}:
        return box_y + extra
    return box_y


def _debug_outline_color(ctx: RenderContext) -> int:
    return 3 if ctx.img.mode == "P" else EINK_FG


def _debug_bbox_color(ctx: RenderContext) -> int:
    return 2 if ctx.img.mode == "P" else EINK_FG


def _draw_debug_rect(ctx: RenderContext, rect: tuple[int, int, int, int], *, color: int) -> None:
    x0, y0, x1, y1 = rect
    if x1 <= x0 or y1 <= y0:
        return
    ctx.draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=color, width=1)


def _paint_component_debug_overlay(ctx: RenderContext, node: ComponentNode) -> None:
    box = node.box
    if box is None:
        return
    _draw_debug_rect(
        ctx,
        (box.x, box.y, box.x + box.width, box.y + box.height),
        color=_debug_outline_color(ctx),
    )
    if node.kind == "text":
        font = node.draw_data.get("font")
        lines = node.draw_data.get("lines", [])
        line_height = node.draw_data.get("line_height", 0)
        total_height = len(lines) * line_height if lines else 0
        if font is not None and lines and line_height > 0:
            align = node.props.get("align", "left")
            align_y = node.props.get("align_y", "top")
            try:
                ink_dy_dbg = int(node.props.get("ink_offset_y", 0) or 0)
            except (TypeError, ValueError):
                ink_dy_dbg = 0
            y = _component_aligned_y(box.y, box.height, total_height, align_y) + ink_dy_dbg
            for line in lines:
                bbox = font.getbbox(line)
                line_width = bbox[2] - bbox[0]
                if align == "center":
                    x = box.x + max(0, (box.width - line_width) // 2)
                elif align == "right":
                    x = box.x + max(0, box.width - line_width)
                else:
                    x = box.x
                _draw_debug_rect(
                    ctx,
                    (x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]),
                    color=_debug_bbox_color(ctx),
                )
                y += line_height
    elif node.kind == "big_number":
        bbox = node.draw_data.get("bbox")
        text = node.draw_data.get("text", "")
        if bbox and text:
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            align = node.props.get("align", "center")
            align_y = node.props.get("align_y", "top")
            if align == "left":
                x = box.x - bbox[0]
            elif align == "right":
                x = box.x + max(0, box.width - text_width) - bbox[0]
            else:
                x = box.x + max(0, (box.width - text_width) // 2) - bbox[0]
            ink_top = _component_aligned_y(box.y, box.height, text_height, align_y)
            y = ink_top - bbox[1]
            _draw_debug_rect(
                ctx,
                (x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]),
                color=_debug_bbox_color(ctx),
            )
    for child in node.children:
        _paint_component_debug_overlay(ctx, child)


def _merge_layout_dict(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_layout_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _uses_component_tree(body: Any, layout: dict) -> bool:
    if layout.get("layout_engine") == "component_tree":
        return True
    if isinstance(body, dict):
        return body.get("type") in {"column", "row", "repeat", "section_box", "box", "float_wrap"}
    return False


def _scaled_value(value: Any, scale: float, default: int = 0, minimum: int = 0) -> int:
    raw = value if isinstance(value, (int, float)) else default
    return max(minimum, int(raw * scale))


def _component_tree_scale(ctx: RenderContext, theme: dict) -> float:
    """Return the effective component-tree scale.

    Raw ctx.scale grows with screen width (e.g. 648 px -> 1.62). Applying that fully to font
    sizes pushes past PCF bitmap coverage and falls back to blurry TTF on e-ink. For wide
    panels (screen_w >= INKSIGHT_LARGE_PANEL_MIN_WIDTH) we cap by INKSIGHT_COMPONENT_TREE_SCALE_MAX
    (default 1.35, same legacy cap as the old 648-only branch). Modes may set layout.component_scale.
    """
    raw = ctx.scale
    override = theme.get("component_scale") or theme.get("scale")
    if override is not None:
        try:
            return max(0.65, float(override))
        except (TypeError, ValueError):
            pass
    if ctx.screen_w >= _LARGE_PANEL_MIN_W:
        return min(raw, _COMPONENT_TREE_SCALE_CAP)
    return raw


def _component_grow(node: ComponentNode) -> int:
    grow = node.props.get("grow", node.props.get("flex_grow", 0))
    try:
        return max(0, int(grow))
    except (TypeError, ValueError):
        return 0


def _component_text_value(node: ComponentNode) -> str:
    field_name = node.props.get("field")
    template = node.props.get("template")
    text = node.props.get("text")
    if field_name:
        value = node.content.get(field_name, "")
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)
    if template:
        return _resolve_template(node.content, template)
    if text:
        return _resolve_template(node.content, str(text))
    return ""


def _component_padding(props: dict, scale: float) -> tuple[int, int, int, int]:
    px = _scaled_value(props.get("padding_x"), scale)
    py = _scaled_value(props.get("padding_y"), scale)
    left = _scaled_value(props.get("padding_left"), scale, px)
    right = _scaled_value(props.get("padding_right"), scale, px)
    top = _scaled_value(props.get("padding_top"), scale, py)
    bottom = _scaled_value(props.get("padding_bottom"), scale, py)
    return left, top, right, bottom


def _component_fixed_width(node: ComponentNode, scale: float) -> int:
    return _scaled_value(node.props.get("width"), scale)


def _component_load_font(node: ComponentNode, text: str, theme: dict, scale: float, default_font: str, default_size: int) -> tuple[Any, int]:
    font_size = _scaled_value(node.props.get("font_size"), scale, default_size, 6)
    font_name = node.props.get("font_name")
    font_key = node.props.get("font", theme.get("body_font", default_font))
    if font_name:
        if has_cjk(text) and "Noto" not in font_name:
            font_name = "NotoSerifSC-Regular.ttf"
        return load_font_by_name(font_name, font_size), font_size
    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    return load_font(font_key, font_size), font_size


def _fit_line_with_ellipsis(text: str, font: Any, max_width: int) -> str:
    if max_width <= 0:
        return "..."
    b0 = safe_font_bbox(font, text)
    if b0[2] - b0[0] <= max_width:
        return text
    ellipsis = "..."
    eb = safe_font_bbox(font, ellipsis)
    if eb[2] - eb[0] > max_width:
        return ellipsis
    trimmed = text.rstrip(". ")
    while trimmed:
        candidate = trimmed.rstrip() + ellipsis
        cb = safe_font_bbox(font, candidate)
        if cb[2] - cb[0] <= max_width:
            return candidate
        trimmed = trimmed[:-1]
    return ellipsis


def _component_measure_text(node: ComponentNode, available_width: int | None, theme: dict, scale: float) -> None:
    text = _component_text_value(node)
    if not text:
        node.measured_width = 0
        node.measured_height = 0
        node.draw_data = {"lines": [], "font": None, "line_height": 0}
        return
    font, font_size = _component_load_font(node, text, theme, scale, "noto_serif_regular", theme.get("body_font_size", 12))
    max_lines = node.props.get("max_lines")
    ellipsis = node.props.get("ellipsis", True)
    if available_width is None:
        lines = [text]
    else:
        lines = wrap_text(text, font, max(1, available_width))
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines and ellipsis:
            lines[-1] = _fit_line_with_ellipsis(lines[-1], font, max(1, available_width or 0))
    line_height = _scaled_value(node.props.get("line_height"), scale, font_size + theme.get("body_line_gap", 4), 1)
    text_width = 0
    for line in lines:
        bbox = safe_font_bbox(font, line)
        text_width = max(text_width, bbox[2] - bbox[0])
    node.measured_width = available_width if available_width is not None else text_width
    node.measured_height = len(lines) * line_height if lines else 0
    node.draw_data = {
        "lines": lines,
        "font": font,
        "line_height": line_height,
        "text_width": text_width,
        "text_height": len(lines) * line_height if lines else 0,
    }


def _measure_component_big_number(node: ComponentNode, theme: dict, scale: float) -> None:
    text = _component_text_value(node)
    if not text or text == "--":
        node.measured_width = 0
        node.measured_height = 0
        node.draw_data = {"font": None, "text": ""}
        return
    unit = str(node.props.get("unit", "") or "")
    if unit:
        text = f"{text}{unit}"
    font, font_size = _component_load_font(node, text, theme, scale, "noto_serif_bold", 42)
    bbox = font.getbbox(text)
    node.measured_width = max(0, bbox[2] - bbox[0])
    node.measured_height = max(0, bbox[3] - bbox[1])
    node.draw_data = {"font": font, "text": text, "bbox": bbox}


def _measure_component_progress_bar(node: ComponentNode, scale: float) -> None:
    width = _scaled_value(node.props.get("width"), scale, 80, 4)
    height = _scaled_value(node.props.get("height"), scale, 6, 2)
    node.measured_width = width
    node.measured_height = height
    node.draw_data = {"width": width, "height": height}


def _measure_component_separator(node: ComponentNode, available_width: int | None, scale: float) -> None:
    line_width = max(1, int(node.props.get("line_width", 1)))
    width = available_width if available_width is not None else _scaled_value(node.props.get("width"), scale, 60, 4)
    node.measured_width = max(0, width)
    node.measured_height = line_width
    node.draw_data = {"line_width": line_width}


def _build_component_node(defn: dict, content: dict) -> ComponentNode:
    kind = defn.get("type", "")
    if kind == "repeat":
        items = content.get(defn.get("field", ""), [])
        if not isinstance(items, list):
            items = []
        limit = defn.get("limit", defn.get("max_items", len(items)))
        try:
            lim_int = int(limit) if limit is not None else len(items)
        except (TypeError, ValueError):
            lim_int = len(items)
        raw_items = items[:lim_int] if lim_int >= 0 else items
        pair_step = int(defn.get("pair_step", 1) or 1)
        pair_sep = str(defn.get("pair_separator", ""))
        if pair_step > 1 and raw_items:
            paired: list[Any] = []
            for i in range(0, len(raw_items), pair_step):
                chunk = raw_items[i : i + pair_step]
                if not chunk:
                    continue
                if all(isinstance(x, str) for x in chunk):
                    paired.append(pair_sep.join(chunk))
                else:
                    paired.extend(chunk)
            items = paired
        else:
            items = raw_items
        item_def = defn.get("item")
        children: list[ComponentNode] = []
        if isinstance(item_def, dict):
            for idx, item in enumerate(items):
                item_content = dict(content)
                item_content["index"] = idx + 1
                item_content["_item"] = item
                item_content["_value"] = item
                if isinstance(item, dict):
                    item_content.update(item)
                children.append(_build_component_node(item_def, item_content))
        return ComponentNode(kind=kind, props=defn, content=content, children=children)
    children = [
        _build_component_node(child, content)
        for child in defn.get("children", [])
        if isinstance(child, dict)
    ]
    return ComponentNode(kind=kind, props=defn, content=content, children=children)


def _float_wrap_field_text(node: ComponentNode) -> str:
    field_name = node.props.get("text_field") or node.props.get("field")
    if not field_name:
        return ""
    value = node.content.get(str(field_name), "")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _measure_float_wrap_node(node: ComponentNode, available_width: int | None, theme: dict, scale: float) -> None:
    gap = _scaled_value(node.props.get("gap"), scale, 4, 0)
    float_below_gap = _scaled_value(node.props.get("float_below_gap"), scale, 2, 0)
    inner_w = max(0, (available_width or 0))
    if not node.children:
        node.measured_width = inner_w
        node.measured_height = 0
        node.draw_data = {
            "gap": gap,
            "float_below_gap": float_below_gap,
            "float_w": 0,
            "float_h": 0,
            "side_lines": [],
            "below_lines": [],
            "font": None,
            "line_height": 0,
        }
        return
    fc = node.children[0]
    _measure_component_node(fc, available_width, theme, scale)
    fw, fh = fc.measured_width, fc.measured_height
    side_w = max(0, inner_w - fw - gap)
    text = _strip_emoji(_float_wrap_field_text(node))
    shim = ComponentNode(kind="text", props=node.props, content=node.content, children=[])
    font, font_size = _component_load_font(
        shim, text if text.strip() else " ",
        theme, scale,
        "noto_serif_regular",
        theme.get("body_font_size", 12),
    )
    line_height = _scaled_value(node.props.get("line_height"), scale, font_size + theme.get("body_line_gap", 4), 1)
    if not text.strip():
        node.measured_width = inner_w if inner_w > 0 else fw
        node.measured_height = fh
        node.draw_data = {
            "gap": gap,
            "float_below_gap": float_below_gap,
            "float_w": fw,
            "float_h": fh,
            "side_lines": [],
            "below_lines": [],
            "font": None,
            "line_height": line_height,
        }
        return
    side_lines, remainder = wrap_text_fill_sidebar(text, font, side_w, fh, line_height)
    below_w = max(1, inner_w - fw - gap) if inner_w > 0 else max(1, side_w or 1)
    below_lines = wrap_text(remainder, font, below_w) if remainder else []
    max_below = node.props.get("wrap_below_max_lines")
    if max_below is not None:
        try:
            mb = int(max_below)
            if mb >= 0 and len(below_lines) > mb:
                below_lines = below_lines[:mb]
                ellipsis = node.props.get("ellipsis", True)
                if below_lines and ellipsis:
                    below_lines[-1] = _fit_line_with_ellipsis(below_lines[-1], font, below_w)
        except (TypeError, ValueError):
            pass
    side_text_bottom = len(side_lines) * line_height
    if below_lines:
        text_stack_bottom = side_text_bottom + float_below_gap + len(below_lines) * line_height
        total_h = max(fh, text_stack_bottom)
    else:
        total_h = fh
    node.measured_width = inner_w if inner_w > 0 else fw + gap + max(side_w, 1)
    node.measured_height = total_h
    node.draw_data = {
        "gap": gap,
        "float_below_gap": float_below_gap,
        "float_w": fw,
        "float_h": fh,
        "below_x_shift": fw + gap,
        "below_text_width": below_w,
        "side_text_bottom": side_text_bottom,
        "side_lines": side_lines,
        "below_lines": below_lines,
        "font": font,
        "line_height": line_height,
    }


def _measure_component_node(node: ComponentNode, available_width: int | None, theme: dict, scale: float) -> None:
    if node.kind == "text":
        _component_measure_text(node, available_width, theme, scale)
        return
    if node.kind == "big_number":
        _measure_component_big_number(node, theme, scale)
        return
    if node.kind == "progress_bar":
        _measure_component_progress_bar(node, scale)
        return
    if node.kind == "separator":
        _measure_component_separator(node, available_width, scale)
        return
    if node.kind == "spacer":
        sh_raw = node.props.get("height", node.props.get("min_height", 6))
        sh = _scaled_value(sh_raw, scale, 6, 1)
        node.measured_width = available_width if available_width is not None else 0
        node.measured_height = max(0, int(sh))
        node.draw_data = {}
        return
    if node.kind == "repeat":
        gap = _scaled_value(node.props.get("gap"), scale)
        total_height = 0
        max_width = 0
        for idx, child in enumerate(node.children):
            _measure_component_node(child, available_width, theme, scale)
            total_height += child.measured_height
            if idx > 0:
                total_height += gap
            max_width = max(max_width, child.measured_width)
        node.measured_width = available_width if available_width is not None else max_width
        node.measured_height = total_height
        node.draw_data = {"gap": gap}
        return
    if node.kind == "column":
        left, top, right, bottom = _component_padding(node.props, scale)
        gap = _scaled_value(node.props.get("gap"), scale)
        inner_width = None if available_width is None else max(0, available_width - left - right)
        total_height = top + bottom
        max_width = 0
        visible_count = 0
        for child in node.children:
            _measure_component_node(child, inner_width, theme, scale)
            if child.measured_height <= 0 and child.measured_width <= 0:
                continue
            if visible_count > 0:
                total_height += gap
            total_height += child.measured_height
            visible_count += 1
            max_width = max(max_width, child.measured_width)
        fixed_width = _scaled_value(node.props.get("width"), scale)
        width = fixed_width or (available_width if available_width is not None else max_width + left + right)
        min_height = _scaled_value(node.props.get("min_height"), scale)
        fixed_height = _scaled_value(node.props.get("height"), scale)
        node.measured_width = width
        node.measured_height = max(total_height, min_height, fixed_height)
        node.draw_data = {
            "padding": (left, top, right, bottom),
            "gap": gap,
        }
        return
    if node.kind == "row":
        left, top, right, bottom = _component_padding(node.props, scale)
        gap = _scaled_value(node.props.get("gap"), scale)
        inner_width = None if available_width is None else max(0, available_width - left - right)
        total_gap = gap * max(0, len(node.children) - 1)
        fixed_width = 0
        grow_total = 0
        for child in node.children:
            if _component_grow(child) > 0:
                grow_total += _component_grow(child)
                continue
            child_width_hint = _component_fixed_width(child, scale) or None
            _measure_component_node(child, child_width_hint, theme, scale)
            fixed_width += child.measured_width
        remaining_width = max(0, (inner_width or 0) - fixed_width - total_gap)
        remaining_slots = grow_total
        for child in node.children:
            grow = _component_grow(child)
            if grow <= 0:
                continue
            child_width = remaining_width if remaining_slots <= grow else remaining_width * grow // remaining_slots
            _measure_component_node(child, child_width, theme, scale)
            remaining_width -= child_width
            remaining_slots -= grow
        content_width = fixed_width + total_gap + sum(
            child.measured_width for child in node.children if _component_grow(child) > 0
        )
        content_height = max((child.measured_height for child in node.children), default=0)
        fixed_width = _scaled_value(node.props.get("width"), scale)
        width = fixed_width or (available_width if available_width is not None else content_width + left + right)
        min_height = _scaled_value(node.props.get("min_height"), scale)
        fixed_height = _scaled_value(node.props.get("height"), scale)
        node.measured_width = width
        node.measured_height = max(content_height + top + bottom, min_height, fixed_height)
        node.draw_data = {
            "padding": (left, top, right, bottom),
            "gap": gap,
        }
        return
    if node.kind == "section_box":
        title = _resolve_template(node.content, str(node.props.get("title", "")))
        title_font_size = _scaled_value(node.props.get("title_font_size"), scale, theme.get("section_title_font_size", 12), 6)
        title_font_key = node.props.get("title_font", theme.get("section_title_font", "noto_serif_regular"))
        if has_cjk(title):
            title_font_key = _pick_cjk_font(title_font_key)
        title_font = load_font(title_font_key, title_font_size)
        icon_name = node.props.get("icon")
        icon_size = _scaled_value(node.props.get("icon_size"), scale, theme.get("section_icon_size", 12), 0)
        title_gap = _scaled_value(node.props.get("title_gap"), scale, theme.get("section_title_gap", 6))
        content_indent = _scaled_value(node.props.get("content_indent"), scale, theme.get("section_content_indent", 36))
        child_gap = _scaled_value(node.props.get("gap"), scale, theme.get("section_content_gap", 4))
        title_bbox = title_font.getbbox(title) if title else (0, 0, 0, 0)
        title_height = max(icon_size, title_bbox[3] - title_bbox[1])
        child_width = None if available_width is None else max(0, available_width - content_indent)
        content_height = 0
        visible_count = 0
        for child in node.children:
            _measure_component_node(child, child_width, theme, scale)
            if child.measured_height <= 0 and child.measured_width <= 0:
                continue
            if visible_count > 0:
                content_height += child_gap
            content_height += child.measured_height
            visible_count += 1
        min_height = _scaled_value(node.props.get("min_height"), scale)
        fixed_height = _scaled_value(node.props.get("height"), scale)
        fixed_width = _scaled_value(node.props.get("width"), scale)
        node.measured_width = fixed_width or available_width or max(0, content_indent + max((child.measured_width for child in node.children), default=0))
        node.measured_height = max(title_height + title_gap + content_height, min_height, fixed_height)
        node.draw_data = {
            "title": title,
            "title_font": title_font,
            "title_height": title_height,
            "title_gap": title_gap,
            "icon_name": icon_name,
            "icon_size": icon_size,
            "content_indent": content_indent,
            "child_gap": child_gap,
        }
        return
    if node.kind == "float_wrap":
        _measure_float_wrap_node(node, available_width, theme, scale)
        return
    if node.kind == "box":
        left, top, right, bottom = _component_padding(node.props, scale)
        inner_width = None if available_width is None else max(0, available_width - left - right)
        max_width = 0
        max_height = 0
        for child in node.children:
            _measure_component_node(child, inner_width, theme, scale)
            max_width = max(max_width, child.measured_width)
            max_height = max(max_height, child.measured_height)
        fixed_width = _scaled_value(node.props.get("width"), scale)
        node.measured_width = fixed_width or (available_width if available_width is not None else max_width + left + right)
        node.measured_height = max_height + top + bottom
        node.draw_data = {"padding": (left, top, right, bottom)}
        return
    node.measured_width = 0
    node.measured_height = 0
    node.draw_data = {}


def _layout_component_node(node: ComponentNode, x: int, y: int, width: int, height: int, theme: dict, scale: float) -> None:
    node.box = ComponentBox(x, y, width, height)
    if node.kind == "text":
        return
    if node.kind == "repeat":
        gap = node.draw_data.get("gap", 0)
        cursor_y = y
        for child in node.children:
            _layout_component_node(child, x, cursor_y, width, child.measured_height, theme, scale)
            cursor_y += child.measured_height + gap
        return
    if node.kind == "column":
        left, top, right, bottom = node.draw_data.get("padding", (0, 0, 0, 0))
        gap = node.draw_data.get("gap", 0)
        inner_x = x + left
        inner_y = y + top
        inner_width = max(0, width - left - right)
        inner_height = max(0, height - top - bottom)
        visible_children = [child for child in node.children if child.measured_height > 0 or child.measured_width > 0]
        if not visible_children:
            return
        gap_total = gap * max(0, len(visible_children) - 1)
        base_height = sum(child.measured_height for child in visible_children)
        extra = max(0, inner_height - base_height - gap_total)
        grow_total = sum(_component_grow(child) for child in visible_children)
        justify = node.props.get("justify", "start")
        cursor_y = inner_y
        gap_step = gap
        if grow_total <= 0:
            if justify == "center":
                cursor_y += extra // 2
            elif justify == "end":
                cursor_y += extra
            elif justify == "space_between" and len(visible_children) > 1:
                gap_step = gap + extra // (len(visible_children) - 1)
        bias_px = node.props.get("content_bias_px")
        if bias_px is not None:
            try:
                cursor_y -= int(bias_px)
            except (TypeError, ValueError):
                pass
            cursor_y = max(inner_y, cursor_y)
        for idx, child in enumerate(visible_children):
            child_height = child.measured_height
            grow = _component_grow(child)
            if grow_total > 0 and grow > 0:
                extra_height = extra if grow_total <= grow else extra * grow // grow_total
                child_height += extra_height
                extra -= extra_height
                grow_total -= grow
            _layout_component_node(child, inner_x, cursor_y, inner_width, child_height, theme, scale)
            cursor_y += child_height
            if idx < len(visible_children) - 1:
                cursor_y += gap_step
        return
    if node.kind == "row":
        left, top, right, bottom = node.draw_data.get("padding", (0, 0, 0, 0))
        gap = node.draw_data.get("gap", 0)
        inner_x = x + left
        inner_y = y + top
        inner_width = max(0, width - left - right)
        inner_height = max(0, height - top - bottom)
        fixed_width = sum(child.measured_width for child in node.children if _component_grow(child) <= 0)
        grow_children = [child for child in node.children if _component_grow(child) > 0]
        grow_total = sum(_component_grow(child) for child in grow_children)
        gap_total = gap * max(0, len(node.children) - 1)
        remaining_width = max(0, inner_width - fixed_width - gap_total)
        align = node.props.get("align", "center")
        cursor_x = inner_x
        for idx, child in enumerate(node.children):
            grow = _component_grow(child)
            child_width = child.measured_width
            if grow > 0:
                child_width = remaining_width if grow_total <= grow else remaining_width * grow // grow_total
                remaining_width -= child_width
                grow_total -= grow
            child_height = child.measured_height
            child_y = inner_y
            if align == "center":
                child_y = inner_y + max(0, (inner_height - child_height) // 2)
            elif align == "end":
                child_y = inner_y + max(0, inner_height - child_height)
            elif align == "stretch":
                child_height = inner_height
            _layout_component_node(child, cursor_x, child_y, child_width, child_height, theme, scale)
            cursor_x += child_width
            if idx < len(node.children) - 1:
                cursor_x += gap
        return
    if node.kind == "section_box":
        title_gap = node.draw_data.get("title_gap", 0)
        title_height = node.draw_data.get("title_height", 0)
        content_indent = node.draw_data.get("content_indent", 0)
        child_gap = node.draw_data.get("child_gap", 0)
        child_x = x + content_indent
        raw_coff = node.props.get("content_ink_offset_y")
        try:
            content_off = int(raw_coff) if raw_coff is not None else 0
        except (TypeError, ValueError):
            content_off = 0
        child_y = y + title_height + title_gap + content_off
        child_width = max(0, width - content_indent)
        for idx, child in enumerate([c for c in node.children if c.measured_height > 0 or c.measured_width > 0]):
            _layout_component_node(child, child_x, child_y, child_width, child.measured_height, theme, scale)
            child_y += child.measured_height
            if idx < len(node.children) - 1:
                child_y += child_gap
        return
    if node.kind == "float_wrap":
        dd = node.draw_data
        fw = int(dd.get("float_w") or 0)
        fh = int(dd.get("float_h") or 0)
        if node.children:
            _layout_component_node(node.children[0], x, y, fw, fh, theme, scale)
        return
    if node.kind == "box":
        left, top, right, bottom = node.draw_data.get("padding", (0, 0, 0, 0))
        inner_x = x + left
        inner_y = y + top
        inner_width = max(0, width - left - right)
        inner_height = max(0, height - top - bottom)
        for child in node.children:
            _layout_component_node(child, inner_x, inner_y, inner_width, min(inner_height, child.measured_height), theme, scale)
        return


def _paint_component_node(ctx: RenderContext, node: ComponentNode, theme: dict, scale: float) -> None:
    box = node.box
    if box is None:
        return
    if node.kind == "spacer":
        return
    if node.kind == "float_wrap":
        for child in node.children:
            _paint_component_node(ctx, child, theme, scale)
        dd = node.draw_data
        font = dd.get("font")
        if font is None:
            return
        lh = int(dd.get("line_height") or 0)
        if lh <= 0:
            return
        fw = int(dd.get("float_w") or 0)
        gap = int(dd.get("gap") or 0)
        fill = ctx.resolve_color(node.props)
        side_x = box.x + fw + gap
        sy = box.y
        for i, ln in enumerate(dd.get("side_lines") or []):
            ctx.draw.text((side_x, sy + i * lh), ln, fill=fill, font=font)
        below = dd.get("below_lines") or []
        if below:
            stb = int(dd.get("side_text_bottom") or 0)
            fbg = int(dd.get("float_below_gap") or 0)
            by = box.y + stb + fbg
            bx_shift = int(dd.get("below_x_shift") or 0)
            below_x = box.x + bx_shift
            for i, ln in enumerate(below):
                ctx.draw.text((below_x, by + i * lh), ln, fill=fill, font=font)
        return
    if node.kind == "text":
        font = node.draw_data.get("font")
        if font is None:
            return
        lines = node.draw_data.get("lines", [])
        line_height = node.draw_data.get("line_height", 0)
        align = node.props.get("align", "left")
        align_y = node.props.get("align_y", "top")
        total_height = node.draw_data.get("text_height", 0)
        try:
            ink_dy = int(node.props.get("ink_offset_y", 0) or 0)
        except (TypeError, ValueError):
            ink_dy = 0
        y = _component_aligned_y(box.y, box.height, total_height, align_y) + ink_dy
        for line in lines:
            bbox = font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            if align == "center":
                x = box.x + max(0, (box.width - line_width) // 2)
            elif align == "right":
                x = box.x + max(0, box.width - line_width)
            else:
                x = box.x
            ctx.draw.text((x, y), line, fill=ctx.resolve_color(node.props), font=font)
            y += line_height
        return
    if node.kind == "big_number":
        font = node.draw_data.get("font")
        text = node.draw_data.get("text", "")
        if font is None or not text:
            return
        bbox = node.draw_data.get("bbox") or font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        align = node.props.get("align", "center")
        align_y = node.props.get("align_y", "top")
        if align == "left":
            x = box.x - bbox[0]
        elif align == "right":
            x = box.x + max(0, box.width - text_width) - bbox[0]
        else:
            x = box.x + max(0, (box.width - text_width) // 2) - bbox[0]
        ink_top = _component_aligned_y(box.y, box.height, text_height, align_y)
        y = ink_top - bbox[1]
        ctx.draw.text((x, y), text, fill=ctx.resolve_color(node.props), font=font)
        return
    if node.kind == "progress_bar":
        value = _num(node.content.get(node.props.get("field", ""), ""))
        max_value = max(_num(node.content.get(node.props.get("max_field", ""), "")), 1)
        ratio = max(0.0, min(1.0, value / max_value))
        width = min(box.width, node.draw_data.get("width", box.width))
        height = min(box.height, node.draw_data.get("height", box.height))
        align = node.props.get("align", "left")
        if align == "center":
            x = box.x + max(0, (box.width - width) // 2)
        elif align == "right":
            x = box.x + max(0, box.width - width)
        else:
            x = box.x
        y = box.y
        ctx.draw.rectangle([x, y, x + width, y + height], outline=EINK_FG, width=1)
        fill_w = int((width - 2) * ratio)
        if fill_w > 0:
            ctx.draw.rectangle([x + 1, y + 1, x + 1 + fill_w, y + height - 1], fill=EINK_FG)
        return
    if node.kind == "separator":
        style = node.props.get("style", "solid")
        line_width = node.draw_data.get("line_width", 1)
        margin_x = _scaled_value(node.props.get("margin_x"), scale)
        x0 = box.x + margin_x
        x1 = box.x + max(0, box.width - margin_x)
        y = box.y
        if style == "short":
            width = min(box.width, _scaled_value(node.props.get("width"), scale, 60, 4))
            x0 = box.x + max(0, (box.width - width) // 2)
            x1 = x0 + width
            ctx.draw.line([(x0, y), (x1, y)], fill=ctx.resolve_color(node.props), width=line_width)
        elif style == "dashed":
            draw_dashed_line(ctx.draw, (x0, y), (x1, y), fill=ctx.resolve_color(node.props), width=line_width)
        else:
            ctx.draw.line([(x0, y), (x1, y)], fill=ctx.resolve_color(node.props), width=line_width)
        return
    if node.kind == "section_box":
        title = node.draw_data.get("title", "")
        title_font = node.draw_data.get("title_font")
        title_height = node.draw_data.get("title_height", 0)
        icon_name = node.draw_data.get("icon_name")
        icon_size = node.draw_data.get("icon_size", 0)
        title_x = box.x
        if icon_name:
            icon_img = load_icon(icon_name, size=(icon_size, icon_size))
            if icon_img:
                ctx.paste_icon(icon_img, (title_x, box.y))
                title_x += _scaled_value(theme.get("section_icon_gap"), scale, 16)
        if title and title_font is not None:
            title_y = box.y + max(0, (title_height - (title_font.getbbox(title)[3] - title_font.getbbox(title)[1])) // 2)
            ctx.draw.text((title_x, title_y), title, fill=ctx.resolve_color(node.props), font=title_font)
    for child in node.children:
        _paint_component_node(ctx, child, theme, scale)
    if node.props.get("border") and box.width > 0 and box.height > 0:
        bw = _scaled_value(node.props.get("border_width"), scale, 1, 1)
        ctx.draw.rectangle(
            [box.x, box.y, box.x + box.width - 1, box.y + box.height - 1],
            outline=EINK_FG, width=bw,
        )


def _render_component_tree_mode(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    content: dict,
    body_tree: dict,
    theme: dict,
    *,
    screen_w: int,
    screen_h: int,
    status_bar_bottom: int,
    footer_height: int,
    footer_top_offset: int = 0,
    colors: int,
) -> RenderContext:
    ctx = RenderContext(
        draw=draw,
        img=img,
        content=content,
        screen_w=screen_w,
        screen_h=screen_h,
        y=status_bar_bottom,
        footer_height=footer_height,
        footer_top_offset=footer_top_offset,
        colors=colors,
    )
    scale = _component_tree_scale(ctx, theme)
    root = _build_component_node(body_tree, content)
    available_height = max(0, ctx.footer_top - status_bar_bottom)
    _measure_component_node(root, screen_w, theme, scale)
    root_height = available_height if root.kind == "column" else min(available_height, root.measured_height)
    _layout_component_node(root, 0, status_bar_bottom, screen_w, root_height, theme, scale)
    _paint_component_node(ctx, root, theme, scale)
    debug_overlay = body_tree.get("debug_overlay")
    if debug_overlay is None:
        debug_overlay = theme.get("debug_overlay")
    if debug_overlay:
        _paint_component_debug_overlay(ctx, root)
    return ctx


# ── Decorations ──────────────────────────────────────────────


def _load_decoration_image(
    name: str, size: tuple[int, int], *,
    image_mode: str = "auto", dither: bool = False,
) -> Image.Image | None:
    """Load a decoration image, converting to 1-bit for e-ink display.

    image_mode controls the processing algorithm:
      "circle"        - crop to circle with border, keep content inside
      "invert"        - invert colors (for dark-bg icons with white content)
      "invert_dither" - dither then invert bg to white (best for dark-bg detail)
      "color_dither"  - remove colored bg via floodfill then dither (colored-bg icons)
      "auto"          - threshold/dither with transparent white areas
    """
    path = _BACKEND_ROOT / "fonts" / "icons" / f"{name}.png"
    if not path.exists():
        return None
    src = Image.open(path).convert("RGBA")
    src = src.resize(size, Image.LANCZOS)
    w, h = size
    gray = src.convert("L")

    if image_mode == "circle":
        from PIL import ImageDraw as PilDraw
        r = min(w, h) // 2
        cx, cy = w // 2, h // 2
        circle_mask = Image.new("L", size, 0)
        md = PilDraw.Draw(circle_mask)
        md.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        content = gray.point(lambda v: 0 if v < 192 else 255, "1")
        result = Image.new("1", size, 1)
        result.paste(content, mask=circle_mask)
        rd = ImageDraw.Draw(result)
        rd.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=1)
        return result

    if image_mode == "invert":
        inverted = gray.point(lambda v: 0 if v > 128 else 255, "1")
        alpha = gray.point(lambda v: 255 if v > 64 else 0, "L")
        result = Image.new("1", size, 1)
        result.paste(inverted, mask=alpha)
        return result

    if image_mode == "invert_dither":
        from PIL import ImageDraw as PilDraw
        clean = gray.copy()
        for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if clean.getpixel(corner) < 30:
                PilDraw.floodfill(clean, corner, 255, thresh=30)
        return clean.convert("1")

    if image_mode == "color_dither":
        from PIL import ImageDraw as PilDraw
        clean = gray.copy()
        bg_val = sum(clean.getpixel(c) for c in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]) // 4
        thresh = 40
        for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if abs(clean.getpixel(corner) - bg_val) <= thresh:
                PilDraw.floodfill(clean, corner, 255, thresh=thresh)
        return clean.convert("1")

    if dither:
        mono = gray.convert("1")
        alpha = gray.point(lambda v: 255 if v < 220 else 0, "L")
    else:
        mono = gray.point(lambda v: 0 if v < 128 else 255, "1")
        alpha = gray.point(lambda v: 255 if v < 200 else 0, "1")
    result = Image.new("1", size, 1)
    result.paste(mono, mask=alpha)
    return result


def _apply_decorations(
    img: Image.Image,
    decorations: list[dict],
    screen_w: int,
    screen_h: int,
    status_bar_bottom: int,
) -> None:
    """Paste decoration images at absolute positions."""
    if not decorations:
        return
    scale = screen_w / 400.0
    for dec in decorations:
        icon_name = dec.get("icon")
        if not icon_name:
            continue
        size = int(dec.get("size", 36) * scale)
        dither = dec.get("dither", False)
        image_mode = dec.get("image_mode", "auto")
        dec_img = _load_decoration_image(
            icon_name, (size, size), image_mode=image_mode, dither=dither,
        )
        if dec_img is None:
            continue
        margin = int(dec.get("margin", 8) * scale)
        anchor = dec.get("anchor", "top_left")
        if anchor == "top_left":
            x, y = margin, status_bar_bottom + margin
        elif anchor == "top_right":
            x, y = screen_w - size - margin, status_bar_bottom + margin
        elif anchor == "bottom_left":
            x, y = margin, screen_h - size - margin
        elif anchor == "bottom_right":
            x, y = screen_w - size - margin, screen_h - size - margin
        else:
            x, y = margin, status_bar_bottom + margin
        paste_icon_onto(img, dec_img, (x, y))


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
    colors: int = 2,
    language: str = "zh",
) -> Image.Image:
    """Render a JSON-defined mode to an e-ink image (1-bit or 4-color palette)."""
    if colors >= 3:
        img = Image.new("P", (screen_w, screen_h), EINK_BG)
        pal = EINK_4COLOR_PALETTE + [0] * (768 - len(EINK_4COLOR_PALETTE))
        img.putpalette(pal)
    else:
        img = Image.new("1", (screen_w, screen_h), EINK_BG)
    draw = ImageDraw.Draw(img)
    apply_text_fontmode(draw)
    layout = mode_def.get("layout", {})
    overrides = mode_def.get("layout_overrides", {})
    size_key = f"{screen_w}x{screen_h}"
    if size_key in overrides:
        layout = _merge_layout_dict(layout, overrides[size_key])
    layout = expand_layout_presets(layout)

    sb = layout.get("status_bar", {})
    ft_layout = layout.get("footer", {})
    status_bar_pct = 0.10 if screen_h < 200 else 0.12
    # 296×128：旧 draw_status_bar 横线在 int(h*0.11)（约 14px）；若用 int(h*0.10)+2 与之相同，视觉上“没下移”
    if screen_h <= 128:
        status_bar_bottom = int(screen_h * 0.11) + 2
    else:
        status_bar_bottom = int(screen_h * status_bar_pct)

    _dsb_kw: dict[str, Any] = dict(
        draw=draw,
        img=img,
        date_str=date_str,
        weather_str=weather_str,
        battery_pct=int(battery_pct),
        weather_code=weather_code,
        line_width=sb.get("line_width", 1),
        dashed=sb.get("dashed", False),
        time_str=time_str,
        screen_w=screen_w,
        screen_h=screen_h,
        colors=colors,
        language=language,
    )
    if screen_h <= 128:
        _dsb_kw["separator_y"] = status_bar_bottom
    draw_status_bar(**_dsb_kw)

    scale = screen_w / 400.0
    if scale < 0.92:
        scale = 0.92
    min_scale = min(scale, screen_h / 300.0)
    if min_scale < 0.65:
        min_scale = 0.65
    footer_height = int(ft_layout.get("height", 30) * min_scale)
    # 2.9"（128px 高等）：页脚要容纳图标 + 左右文案，缩放后仍须足够高度，否则会贴底
    if screen_h <= 128:
        footer_height = max(footer_height, 24)
    footer_top = screen_h - footer_height
    # 页脚顶部分隔线相对「内容上边界」下移 2–3px，与 draw_footer(y_line) 一致
    footer_top_offset = 0
    if screen_h <= 128:
        footer_top_offset = 3
        footer_top += footer_top_offset

    body = layout.get("body", [])
    if _uses_component_tree(body, layout):
        theme = dict(layout.get("component_theme", {}))
        if "debug_overlay" in layout:
            theme["debug_overlay"] = layout.get("debug_overlay")
        ctx = _render_component_tree_mode(
            draw,
            img,
            content,
            body,
            theme,
            screen_w=screen_w,
            screen_h=screen_h,
            status_bar_bottom=status_bar_bottom,
            footer_height=footer_height,
            footer_top_offset=footer_top_offset,
            colors=colors,
        )
    else:
        body_align = layout.get("body_align", "center")
        _has_vcenter = any(
            b.get("type") == "centered_text" and b.get("vertical_center", True)
            for b in body
        )

        if _has_vcenter and len(body) == 1:
            ctx = RenderContext(
                draw=draw, img=img, content=content,
                screen_w=screen_w, screen_h=screen_h,
                y=status_bar_bottom, footer_height=footer_height, footer_top_offset=footer_top_offset, colors=colors,
            )
            _render_centered_text(ctx, body[0], use_full_body=True)
        elif body_align == "center" and body:
            measure_img = Image.new("1", (screen_w, screen_h), EINK_BG)
            measure_ctx = RenderContext(
                draw=ImageDraw.Draw(measure_img), img=measure_img, content=content,
                screen_w=screen_w, screen_h=screen_h,
                y=status_bar_bottom, footer_height=footer_height, footer_top_offset=footer_top_offset,
            )
            apply_text_fontmode(measure_ctx.draw)
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
                y=status_bar_bottom + offset, footer_height=footer_height, footer_top_offset=footer_top_offset,
                colors=colors,
            )
            for block in body:
                if ctx.y >= footer_top - 10:
                    break
                _render_block(ctx, block)
        else:
            ctx = RenderContext(
                draw=draw, img=img, content=content,
                screen_w=screen_w, screen_h=screen_h,
                y=status_bar_bottom, footer_height=footer_height, footer_top_offset=footer_top_offset, colors=colors,
            )
            for block in body:
                if ctx.y >= footer_top - 10:
                    break
                _render_block(ctx, block)

    _apply_decorations(img, layout.get("decorations", []), screen_w, screen_h, status_bar_bottom)

    ft = ft_layout
    mode_id = mode_def.get("mode_id", "")
    label = _localized_footer_label(mode_id, ft.get("label", mode_id), language)
    attribution = ctx.resolve(ft.get("attribution_template", "")) if ft.get("attribution_template") else ""
    attribution = _localized_footer_attribution(mode_id, attribution, language)
    _attr_font_size = ft.get("font_size")
    if _attr_font_size is not None:
        _attr_font_size = int(_attr_font_size * scale)
    draw_footer(
        draw, img, label, attribution,
        mode_id=mode_id,
        weather_code=content.get("today_code", content.get("code")),
        line_width=ft.get("line_width", 1),
        dashed=ft.get("dashed", False),
        attr_font_size=_attr_font_size,
        screen_w=screen_w, screen_h=screen_h,
        colors=colors,
        footer_top=footer_top,
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

    font_size = max(10, int(block.get("font_size", 16) * ctx.scale))
    font_name = block.get("font_name")
    font_key = block.get("font", "noto_serif_light")
    max_ratio = block.get("max_width_ratio", 0.88)
    line_spacing = int(block.get("line_spacing", 8) * ctx.scale)

    body_height = ctx.footer_top - ctx.y
    max_w = int(ctx.available_width * max_ratio)
    lines = []
    font = None
    line_h = font_size + line_spacing
    total_h = 0
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
        ctx.draw.text((x, y_start + i * line_h), line, fill=ctx.resolve_color(block), font=font)

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
    font_name = block.get("font_name")
    font_key = block.get("font", "noto_serif_regular")
    if font_name and not has_cjk(text):
        font = load_font_by_name(font_name, font_size)
    elif has_cjk(text):
        font_key = _pick_cjk_font(font_key)
        font = load_font(font_key, font_size)
    else:
        font = load_font(font_key, font_size)

    align = block.get("align", "center")
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    max_lines = block.get("max_lines", 3)
    max_w = max(20, ctx.available_width - margin_x * 2)
    line_height = block.get("line_height")
    if line_height is not None:
        line_height = int(line_height * ctx.scale)
    else:
        line_height = font_size + 6

    lines = wrap_text(text, font, max_w)

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines and block.get("ellipsis", True):
            lines[-1] = lines[-1].rstrip() + "..."

    start_y = ctx.y
    rendered_lines = 0
    last_line_h = font_size
    for line in lines:
        line_y = start_y + rendered_lines * line_height
        if line_y >= ctx.footer_top - 10:
            break
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        last_line_h = max(1, bbox[3] - bbox[1])
        if align == "center":
            x = ctx.x_offset + (ctx.available_width - lw) // 2
        elif align == "right":
            x = ctx.x_offset + ctx.available_width - margin_x - lw
        else:
            x = ctx.x_offset + margin_x
        ctx.draw.text((x, line_y), line, fill=ctx.resolve_color(block), font=font)
        rendered_lines += 1
    if rendered_lines:
        used_h = (rendered_lines - 1) * line_height + last_line_h
        if block.get("reserve_line_height"):
            used_h = max(used_h, rendered_lines * line_height)
        min_height = block.get("min_height")
        if min_height is not None:
            used_h = max(used_h, int(min_height * ctx.scale))
        ctx.y = start_y + used_h
        margin_bottom = block.get("margin_bottom")
        if margin_bottom is not None:
            ctx.y += int(margin_bottom * ctx.scale)


def _render_separator(ctx: RenderContext, block: dict) -> None:
    style = block.get("style", "solid")
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    line_width = block.get("line_width", 1)

    color = ctx.resolve_color(block)
    if style == "short":
        w = int(block.get("width", 60) * ctx.scale)
        x0 = ctx.x_offset + (ctx.available_width - w) // 2
        ctx.draw.line([(x0, ctx.y), (x0 + w, ctx.y)], fill=color, width=line_width)
    elif style == "dashed":
        draw_dashed_line(ctx.draw, (ctx.x_offset + margin_x, ctx.y), (ctx.x_offset + ctx.available_width - margin_x, ctx.y),
                         fill=color, width=line_width)
    else:
        ctx.draw.line([(ctx.x_offset + margin_x, ctx.y), (ctx.x_offset + ctx.available_width - margin_x, ctx.y)],
                      fill=color, width=line_width)
    ctx.y += 8 + line_width


def _render_section(ctx: RenderContext, block: dict) -> None:
    raw_title = block.get("title") or block.get("label", "")
    icon_name = block.get("icon")
    if not icon_name:
        icon_name = _section_icon_from_label(raw_title)
    title = _strip_emoji(raw_title)
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
            ctx.paste_icon(icon_img, (x, ctx.y))
            x += int(16 * ctx.scale)

    ctx.draw.text((x, ctx.y), title, fill=ctx.resolve_color(block), font=font)
    ctx.y += title_font_size + int(6 * ctx.scale)

    for child in block.get("children") or block.get("blocks", []):
        if ctx.y >= ctx.footer_top - 10:
            break
        _render_block(ctx, child)

    mb = block.get("margin_bottom")
    if mb is not None:
        ctx.y += int(mb * ctx.scale)


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

    # Ensure CJK font for list items (poetry lines are Chinese strings)
    font_key_cjk = _pick_cjk_font(font_key)
    font = load_font(font_key_cjk, font_size)
    rendered_count = 0
    last_item_spacing = spacing
    last_item_last_line_h = font_size
    for i, item in enumerate(items[:max_items]):
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
        item_height = spacing * max(1, len(lines))

        if ctx.y + item_height > ctx.footer_top:
            remaining = len(items) - rendered_count
            if remaining > 0:
                more_text = f"+{remaining} more"
                more_font = load_font(_pick_cjk_font(font_key), int(11 * ctx.scale))
                ctx.draw.text((ctx.x_offset + margin_x, ctx.y), more_text, fill=ctx.resolve_color(block), font=more_font)
            break
        if ctx.y >= ctx.footer_top - 10:
            break

        color = ctx.resolve_color(block)
        last_line_h = font_size
        if align == "center":
            for line_idx, ln in enumerate(lines):
                bbox = font.getbbox(ln)
                lw = bbox[2] - bbox[0]
                last_line_h = max(1, bbox[3] - bbox[1])
                ctx.draw.text((ctx.x_offset + (ctx.available_width - lw) // 2, ctx.y + line_idx * spacing), ln, fill=color, font=font)
        else:
            for line_idx, ln in enumerate(lines):
                bbox = font.getbbox(ln)
                last_line_h = max(1, bbox[3] - bbox[1])
                ctx.draw.text((ctx.x_offset + margin_x, ctx.y + line_idx * spacing), ln, fill=color, font=font)

        if right_field and isinstance(item, dict):
            rv = str(item.get(right_field, ""))
            if rv:
                score_y = ctx.y + (max(1, len(lines)) - 1) * spacing
                score_bbox = font.getbbox(rv)
                score_w = score_bbox[2] - score_bbox[0]
                score_x = ctx.x_offset + ctx.available_width - margin_x - score_w
                ctx.draw.text((score_x, score_y), rv, fill=color, font=font)

        ctx.y += item_height
        rendered_count += 1
        last_item_spacing = spacing
        last_item_last_line_h = last_line_h
    if rendered_count:
        ctx.y = ctx.y - last_item_spacing + last_item_last_line_h


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
    # Use horizontal scale like font_size/margins—not min_scale (which clamps hard on low
    # heights and makes small height tweaks round to negligible pixel deltas).
    if block.get("height_px") is not None:
        try:
            ctx.y += max(0, int(block["height_px"]))
        except (TypeError, ValueError):
            ctx.y += 0
        return
    try:
        h = float(block.get("height", 12))
    except (TypeError, ValueError):
        h = 12.0
    ctx.y += max(0, int(round(h * ctx.scale)))


def _render_rating_choices(ctx: RenderContext, block: dict) -> None:
    labels = block.get("labels") or ["忘了", "模糊", "记住"]
    if not isinstance(labels, list) or not labels:
        return

    try:
        selected = int(ctx.get_field(block.get("selected_field", "rating_cursor")) or 0)
    except (TypeError, ValueError):
        selected = 0
    selected %= len(labels)

    font_size = int(block.get("font_size", 14) * ctx.scale)
    font_key = block.get("font", "noto_serif_regular")
    if any(has_cjk(str(label)) for label in labels):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)

    margin_x = int(block.get("margin_x", 26) * ctx.scale)
    gap = int(block.get("gap", 8) * ctx.scale)
    height = int(block.get("height", 24) * ctx.scale)
    outline_width = max(1, int(block.get("line_width", 1) * ctx.scale))
    margin_bottom = int(block.get("margin_bottom", 6) * ctx.scale)
    selected_style = str(block.get("selected_style", "fill")).lower()

    count = len(labels)
    total_w = max(20, ctx.available_width - margin_x * 2)
    chip_w = max(12, (total_w - gap * (count - 1)) // count)
    y = ctx.y
    x = ctx.x_offset + margin_x

    for i, raw_label in enumerate(labels):
        label = str(raw_label)
        x0 = x + i * (chip_w + gap)
        x1 = x0 + chip_w
        y1 = y + height
        is_selected = i == selected
        if is_selected and selected_style != "cursor":
            ctx.draw.rectangle([x0, y, x1, y1], fill=EINK_FG)
            text_fill = EINK_BG
        else:
            ctx.draw.rectangle([x0, y, x1, y1], outline=EINK_FG, width=outline_width)
            text_fill = EINK_FG

        bbox = font.getbbox(label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = x0 + (chip_w - text_w) // 2 - bbox[0]
        ty = y + (height - text_h) // 2 - bbox[1]
        ctx.draw.text((tx, ty), label, fill=text_fill, font=font)
        if is_selected and selected_style == "cursor":
            marker_w = max(6, int(block.get("cursor_width", 12) * ctx.scale))
            marker_h = max(2, int(block.get("cursor_height", 3) * ctx.scale))
            marker_gap = max(1, int(block.get("cursor_gap", 2) * ctx.scale))
            mx0 = x0 + (chip_w - marker_w) // 2
            my0 = max(y + 1, y1 - marker_h - marker_gap)
            ctx.draw.rectangle([mx0, my0, mx0 + marker_w, my0 + marker_h], fill=EINK_FG)

    ctx.y = y + height + margin_bottom


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
            ctx.paste_icon(icon_img, (x, ctx.y))
            x += icon_size + 4

    ctx.draw.text((x, ctx.y), text, fill=ctx.resolve_color(block), font=font)
    ctx.y += font_size + 6


def _render_weather_icon_text(ctx: RenderContext, block: dict) -> None:
    """Render dynamic weather icon (by code) with a text label on the same line."""
    from .patterns.utils import get_weather_icon

    code_field = block.get("code_field", "today_code")
    text_field = block.get("field")
    template = block.get("text", "")

    code_val = ctx.get_field(code_field)
    try:
        if isinstance(code_val, str):
            code_int = int(code_val)
        else:
            code_int = int(code_val)
    except (TypeError, ValueError):
        code_int = -1

    if text_field:
        text = str(ctx.get_field(text_field))
    else:
        text = template or ""
        text = ctx.resolve(text)

    if not text:
        return

    font_key = block.get("font", "noto_serif_regular")
    font_size = int(block.get("font_size", 14) * ctx.scale)
    icon_size = int(block.get("icon_size", 18) * ctx.scale)
    icon_gap = int(block.get("icon_gap", 4) * ctx.scale)
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * ctx.scale)
    else:
        margin_x = int(ctx.screen_w * 0.06)
    align = str(block.get("align", "left") or "left")
    margin_bottom = int(block.get("margin_bottom", 6) * ctx.scale)
    icon_y_offset = int(block.get("icon_y_offset", 0) * ctx.scale)
    text_y_offset = int(block.get("text_y_offset", 0) * ctx.scale)

    if has_cjk(text):
        font_key = _pick_cjk_font(font_key)
    font = load_font(font_key, font_size)
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]

    y = ctx.y
    icon_present = code_int >= 0
    total_width = text_width + (icon_size + icon_gap if icon_present else 0)
    if align == "center":
        x = ctx.x_offset + max(0, (ctx.available_width - total_width) // 2)
    elif align == "right":
        x = ctx.x_offset + max(0, ctx.available_width - margin_x - total_width)
    else:
        x = ctx.x_offset + margin_x

    if icon_present:
        icon_img = get_weather_icon(code_int)
        if icon_img:
            if icon_img.size[0] != icon_size:
                icon_img = icon_img.resize((icon_size, icon_size), Image.LANCZOS)
            ctx.paste_icon(icon_img, (x, y + icon_y_offset))
        x += icon_size + icon_gap

    ctx.draw.text((x - bbox[0], y - bbox[1] + text_y_offset), text, fill=ctx.resolve_color(block), font=font)
    text_height = bbox[3] - bbox[1]
    text_ink_left = x - bbox[0]
    text_w = bbox[2] - bbox[0]

    suffix_field = block.get("suffix_field")
    suffix_gap = int(block.get("suffix_gap", 8) * ctx.scale)
    suffix_font_size_raw = block.get("suffix_font_size")
    suffix_sz = (
        int(suffix_font_size_raw * ctx.scale)
        if suffix_font_size_raw is not None
        else font_size
    )
    suffix_font_key = block.get("suffix_font", font_key)

    suffix_height = 0
    if suffix_field and align == "left":
        suffix_text_raw = str(ctx.get_field(suffix_field)).strip()
        if suffix_text_raw:
            suf_font_k = suffix_font_key
            if has_cjk(suffix_text_raw):
                suf_font_k = _pick_cjk_font(suf_font_k)
            sfont = load_font(suf_font_k, suffix_sz)
            sbox = sfont.getbbox(suffix_text_raw)
            suffix_height = sbox[3] - sbox[1]
            suf_x = text_ink_left + text_w + suffix_gap - sbox[0]
            suf_y_in = y - sbox[1] + text_y_offset
            ctx.draw.text((suf_x, suf_y_in), suffix_text_raw, fill=ctx.resolve_color(block), font=sfont)

    row_draw_h = max(
        icon_size + max(0, icon_y_offset) if icon_present else 0,
        text_height + abs(text_y_offset),
        suffix_height + abs(text_y_offset),
    )
    ctx.y += row_draw_h + margin_bottom


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
    font_key = block.get("font", "noto_serif_bold")
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
        x = ctx.x_offset + margin_x - bbox[0]
    elif align == "right":
        x = ctx.x_offset + ctx.available_width - margin_x - tw - bbox[0]
    else:
        x = ctx.x_offset + (ctx.available_width - tw) // 2 - bbox[0]
    y = ctx.y - bbox[1]
    ctx.draw.text((x, y), text, fill=ctx.resolve_color(block), font=font)
    ctx.y += max(0, bbox[3] - bbox[1]) + 6


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


def _render_forecast_cards(ctx: RenderContext, block: dict) -> None:
    """Render multi-day forecast cards similar to the reference UI."""
    field_name = block.get("field", "forecast")
    items = ctx.get_field(field_name)
    if not isinstance(items, list) or not items:
        return

    max_items = int(block.get("max_items", 4))
    items = [it for it in items if isinstance(it, dict)][:max_items]
    if not items:
        return

    scale = ctx.scale
    day_field = block.get("day_field", "day")
    date_field = block.get("date_field", "date")
    desc_field = block.get("desc_field", "desc")
    code_field = block.get("code_field", "code")
    temp_min_field = block.get("temp_min_field", "temp_min")
    temp_max_field = block.get("temp_max_field", "temp_max")
    temp_range_field = block.get("temp_range_field", "temp_range")
    show_desc = bool(block.get("show_desc", True))
    show_temp = bool(block.get("show_temp", True))
    margin_x = block.get("margin_x")
    if margin_x is not None:
        margin_x = int(margin_x * scale)
    else:
        margin_x = int(ctx.screen_w * 0.02)
    gap = int(block.get("gap", 6) * scale)
    day_gap = int(block.get("day_gap", 3) * scale)
    date_gap = int(block.get("date_gap", 5) * scale)
    icon_gap = int(block.get("icon_gap", 4) * scale)
    desc_gap = int(block.get("desc_gap", 3) * scale)
    margin_bottom = int(block.get("margin_bottom", 4) * scale)

    total_width = ctx.available_width - margin_x * 2
    n = len(items)
    card_min_width = int(block.get("card_min_width", 40) * scale)
    requested_card_width = block.get("card_width")
    if requested_card_width is not None:
        card_width = max(card_min_width, int(requested_card_width * scale))
    else:
        card_width = max(card_min_width, (total_width - gap * (n - 1)) // n)

    sample_text = " ".join(
        f"{item.get(day_field, '')} {item.get(date_field, '')} {item.get(desc_field, '')}"
        for item in items
    )
    default_day_font = "noto_serif_regular" if has_cjk(sample_text) else "lora_regular"
    default_date_font = "noto_serif_light" if has_cjk(sample_text) else "inter_medium"
    default_desc_font = "noto_serif_light" if has_cjk(sample_text) else "lora_regular"
    default_temp_font = "noto_serif_light" if has_cjk(sample_text) else "inter_medium"
    font_day = load_font(block.get("day_font", default_day_font), int(block.get("day_font_size", 14) * scale))
    font_date = load_font(block.get("date_font", default_date_font), int(block.get("date_font_size", 12) * scale))
    font_desc = load_font(block.get("desc_font", default_desc_font), int(block.get("desc_font_size", 12) * scale))
    font_temp = load_font(block.get("temp_font", default_temp_font), int(block.get("temp_font_size", 12) * scale))

    from .patterns.utils import get_weather_icon

    top_y = ctx.y
    card_bottom_max = top_y

    for idx, item in enumerate(items):
        x0 = ctx.x_offset + margin_x + idx * (card_width + gap)
        x_center = x0 + card_width // 2
        y = top_y

        day = str(item.get(day_field, ""))
        date = str(item.get(date_field, ""))
        desc = str(item.get(desc_field, ""))
        temp_min_raw = item.get(temp_min_field)
        temp_max_raw = item.get(temp_max_field)
        temp_label = ""
        if temp_min_raw is not None and temp_max_raw is not None:
            try:
                tmin = int(round(_num(temp_min_raw)))
                tmax = int(round(_num(temp_max_raw)))
                temp_label = f"{tmin}/{tmax}°"
            except (TypeError, ValueError):
                temp_label = ""
        if not temp_label:
            temp_label = str(item.get(temp_range_field, ""))
        code = item.get(code_field, -1)

        if day:
            bbox = font_day.getbbox(day)
            dw = bbox[2] - bbox[0]
            ctx.draw.text((x_center - dw / 2, y), day, fill=EINK_FG, font=font_day)
            y += (bbox[3] - bbox[1]) + day_gap

        if date:
            bbox = font_date.getbbox(date)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            ctx.draw.text((x_center - tw / 2, y), date, fill=EINK_FG, font=font_date)
            y += th + date_gap

        icon_size = int(block.get("icon_size", 32) * scale)
        try:
            if isinstance(code, str):
                code_int = int(code)
            else:
                code_int = int(code)
        except (TypeError, ValueError):
            code_int = -1
        wx_icon = get_weather_icon(code_int) if code_int >= 0 else None
        if wx_icon:
            if wx_icon.size[0] != icon_size:
                wx_icon = wx_icon.resize((icon_size, icon_size), Image.LANCZOS)
            ctx.paste_icon(wx_icon, (int(x_center - icon_size / 2), int(y)))
            y += icon_size + icon_gap

        if show_desc and desc:
            bbox = font_desc.getbbox(desc)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            ctx.draw.text((x_center - tw / 2, y), desc, fill=EINK_FG, font=font_desc)
            y += th + desc_gap

        if show_temp and temp_label:
            bbox = font_temp.getbbox(temp_label)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            ctx.draw.text((x_center - tw / 2, y), temp_label, fill=EINK_FG, font=font_temp)
            y += th

        card_bottom_max = max(card_bottom_max, y)

    ctx.y = card_bottom_max + margin_bottom


def _measure_column_blocks_height(
    ctx: RenderContext,
    blocks: list,
    *,
    x_offset: int,
    available_width: int,
) -> int:
    """Total vertical advance Y if ``blocks`` were rendered at y=0 (off-screen bitmap). Used for valign in two_column."""
    if not blocks:
        return 0
    w, h = max(1, ctx.screen_w), max(1, ctx.screen_h)
    measure_img = Image.new("1", (w, h), EINK_BG)
    measure_draw = ImageDraw.Draw(measure_img)
    apply_text_fontmode(measure_draw)
    mc = RenderContext(
        draw=measure_draw,
        img=measure_img,
        content=ctx.content,
        screen_w=ctx.screen_w,
        screen_h=ctx.screen_h,
        y=0,
        x_offset=x_offset,
        available_width=available_width,
        footer_height=ctx.footer_height,
        footer_top_offset=ctx.footer_top_offset,
        colors=ctx.colors,
    )
    for child in blocks:
        if mc.y >= ctx.footer_top - 10:
            break
        _render_block(mc, child)
    return max(0, mc.y)


def _render_two_column(ctx: RenderContext, block: dict) -> None:
    # Very short screens: stack left then right vertically (saves horizontal space was wrong on 296-wide).
    # Weather 296x128 passes stack_when_short: false for a true split column layout.
    if ctx.screen_h < 200 and block.get("stack_when_short", True):
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
    right_avail = max(0, ctx.screen_w - right_x)
    lv = str(block.get("left_valign", "top") or "top").lower()
    rv = str(block.get("right_valign", "top") or "top").lower()
    measure_valign = any(v in ("center", "bottom") for v in (lv, rv))

    row_y0 = ctx.y
    left_h = right_h = 0
    if measure_valign:
        left_h = _measure_column_blocks_height(
            ctx, block.get("left", []), x_offset=left_x, available_width=left_width
        )
        right_h = _measure_column_blocks_height(
            ctx, block.get("right", []), x_offset=right_x, available_width=right_avail
        )
    row_h_base = max(left_h, right_h) if measure_valign else 0
    row_min_design = block.get("row_min_height")
    if measure_valign and row_min_design is not None:
        try:
            row_h = max(row_h_base, int(float(row_min_design) * ctx.scale))
        except (TypeError, ValueError):
            row_h = row_h_base
    else:
        row_h = row_h_base

    left_extra_px = int(block.get("left_offset_px") or 0)
    right_extra_px = int(block.get("right_offset_px") or 0)

    def _valign_delta(content_h: int, mode: str) -> int:
        if not measure_valign or mode == "top":
            return 0
        if mode == "center":
            return max(0, (row_h - content_h) // 2)
        if mode == "bottom":
            return max(0, row_h - content_h)
        return 0

    left_dy = _valign_delta(left_h, lv) + left_extra_px
    right_dy = _valign_delta(right_h, rv) + right_extra_px

    left_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=row_y0 + left_dy,
        x_offset=left_x, available_width=left_width,
        footer_height=ctx.footer_height,
        footer_top_offset=ctx.footer_top_offset,
    )
    right_ctx = RenderContext(
        draw=ctx.draw, img=ctx.img, content=ctx.content,
        screen_w=ctx.screen_w, screen_h=ctx.screen_h, y=row_y0 + right_dy,
        x_offset=right_x, available_width=right_avail,
        footer_height=ctx.footer_height,
        footer_top_offset=ctx.footer_top_offset,
    )
    for child in block.get("left", []):
        _render_block(left_ctx, child)
    for child in block.get("right", []):
        _render_block(right_ctx, child)
    # row_h / valign only offsets children; advancing ctx.y by row_y0+row_h would reserve
    # blank space below the columns and clip following body blocks (e.g. WEATHER advice on 296x128).
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
        
        ctx.paste_icon(weather_icon, (x, ctx.y))
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
                ctx.paste_icon(icon_img, (x, ctx.y))
                x += int(16 * ctx.scale)
        ctx.draw.text((x, ctx.y), text, fill=EINK_FG, font=font)
        ctx.y += line_h


def _resolve_local_asset(url: str) -> str | None:
    """Resolve known local URLs to local filesystem paths."""
    backend_root = Path(__file__).resolve().parent.parent
    repo_root = backend_root.parent

    def _resolve_under(root: Path, rel_path: str) -> str | None:
        root = root.resolve()
        local = (root / rel_path).resolve()
        try:
            local.relative_to(root)
        except ValueError:
            return None
        if local != root and local.exists() and local.is_file():
            return str(local)
        return None

    if url.startswith("/static/"):
        return _resolve_under(backend_root / "static", url[len("/static/"):])
    if url.startswith("/webconfig/"):
        legacy_path = url[len("/webconfig/"):]
        if legacy_path.startswith("assets/art/"):
            return _resolve_under(backend_root / "static" / "art", legacy_path[len("assets/art/"):])
        return _resolve_under(repo_root / "webconfig", legacy_path)
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    path = parsed.path or ""
    if path.startswith("/api/uploads/"):
        upload_id = path.rsplit("/", 1)[-1].strip()
        if not upload_id:
            return None
        try:
            __import__("uuid").UUID(upload_id)
        except ValueError:
            return None
        local = _UPLOAD_DIR / f"{upload_id}.bin"
        if local.exists() and local.is_file():
            return str(local)
    return None


def _render_image(ctx: RenderContext, block: dict) -> None:
    field_name = block.get("field", "image_url")
    image_url = str(ctx.get_field(field_name) or "")
    if not image_url:
        return
    width = int(block.get("width", 220) * ctx.scale)
    height = int(block.get("height", 140) * ctx.scale)
    x = int(block.get("x", (ctx.screen_w - width) // 2))
    y = int(block.get("y", ctx.y))
    fit = str(block.get("fit", "fill") or "fill")
    align_x = str(block.get("align_x", "center") or "center")
    align_y = str(block.get("align_y", "center") or "center")
    photo_enhance = bool(block.get("photo_enhance", False))
    margin_bottom = int(block.get("margin_bottom", 6) * ctx.scale)
    # Try pre-fetched data first (async download from json_content.py)
    prefetched = ctx.content.get(f"_prefetched_{field_name}")
    if prefetched:
        from io import BytesIO
        img = convert_image_block(
            Image.open(BytesIO(prefetched)),
            width,
            height,
            ctx.colors,
            fit=fit,
            align_x=align_x,
            align_y=align_y,
            photo_enhance=photo_enhance,
        )
        if ctx.colors >= 3:
            ctx.img.paste(img, (x, y))
        else:
            ctx.paste_icon(img, (x, y))
        ctx.y = y + height + margin_bottom
        return
    local_path = _resolve_local_asset(image_url)
    if local_path:
        try:
            img = convert_image_block(
                Image.open(local_path),
                width,
                height,
                ctx.colors,
                fit=fit,
                align_x=align_x,
                align_y=align_y,
                photo_enhance=photo_enhance,
            )
            if ctx.colors >= 3:
                ctx.img.paste(img, (x, y))
            else:
                ctx.paste_icon(img, (x, y))
            ctx.y = y + height + margin_bottom
            return
        except (OSError, UnidentifiedImageError):
            logger.warning("[JSONRenderer] Failed to load local asset %s", local_path, exc_info=True)
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
            except (httpx.HTTPError, ValueError) as e:
                last_error = e
                resp = None
        if resp is None:
            raise last_error if last_error else ValueError("image fetch failed")
        from io import BytesIO
        img = convert_image_block(
            Image.open(BytesIO(resp.content)),
            width,
            height,
            ctx.colors,
            fit=fit,
            align_x=align_x,
            align_y=align_y,
            photo_enhance=photo_enhance,
        )
        if ctx.colors >= 3:
            ctx.img.paste(img, (x, y))
        else:
            ctx.paste_icon(img, (x, y))
        ctx.y = y + height + margin_bottom
    except (httpx.HTTPError, ValueError, OSError, UnidentifiedImageError):
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


def _calendar_cell_day_str(cell: Any) -> str:
    if cell is None:
        return ""
    return str(cell).strip()


def _calendar_row_contains_day(row: Any, day: str) -> bool:
    if not isinstance(row, list):
        return False
    t = str(day).strip()
    if not t:
        return False
    return any(_calendar_cell_day_str(c) == t for c in row)


def _calendar_has_leading_carry_row(norm: list[Any]) -> bool:
    """True when row 0 is a prior-month tail row and row 1 starts the month's days (has day 1)."""
    if len(norm) < 2:
        return False
    return not _calendar_row_contains_day(norm[0], "1") and _calendar_row_contains_day(
        norm[1], "1"
    )


def slice_calendar_rows_around_day(rows: list[Any], today: str, *, max_rows: int) -> list[Any]:
    """Return at most ``max_rows`` week-rows so ``today`` appears when possible.

    Rules (``max_rows`` == 2):
    - Today's week is row 1 of the month: show rows 1–2.
    - Today's week is neither first nor last: show that row and the next row.
      If the grid has a leading previous-month row followed by the week that
      contains day 1, shift the window up by one so week 1 stays visible with
      today's week.
    - Today's week is the last row: show the previous row and the last row.
    """
    if max_rows < 1 or not rows:
        return rows
    norm: list[Any] = [r if isinstance(r, list) else [] for r in rows]
    n = len(norm)
    if n <= max_rows:
        return norm[:]
    t = str(today).strip()
    idx: int | None = None
    for i, row in enumerate(norm):
        if _calendar_row_contains_day(row, t):
            idx = i
            break
    if idx is None:
        return norm[:max_rows]
    if idx == 0:
        start = 0
    elif idx >= n - 1:
        start = max(0, n - max_rows)
    elif (
        max_rows == 2
        and 2 <= idx < n - 1
        and _calendar_has_leading_carry_row(norm)
    ):
        # Extra week row from the previous month above row 1: keep "week of day 1" + today week
        # (avoids jumping past the first full month week when the match index shifts by +1).
        start = idx - 1
    else:
        start = idx
    return norm[start : start + max_rows]


def _render_calendar_grid(ctx: RenderContext, block: dict) -> None:
    """Render a 7-column monthly calendar grid with today highlight and sub-labels."""
    rows_raw = ctx.get_field(block.get("rows_field", "calendar_rows"))
    rows = rows_raw if isinstance(rows_raw, list) else []
    headers = ctx.get_field(block.get("headers_field", "weekday_headers"))
    today = str(ctx.get_field(block.get("today_field", "today_day")))
    day_labels = ctx.get_field(block.get("labels_field", "day_labels")) or {}
    day_label_types = ctx.get_field(block.get("label_types_field", "day_label_types")) or {}
    if not isinstance(rows, list) or not isinstance(headers, list):
        return
    mr_raw = block.get("max_rows")
    if mr_raw is not None:
        try:
            rows = slice_calendar_rows_around_day(rows, today, max_rows=max(1, int(mr_raw)))
        except (TypeError, ValueError):
            pass

    if not isinstance(day_labels, dict):
        day_labels = {}
    if not isinstance(day_label_types, dict):
        day_label_types = {}

    font_size = int(block.get("font_size", 14) * ctx.scale)
    header_font_size = int(block.get("header_font_size", 10) * ctx.scale)
    sub_font_size = max(int(block.get("sub_font_size", 7) * ctx.scale), 6)
    reminder_font_size = max(int(block.get("reminder_font_size", sub_font_size) * ctx.scale), 6)
    font_key = _pick_cjk_font(block.get("font", "noto_serif_regular"))
    reminder_font_key = _pick_cjk_font(block.get("reminder_font", "noto_serif_light"))
    font = load_font(font_key, font_size)
    header_font = load_font(font_key, header_font_size)
    sub_font = load_font(font_key, sub_font_size)
    reminder_font = load_font(reminder_font_key, reminder_font_size)

    margin_x = int(block.get("margin_x", 12) * ctx.scale)
    cell_h = int(block.get("cell_height", 24) * ctx.scale)
    grid_w = ctx.available_width - margin_x * 2
    cell_w = grid_w // 7
    x0 = ctx.x_offset + margin_x
    weekend_start = int(block.get("weekend_start", 5))
    header_gap = int(block.get("header_gap", 3) * ctx.scale)
    date_line_gap = int(block.get("date_line_gap", 1) * ctx.scale)
    show_day_labels = bool(block.get("show_day_labels", True))
    today_style = str(block.get("today_style", "filled") or "filled")
    today_padding = int(block.get("today_padding", 1) * ctx.scale)

    weekend_color = _resolve_named_color(ctx, block.get("weekend_color", "red"), EINK_FG)
    today_bg = _resolve_named_color(ctx, block.get("today_fill_color", "red"), EINK_FG)
    today_text_color = _resolve_named_color(ctx, block.get("today_text_color"), EINK_BG)
    reminder_color = _resolve_named_color(ctx, block.get("reminder_color", "yellow"), EINK_FG)
    festival_color = _resolve_named_color(ctx, block.get("festival_color", "red"), EINK_FG)

    for ci, hdr in enumerate(headers[:7]):
        cx = x0 + ci * cell_w + cell_w // 2
        bbox = header_font.getbbox(hdr)
        tw = bbox[2] - bbox[0]
        color = weekend_color if ci >= weekend_start else EINK_FG
        ctx.draw.text((cx - tw // 2, ctx.y), hdr, fill=color, font=header_font)
    ctx.y += header_font_size + header_gap

    date_line_h = font_size + date_line_gap

    for row in rows:
        if not isinstance(row, list):
            continue
        if ctx.y + cell_h > ctx.footer_top - 10:
            break
        for ci, day_str in enumerate(row[:7]):
            ds = _calendar_cell_day_str(day_str)
            if not ds:
                continue
            cx = x0 + ci * cell_w + cell_w // 2
            bbox = font.getbbox(ds)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = cx - tw // 2
            ty = ctx.y

            if ds == str(today).strip():
                r = max(tw, th) // 2 + today_padding
                cy = ty + th // 2 + int(2 * ctx.scale)
                ec = (cx - r, cy - r, cx + r, cy + r)
                if today_style == "outline":
                    ctx.draw.ellipse(ec, outline=today_bg, width=1)
                elif today_style == "none":
                    pass
                else:
                    ctx.draw.ellipse(ec, fill=today_bg)
                ctx.draw.text((tx, ty), ds, fill=today_text_color if today_style != "none" else EINK_FG, font=font)
            else:
                color = weekend_color if ci >= weekend_start else EINK_FG
                ctx.draw.text((tx, ty), ds, fill=color, font=font)

            sub = day_labels.get(ds, "")
            if show_day_labels and sub:
                lt = day_label_types.get(ds, "lunar")
                label_font = reminder_font if lt == "reminder" else sub_font
                sb = label_font.getbbox(sub)
                sw = sb[2] - sb[0]
                sx = cx - sw // 2
                sy = ty + date_line_h
                if lt == "reminder":
                    sub_color = reminder_color
                elif lt in ("festival", "solar_term"):
                    sub_color = festival_color
                else:
                    sub_color = EINK_FG
                ctx.draw.text((sx, sy), sub, fill=sub_color, font=label_font)
        ctx.y += cell_h


def _render_timetable_grid(ctx: RenderContext, block: dict) -> None:
    """Render a timetable grid -- daily (list) or weekly (table)."""
    style = str(ctx.get_field("style") or "daily")
    if style == "weekly":
        _render_timetable_weekly(ctx, block)
    else:
        _render_timetable_daily(ctx, block)


def _render_timetable_daily(ctx: RenderContext, block: dict) -> None:
    slots = ctx.get_field(block.get("field", "slots"))
    if not isinstance(slots, list):
        return

    raw_font_size = float(block.get("font_size", 11))
    raw_loc_font_size = float(block.get("location_font_size", max(8, raw_font_size - 2)))
    font_size = int(raw_font_size * ctx.scale)
    loc_font_size = int(raw_loc_font_size * ctx.scale)
    font_key = _pick_cjk_font(block.get("font", "noto_serif_regular"))
    font = load_font(font_key, font_size)
    small_font = load_font(font_key, max(8, loc_font_size))

    margin_x = int(block.get("margin_x", 12) * ctx.scale)
    row_h = int(block.get("row_height", 28) * ctx.scale)
    grid_w = ctx.available_width - margin_x * 2
    time_col_ratio = float(block.get("time_col_ratio", 0.22))
    time_col_w = int(grid_w * time_col_ratio)
    x0 = ctx.x_offset + margin_x

    highlight_color = _resolve_named_color(ctx, block.get("highlight_color", "red"), EINK_FG)
    accent_color = _resolve_named_color(ctx, block.get("accent_color", "yellow"), EINK_FG)
    current_text_color = _resolve_named_color(ctx, block.get("current_text_color"), EINK_BG)
    show_location = bool(block.get("show_location", True))
    show_separator = bool(block.get("show_separator", True))
    time_field = str(block.get("time_field", "time"))
    name_field = str(block.get("name_field", "name"))
    location_field = str(block.get("location_field", "location"))
    current_field = str(block.get("current_field", "current"))

    for i, slot in enumerate(slots):
        if not isinstance(slot, dict):
            continue
        if ctx.y + row_h > ctx.footer_top - 10:
            break

        time_str = str(slot.get(time_field, ""))
        name = str(slot.get(name_field, ""))
        is_current = slot.get(current_field, False)
        loc = str(slot.get(location_field, ""))

        if is_current:
            ctx.draw.rectangle(
                [x0, ctx.y, x0 + grid_w, ctx.y + row_h - 1],
                fill=highlight_color if ctx.colors >= 3 else EINK_FG,
            )
            text_color = current_text_color
        else:
            text_color = EINK_FG

        ctx.draw.text((x0 + 2, ctx.y + 4), time_str, fill=text_color, font=small_font)
        ctx.draw.text((x0 + time_col_w, ctx.y + 2), name, fill=text_color, font=font)
        if show_location and loc:
            loc_color = current_text_color if is_current and ctx.colors >= 3 else accent_color
            ctx.draw.text((x0 + time_col_w, ctx.y + font_size + 3), loc, fill=loc_color, font=small_font)

        ctx.y += row_h

        if show_separator and i < len(slots) - 1:
            ctx.draw.line([(x0, ctx.y - 1), (x0 + grid_w, ctx.y - 1)], fill=EINK_FG, width=1)


def _fit_text(text: str, font: Any, max_w: int) -> tuple[str, str]:
    """Split text into (fits, remainder). Truncates only as last resort."""
    if font.getlength(text) <= max_w:
        return text, ""
    for i in range(len(text), 0, -1):
        if font.getlength(text[:i]) <= max_w:
            return text[:i], text[i:]
    return "", text


def _draw_two_line_cell(
    ctx: RenderContext, cx: int, cy: int, col_w: int, row_h: int,
    name: str, loc: str, font_key: str, base_size: int,
    text_color: int, loc_color: int,
) -> None:
    max_w = col_w - 4
    f = load_font(font_key, base_size)
    sf = load_font(font_key, max(8, base_size - 2))
    sub_sz = max(8, base_size - 2)
    line_h = base_size + 1

    line1, remainder = _fit_text(name, f, max_w)

    if not remainder:
        loc_disp, _ = _fit_text(loc, sf, max_w)
        total_h = line_h + sub_sz
        ny = cy + (row_h - total_h) // 2
        nb = f.getbbox(line1); nw = nb[2] - nb[0]
        ctx.draw.text((cx + (col_w - nw) // 2, ny), line1, fill=text_color, font=f)
        lb = sf.getbbox(loc_disp); lw = lb[2] - lb[0]
        ctx.draw.text((cx + (col_w - lw) // 2, ny + line_h), loc_disp, fill=loc_color, font=sf)
        return

    line2, leftover = _fit_text(remainder, sf, max_w)
    if leftover:
        line2 = line2[: max(0, len(line2) - len(leftover))] + leftover if not line2 else line2
    loc_disp, _ = _fit_text(loc, sf, max_w)

    total_h = line_h + sub_sz + sub_sz
    ny = cy + (row_h - total_h) // 2

    nb = f.getbbox(line1); nw = nb[2] - nb[0]
    ctx.draw.text((cx + (col_w - nw) // 2, ny), line1, fill=text_color, font=f)

    l2b = sf.getbbox(line2); l2w = l2b[2] - l2b[0]
    ctx.draw.text((cx + (col_w - l2w) // 2, ny + line_h), line2, fill=text_color, font=sf)

    lb = sf.getbbox(loc_disp); lw = lb[2] - lb[0]
    ctx.draw.text((cx + (col_w - lw) // 2, ny + line_h + sub_sz), loc_disp, fill=loc_color, font=sf)


def _draw_single_line_cell(
    ctx: RenderContext, cx: int, cy: int, col_w: int, row_h: int,
    text: str, font_key: str, base_size: int, text_color: int,
) -> None:
    f = load_font(font_key, base_size)
    disp, _ = _fit_text(text, f, col_w - 4)
    tb = f.getbbox(disp)
    tw = tb[2] - tb[0]
    ctx.draw.text((cx + (col_w - tw) // 2, cy + (row_h - base_size) // 2), disp, fill=text_color, font=f)


def _render_timetable_weekly(ctx: RenderContext, block: dict) -> None:
    periods = ctx.get_field(block.get("periods_field", "periods"))
    grid = ctx.get_field(block.get("grid_field", "grid"))
    weekdays = ctx.get_field(block.get("weekdays_field", "weekdays")) or ["一", "二", "三", "四", "五"]
    current_day = ctx.get_field(block.get("current_day_field", "current_day"))
    current_period = ctx.get_field(block.get("current_period_field", "current_period"))
    if not isinstance(periods, list) or not isinstance(grid, list):
        return
    if not isinstance(current_day, int):
        current_day = -1
    if not isinstance(current_period, int):
        current_period = -1

    font_size = int(block.get("font_size", 11) * ctx.scale)
    header_font_size = int(block.get("header_font_size", font_size) * ctx.scale) if block.get("header_font_size") else font_size
    font_key = _pick_cjk_font(block.get("font", "noto_serif_regular"))
    font = load_font(font_key, font_size)
    sub_font = load_font(font_key, max(8, font_size - 2))
    header_font = load_font(font_key, header_font_size)
    period_font = load_font(font_key, max(8, font_size - 2))

    margin_x = int(block.get("margin_x", 8) * ctx.scale)
    grid_w = ctx.available_width - margin_x * 2
    x0 = ctx.x_offset + margin_x

    has_time_range = any("-" in p and ":" in p for p in periods)
    time_col_ratio = float(block.get("time_col_ratio", 0.22 if has_time_range else 0.14))

    n_periods = len(periods)
    header_h = int(block.get("header_height", 16) * ctx.scale)
    avail_h = ctx.footer_top - ctx.y - header_h - int(4 * ctx.scale)
    requested_row_height = block.get("row_height")
    if requested_row_height is not None:
        row_h = int(requested_row_height * ctx.scale)
    else:
        row_h = max(int(16 * ctx.scale), avail_h // max(n_periods, 1))

    time_col_w = int(grid_w * time_col_ratio)
    day_count = max(1, len(weekdays))
    day_col_w = (grid_w - time_col_w) // day_count

    highlight_color = _resolve_named_color(ctx, block.get("highlight_color", "red"), EINK_FG)
    accent_color = _resolve_named_color(ctx, block.get("accent_color", "yellow"), EINK_FG)
    current_text_color = _resolve_named_color(ctx, block.get("current_text_color"), EINK_BG)
    show_location = bool(block.get("show_location", True))

    hx = x0 + time_col_w
    for di, wd_label in enumerate(weekdays[:day_count]):
        cell_x = hx + di * day_col_w
        cx = cell_x + day_col_w // 2
        bb = header_font.getbbox(wd_label)
        tw = bb[2] - bb[0]
        tx = cx - tw // 2
        color = highlight_color if di == current_day else EINK_FG
        if di == current_day and ctx.colors < 3:
            ctx.draw.rectangle(
                [
                    cell_x + 1,
                    ctx.y,
                    cell_x + day_col_w - 2,
                    ctx.y + header_h - 1,
                ],
                fill=EINK_FG,
            )
            color = EINK_BG
        ctx.draw.text((tx, ctx.y), wd_label, fill=color, font=header_font)
    ctx.y += header_h
    ctx.draw.line([(x0, ctx.y), (x0 + grid_w, ctx.y)], fill=EINK_FG, width=1)
    ctx.y += 1

    sep_indices: set[int] = set()
    if has_time_range:
        for pi, p_label in enumerate(periods):
            try:
                h = int(p_label.split("-")[0].strip().split(":")[0])
                if pi > 0:
                    prev_h = int(periods[pi - 1].split("-")[0].strip().split(":")[0])
                    if prev_h < 12 <= h:
                        sep_indices.add(pi)
                    elif prev_h < 18 <= h:
                        sep_indices.add(pi)
            except (ValueError, IndexError):
                pass
    else:
        mid = n_periods // 2
        if mid > 0:
            sep_indices.add(mid)

    for pi, p_label in enumerate(periods):
        if ctx.y + row_h > ctx.footer_top - 4:
            break

        if pi in sep_indices:
            sep_y = ctx.y - 1
            ctx.draw.line([(x0, sep_y), (x0 + grid_w, sep_y)], fill=EINK_FG, width=1)

        bb = period_font.getbbox(p_label)
        pw = bb[2] - bb[0]
        px = x0 + (time_col_w - pw) // 2
        py = ctx.y + (row_h - font_size) // 2
        ctx.draw.text((px, py), p_label, fill=EINK_FG, font=period_font)

        row_data = grid[pi] if pi < len(grid) else []

        for di in range(day_count):
            cell_x = x0 + time_col_w + di * day_col_w
            cell_text = str(row_data[di]) if di < len(row_data) else ""

            is_current_cell = (di == current_day and pi == current_period)
            highlight_col = (not has_time_range and di == current_day)
            highlight_today_course_bw = (ctx.colors < 3 and di == current_day and bool(cell_text))

            if is_current_cell or highlight_today_course_bw:
                ctx.draw.rectangle(
                    [cell_x + 1, ctx.y, cell_x + day_col_w - 1, ctx.y + row_h - 1],
                    fill=highlight_color if ctx.colors >= 3 else EINK_FG,
                )
                text_color = current_text_color
            elif highlight_col:
                ctx.draw.rectangle(
                    [cell_x + 1, ctx.y, cell_x + day_col_w - 1, ctx.y + row_h - 1],
                    fill=highlight_color if ctx.colors >= 3 else EINK_FG,
                )
                text_color = current_text_color
            else:
                text_color = EINK_FG

            if cell_text:
                if show_location and "/" in cell_text:
                    full_name, loc_part = cell_text.split("/", 1)
                    _draw_two_line_cell(
                        ctx, cell_x, ctx.y, day_col_w, row_h,
                        full_name, loc_part, font_key, font_size,
                        text_color, current_text_color if text_color == current_text_color else accent_color,
                    )
                else:
                    _draw_single_line_cell(
                        ctx, cell_x, ctx.y, day_col_w, row_h,
                        cell_text, font_key, font_size, text_color,
                    )

        ctx.y += row_h


# ── Register block types ─────────────────────────────────────

_BLOCK_RENDERERS["centered_text"] = _render_centered_text
_BLOCK_RENDERERS["text"] = _render_text
_BLOCK_RENDERERS["separator"] = _render_separator
_BLOCK_RENDERERS["section"] = _render_section
_BLOCK_RENDERERS["list"] = _render_list
_BLOCK_RENDERERS["vertical_stack"] = _render_vertical_stack
_BLOCK_RENDERERS["conditional"] = _render_conditional
_BLOCK_RENDERERS["spacer"] = _render_spacer
_BLOCK_RENDERERS["rating_choices"] = _render_rating_choices
_BLOCK_RENDERERS["icon_text"] = _render_icon_text
_BLOCK_RENDERERS["weather_icon_text"] = _render_weather_icon_text
_BLOCK_RENDERERS["two_column"] = _render_two_column
_BLOCK_RENDERERS["image"] = _render_image
_BLOCK_RENDERERS["progress_bar"] = _render_progress_bar
_BLOCK_RENDERERS["temp_chart"] = _render_temp_chart
_BLOCK_RENDERERS["forecast_cards"] = _render_forecast_cards
_BLOCK_RENDERERS["big_number"] = _render_big_number
_BLOCK_RENDERERS["icon_list"] = _render_icon_list
_BLOCK_RENDERERS["key_value"] = _render_key_value
_BLOCK_RENDERERS["group"] = _render_group
_BLOCK_RENDERERS["weather_icon"] = _render_weather_icon
_BLOCK_RENDERERS["calendar_grid"] = _render_calendar_grid
_BLOCK_RENDERERS["timetable_grid"] = _render_timetable_grid
