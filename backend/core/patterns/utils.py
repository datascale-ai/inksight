"""
渲染工具函数
提供所有模式共用的基础渲染功能
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)
from ..config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    EINK_BACKGROUND,
    EINK_FOREGROUND,
    EINK_COLOR_NAME_MAP,
    EINK_COLOR_AVAILABILITY,
    WEATHER_ICON_MAP,
    ICON_SIZES,
    FONTS,
    FONT_SIZES,
)

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
TRUETYPE_DIR = os.path.join(FONTS_DIR, "truetype")
BITMAP_DIR = os.path.join(FONTS_DIR, "bitmap")
ICONS_DIR = os.path.join(FONTS_DIR, "icons")

SCREEN_W = SCREEN_WIDTH
SCREEN_H = SCREEN_HEIGHT
EINK_BG = EINK_BACKGROUND
EINK_FG = EINK_FOREGROUND


def paste_icon_onto(target: Image.Image, icon: Image.Image, pos: tuple[int, int], fill: int = EINK_FG) -> None:
    """Paste a 1-bit icon handling palette mode transparency."""
    if target.mode == "P":
        mask = icon.convert("L").point(lambda p: 255 - p)
        target.paste(fill, pos, mask)
    else:
        target.paste(icon, pos)

_font_warned: set[str] = set()
_bitmap_warned: set[str] = set()
_font_engine = os.getenv("INKSIGHT_FONT_ENGINE", "bitmap").strip().lower()
_force_bitmap = _font_engine in {"bitmap", "pixel", "pil"}
_fontmode = os.getenv("INKSIGHT_TEXT_FONTMODE", "1").strip() or "1"
_bitmap_suffix_to_load_size = {9: 12, 10: 13, 11: 15, 12: 16, 13: 14}
# After component-tree scale (~1.35 on 648px+ wide screens), body/title pt often lands in
# the high teens or low twenties; default 16 blocked PCF and forced anti-aliased TTF on e-ink.
_bitmap_max_request_size = int(os.getenv("INKSIGHT_BITMAP_MAX_REQUEST_SIZE", "24"))
_bitmap_max_size_delta = int(os.getenv("INKSIGHT_BITMAP_MAX_SIZE_DELTA", "8"))


def apply_text_fontmode(draw: ImageDraw.ImageDraw) -> None:
    """Configure Pillow text rasterization (`ImageDraw.Draw.fontmode`).

    On mode ``1`` (binary) images, ``fontmode="L"`` anti-aliases into gray values that
    threshold poorly on e-ink previews and look uniformly blurry across modes (BRIEFING,
    DAILY, etc.). Mono ``"1"`` matches crisp PCF bitmaps and avoids mushy strokes.
    """
    im = getattr(draw, "_image", None) or getattr(draw, "im", None)
    if im is not None and getattr(im, "mode", None) == "1":
        draw.fontmode = "1"
        return
    draw.fontmode = "1" if _fontmode != "L" else "L"


def _bitmap_load_size_for_suffix(suffix: int) -> int:
    return _bitmap_suffix_to_load_size.get(suffix, suffix)


def _available_bitmap_suffixes(font_name: str) -> list[int]:
    name = os.path.basename(font_name)
    stem, _ = os.path.splitext(name)
    suffixes = set(_bitmap_suffix_to_load_size.keys())
    try:
        for rel in os.listdir(BITMAP_DIR):
            m = re.fullmatch(rf"{re.escape(stem)}-(\d+)\.(pcf|otb|pil|ttf|otf)", rel, re.IGNORECASE)
            if m:
                suffixes.add(int(m.group(1)))
    except OSError:
        pass
    return sorted(suffixes)


def _ordered_bitmap_suffixes(font_name: str, size: int) -> list[int]:
    return sorted(
        _available_bitmap_suffixes(font_name),
        key=lambda s: abs(_bitmap_load_size_for_suffix(s) - size),
    )


def _bitmap_load_size_from_path(path: str, requested_size: int) -> int:
    m = re.search(r"-(\d+)\.(pcf|otb|ttf|otf)$", path.lower())
    if m:
        suffix = int(m.group(1))
        return _bitmap_load_size_for_suffix(suffix)
    return requested_size


def _bitmap_candidates(font_name: str, size: int) -> list[str]:
    name = os.path.basename(font_name)
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext in {".pil", ".pcf", ".otb"}:
        return [name]
    suffixes = _ordered_bitmap_suffixes(font_name, size)
    suffixes = [
        s for s in suffixes
        if abs(_bitmap_load_size_for_suffix(s) - size) <= _bitmap_max_size_delta
    ]
    sized_pcf = [f"{stem}-{s}.pcf" for s in suffixes]
    sized_otb = [f"{stem}-{s}.otb" for s in suffixes]
    sized_pil = [f"{stem}-{s}.pil" for s in suffixes]
    sized_ttf = [f"{stem}-{s}.ttf" for s in suffixes]
    sized_otf = [f"{stem}-{s}.otf" for s in suffixes]
    return [
        *sized_pcf,
        *sized_otb,
        *sized_pil,
        *sized_ttf,
        *sized_otf,
        f"{stem}.pcf",
        f"{stem}.otb",
        f"{stem}.pil",
        f"{stem}.ttf",
        f"{stem}.otf",
    ]


def _bitmap_font_accepts_unicode_measurement(font: ImageFont.ImageFont) -> bool:
    """Skip legacy PIL bitmap fonts that only support latin-1 (breaks CJK layout)."""
    try:
        font.getbbox("\u4e94")
        return True
    except (UnicodeEncodeError, TypeError, ValueError, OSError):
        return False


def safe_font_bbox(font: ImageFont.ImageFont, text: str) -> tuple[int, int, int, int]:
    """Bounding box for wrapping/measurement; avoids latin-1-only PIL bitmap crashes on CJK."""
    if not text:
        return (0, 0, 0, 0)
    try:
        return font.getbbox(text)
    except (UnicodeEncodeError, TypeError, ValueError, OSError):
        pass
    im = Image.new("L", (8, 8), 255)
    draw = ImageDraw.Draw(im)
    try:
        return draw.textbbox((0, 0), text, font=font)
    except (UnicodeEncodeError, TypeError, ValueError, OSError):
        pass
    try:
        px = int(getattr(font, "size", 0) or 0)
    except Exception:
        px = 0
    if px <= 0:
        px = 16
    w = max(1, len(text)) * max(6, int(px * 0.55))
    return (0, -int(px * 0.8), int(w), int(px * 0.25))


def _load_bitmap_font(font_name: str, size: int) -> ImageFont.ImageFont | None:
    if size > _bitmap_max_request_size:
        return None
    for rel in _bitmap_candidates(font_name, size):
        path = os.path.join(BITMAP_DIR, rel)
        if not os.path.exists(path):
            continue
        try:
            lower = path.lower()
            if lower.endswith(".pil"):
                ft = ImageFont.load(path)
            else:
                load_size = _bitmap_load_size_from_path(path, size)
                ft = ImageFont.truetype(path, load_size)
            if not _bitmap_font_accepts_unicode_measurement(ft):
                continue
            return ft
        except Exception:
            if rel not in _bitmap_warned:
                _bitmap_warned.add(rel)
                logger.warning(f"[FONT] Failed to load bitmap font: {path}", exc_info=True)
    return None


def load_font(font_key: str, size: int, force_truetype: bool = False) -> ImageFont.ImageFont:
    """从配置加载字体"""
    font_name = FONTS.get(font_key)
    if not font_name:
        # Fallback to CJK font if default font key not found
        fallback_cjk = "NotoSerifSC-Regular.ttf"
        fallback_path = os.path.join(TRUETYPE_DIR, fallback_cjk)
        if os.path.exists(fallback_path):
            return ImageFont.truetype(fallback_path, size)
        return ImageFont.load_default()
    if _force_bitmap and not force_truetype:
        bitmap_font = _load_bitmap_font(font_name, size)
        if bitmap_font is not None:
            return bitmap_font
    path = os.path.join(TRUETYPE_DIR, font_name)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            logger.warning(f"[FONT] Failed to load {font_name}: {e}")
            # Fallback to CJK font if loading fails
            fallback_cjk = "NotoSerifSC-Regular.ttf"
            fallback_path = os.path.join(TRUETYPE_DIR, fallback_cjk)
            if os.path.exists(fallback_path):
                return ImageFont.truetype(fallback_path, size)
    if font_key not in _font_warned:
        _font_warned.add(font_key)
        logger.warning(f"[FONT] Missing {font_name}, run: python scripts/setup_fonts.py")
    # Final fallback: try CJK font before default
    fallback_cjk = "NotoSerifSC-Regular.ttf"
    fallback_path = os.path.join(TRUETYPE_DIR, fallback_cjk)
    if os.path.exists(fallback_path):
        return ImageFont.truetype(fallback_path, size)
    return ImageFont.load_default()


def load_font_by_name(name: str, size: int, force_truetype: bool = False) -> ImageFont.ImageFont:
    """直接通过文件名加载字体（兼容旧代码）"""
    if _force_bitmap and not force_truetype:
        bitmap_font = _load_bitmap_font(name, size)
        if bitmap_font is not None:
            return bitmap_font
    path = os.path.join(TRUETYPE_DIR, name)
    if os.path.exists(path):
        if name.lower().endswith(".pil"):
            return ImageFont.load(path)
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            logger.warning(f"[FONT] Failed to load {name}: {e}")
            fallback_cjk = "NotoSerifSC-Regular.ttf"
            fallback_path = os.path.join(TRUETYPE_DIR, fallback_cjk)
            if os.path.exists(fallback_path):
                return ImageFont.truetype(fallback_path, size)
    if name not in _font_warned:
        _font_warned.add(name)
        logger.warning(f"[FONT] Missing {name}, run: python scripts/setup_fonts.py")
    return ImageFont.load_default()


def rgba_to_mono(
    img: Image.Image, target_size: tuple[int, int] | None = None
) -> Image.Image:
    """Convert an RGBA icon to monochrome (mode '1'), optionally resizing."""
    if target_size:
        img = img.resize(target_size, Image.LANCZOS)
    img = img.convert("RGBA")
    mono = Image.new("1", img.size, 1)
    for x in range(img.width):
        for y in range(img.height):
            _, _, _, a = img.getpixel((x, y))
            if a > 128:
                mono.putpixel((x, y), 0)
    return mono


def load_icon(name: str, size: tuple[int, int] | None = None) -> Image.Image | None:
    """Load a PNG icon from ICONS_DIR, convert to monochrome, optionally resize."""
    path = os.path.join(ICONS_DIR, f"{name}.png")
    if os.path.exists(path):
        img = Image.open(path)
        if img.mode == "1":
            if size:
                img = img.resize(size, Image.LANCZOS)
            return img
        return rgba_to_mono(img, size)
    return None


def get_weather_icon(weather_code: int) -> Image.Image | None:
    """Get weather icon image by WMO weather code."""
    icon_name = WEATHER_ICON_MAP.get(weather_code, "cloud")
    return load_icon(icon_name, size=ICON_SIZES["weather"])


def get_mode_icon(mode: str) -> Image.Image | None:
    """Get footer mode icon (book, electric_bolt, etc.)."""
    icon_name = None
    try:
        from ..mode_registry import get_registry
        info = get_registry().get_mode_info(mode)
        if info:
            icon_name = info.icon
    except (ImportError, AttributeError, RuntimeError):
        logger.warning("[FONT] Falling back to static mode icon mapping for %s", mode, exc_info=True)
        # Registry may be unavailable in some test/bootstrap paths.
        fallback_icons = {
            "DAILY": "sunny",
            "BRIEFING": "global",
            "ARTWALL": "art",
            "RECIPE": "food",
            "COUNTDOWN": "flag",
        }
        icon_name = fallback_icons.get(mode.upper())
    if icon_name:
        return load_icon(icon_name, size=ICON_SIZES["mode"])
    return None


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple,
    end: tuple,
    fill=0,
    width: int = 1,
    dash_len: int = 4,
    gap_len: int = 4,
):
    """Draw a horizontal dashed line (for zen/faded style)."""
    x0, y0 = start
    x1, _ = end
    x = x0
    while x < x1:
        seg_end = min(x + dash_len, x1)
        draw.line([(x, y0), (seg_end, y0)], fill=fill, width=width)
        x += dash_len + gap_len


def _resolve_status_bar_time(time_str: str = "") -> tuple[str, int]:
    """Return a zero-padded HH:MM string and its hour for period labels."""
    match = re.match(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$", str(time_str or ""))
    if match:
        try:
            hour = int(match.group(1))
            minute = int(match.group(2))
            second = int(match.group(3) or 0)
            if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                return f"{hour:02d}:{minute:02d}", hour
        except ValueError:
            pass

    now = datetime.now()
    return f"{now.hour:02d}:{now.minute:02d}", now.hour


def _status_bar_dynamic_group_layout(
    draw: ImageDraw.ImageDraw,
    time_text: str,
    battery_pct: int,
    font_en: ImageFont.ImageFont,
    screen_w: int,
    screen_h: int,
) -> dict[str, int]:
    """Calculate the right-aligned time and battery group using real text bounds."""
    scale = screen_w / 400.0
    pad_pct = 0.02 if screen_h < 200 else 0.03
    pad_x = int(screen_w * pad_pct)
    battery_text = f"{int(battery_pct)}%"
    battery_bbox = draw.textbbox((0, 0), battery_text, font=font_en)
    time_bbox = draw.textbbox((0, 0), time_text, font=font_en)
    battery_text_x = screen_w - pad_x - battery_bbox[2]
    battery_text_left = battery_text_x + battery_bbox[0]
    battery_box_w = int(22 * scale)
    battery_box_h = int(11 * scale)
    battery_gap = int(6 * scale)
    battery_x = battery_text_left - battery_gap - battery_box_w
    time_gap = int(8 * scale)
    time_right = battery_x - time_gap
    time_x = time_right - time_bbox[2]
    return {
        "time_x": time_x,
        "time_y": int(screen_h * (0.02 if screen_h < 200 else 0.03)),
        "time_left": time_x + time_bbox[0],
        "time_right": time_x + time_bbox[2],
        "battery_x": battery_x,
        "battery_y": int(screen_h * (0.02 if screen_h < 200 else 0.03)) + 1,
        "battery_box_w": battery_box_w,
        "battery_box_h": battery_box_h,
        "battery_text_x": battery_text_x,
        "battery_text_y": int(screen_h * (0.02 if screen_h < 200 else 0.03)),
        "battery_text_right": battery_text_x + battery_bbox[2],
        "group_left": min(time_x + time_bbox[0], battery_x),
        "group_right": screen_w - pad_x,
    }


def _draw_status_bar_dynamic_group(
    draw: ImageDraw.ImageDraw,
    time_text: str,
    battery_pct: int,
    font_en: ImageFont.ImageFont,
    screen_w: int,
    screen_h: int,
    colors: int,
) -> dict[str, int]:
    """Draw the right-side time and battery group and return its geometry."""
    layout = _status_bar_dynamic_group_layout(
        draw, time_text, battery_pct, font_en, screen_w, screen_h,
    )
    battery_text = f"{int(battery_pct)}%"
    battery_fill = EINK_FG
    available = EINK_COLOR_AVAILABILITY.get(colors, frozenset())
    if battery_pct < 20 and "red" in available:
        battery_fill = EINK_COLOR_NAME_MAP["red"]
    elif battery_pct < 50 and "yellow" in available:
        battery_fill = EINK_COLOR_NAME_MAP["yellow"]

    draw.text((layout["time_x"], layout["time_y"]), time_text, fill=EINK_FG, font=font_en)
    bx = layout["battery_x"]
    by = layout["battery_y"]
    batt_box_w = layout["battery_box_w"]
    batt_box_h = layout["battery_box_h"]
    scale = screen_w / 400.0
    draw.rectangle([bx, by, bx + batt_box_w, by + batt_box_h], outline=battery_fill, width=1)
    draw.rectangle(
        [bx + batt_box_w, by + int(3 * scale), bx + batt_box_w + int(2 * scale), by + int(8 * scale)],
        fill=battery_fill,
    )
    fill_w = int((batt_box_w - 4) * battery_pct / 100)
    if fill_w > 0:
        draw.rectangle([bx + 2, by + 2, bx + 2 + fill_w, by + batt_box_h - 2], fill=battery_fill)
    draw.text(
        (layout["battery_text_x"], layout["battery_text_y"]),
        battery_text,
        fill=battery_fill,
        font=font_en,
    )
    return layout


def refresh_status_bar_dynamic_right(
    img: Image.Image,
    battery_pct: int,
    *,
    time_str: str = "",
    screen_w: int | None = None,
    screen_h: int | None = None,
    colors: int = 2,
) -> Image.Image:
    """Refresh only the right-side time/battery area on a cached image copy."""
    updated = img.copy()
    width = screen_w or updated.width
    height = screen_h or updated.height
    draw = ImageDraw.Draw(updated)
    apply_text_fontmode(draw)
    scale = width / 400.0
    time_text, _ = _resolve_status_bar_time(time_str)
    font_en = load_font("inter_medium", int(FONT_SIZES["status_bar"]["en"] * scale))

    max_layout = _status_bar_dynamic_group_layout(
        draw, time_text, 100, font_en, width, height,
    )
    line_y = int(height * 0.11)
    clear_bottom = max(0, min(height, line_y))
    clear_left = max(0, max_layout["group_left"] - max(1, int(2 * scale)))
    if clear_bottom > 0:
        draw.rectangle([clear_left, 0, width - 1, clear_bottom - 1], fill=EINK_BG)
    _draw_status_bar_dynamic_group(
        draw, time_text, int(battery_pct), font_en, width, height, colors,
    )
    return updated


def draw_status_bar(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    date_str: str,
    weather_str: str,
    battery_pct: int,
    weather_code: int = -1,
    line_width: int = 1,
    dashed: bool = False,
    time_str: str = "",
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
    colors: int = 2,
    language: str = "zh",
    separator_y: int | None = None,
):
    """绘制顶部状态栏"""
    is_en = language == "en"
    scale = screen_w / 400.0
    if is_en:
        font_date = load_font("lora_regular", int(FONT_SIZES["status_bar"]["cn"] * scale))
        period_font = load_font("lora_regular", max(9, int(FONT_SIZES["status_bar"]["cn"] * scale)))
    else:
        font_date = load_font("noto_serif_extralight", int(FONT_SIZES["status_bar"]["cn"] * scale))
        period_font_size = max(9, int(FONT_SIZES["status_bar"]["cn"] * scale))
        period_font = _load_bitmap_font("NotoSerifSC-Regular", period_font_size)
        if period_font is None:
            period_font = load_font("noto_serif_regular", period_font_size)
    font_en = load_font("inter_medium", int(FONT_SIZES["status_bar"]["en"] * scale))

    time_text, hour = _resolve_status_bar_time(time_str)

    if is_en:
        if hour >= 23 or hour < 5:
            period_label = "Night"
        elif hour < 12:
            period_label = "AM"
        elif hour < 18:
            period_label = "PM"
        else:
            period_label = "Eve"
    else:
        if hour >= 23 or hour < 2:
            period_label = "深夜"
        elif hour < 5:
            period_label = "凌晨"
        elif hour < 8:
            period_label = "早晨"
        elif hour < 12:
            period_label = "上午"
        elif hour < 14:
            period_label = "中午"
        elif hour < 18:
            period_label = "下午"
        elif hour < 20:
            period_label = "傍晚"
        else:
            period_label = "夜晚"

    pad_pct = 0.02 if screen_h < 200 else 0.03
    pad_y = int(screen_h * pad_pct)
    pad_x = int(screen_w * pad_pct)
    y = pad_y
    x = pad_x
    draw.text((x, y), period_label, fill=EINK_FG, font=period_font)
    bbox_period = draw.textbbox((0, 0), period_label, font=period_font)
    x += (bbox_period[2] - bbox_period[0]) + int(8 * scale)
    draw.text((x, y), date_str, fill=EINK_FG, font=font_date)

    wx = screen_w // 2 - int(28 * scale)
    weather_icon = get_weather_icon(weather_code) if weather_code >= 0 else None
    if weather_icon:
        icon_fill = EINK_COLOR_NAME_MAP.get("red", EINK_FG) if colors >= 3 else EINK_FG
        paste_icon_onto(img, weather_icon, (wx, y - 1), fill=icon_fill)
        draw.text((wx + int(18 * scale), y), weather_str, fill=EINK_FG, font=font_date)
    else:
        draw.text((wx, y), weather_str, fill=EINK_FG, font=font_date)

    _draw_status_bar_dynamic_group(
        draw, time_text, battery_pct, font_en, screen_w, screen_h, colors,
    )

    if separator_y is not None:
        line_y = max(0, min(int(separator_y), max(0, screen_h - 1)))
    else:
        line_y = int(screen_h * 0.11)
    if dashed:
        draw_dashed_line(draw, (0, line_y), (screen_w, line_y), fill=EINK_FG, width=line_width)
    else:
        draw.line([(0, line_y), (screen_w, line_y)], fill=EINK_FG, width=line_width)


def has_cjk(text: str) -> bool:
    """Check if text contains CJK (Chinese/Japanese/Korean) characters."""
    return any("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" for ch in text)


def draw_footer(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    mode: str,
    attribution: str,
    mode_id: str = "",
    weather_code: int | None = None,
    line_width: int = 1,
    dashed: bool = False,
    attr_font: str | None = None,
    attr_font_size: int | None = None,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
    colors: int = 2,
    footer_top: int | None = None,
):
    """绘制底部页脚。

    ``footer_top`` 由 JSON 渲染器传入时表示正文与页脚分界线（与预留的 footer 高度一致）。
    在 296×128 等小高度屏上必须用该值对齐，否则会按百分比把文字画到屏幕外而被裁切。
    """
    scale = screen_w / 400.0
    if attr_font_size is None:
        attr_font_size = int(FONT_SIZES["footer"]["attribution"] * scale)

    if footer_top is not None:
        y_line = max(0, min(int(footer_top), max(0, screen_h - 2)))
    else:
        footer_pct = 0.08 if screen_h < 200 else 0.10
        y_line = screen_h - int(screen_h * footer_pct)

    if dashed:
        draw_dashed_line(
            draw, (0, y_line), (screen_w, y_line), fill=EINK_FG, width=line_width
        )
    else:
        draw.line([(0, y_line), (screen_w, y_line)], fill=EINK_FG, width=line_width)

    label_pt = max(6, int(FONT_SIZES["footer"]["label"] * scale))
    font_label = load_font("inter_medium", label_pt)
    if attr_font:
        font_attr = load_font_by_name(attr_font, attr_font_size)
    elif attribution and has_cjk(attribution):
        font_attr = load_font("noto_serif_light", attr_font_size)
    else:
        font_attr = load_font("lora_regular", attr_font_size)

    icon_x = int(12 * scale)
    icon_key = str(mode_id or mode)
    mode_icon = None
    if icon_key.upper() == "WEATHER" and weather_code is not None:
        try:
            mode_icon = get_weather_icon(int(weather_code))
        except (TypeError, ValueError):
            mode_icon = None
    if mode_icon is None:
        mode_icon = get_mode_icon(icon_key)
    icon_h = mode_icon.height if mode_icon else 0

    lb = font_label.getbbox("Mg")
    lab_h = max(1, lb[3] - lb[1])
    ab = font_attr.getbbox("Mg")
    aab_h = max(1, ab[3] - ab[1])
    text_h = max(lab_h, aab_h)
    row_h = max(text_h, icon_h)

    inner_top = y_line + line_width
    band_h = max(0, screen_h - inner_top)

    if band_h >= row_h:
        text_y = inner_top + (band_h - row_h) // 2
    else:
        text_y = inner_top
    max_bottom = screen_h - 3  # 底边留白，避开胶框遮挡感
    label_upper = mode.upper()
    attrib_pad_r = int(12 * scale)
    attrib_anchor_x = screen_w - attrib_pad_r

    label_x_base = icon_x + (int(15 * scale) if mode_icon else 0)

    def _clamp_text_y(ty: int) -> int:
        lbl_bb = draw.textbbox((label_x_base, ty), label_upper, font=font_label)
        bottom = lbl_bb[3]
        if attribution:
            ab0 = draw.textbbox((0, 0), attribution, font=font_attr)
            att_w = ab0[2] - ab0[0]
            ax = attrib_anchor_x - att_w
            att_bb = draw.textbbox((ax, ty), attribution, font=font_attr)
            bottom = max(bottom, att_bb[3])
        if bottom <= max_bottom:
            return ty
        shift = bottom - max_bottom
        return max(inner_top, ty - shift)

    text_y = _clamp_text_y(text_y)

    if mode_icon:
        icon_fill = EINK_COLOR_NAME_MAP.get("red", EINK_FG) if colors >= 3 else EINK_FG
        icon_y = text_y + max(0, (row_h - icon_h) // 2)
        paste_icon_onto(img, mode_icon, (icon_x, icon_y), fill=icon_fill)
        label_x = icon_x + int(15 * scale)
    else:
        label_x = icon_x

    draw.text((label_x, text_y), label_upper, fill=EINK_FG, font=font_label)

    if attribution:
        bbox = draw.textbbox((0, 0), attribution, font=font_attr)
        att_w = bbox[2] - bbox[0]
        draw.text(
            (attrib_anchor_x - att_w, text_y),
            attribution,
            fill=EINK_FG,
            font=font_attr,
        )


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """文本换行"""
    lines = []
    for paragraph in text.split("\n"):
        words = list(paragraph)
        current = ""
        for ch in words:
            test = current + ch
            bbox = safe_font_bbox(font, test)
            span = bbox[2] - bbox[0]
            if span > max_width:
                if current:
                    lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
    return lines


def wrap_text_fill_sidebar(
    text: str,
    font: ImageFont.ImageFont,
    sidebar_width: int,
    sidebar_max_height: int,
    line_height: int,
) -> tuple[list[str], str]:
    """Fill a narrow column beside a float up to sidebar_max_height; return (lines, remaining text).

    Used for e-ink \"text wraps around a left block\" layouts. Each line is the first line of
    ``wrap_text`` on the remaining string; ``line_height`` must match the renderer's line step.
    """
    lines_out: list[str] = []
    if not text or not text.strip():
        return lines_out, ""
    if sidebar_width <= 0 or sidebar_max_height <= 0 or line_height <= 0:
        return lines_out, text.strip()
    rest = text.strip()
    guard = 0
    limit = max(3, len(text) + 2)
    while rest and guard < limit:
        guard += 1
        if len(lines_out) * line_height + line_height > sidebar_max_height:
            break
        chunk = wrap_text(rest, font, max(1, sidebar_width))
        if not chunk or not chunk[0]:
            break
        line = chunk[0]
        lines_out.append(line)
        trimmed = rest.lstrip()
        if trimmed.startswith(line):
            rest = trimmed[len(line) :].lstrip()
        else:
            break
    return lines_out, rest.strip()


def render_quote_body(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    font_size: int,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
):
    """渲染居中的引用文本"""
    if has_cjk(text) and "Noto" not in font_name:
        font_name = "NotoSerifSC-Light.ttf"
    font = load_font_by_name(font_name, font_size)
    lines = wrap_text(text, font, screen_w - 48)
    line_h = font_size + 8
    total_h = len(lines) * line_h
    y_start = 32 + (screen_h - 32 - 30 - total_h) // 2

    for i, line in enumerate(lines):
        bbox = safe_font_bbox(font, line)
        x = (screen_w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_start + i * line_h), line, fill=EINK_FG, font=font)
