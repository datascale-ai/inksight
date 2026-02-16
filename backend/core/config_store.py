from __future__ import annotations

import os
import json
import logging
import aiosqlite
from datetime import datetime

logger = logging.getLogger(__name__)

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
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_configs_mac ON configs(mac)")
        await db.commit()


async def save_config(mac: str, data: dict) -> int:
    now = datetime.now().isoformat()
    refresh_strategy = data.get("refreshStrategy", "random")
    logger.info(
        f"[CONFIG SAVE] mac={mac}, refreshStrategy={refresh_strategy}, modes={data.get('modes')}"
    )

    async with aiosqlite.connect(DB_PATH) as db:
        # Deactivate all existing configs
        await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))

        # Insert new config
        cursor = await db.execute(
            """INSERT INTO configs
               (mac, nickname, modes, refresh_strategy, character_tones,
                language, content_tone, city, refresh_interval, llm_provider, llm_model, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
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
    # Add mac field for cycle index tracking
    if "mac" not in d:
        d["mac"] = d.get("mac", "default")
    return d


async def get_active_config(mac: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM configs WHERE id = ? AND mac = ?", (config_id, mac)
        )
        if not await cursor.fetchone():
            return False
        await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))
        await db.execute("UPDATE configs SET is_active = 1 WHERE id = ?", (config_id,))
        await db.commit()
        return True
