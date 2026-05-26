from PIL import Image

from core import native_dither
from core.image_processing import convert_image_block, quantize_image_for_eink


def test_native_dither_library_is_available():
    assert native_dither._load_lib() is not None


def test_quantizes_black_white_image_to_1bit_with_atkinson():
    src = Image.new("RGB", (8, 1), "white")
    for x in range(4):
        src.putpixel((x, 0), (40, 40, 40))

    out = quantize_image_for_eink(src, colors=2)

    assert out.mode == "1"
    assert set(out.getdata()).issubset({0, 255})


def test_three_color_uses_black_white_red_only_with_atkinson():
    src = Image.new("RGB", (4, 1), "white")
    src.putpixel((0, 0), (0, 0, 0))
    src.putpixel((1, 0), (255, 255, 255))
    src.putpixel((2, 0), (200, 0, 0))
    src.putpixel((3, 0), (232, 176, 0))

    out = quantize_image_for_eink(src, colors=3)

    assert out.mode == "P"
    assert set(out.getdata()).issubset({0, 1, 3})
    assert 2 not in set(out.getdata())


def test_four_color_can_use_yellow_and_red_with_atkinson():
    src = Image.new("RGB", (4, 1), "white")
    src.putpixel((0, 0), (0, 0, 0))
    src.putpixel((1, 0), (255, 255, 255))
    src.putpixel((2, 0), (200, 0, 0))
    src.putpixel((3, 0), (232, 176, 0))

    out = quantize_image_for_eink(src, colors=4)
    values = set(out.getdata())

    assert out.mode == "P"
    assert values.issubset({0, 1, 2, 3})
    assert 2 in values
    assert 3 in values


def test_convert_image_block_supports_photo_enhance():
    src = Image.new("RGB", (8, 4), (120, 120, 120))

    out = convert_image_block(
        src,
        20,
        10,
        2,
        fit="cover",
        photo_enhance=True,
    )

    assert out.size == (20, 10)
    assert out.mode == "1"
