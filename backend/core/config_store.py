from __future__ import annotations

import os
import json
import logging
import secrets
import aiosqlite
from datetime import datetime

logger = logging.getLogger(__name__)

from .db import get_main_db
from .config import (
    DEFAULT_CITY,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_CONTENT_TONE,
    DEFAULT_MODES,
    DEFAULT_REFRESH_STRATEGY,
    DEFAULT_REFRESH_INTERVAL,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "inksight.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                modes TEXT DEFAULT 'STOIC,ROAST,ZEN,DAILY',
                refresh_strategy TEXT DEFAULT 'random',
                character_tones TEXT DEFAULT '',
                language TEXT DEFAULT 'zh',
                content_tone TEXT DEFAULT 'neutral',
                city TEXT DEFAULT '杭州',
                refresh_interval INTEGER DEFAULT 60,
                llm_provider TEXT DEFAULT 'deepseek',
                llm_model TEXT DEFAULT 'deepseek-chat',
                countdown_events TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        # Migration: add countdown_events column if missing
        try:
            await db.execute("ALTER TABLE configs ADD COLUMN countdown_events TEXT DEFAULT '[]'")
            await db.commit()
        except Exception:
            pass  # Column already exists

        # Migration: add time_slot_rules column if missing
        try:
            await db.execute("ALTER TABLE configs ADD COLUMN time_slot_rules TEXT DEFAULT '[]'")
            await db.commit()
        except Exception:
            pass  # Column already exists

        # Migration: add memo_text column if missing
        try:
            await db.execute("ALTER TABLE configs ADD COLUMN memo_text TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass  # Column already exists

        await db.execute("CREATE INDEX IF NOT EXISTS idx_configs_mac ON configs(mac)")

        # Device state table for persisting runtime state (cycle_index, etc.)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_state (
                mac TEXT PRIMARY KEY,
                cycle_index INTEGER DEFAULT 0,
                last_persona TEXT DEFAULT '',
                last_refresh_at TEXT DEFAULT '',
                pending_refresh INTEGER DEFAULT 0,
                pending_mode TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)

        # Migration: add pending_mode column if missing
        try:
            await db.execute("ALTER TABLE device_state ADD COLUMN pending_mode TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass

        # Migration: add auth_token column if missing
        try:
            await db.execute("ALTER TABLE device_state ADD COLUMN auth_token TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass

        await db.commit()


async def save_config(mac: str, data: dict) -> int:
    now = datetime.now().isoformat()
    refresh_strategy = data.get("refreshStrategy", "random")
    logger.info(
        f"[CONFIG SAVE] mac={mac}, refreshStrategy={refresh_strategy}, modes={data.get('modes')}"
    )

    db = await get_main_db()
    # Deactivate all existing configs
    await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))

    # Insert new config
    countdown_events_json = json.dumps(
        data.get("countdownEvents", []), ensure_ascii=False
    )
    time_slot_rules_json = json.dumps(
        data.get("timeSlotRules", []), ensure_ascii=False
    )
    memo_text = data.get("memoText", "")
    cursor = await db.execute(
        """INSERT INTO configs
           (mac, nickname, modes, refresh_strategy, character_tones,
            language, content_tone, city, refresh_interval, llm_provider, llm_model,
            countdown_events, time_slot_rules, memo_text, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            mac,
            data.get("nickname", ""),
            ",".join(data.get("modes", DEFAULT_MODES)),
            refresh_strategy,
            ",".join(data.get("characterTones", [])),
            data.get("language", DEFAULT_LANGUAGE),
            data.get("contentTone", DEFAULT_CONTENT_TONE),
            data.get("city", DEFAULT_CITY),
            data.get("refreshInterval", DEFAULT_REFRESH_INTERVAL),
            data.get("llmProvider", DEFAULT_LLM_PROVIDER),
            data.get("llmModel", DEFAULT_LLM_MODEL),
            countdown_events_json,
            time_slot_rules_json,
            memo_text,
            now,
        ),
    )
    config_id = cursor.lastrowid

    # Keep only the latest 5 configs per device
    await db.execute(
        """DELETE FROM configs
           WHERE mac = ? AND id NOT IN (
               SELECT id FROM configs
               WHERE mac = ?
               ORDER BY created_at DESC
               LIMIT 5
           )""",
        (mac, mac),
    )

    await db.commit()
    logger.info(f"[CONFIG SAVE] ✓ Saved as id={config_id}, is_active=1")
    return config_id


def _row_to_dict(row, columns) -> dict:
    d = dict(zip(columns, row))
    d["modes"] = [m for m in d["modes"].split(",") if m]
    d["character_tones"] = [t for t in d["character_tones"].split(",") if t]
    # Parse JSON list fields from DB TEXT columns and normalize to arrays.
    # This avoids leaking raw JSON strings (for example "[]") to web clients.
    ce_raw = d.get("countdown_events", "[]")
    try:
        ce = json.loads(ce_raw) if isinstance(ce_raw, str) else ce_raw
    except (json.JSONDecodeError, TypeError):
        ce = []
    if not isinstance(ce, list):
        ce = []
    d["countdown_events"] = ce
    d["countdownEvents"] = ce

    tsr_raw = d.get("time_slot_rules", "[]")
    try:
        tsr = json.loads(tsr_raw) if isinstance(tsr_raw, str) else tsr_raw
    except (json.JSONDecodeError, TypeError):
        tsr = []
    if not isinstance(tsr, list):
        tsr = []
    d["time_slot_rules"] = tsr
    # Add mac field for cycle index tracking
    if "mac" not in d:
        d["mac"] = d.get("mac", "default")
    d["memo_text"] = d.get("memo_text", "")
    return d


async def get_active_config(mac: str) -> dict | None:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM configs WHERE mac = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (mac,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    config = _row_to_dict(row, columns)
    logger.info(
        f"[CONFIG LOAD] mac={mac}, id={config.get('id')}, refresh_strategy={config.get('refresh_strategy')}, modes={config.get('modes')}"
    )
    return config


async def get_config_history(mac: str) -> list[dict]:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM configs WHERE mac = ? ORDER BY created_at DESC",
        (mac,),
    )
    rows = await cursor.fetchall()
    if not rows:
        return []
    columns = [desc[0] for desc in cursor.description]
    return [_row_to_dict(r, columns) for r in rows]


async def activate_config(mac: str, config_id: int) -> bool:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT id FROM configs WHERE id = ? AND mac = ?", (config_id, mac)
    )
    if not await cursor.fetchone():
        return False
    await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))
    await db.execute("UPDATE configs SET is_active = 1 WHERE id = ?", (config_id,))
    await db.commit()
    return True


# ── Device state (cycle_index, pending_refresh, etc.) ──────


async def get_cycle_index(mac: str) -> int:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT cycle_index FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def set_cycle_index(mac: str, idx: int):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_state (mac, cycle_index, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET cycle_index = ?, updated_at = ?""",
        (mac, idx, now, idx, now),
    )
    await db.commit()


async def update_device_state(mac: str, **kwargs):
    """Update device state fields (last_persona, last_refresh_at, pending_refresh, etc.)."""
    now = datetime.now().isoformat()
    db = await get_main_db()
    # Ensure row exists
    await db.execute(
        """INSERT INTO device_state (mac, updated_at)
           VALUES (?, ?)
           ON CONFLICT(mac) DO UPDATE SET updated_at = ?""",
        (mac, now, now),
    )
    for key, value in kwargs.items():
        if key in ("last_persona", "last_refresh_at", "pending_refresh", "cycle_index", "pending_mode"):
            await db.execute(
                f"UPDATE device_state SET {key} = ? WHERE mac = ?",
                (value, mac),
            )
    await db.commit()


async def get_device_state(mac: str) -> dict | None:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


async def set_pending_refresh(mac: str, pending: bool = True):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_state (mac, pending_refresh, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET pending_refresh = ?, updated_at = ?""",
        (mac, int(pending), now, int(pending), now),
    )
    await db.commit()


async def consume_pending_refresh(mac: str) -> bool:
    """Check and clear pending refresh flag. Returns True if was pending."""
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT pending_refresh FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if row and row[0]:
        await db.execute(
            "UPDATE device_state SET pending_refresh = 0 WHERE mac = ?", (mac,)
        )
        await db.commit()
        return True
    return False


async def generate_device_token(mac: str) -> str:
    """Generate and store a new auth token for a device."""
    token = secrets.token_urlsafe(32)
    now = datetime.now().isoformat()
    db = await get_main_db()
    cursor = await db.execute(
        """UPDATE device_state SET auth_token = ?, updated_at = ? WHERE mac = ?""",
        (token, now, mac),
    )
    if cursor.rowcount == 0:
        await db.execute(
            """INSERT INTO device_state (mac, auth_token, updated_at) VALUES (?, ?, ?)""",
            (mac, token, now),
        )
    await db.commit()
    return token


async def validate_device_token(mac: str, token: str) -> bool:
    """Validate a device's auth token."""
    if not token:
        return False
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT auth_token FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if not row or not row[0]:
        return False
    return row[0] == token
