#!/usr/bin/env python3
"""
字体下载脚本
从 Google Fonts 下载项目所需的字体文件到 backend/fonts/ 目录。
使用 Python 标准库，零额外依赖。

用法:
    python scripts/setup_fonts.py          # 跳过已存在的字体
    python scripts/setup_fonts.py --force  # 强制重新下载所有字体
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request

# 项目根目录 (backend/)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(BACKEND_DIR, "fonts")

# Google Fonts download/list API (返回 JSON，含 fonts.gstatic.com 直链)
_LIST_API = "https://fonts.google.com/download/list?family={family}"

# 字体族 → 需要提取的文件名列表（basename，对应 config.py FONTS dict）
FONT_FAMILIES: dict[str, list[str]] = {
    "Noto+Serif+SC": [
        "NotoSerifSC-ExtraLight.ttf",
        "NotoSerifSC-Light.ttf",
        "NotoSerifSC-Regular.ttf",
        "NotoSerifSC-Bold.ttf",
        "NotoSerifSC-ExtraBold.ttf",
    ],
    "Lora": [
        "Lora-Regular.ttf",
        "Lora-Bold.ttf",
    ],
    "Inter": [
        "Inter_24pt-Medium.ttf",
    ],
}


def _fetch_manifest(family: str) -> dict:
    """调用 Google Fonts download/list API，返回解析后的 JSON。"""
    url = _LIST_API.format(family=family)
    req = urllib.request.Request(url, headers={"User-Agent": "InkSight-FontSetup/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    # 响应以 XSSI 保护前缀 ")]}" 开头，需要跳过
    prefix = ")]}\'"
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    return json.loads(raw.strip())


def _build_url_map(manifest: dict) -> dict[str, str]:
    """从 manifest 构建 {basename: download_url} 映射。"""
    url_map: dict[str, str] = {}
    for ref in manifest.get("manifest", {}).get("fileRefs", []):
        basename = os.path.basename(ref["filename"])
        url_map[basename] = ref["url"]
    return url_map


def _download_file(url: str, target: str) -> None:
    """下载单个文件，使用临时文件 + 原子重命名避免写一半的损坏文件。"""
    req = urllib.request.Request(url, headers={"User-Agent": "InkSight-FontSetup/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    fd, tmp_path = tempfile.mkstemp(dir=FONTS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp_f:
            tmp_f.write(data)
        os.replace(tmp_path, target)
    except Exception:
        os.unlink(tmp_path)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Download fonts for InkSight")
    parser.add_argument(
        "--force", action="store_true", help="Force re-download even if files exist"
    )
    args = parser.parse_args()

    os.makedirs(FONTS_DIR, exist_ok=True)

    # 统计需要下载的文件
    all_needed: list[tuple[str, str]] = []  # [(family, filename), ...]
    for family, names in FONT_FAMILIES.items():
        for name in names:
            target = os.path.join(FONTS_DIR, name)
            if args.force or not os.path.exists(target):
                all_needed.append((family, name))

    if not all_needed:
        print("All font files already exist. Use --force to re-download.")
        return

    print(f"Need to download {len(all_needed)} font file(s):\n")

    # 按 family 分组，每个 family 只请求一次 API
    families_to_fetch = sorted(set(f for f, _ in all_needed))
    url_maps: dict[str, dict[str, str]] = {}

    for family in families_to_fetch:
        display_name = family.replace("+", " ")
        print(f"  Fetching manifest for {display_name} ...")
        try:
            manifest = _fetch_manifest(family)
            url_maps[family] = _build_url_map(manifest)
        except Exception as exc:
            print(f"  [ERROR] Failed to fetch manifest for {display_name}: {exc}",
                  file=sys.stderr)
            url_maps[family] = {}

    success_count = 0
    for family, name in all_needed:
        url = url_maps.get(family, {}).get(name)
        if not url:
            print(f"  [WARN] No download URL found for {name}, skipping")
            continue
        try:
            target = os.path.join(FONTS_DIR, name)
            _download_file(url, target)
            size_mb = os.path.getsize(target) / (1024 * 1024)
            print(f"  \u2713 {name} ({size_mb:.1f} MB)")
            success_count += 1
        except Exception as exc:
            print(f"  [ERROR] Failed to download {name}: {exc}", file=sys.stderr)

    print(f"\nDone. {success_count}/{len(all_needed)} font(s) installed to {FONTS_DIR}")
    if success_count < len(all_needed):
        sys.exit(1)


if __name__ == "__main__":
    main()
