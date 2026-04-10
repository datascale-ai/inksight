"""
静态数据库模块
负责 3 张静态内容表的定义、初始化、CRUD 操作，以及设备级别的防重游标状态管理。

涉及的 3 个模式：
  POETRY  — 古诗词库
  RIDDLE  — 谜语库
  THISDAY — 历史上的今天库
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

import aiosqlite

from .db import get_main_db

logger = logging.getLogger(__name__)

# 静态模式 ID 常量集合
STATIC_MODE_IDS: frozenset[str] = frozenset({"POETRY", "RIDDLE", "THISDAY"})

# ── 表名常量 ────────────────────────────────────────────────


# ── Schema 定义 ────────────────────────────────────────────


# 各表的 CREATE SQL（带 IF NOT EXISTS，幂等初始化）
_TABLE_SCHEMAS: list[str] = [
    # ── 1. 诗词库 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS static_poetry (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        title        TEXT    NOT NULL,
        author       TEXT    NOT NULL,
        dynasty      TEXT    DEFAULT '',
        lines_json   TEXT    NOT NULL,
        note         TEXT    DEFAULT '',
        season_tag   TEXT    DEFAULT '',
        difficulty   INTEGER DEFAULT 1,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── 2. 谜语库 ──────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS static_riddle (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        category     TEXT    DEFAULT '谜语',
        question     TEXT    NOT NULL,
        hint         TEXT    DEFAULT '',
        answer       TEXT    NOT NULL,
        difficulty   INTEGER DEFAULT 1,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── 3. 历史上的今天 ────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS static_thisday (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        month         INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
        day           INTEGER NOT NULL CHECK(day   BETWEEN 1 AND 31),
        year          INTEGER NOT NULL,
        event_title   TEXT    NOT NULL,
        event_desc    TEXT    DEFAULT '',
        years_ago     TEXT    DEFAULT '',
        significance  TEXT    DEFAULT '',
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
]

# 索引 SQL（用于 CREATE INDEX IF NOT EXISTS）
_INDEX_SCHEMAS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_thisday_md      ON static_thisday(month, day)",
    "CREATE INDEX IF NOT EXISTS idx_poetry_season  ON static_poetry(season_tag)",
    "CREATE INDEX IF NOT EXISTS idx_riddle_cat     ON static_riddle(category)",
]

# device_state 新增列（防重游标）
_DEVICE_STATE_NEW_COLUMNS: dict[str, str] = {
    "static_poetry_cursor":  "INTEGER DEFAULT 0",
    "static_riddle_cursor":  "INTEGER DEFAULT 0",
    "static_thisday_index":  "INTEGER DEFAULT 0",
    "static_thisday_count":  "INTEGER DEFAULT 0",
    "static_updated_at":     "TEXT DEFAULT ''",
}


# ── 初始化 ──────────────────────────────────────────────────


async def init_static_tables() -> None:
    """幂等初始化所有静态内容表和索引。调用一次即可。"""
    db = await get_main_db()
    for sql in _TABLE_SCHEMAS:
        await db.execute(sql)
    for sql in _INDEX_SCHEMAS:
        await db.execute(sql)
    await db.commit()
    logger.info("[StaticDB] Tables initialized")


async def migrate_device_state_columns() -> None:
    """安全迁移 device_state 表，新增静态模式防重游标列（幂等）。"""
    db = await get_main_db()
    cursor = await db.execute("PRAGMA table_info(device_state)")
    existing_cols = {row[1] for row in await cursor.fetchall()}

    for col_name, col_def in _DEVICE_STATE_NEW_COLUMNS.items():
        if col_name not in existing_cols:
            # 从列定义中提取类型（去掉 DEFAULT 部分）以兼容 ALTER TABLE 语法
            col_type = col_def.split(" DEFAULT ")[0]
            try:
                await db.execute(f"ALTER TABLE device_state ADD COLUMN {col_name} {col_type}")
                logger.info("[StaticDB] Added column device_state.%s", col_name)
            except Exception as e:
                logger.warning("[StaticDB] Failed to add column %s: %s", col_name, e)
    await db.commit()


# ── 辅助：设备防重状态读写 ───────────────────────────────────


async def _ensure_device_state_row(mac: str) -> None:
    """确保 device_state 表中存在指定 mac 的行（幂等）。"""
    db = await get_main_db()
    await db.execute(
        """
        INSERT OR IGNORE INTO device_state (mac, updated_at)
        VALUES (?, datetime('now'))
        """,
        (mac.upper(),),
    )
    await db.commit()


async def get_static_cursor(mac: str, mode_id: str) -> int:
    """读取指定设备在指定模式下的游标值。返回 0 表示尚未初始化。"""
    col_map = {
        "POETRY":  "static_poetry_cursor",
        "RIDDLE":  "static_riddle_cursor",
    }
    col = col_map.get(mode_id)
    if not col:
        return 0
    db = await get_main_db()
    cursor = await db.execute(
        f"SELECT {col} FROM device_state WHERE mac = ?",
        (mac.upper(),),
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def set_static_cursor(mac: str, mode_id: str, value: int) -> None:
    """写入指定设备在指定模式下的游标值。"""
    col_map = {
        "POETRY":  "static_poetry_cursor",
        "RIDDLE":  "static_riddle_cursor",
    }
    col = col_map.get(mode_id)
    if not col:
        return
    await _ensure_device_state_row(mac)
    db = await get_main_db()
    await db.execute(
        f"UPDATE device_state SET {col} = ?, static_updated_at = datetime('now') WHERE mac = ?",
        (value, mac.upper()),
    )
    await db.commit()


async def get_thisday_state(mac: str) -> tuple[int, int, int]:
    """读取 THISDAY 的 index / count。返回 (index, count, updated_date_hash)。"""
    db = await get_main_db()
    cursor = await db.execute(
        """
        SELECT static_thisday_index, static_thisday_count, static_updated_at
        FROM device_state WHERE mac = ?
        """,
        (mac.upper(),),
    )
    row = await cursor.fetchone()
    if not row:
        return 0, 0, 0
    index = row[0] or 0
    count = row[1] or 0
    updated_at: str = row[2] or ""
    # 用 updated_at 日期哈希来判断是否跨天
    date_hash = hash(updated_at[:10]) if updated_at else 0
    return index, count, date_hash


async def set_thisday_state(mac: str, index: int, count: int) -> None:
    """写入 THISDAY 的 index 和 count，并更新 static_updated_at。"""
    await _ensure_device_state_row(mac)
    db = await get_main_db()
    await db.execute(
        """
        UPDATE device_state
        SET static_thisday_index = ?, static_thisday_count = ?, static_updated_at = datetime('now')
        WHERE mac = ?
        """,
        (index, count, mac.upper()),
    )
    await db.commit()


# ── 游标法查询（海量随机模式）───────────────────────────────


async def fetch_next_poetry(mac: str) -> Optional[dict]:
    """游标法获取下一首诗词。cursor = 上次展示的 id，找到 > cursor 的第一条。
    
    新设备（cursor=0）会从随机位置开始轮询，避免不同设备展示相同内容。
    """
    cursor_val = await get_static_cursor(mac, "POETRY")
    db = await get_main_db()

    # 新设备：从随机位置开始
    if cursor_val == 0:
        # 获取总记录数
        count_row = await db.execute("SELECT COUNT(*) FROM static_poetry")
        total = (await count_row.fetchone())[0]
        if total == 0:
            return None
        # 基于 MAC 哈希生成伪随机偏移，确保同一设备每次重启都从同一位置开始
        import hashlib
        hash_val = int(hashlib.md5(f"{mac}:POETRY".encode()).hexdigest(), 16)
        random_offset = (hash_val % total) + 1  # 1-indexed
        cursor = await db.execute(
            "SELECT id, title, author, dynasty, lines_json, note, season_tag FROM static_poetry ORDER BY id ASC LIMIT ?",
            (random_offset - 1,),
        )
        row = await cursor.fetchone()
        if row:
            await set_static_cursor(mac, "POETRY", row[0])
            return _poetry_row_to_content(row)
        return None

    cursor = await db.execute(
        "SELECT id, title, author, dynasty, lines_json, note, season_tag FROM static_poetry WHERE id > ? ORDER BY id ASC LIMIT 1",
        (cursor_val,),
    )
    row = await cursor.fetchone()

    if row:
        await set_static_cursor(mac, "POETRY", row[0])
        return _poetry_row_to_content(row)

    # 游标到底，重置并从头取（保持原有逻辑，轮询完一轮）
    cursor = await db.execute(
        "SELECT id, title, author, dynasty, lines_json, note, season_tag FROM static_poetry ORDER BY id ASC LIMIT 1"
    )
    row = await cursor.fetchone()
    if row:
        await set_static_cursor(mac, "POETRY", row[0])
        return _poetry_row_to_content(row)

    return None


async def fetch_next_riddle(mac: str) -> Optional[dict]:
    """游标法获取下一条谜语。新设备从随机位置开始轮询。"""
    cursor_val = await get_static_cursor(mac, "RIDDLE")
    db = await get_main_db()

    # 新设备：从随机位置开始
    if cursor_val == 0:
        count_row = await db.execute("SELECT COUNT(*) FROM static_riddle")
        total = (await count_row.fetchone())[0]
        if total == 0:
            return None
        import hashlib
        hash_val = int(hashlib.md5(f"{mac}:RIDDLE".encode()).hexdigest(), 16)
        random_offset = (hash_val % total) + 1
        cursor = await db.execute(
            "SELECT id, category, question, hint, answer FROM static_riddle ORDER BY id ASC LIMIT ?",
            (random_offset - 1,),
        )
        row = await cursor.fetchone()
        if row:
            await set_static_cursor(mac, "RIDDLE", row[0])
            return _riddle_row_to_content(row)
        return None

    cursor = await db.execute(
        "SELECT id, category, question, hint, answer FROM static_riddle WHERE id > ? ORDER BY id ASC LIMIT 1",
        (cursor_val,),
    )
    row = await cursor.fetchone()

    if row:
        await set_static_cursor(mac, "RIDDLE", row[0])
        return _riddle_row_to_content(row)

    cursor = await db.execute(
        "SELECT id, category, question, hint, answer FROM static_riddle ORDER BY id ASC LIMIT 1"
    )
    row = await cursor.fetchone()
    if row:
        await set_static_cursor(mac, "RIDDLE", row[0])
        return _riddle_row_to_content(row)

    return None


# ── 轮询索引法查询（日期相关模式）────────────────────────────


async def fetch_thisday_record(month: int, day: int, mac: str) -> Optional[dict]:
    """按月日查询历史上的今天记录，使用设备级轮询索引展示不同记录。"""
    db = await get_main_db()

    # 查询当天所有记录
    cursor = await db.execute(
        """
        SELECT id, year, event_title, event_desc, years_ago, significance
        FROM static_thisday
        WHERE month = ? AND day = ?
        ORDER BY year ASC
        """,
        (month, day),
    )
    rows = await cursor.fetchall()

    if not rows:
        return None

    today = date.today()
    today_hash = hash(f"{today.month}-{today.day}")

    # 读取设备的当前索引
    saved_index, saved_count, saved_date_hash = await get_thisday_state(mac)

    # 跨天重置索引（每天第一次访问时）
    if today_hash != saved_date_hash:
        saved_index = 0
        saved_count = len(rows)

    count = len(rows)
    index = saved_index % count  # 安全取模
    row = rows[index]

    # 更新状态
    await set_thisday_state(mac, saved_index + 1, count)

    return _thisday_row_to_content(row)


# ── 行转内容字典（与原有 JSON 模式的 fallback 格式完全对齐）──


def _poetry_row_to_content(row: tuple) -> dict:
    id_, title, author, dynasty, lines_json, note, season_tag = row
    try:
        lines = json.loads(lines_json)
    except (json.JSONDecodeError, TypeError):
        lines = []
    return {
        "title":   title or "",
        "author":  author or "",
        "lines":   lines if isinstance(lines, list) else [],
        "note":    note or "",
        "_static_id": id_,
    }


def _riddle_row_to_content(row: tuple) -> dict:
    id_, category, question, hint, answer = row
    return {
        "category":  category or "谜语",
        "question":  question or "",
        "hint":      hint or "",
        "answer":    answer or "",
        "_static_id": id_,
    }


def _thisday_row_to_content(row: tuple) -> dict:
    id_, year, event_title, event_desc, years_ago, significance = row
    return {
        "year":          str(year) if year else "",
        "event_title":   event_title or "",
        "event_desc":    event_desc or "",
        "years_ago":     years_ago or "",
        "significance":  significance or "",
        "_static_id":    id_,
    }


# ── 首次初始化检查 ───────────────────────────────────────────


async def is_poetry_initialized() -> bool:
    """检查诗词数据库是否已完成初始化（有数据）。"""
    return await is_poetry_available()


# ── 数据存在性检查（用于降级决策）────────────────────────────


async def is_poetry_available() -> bool:
    db = await get_main_db()
    cursor = await db.execute("SELECT 1 FROM static_poetry LIMIT 1")
    row = await cursor.fetchone()
    return row is not None


async def is_riddle_available() -> bool:
    db = await get_main_db()
    cursor = await db.execute("SELECT 1 FROM static_riddle LIMIT 1")
    row = await cursor.fetchone()
    return row is not None


async def is_thisday_available(month: int, day: int) -> bool:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT 1 FROM static_thisday WHERE month = ? AND day = ? LIMIT 1",
        (month, day),
    )
    row = await cursor.fetchone()
    return row is not None


# ── 批量导入（供 init_static_data.py 调用）────────────────


async def bulk_insert_poetry(records: list[dict]) -> int:
    """批量插入诗词记录。records 为字典列表。返回插入条数。"""
    if not records:
        return 0
    db = await get_main_db()
    now = str(date.today())
    values = [
        (
            r.get("title", ""),
            r.get("author", ""),
            r.get("dynasty", ""),
            json.dumps(r.get("lines", []), ensure_ascii=False),
            r.get("note", ""),
            r.get("season_tag", ""),
            int(r.get("difficulty", 1)),
            now,
        )
        for r in records
    ]
    await db.executemany(
        """
        INSERT INTO static_poetry (title, author, dynasty, lines_json, note, season_tag, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    await db.commit()
    logger.info("[StaticDB] Inserted %d poetry records", len(records))
    return len(records)


async def bulk_insert_riddle(records: list[dict]) -> int:
    """批量插入谜语记录。"""
    if not records:
        return 0
    db = await get_main_db()
    now = str(date.today())
    values = [
        (
            r.get("category", "谜语"),
            r.get("question", ""),
            r.get("hint", ""),
            r.get("answer", ""),
            int(r.get("difficulty", 1)),
            now,
        )
        for r in records
    ]
    await db.executemany(
        """
        INSERT INTO static_riddle (category, question, hint, answer, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    await db.commit()
    logger.info("[StaticDB] Inserted %d riddle records", len(records))
    return len(records)


async def bulk_insert_thisday(records: list[dict]) -> int:
    """批量插入历史上的今天记录。"""
    if not records:
        return 0
    db = await get_main_db()
    now = str(date.today())
    values = [
        (
            int(r.get("month", 1)),
            int(r.get("day", 1)),
            int(r.get("year", 0)),
            r.get("event_title", ""),
            r.get("event_desc", ""),
            r.get("years_ago", ""),
            r.get("significance", ""),
            now,
        )
        for r in records
    ]
    await db.executemany(
        """
        INSERT INTO static_thisday (month, day, year, event_title, event_desc, years_ago, significance, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    await db.commit()
    logger.info("[StaticDB] Inserted %d thisday records", len(records))
    return len(records)
