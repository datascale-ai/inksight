from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .db import get_main_db

VOCAB_MODE_ID = "VOCAB_REVIEW"
DEFAULT_DECK_ID = "core_en"
DEFAULT_DAILY_LIMIT = 30
DEFAULT_NEW_CARDS_PER_DAY = 10
RATINGS = ("forgot", "fuzzy", "remember")
RATING_LABELS = {
    "forgot": "忘了",
    "fuzzy": "模糊",
    "remember": "记住",
}

_DATA_DIR = Path(__file__).resolve().parent / "vocab_data"


async def seed_builtin_vocab() -> None:
    if not _DATA_DIR.exists():
        return

    now = datetime.now().isoformat()
    db = await get_main_db()
    for path in sorted(_DATA_DIR.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            word = str(item.get("word") or "").strip()
            definition = str(item.get("definition") or "").strip()
            if not word or not definition:
                continue
            await db.execute(
                """
                INSERT OR IGNORE INTO vocab_items
                    (deck_id, word, phonetic, definition, example, difficulty, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(item.get("deck_id") or DEFAULT_DECK_ID),
                    word,
                    str(item.get("phonetic") or ""),
                    definition,
                    str(item.get("example") or ""),
                    int(item.get("difficulty") or 1),
                    now,
                ),
            )
    await db.commit()


def _mode_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    config = config or {}
    settings = config.get("mode_settings")
    if isinstance(settings, dict):
        return settings
    overrides = config.get("mode_overrides")
    if isinstance(overrides, dict):
        override = overrides.get(VOCAB_MODE_ID)
        if isinstance(override, dict):
            return override
    return {}


def resolve_vocab_settings(config: dict[str, Any] | None) -> tuple[str, int, int]:
    settings = _mode_settings(config)
    deck_id = str(settings.get("deck_id") or DEFAULT_DECK_ID).strip() or DEFAULT_DECK_ID
    daily_limit = _bounded_int(settings.get("daily_limit"), DEFAULT_DAILY_LIMIT, 1, 200)
    new_cards = _bounded_int(settings.get("new_cards_per_day"), DEFAULT_NEW_CARDS_PER_DAY, 0, daily_limit)
    return deck_id, daily_limit, new_cards


def _bounded_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


async def ensure_vocab_session(mac: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    deck_id, daily_limit, new_cards_per_day = resolve_vocab_settings(config)
    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat()
    db = await get_main_db()

    cursor = await db.execute("SELECT * FROM vocab_session_state WHERE mac = ?", (mac,))
    row = await cursor.fetchone()
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    session = dict(zip(columns, row)) if row else None
    if not session:
        await db.execute(
            """
            INSERT INTO vocab_session_state
                (mac, deck_id, side, rating_cursor, review_date, reviewed_count, new_count, updated_at)
            VALUES (?, ?, 'front', 0, ?, 0, 0, ?)
            """,
            (mac, deck_id, today, now),
        )
        await db.commit()
        session = {
            "mac": mac,
            "deck_id": deck_id,
            "current_item_id": None,
            "side": "front",
            "rating_cursor": 0,
            "review_date": today,
            "reviewed_count": 0,
            "new_count": 0,
        }
    elif session.get("review_date") != today or session.get("deck_id") != deck_id:
        session.update({"deck_id": deck_id, "review_date": today, "reviewed_count": 0, "new_count": 0})
        await db.execute(
            """
            UPDATE vocab_session_state
            SET deck_id = ?, review_date = ?, reviewed_count = 0, new_count = 0, updated_at = ?
            WHERE mac = ?
            """,
            (deck_id, today, now, mac),
        )
        await db.commit()

    current = await _get_current_item(db, session.get("current_item_id"), deck_id)
    if current and int(session.get("reviewed_count") or 0) < daily_limit:
        return {**session, "item": current, "daily_limit": daily_limit, "new_cards_per_day": new_cards_per_day}

    item, is_new = await _select_next_item(db, mac, deck_id, daily_limit, new_cards_per_day, session)
    if item:
        await db.execute(
            """
            UPDATE vocab_session_state
            SET current_item_id = ?, side = 'front', rating_cursor = 0, updated_at = ?
            WHERE mac = ?
            """,
            (item["id"], now, mac),
        )
        await db.commit()
        session.update({"current_item_id": item["id"], "side": "front", "rating_cursor": 0, "current_is_new": is_new})
    else:
        await db.execute(
            "UPDATE vocab_session_state SET current_item_id = NULL, side = 'front', rating_cursor = 0, updated_at = ? WHERE mac = ?",
            (now, mac),
        )
        await db.commit()
        session.update({"current_item_id": None, "side": "front", "rating_cursor": 0, "current_is_new": False})
    return {**session, "item": item, "daily_limit": daily_limit, "new_cards_per_day": new_cards_per_day}


async def handle_vocab_event(mac: str, action: str, config: dict[str, Any] | None = None, rating: str | None = None) -> dict[str, Any]:
    action = str(action or "").strip().lower()
    if action == "enter":
        await ensure_vocab_session(mac, config)
        now = datetime.now().isoformat()
        db = await get_main_db()
        await db.execute(
            "UPDATE vocab_session_state SET side = 'front', rating_cursor = 0, updated_at = ? WHERE mac = ?",
            (now, mac),
        )
        await db.commit()
        return {"ok": True, "action": action}

    session = await ensure_vocab_session(mac, config)
    now = datetime.now().isoformat()
    db = await get_main_db()
    if action == "flip":
        await db.execute("UPDATE vocab_session_state SET side = 'back', updated_at = ? WHERE mac = ?", (now, mac))
        await db.commit()
    elif action == "next_rating":
        cursor = (int(session.get("rating_cursor") or 0) + 1) % len(RATINGS)
        await db.execute("UPDATE vocab_session_state SET rating_cursor = ?, updated_at = ? WHERE mac = ?", (cursor, now, mac))
        await db.commit()
    elif action == "submit_rating":
        item = session.get("item")
        if item:
            selected = str(rating or RATINGS[int(session.get("rating_cursor") or 0) % len(RATINGS)])
            if selected not in RATINGS:
                selected = "fuzzy"
            was_new = await _is_current_new(db, mac, item["id"])
            await _apply_rating(db, mac, int(item["id"]), selected)
            await _advance_session(db, mac, config, was_new=was_new)
    else:
        return {"ok": False, "error": "invalid_action"}
    return {"ok": True, "action": action}


async def get_vocab_content(mac: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    session = await ensure_vocab_session(mac, config)
    item = session.get("item")
    reviewed = int(session.get("reviewed_count") or 0)
    daily_limit = int(session.get("daily_limit") or DEFAULT_DAILY_LIMIT)
    if not item:
        return {
            "state": "empty",
            "word": "今日完成",
            "phonetic": "",
            "definition": "没有到期或新词卡了",
            "example": "",
            "progress": f"{reviewed}/{daily_limit}",
            "rating_label": "",
            "rating_cursor": 0,
            "rating_hint": "明天再来",
        }
    rating = RATINGS[int(session.get("rating_cursor") or 0) % len(RATINGS)]
    rating_cursor = int(session.get("rating_cursor") or 0) % len(RATINGS)
    return {
        "state": str(session.get("side") or "front"),
        "word": item["word"],
        "phonetic": item.get("phonetic") or "",
        "definition": item["definition"],
        "example": item.get("example") or "",
        "progress": f"{reviewed}/{daily_limit}",
        "rating_label": RATING_LABELS[rating],
        "rating_cursor": rating_cursor,
        "rating_hint": "短按切换评分，长按提交",
    }


async def _get_current_item(db, item_id: Any, deck_id: str) -> dict[str, Any] | None:
    if not item_id:
        return None
    cursor = await db.execute(
        "SELECT id, deck_id, word, phonetic, definition, example, difficulty FROM vocab_items WHERE id = ? AND deck_id = ?",
        (item_id, deck_id),
    )
    row = await cursor.fetchone()
    return _item_from_row(row) if row else None


async def _select_next_item(db, mac: str, deck_id: str, daily_limit: int, new_cards_per_day: int, session: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    if int(session.get("reviewed_count") or 0) >= daily_limit:
        return None, False
    now = datetime.now().isoformat()
    cursor = await db.execute(
        """
        SELECT vi.id, vi.deck_id, vi.word, vi.phonetic, vi.definition, vi.example, vi.difficulty
        FROM vocab_progress vp
        JOIN vocab_items vi ON vi.id = vp.vocab_item_id
        WHERE vp.mac = ? AND vi.deck_id = ? AND vp.due_at <= ?
        ORDER BY vp.due_at ASC, vi.difficulty ASC, vi.id ASC
        LIMIT 1
        """,
        (mac, deck_id, now),
    )
    row = await cursor.fetchone()
    if row:
        return _item_from_row(row), False

    if int(session.get("new_count") or 0) >= new_cards_per_day:
        return None, False
    cursor = await db.execute(
        """
        SELECT vi.id, vi.deck_id, vi.word, vi.phonetic, vi.definition, vi.example, vi.difficulty
        FROM vocab_items vi
        LEFT JOIN vocab_progress vp ON vp.vocab_item_id = vi.id AND vp.mac = ?
        WHERE vi.deck_id = ? AND vp.vocab_item_id IS NULL
        ORDER BY RANDOM()
        LIMIT 1
        """,
        (mac, deck_id),
    )
    row = await cursor.fetchone()
    return (_item_from_row(row), True) if row else (None, False)


def _item_from_row(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "deck_id": row[1],
        "word": row[2],
        "phonetic": row[3],
        "definition": row[4],
        "example": row[5],
        "difficulty": row[6],
    }


async def _apply_rating(db, mac: str, item_id: int, rating: str) -> None:
    now_dt = datetime.now()
    now = now_dt.isoformat()
    cursor = await db.execute(
        """
        SELECT interval_days, ease_factor, repetitions, lapses
        FROM vocab_progress WHERE mac = ? AND vocab_item_id = ?
        """,
        (mac, item_id),
    )
    row = await cursor.fetchone()
    interval = int(row[0]) if row else 0
    ease = float(row[1]) if row else 2.5
    reps = int(row[2]) if row else 0
    lapses = int(row[3]) if row else 0

    if rating == "forgot":
        interval = 0
        reps = 0
        lapses += 1
        ease = max(1.3, ease - 0.2)
        due_at = now_dt + timedelta(minutes=10)
    elif rating == "fuzzy":
        interval = max(1, interval)
        reps = max(1, reps)
        ease = max(1.3, ease - 0.1)
        due_at = now_dt + timedelta(days=interval)
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        ease = ease + (0.1 - (5 - 5) * (0.08 + (5 - 5) * 0.02))
        due_at = now_dt + timedelta(days=interval)

    await db.execute(
        """
        INSERT INTO vocab_progress
            (mac, vocab_item_id, due_at, interval_days, ease_factor, repetitions, lapses, last_grade, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mac, vocab_item_id) DO UPDATE SET
            due_at = excluded.due_at,
            interval_days = excluded.interval_days,
            ease_factor = excluded.ease_factor,
            repetitions = excluded.repetitions,
            lapses = excluded.lapses,
            last_grade = excluded.last_grade,
            updated_at = excluded.updated_at
        """,
        (mac, item_id, due_at.isoformat(), interval, ease, reps, lapses, rating, now),
    )


async def _advance_session(db, mac: str, config: dict[str, Any] | None, *, was_new: bool) -> None:
    cursor = await db.execute("SELECT * FROM vocab_session_state WHERE mac = ?", (mac,))
    row = await cursor.fetchone()
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    session = dict(zip(columns, row)) if row else {}
    deck_id, daily_limit, new_cards_per_day = resolve_vocab_settings(config)
    reviewed = int(session.get("reviewed_count") or 0) + 1
    new_count = int(session.get("new_count") or 0) + (1 if was_new else 0)
    session.update({"reviewed_count": reviewed, "new_count": new_count, "deck_id": deck_id})
    item, _is_new = await _select_next_item(db, mac, deck_id, daily_limit, new_cards_per_day, session)
    now = datetime.now().isoformat()
    await db.execute(
        """
        UPDATE vocab_session_state
        SET current_item_id = ?, side = 'front', rating_cursor = 0,
            reviewed_count = ?, new_count = ?, updated_at = ?
        WHERE mac = ?
        """,
        (item["id"] if item else None, reviewed, new_count, now, mac),
    )
    await db.commit()


async def _is_current_new(db, mac: str, item_id: Any) -> bool:
    if not item_id:
        return False
    cursor = await db.execute(
        "SELECT 1 FROM vocab_progress WHERE mac = ? AND vocab_item_id = ?",
        (mac, item_id),
    )
    return await cursor.fetchone() is None
