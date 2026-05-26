from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


RAW_BASE = "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/json_original/json-sentence"
OUT_DIR = Path(__file__).resolve().parents[1] / "core" / "vocab_data"

DECKS: dict[str, dict[str, Any]] = {
    "primary_en": {
        "difficulty": 1,
        "sources": [
            "PEPXiaoXue3_1.json",
            "PEPXiaoXue3_2.json",
            "PEPXiaoXue4_1.json",
            "PEPXiaoXue4_2.json",
            "PEPXiaoXue5_1.json",
            "PEPXiaoXue5_2.json",
            "PEPXiaoXue6_1.json",
            "PEPXiaoXue6_2.json",
        ],
    },
    "middle_school_en": {"difficulty": 2, "sources": ["ChuZhong_2.json", "ChuZhong_3.json"]},
    "high_school_en": {"difficulty": 3, "sources": ["GaoZhong_2.json", "GaoZhong_3.json"]},
    "cet4_en": {"difficulty": 4, "sources": ["CET4_1.json", "CET4_2.json", "CET4_3.json"]},
    "cet6_en": {"difficulty": 5, "sources": ["CET6_1.json", "CET6_2.json", "CET6_3.json"]},
    "ielts_en": {"difficulty": 6, "sources": ["IELTS_2.json", "IELTS_3.json"]},
    "toefl_en": {"difficulty": 7, "sources": ["TOEFL_2.json", "TOEFL_3.json"]},
}


def fetch_source(name: str) -> list[dict[str, Any]]:
    url = f"{RAW_BASE}/{urllib.parse.quote(name)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError(f"{name}: expected list, got {type(data).__name__}")
    return [item for item in data if isinstance(item, dict)]


def clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_phonetic(value: Any) -> str:
    text = clean_text(value).strip("/")
    return f"/{text}/" if text else ""


def pick_definition(item: dict[str, Any]) -> str:
    translations = item.get("translations")
    parts: list[str] = []
    if isinstance(translations, list):
        for translation in translations[:3]:
            if not isinstance(translation, dict):
                continue
            body = clean_text(translation.get("translation"))
            pos = clean_text(translation.get("type"))
            if not body:
                continue
            parts.append(f"{pos}. {body}" if pos else body)
    return "；".join(parts)


def pick_example(item: dict[str, Any]) -> str:
    sentences = item.get("sentences")
    if isinstance(sentences, list):
        for sentence in sentences:
            if not isinstance(sentence, dict):
                continue
            text = clean_text(sentence.get("sentence"))
            if text:
                return text
    return ""


def convert_item(deck_id: str, difficulty: int, item: dict[str, Any]) -> dict[str, Any] | None:
    word = clean_text(item.get("word"))
    definition = pick_definition(item)
    if not word or not definition:
        return None
    phonetic = normalize_phonetic(item.get("us") or item.get("uk"))
    return {
        "deck_id": deck_id,
        "word": word,
        "phonetic": phonetic,
        "definition": definition,
        "example": pick_example(item),
        "difficulty": difficulty,
    }


def build_deck(deck_id: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    difficulty = int(spec["difficulty"])
    for source in spec["sources"]:
        for raw_item in fetch_source(source):
            item = convert_item(deck_id, difficulty, raw_item)
            if item is None:
                continue
            key = item["word"].casefold()
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
    return output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for deck_id, spec in DECKS.items():
        items = build_deck(deck_id, spec)
        path = OUT_DIR / f"{deck_id}.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{deck_id}: {len(items)} -> {path}")


if __name__ == "__main__":
    main()
