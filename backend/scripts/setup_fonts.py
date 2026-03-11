#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(BACKEND_DIR, "fonts")
TRUETYPE_DIR = os.path.join(FONTS_DIR, "truetype")
BITMAP_DIR = os.path.join(FONTS_DIR, "bitmap")

_LIST_API = "https://fonts.google.com/download/list?family={family}"

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

BITMAP_FONT_URLS: dict[str, str] = {
    "wqy-song-9": "https://raw.githubusercontent.com/carrothu-cn/chinese-bitmap-fonts/master/wenquanyi_9pt.pcf",
    "wqy-song-10": "https://raw.githubusercontent.com/carrothu-cn/chinese-bitmap-fonts/master/wenquanyi_10pt.pcf",
    "wqy-song-11": "https://raw.githubusercontent.com/carrothu-cn/chinese-bitmap-fonts/master/wenquanyi_11pt.pcf",
    "wqy-song-12": "https://raw.githubusercontent.com/carrothu-cn/chinese-bitmap-fonts/master/wenquanyi_12pt.pcf",
    "wqy-zenhei-13": "https://raw.githubusercontent.com/carrothu-cn/chinese-bitmap-fonts/master/wenquanyi_13px.pcf",
}

ALIAS_FONT_NAMES = [
    "NotoSerifSC-ExtraLight",
    "NotoSerifSC-Light",
    "NotoSerifSC-Regular",
    "NotoSerifSC-Bold",
    "NotoSerifSC-ExtraBold",
    "Lora-Regular",
    "Lora-Bold",
    "Inter_24pt-Medium",
]


def _fetch_manifest(family: str) -> dict:
    url = _LIST_API.format(family=family)
    req = urllib.request.Request(url, headers={"User-Agent": "InkSight-FontSetup/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    prefix = ")]}\'"
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    return json.loads(raw.strip())


def _build_url_map(manifest: dict) -> dict[str, str]:
    url_map: dict[str, str] = {}
    for ref in manifest.get("manifest", {}).get("fileRefs", []):
        basename = os.path.basename(ref["filename"])
        url_map[basename] = ref["url"]
    return url_map


def _download_file(url: str, target: str, user_agent: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    target_dir = os.path.dirname(target)
    os.makedirs(target_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp_f:
            tmp_f.write(data)
        os.replace(tmp_path, target)
    except OSError:
        os.unlink(tmp_path)
        raise


def _copy_if_needed(src: str, dst: str, force: bool) -> bool:
    if not force and os.path.exists(dst):
        return False
    shutil.copyfile(src, dst)
    return True


def _build_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for name in ALIAS_FONT_NAMES:
        lower = name.lower()
        alias_map[name] = "wqy-zenhei" if "bold" in lower else "wqy-song"
    return alias_map


def _install_vector_fonts(force: bool) -> tuple[int, int]:
    all_needed: list[tuple[str, str]] = []
    for family, names in FONT_FAMILIES.items():
        for name in names:
            target = os.path.join(TRUETYPE_DIR, name)
            if force or not os.path.exists(target):
                all_needed.append((family, name))

    if not all_needed:
        print("Vector fonts: already up to date.")
        return 0, 0

    print(f"Vector fonts: need {len(all_needed)} file(s).")
    families_to_fetch = sorted(set(f for f, _ in all_needed))
    url_maps: dict[str, dict[str, str]] = {}
    for family in families_to_fetch:
        display_name = family.replace("+", " ")
        print(f"  Fetching manifest for {display_name} ...")
        try:
            manifest = _fetch_manifest(family)
            url_maps[family] = _build_url_map(manifest)
        except (
            json.JSONDecodeError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            ValueError,
        ) as exc:
            print(f"  [ERROR] Failed manifest for {display_name}: {exc}", file=sys.stderr)
            url_maps[family] = {}

    success_count = 0
    for family, name in all_needed:
        url = url_maps.get(family, {}).get(name)
        if not url:
            print(f"  [WARN] No download URL for {name}, skipping")
            continue
        try:
            target = os.path.join(TRUETYPE_DIR, name)
            _download_file(url, target, "InkSight-FontSetup/1.0")
            size_mb = os.path.getsize(target) / (1024 * 1024)
            print(f"  \u2713 {name} ({size_mb:.1f} MB)")
            success_count += 1
        except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
            print(f"  [ERROR] Failed {name}: {exc}", file=sys.stderr)
    return success_count, len(all_needed)


def _install_bitmap_fonts(force: bool) -> tuple[int, int, int]:
    os.makedirs(BITMAP_DIR, exist_ok=True)

    downloaded = 0
    for base_name, font_url in BITMAP_FONT_URLS.items():
        pcf_path = os.path.join(BITMAP_DIR, f"{base_name}.pcf")
        if force or not os.path.exists(pcf_path):
            _download_file(font_url, pcf_path, "InkSight-BitmapFontSetup/1.0")
            downloaded += 1

    linked = 0
    alias_map = _build_alias_map()
    for font_name, base_name in alias_map.items():
        default_src_name = "wqy-song-12" if base_name == "wqy-song" else "wqy-zenhei-13"
        src = os.path.join(BITMAP_DIR, f"{default_src_name}.pcf")
        if not os.path.exists(src):
            print(f"Missing base bitmap font file: {src}", file=sys.stderr)
            sys.exit(1)
        dst = os.path.join(BITMAP_DIR, f"{font_name}.pcf")
        if _copy_if_needed(src, dst, force):
            linked += 1

        for sz in (9, 10, 11, 12):
            sized_src = os.path.join(BITMAP_DIR, f"wqy-song-{sz}.pcf")
            if not os.path.exists(sized_src):
                print(f"Missing base bitmap font file: {sized_src}", file=sys.stderr)
                sys.exit(1)
            sized_dst = os.path.join(BITMAP_DIR, f"{font_name}-{sz}.pcf")
            if _copy_if_needed(sized_src, sized_dst, force):
                linked += 1
        sized_src_13 = os.path.join(BITMAP_DIR, "wqy-zenhei-13.pcf")
        sized_dst_13 = os.path.join(BITMAP_DIR, f"{font_name}-13.pcf")
        if _copy_if_needed(sized_src_13, sized_dst_13, force):
            linked += 1

    return downloaded, linked, len(BITMAP_FONT_URLS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download vector + bitmap fonts for InkSight")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist")
    args = parser.parse_args()

    os.makedirs(FONTS_DIR, exist_ok=True)
    os.makedirs(TRUETYPE_DIR, exist_ok=True)

    vec_ok, vec_need = _install_vector_fonts(args.force)
    bm_down, bm_alias, bm_need = _install_bitmap_fonts(args.force)

    print(
        f"Done. vector={vec_ok}/{vec_need}, "
        f"bitmap_downloaded={bm_down}/{bm_need}, bitmap_aliased={bm_alias}"
    )
    if vec_ok < vec_need:
        sys.exit(1)


if __name__ == "__main__":
    main()
