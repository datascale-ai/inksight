from __future__ import annotations

from datetime import datetime


async def _column_exists(db, table: str, column: str) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return any(row[1] == column for row in rows)


async def _add_column_if_missing(db, table: str, column: str, ddl: str) -> None:
    if await _column_exists(db, table, column):
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def run_main_db_migrations(db, *, defaults: dict[str, str]) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    cursor = await db.execute("SELECT version FROM schema_versions")
    applied_versions = {row[0] for row in await cursor.fetchall()}

    migrations = [
        (1, "configs.countdown_events", lambda: _add_column_if_missing(db, "configs", "countdown_events", "countdown_events TEXT DEFAULT '[]'")),
        (2, "configs.time_slot_rules", lambda: _add_column_if_missing(db, "configs", "time_slot_rules", "time_slot_rules TEXT DEFAULT '[]'")),
        (3, "configs.memo_text", lambda: _add_column_if_missing(db, "configs", "memo_text", "memo_text TEXT DEFAULT ''")),
        (4, "configs.llm_api_key", lambda: _add_column_if_missing(db, "configs", "llm_api_key", "llm_api_key TEXT DEFAULT ''")),
        (5, "configs.image_provider", lambda: _add_column_if_missing(db, "configs", "image_provider", f"image_provider TEXT DEFAULT '{defaults['image_provider']}'")),
        (6, "configs.image_model", lambda: _add_column_if_missing(db, "configs", "image_model", f"image_model TEXT DEFAULT '{defaults['image_model']}'")),
        (7, "configs.image_api_key", lambda: _add_column_if_missing(db, "configs", "image_api_key", "image_api_key TEXT DEFAULT ''")),
        (8, "configs.mode_overrides", lambda: _add_column_if_missing(db, "configs", "mode_overrides", "mode_overrides TEXT DEFAULT '{}'")),
        (9, "device_state.pending_mode", lambda: _add_column_if_missing(db, "device_state", "pending_mode", "pending_mode TEXT DEFAULT ''")),
        (10, "device_state.last_state_poll_at", lambda: _add_column_if_missing(db, "device_state", "last_state_poll_at", "last_state_poll_at TEXT DEFAULT ''")),
        (11, "device_state.auth_token", lambda: _add_column_if_missing(db, "device_state", "auth_token", "auth_token TEXT DEFAULT ''")),
        (12, "device_state.runtime_mode", lambda: _add_column_if_missing(db, "device_state", "runtime_mode", "runtime_mode TEXT DEFAULT 'interval'")),
        (13, "device_state.expected_refresh_min", lambda: _add_column_if_missing(db, "device_state", "expected_refresh_min", "expected_refresh_min INTEGER DEFAULT 0")),
        (14, "device_state.last_reconnect_regen_at", lambda: _add_column_if_missing(db, "device_state", "last_reconnect_regen_at", "last_reconnect_regen_at TEXT DEFAULT ''")),
        (15, "device_claim_tokens.pair_code", lambda: _add_column_if_missing(db, "device_claim_tokens", "pair_code", "pair_code TEXT DEFAULT ''")),
    ]

    now = datetime.now().isoformat()
    for version, name, apply in migrations:
        if version in applied_versions:
            continue
        await apply()
        await db.execute(
            "INSERT INTO schema_versions (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, now),
        )

    await db.commit()
