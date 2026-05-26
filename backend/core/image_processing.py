"""Reusable image fitting and e-ink quantization helpers."""
from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from . import native_dither


def _aligned_offset(container: int, content: int, align: str) -> int:
    if align in ("left", "top", "start"):
        return 0
    if align in ("right", "bottom", "end"):
        return container - content
    return (container - content) // 2


def fit_image_to_box(
    src: Image.Image,
    width: int,
    height: int,
    *,
    fit: str = "fill",
    align_x: str = "center",
    align_y: str = "center",
) -> Image.Image:
    """Fit an image into an RGB box using JSON image-block semantics."""
    src_rgba = ImageOps.exif_transpose(src).convert("RGBA")
    fit_mode = str(fit or "fill").lower()
    if fit_mode in ("fill", "stretch"):
        base = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        base.alpha_composite(src_rgba.resize((width, height), Image.LANCZOS))
        return base.convert("RGB")

    src_w = max(1, src_rgba.size[0])
    src_h = max(1, src_rgba.size[1])
    scale_x = width / src_w
    scale_y = height / src_h
    scale = min(scale_x, scale_y) if fit_mode == "contain" else max(scale_x, scale_y)
    resized_w = max(1, int(round(src_w * scale)))
    resized_h = max(1, int(round(src_h * scale)))
    resized = src_rgba.resize((resized_w, resized_h), Image.LANCZOS)
    base = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    paste_x = _aligned_offset(width, resized_w, align_x)
    paste_y = _aligned_offset(height, resized_h, align_y)
    base.alpha_composite(resized, (paste_x, paste_y))
    return base.convert("RGB")


def enhance_photo_for_eink(rgb: Image.Image) -> Image.Image:
    """Conservative photo preparation before e-ink quantization."""
    img = ImageOps.autocontrast(rgb.convert("RGB"), cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Sharpness(img).enhance(1.25)
    return img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=3))


def quantize_image_for_eink(
    rgb: Image.Image,
    *,
    colors: int,
    photo_enhance: bool = False,
) -> Image.Image:
    """Quantize RGB image data for 2-, 3-, or 4-color e-ink output with Atkinson dithering."""
    prepared = enhance_photo_for_eink(rgb) if photo_enhance else rgb.convert("RGB")

    if colors < 3:
        gray = ImageOps.autocontrast(prepared.convert("L"), cutoff=1)
        return native_dither.atkinson_bw(gray)

    return native_dither.atkinson_palette(prepared, 3 if colors == 3 else 4)


def convert_image_block(
    src: Image.Image,
    width: int,
    height: int,
    colors: int,
    *,
    fit: str = "fill",
    align_x: str = "center",
    align_y: str = "center",
    photo_enhance: bool = False,
) -> Image.Image:
    """Fit and quantize an image for a JSON image block."""
    fitted = fit_image_to_box(src, width, height, fit=fit, align_x=align_x, align_y=align_y)
    return quantize_image_for_eink(
        fitted,
        colors=colors,
        photo_enhance=photo_enhance,
    )
