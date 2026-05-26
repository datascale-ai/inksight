# Native e-ink dithering

This directory contains the optional C++ implementation for Atkinson dithering.

Build from the repository root:

```bash
python3 backend/scripts/build_native_dither.py
```

The generated `libeink_dither.so` is ignored by git. Runtime code automatically
uses it when present and falls back to the Python implementation when it is not.
