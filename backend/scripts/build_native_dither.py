from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "core" / "native" / "eink_dither.cpp"
OUT = ROOT / "core" / "native" / "libeink_dither.so"


def main() -> None:
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ not found")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        compiler,
        "-O3",
        "-std=c++17",
        "-fPIC",
        "-shared",
        str(SRC),
        "-o",
        str(OUT),
    ]
    subprocess.run(cmd, check=True)
    print(OUT)


if __name__ == "__main__":
    main()
