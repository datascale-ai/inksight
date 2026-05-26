"""ctypes bridge for native e-ink dithering."""
from __future__ import annotations

import ctypes
from pathlib import Path

from PIL import Image

from .config import EINK_4COLOR_PALETTE

import platform

_EXT = ".dll" if platform.system() == "Windows" else ".so"
_LIB_PATH = Path(__file__).resolve().parent / "native" / f"libeink_dither{_EXT}"
_LIB: ctypes.CDLL | None = None
_BUILD_HINT = "run `python3 backend/scripts/build_native_dither.py` from the repository root"


def _load_lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is not None:
        return _LIB
    if not _LIB_PATH.exists():
        raise RuntimeError(f"native dithering library not found at {_LIB_PATH}; {_BUILD_HINT}")
    try:
        lib = ctypes.CDLL(str(_LIB_PATH))
        lib.inksight_atkinson_bw.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        lib.inksight_atkinson_bw.restype = ctypes.c_int
        lib.inksight_atkinson_palette.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        lib.inksight_atkinson_palette.restype = ctypes.c_int
        _LIB = lib
        return lib
    except OSError as exc:
        raise RuntimeError(f"failed to load native dithering library at {_LIB_PATH}: {exc}") from exc

def atkinson_bw(gray: Image.Image) -> Image.Image:
    lib = _load_lib()
    src = gray.convert("L")
    w, h = src.size
    in_buf = src.tobytes()
    out_buf = ctypes.create_string_buffer(w * h)
    err_buf = ctypes.create_string_buffer(256)
    status = lib.inksight_atkinson_bw(
        in_buf,
        w,
        h,
        out_buf,
        err_buf,
        len(err_buf),
    )
    if status != 0:
        raise RuntimeError(f"native black/white Atkinson dithering failed: {err_buf.value.decode('utf-8', errors='replace')}")
    return Image.frombytes("L", (w, h), out_buf.raw).convert("1", dither=Image.Dither.NONE)


def atkinson_palette(rgb: Image.Image, colors: int) -> Image.Image:
    lib = _load_lib()
    if colors not in (3, 4):
        raise ValueError("native palette Atkinson dithering supports only 3 or 4 colors")
    src = rgb.convert("RGB")
    w, h = src.size
    in_buf = src.tobytes()
    out_buf = ctypes.create_string_buffer(w * h)
    err_buf = ctypes.create_string_buffer(256)
    status = lib.inksight_atkinson_palette(
        in_buf,
        w,
        h,
        int(colors),
        out_buf,
        err_buf,
        len(err_buf),
    )
    if status != 0:
        raise RuntimeError(f"native palette Atkinson dithering failed: {err_buf.value.decode('utf-8', errors='replace')}")
    out = Image.frombytes("P", (w, h), out_buf.raw)
    out.putpalette(EINK_4COLOR_PALETTE + [0] * (768 - len(EINK_4COLOR_PALETTE)))
    return out
