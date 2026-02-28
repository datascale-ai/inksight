"""
Statistics data collection and querying.
Stores render logs, content history, and device heartbeats in SQLite.
"""
from __future__ import annotations

import hashlib
import json
import os
import logging
import aiosqlite
from datetime import datetime

logger = logging.getLogger(__name__)

from .db import get_main_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "inksight.db")


async def init_stats_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS render_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                persona TEXT NOT NULL,
                cache_hit INTEGER DEFAULT 0,
                render_time_ms INTEGER DEFAULT 0,
                llm_tokens INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                battery_voltage REAL,
                wifi_rssi INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                mode_id TEXT NOT NULL,
                content TEXT DEFAULT '{}',
                content_hash TEXT DEFAULT '',
                is_favorite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS habit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                habit_name TEXT NOT NULL,
                date TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(mac, habit_name, date)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_render_logs_mac ON render_logs(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_render_logs_created ON render_logs(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_mac ON device_heartbeats(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_content_history_mac ON content_history(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_content_history_hash ON content_history(mac, mode_id, content_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_habit_mac ON habit_records(mac)")
        await db.commit()


async def log_render(
    mac: str,
    persona: str,
    cache_hit: bool,
    render_time_ms: int,
    status: str = "success",
):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO render_logs (mac, persona, cache_hit, render_time_ms, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mac, persona, int(cache_hit), render_time_ms, status, now),
    )
    await db.commit()


async def log_heartbeat(mac: str, battery_voltage: float, wifi_rssi: int | None = None):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_heartbeats (mac, battery_voltage, wifi_rssi, created_at)
           VALUES (?, ?, ?, ?)""",
        (mac, battery_voltage, wifi_rssi, now),
    )
    # Keep only the latest 1000 heartbeats per device
    await db.execute(
        """DELETE FROM device_heartbeats
           WHERE mac = ? AND id NOT IN (
               SELECT id FROM device_heartbeats WHERE mac = ?
               ORDER BY created_at DESC LIMIT 1000
           )""",
        (mac, mac),
    )
    await db.commit()


async def get_device_stats(mac: str) -> dict:
    """Get comprehensive stats for a device."""
    db = await get_main_db()
    # Total renders
    cursor = await db.execute(
        "SELECT COUNT(*) FROM render_logs WHERE mac = ?", (mac,)
    )
    total_renders = (await cursor.fetchone())[0]

    # Cache hit rate
    cursor = await db.execute(
        "SELECT COUNT(*) FROM render_logs WHERE mac = ? AND cache_hit = 1", (mac,)
    )
    cache_hits = (await cursor.fetchone())[0]
    cache_hit_rate = round(cache_hits / total_renders * 100, 1) if total_renders > 0 else 0

    # Mode frequency
    cursor = await db.execute(
        """SELECT persona, COUNT(*) as cnt FROM render_logs
           WHERE mac = ? GROUP BY persona ORDER BY cnt DESC""",
        (mac,),
    )
    mode_frequency = {row[0]: row[1] for row in await cursor.fetchall()}

    # Last render
    cursor = await db.execute(
        "SELECT persona, created_at FROM render_logs WHERE mac = ? ORDER BY created_at DESC LIMIT 1",
        (mac,),
    )
    last_render_row = await cursor.fetchone()
    last_render = {"persona": last_render_row[0], "time": last_render_row[1]} if last_render_row else None

    # Battery voltage trend (last 30 entries)
    cursor = await db.execute(
        """SELECT battery_voltage, wifi_rssi, created_at FROM device_heartbeats
           WHERE mac = ? ORDER BY created_at DESC LIMIT 30""",
        (mac,),
    )
    heartbeats = [
        {"voltage": row[0], "rssi": row[1], "time": row[2]}
        for row in await cursor.fetchall()
    ]
    heartbeats.reverse()

    # Daily render counts (last 30 days)
    cursor = await db.execute(
        """SELECT DATE(created_at) as day, COUNT(*) as cnt
           FROM render_logs WHERE mac = ?
           GROUP BY day ORDER BY day DESC LIMIT 30""",
        (mac,),
    )
    daily_renders = [
        {"date": row[0], "count": row[1]}
        for row in await cursor.fetchall()
    ]
    daily_renders.reverse()

    # Average render time
    cursor = await db.execute(
        "SELECT AVG(render_time_ms) FROM render_logs WHERE mac = ? AND status = 'success'",
        (mac,),
    )
    avg_render_time = round((await cursor.fetchone())[0] or 0)

    # Error count
    cursor = await db.execute(
        "SELECT COUNT(*) FROM render_logs WHERE mac = ? AND status = 'error'",
        (mac,),
    )
    error_count = (await cursor.fetchone())[0]

    return {
        "mac": mac,
        "total_renders": total_renders,
        "cache_hit_rate": cache_hit_rate,
        "mode_frequency": mode_frequency,
        "last_render": last_render,
        "heartbeats": heartbeats,
        "daily_renders": daily_renders,
        "avg_render_time_ms": avg_render_time,
        "error_count": error_count,
    }


async def get_stats_overview() -> dict:
    """Get global overview stats across all devices."""
    db = await get_main_db()
    # Total devices
    cursor = await db.execute(
        "SELECT COUNT(DISTINCT mac) FROM render_logs"
    )
    total_devices = (await cursor.fetchone())[0]

    # Total renders
    cursor = await db.execute("SELECT COUNT(*) FROM render_logs")
    total_renders = (await cursor.fetchone())[0]

    # Global cache hit rate
    cursor = await db.execute(
        "SELECT COUNT(*) FROM render_logs WHERE cache_hit = 1"
    )
    cache_hits = (await cursor.fetchone())[0]
    cache_hit_rate = round(cache_hits / total_renders * 100, 1) if total_renders > 0 else 0

    # Global mode frequency
    cursor = await db.execute(
        "SELECT persona, COUNT(*) as cnt FROM render_logs GROUP BY persona ORDER BY cnt DESC"
    )
    mode_frequency = {row[0]: row[1] for row in await cursor.fetchall()}

    # Recent active devices
    cursor = await db.execute(
        """SELECT mac, MAX(created_at) as last_seen, COUNT(*) as renders
           FROM render_logs GROUP BY mac ORDER BY last_seen DESC LIMIT 20"""
    )
    devices = [
        {"mac": row[0], "last_seen": row[1], "total_renders": row[2]}
        for row in await cursor.fetchall()
    ]

    return {
        "total_devices": total_devices,
        "total_renders": total_renders,
        "cache_hit_rate": cache_hit_rate,
        "mode_frequency": mode_frequency,
        "devices": devices,
    }


async def get_render_history(mac: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """Get render history for a device with pagination."""
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT persona, cache_hit, render_time_ms, status, created_at
           FROM render_logs WHERE mac = ?
           ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        (mac, limit, offset),
    )
    return [
        {
            "persona": row[0],
            "cache_hit": bool(row[1]),
            "render_time_ms": row[2],
            "status": row[3],
            "time": row[4],
        }
        for row in await cursor.fetchall()
    ]


# ── Content history ──────────────────────────────────────────


def _compute_content_hash(content: dict | str | None) -> str:
    """Compute a short hash for content deduplication."""
    if content is None:
        return ""
    text = json.dumps(content, sort_keys=True, ensure_ascii=False) if isinstance(content, dict) else str(content)
    return hashlib.md5(text.encode()).hexdigest()[:12]


async def save_render_content(mac: str, mode_id: str, content: dict | None):
    """Save rendered content to history for dedup and browsing."""
    now = datetime.now().isoformat()
    content_str = json.dumps(content, ensure_ascii=False) if content else "{}"
    content_hash = _compute_content_hash(content)
    db = await get_main_db()
    await db.execute(
        """INSERT INTO content_history (mac, mode_id, content, content_hash, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (mac, mode_id, content_str, content_hash, now),
    )
    await db.execute(
        """DELETE FROM content_history
           WHERE mac = ? AND id NOT IN (
               SELECT id FROM content_history WHERE mac = ?
               ORDER BY created_at DESC LIMIT 500
           )""",
        (mac, mac),
    )
    await db.commit()


async def get_content_history(
    mac: str, limit: int = 30, offset: int = 0, mode: str | None = None,
) -> list[dict]:
    db = await get_main_db()
    if mode:
        cursor = await db.execute(
            """SELECT id, mode_id, content, is_favorite, created_at
               FROM content_history WHERE mac = ? AND mode_id = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (mac, mode.upper(), limit, offset),
        )
    else:
        cursor = await db.execute(
            """SELECT id, mode_id, content, is_favorite, created_at
               FROM content_history WHERE mac = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (mac, limit, offset),
        )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        try:
            content = json.loads(row[2]) if row[2] else {}
        except (json.JSONDecodeError, TypeError):
            content = {}
        results.append({
            "id": row[0],
            "mode_id": row[1],
            "content": content,
            "is_favorite": bool(row[3]),
            "time": row[4],
        })
    return results


async def get_latest_render_content(mac: str) -> dict | None:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT mode_id, content FROM content_history
           WHERE mac = ? ORDER BY created_at DESC LIMIT 1""",
        (mac,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    try:
        content = json.loads(row[1]) if row[1] else {}
    except (json.JSONDecodeError, TypeError):
        content = {}
    return {"mode_id": row[0], "content": content}


async def add_favorite(mac: str, mode_id: str, content_json: str | None):
    now = datetime.now().isoformat()
    content_str = content_json or "{}"
    content_hash = ""
    try:
        content_hash = _compute_content_hash(json.loads(content_str))
    except Exception:
        pass
    db = await get_main_db()
    await db.execute(
        """INSERT INTO content_history (mac, mode_id, content, content_hash, is_favorite, created_at)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (mac, mode_id, content_str, content_hash, now),
    )
    await db.commit()


async def get_favorites(mac: str, limit: int = 30) -> list[dict]:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT id, mode_id, content, created_at FROM content_history
           WHERE mac = ? AND is_favorite = 1
           ORDER BY created_at DESC LIMIT ?""",
        (mac, limit),
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        try:
            content = json.loads(row[2]) if row[2] else {}
        except (json.JSONDecodeError, TypeError):
            content = {}
        results.append({
            "id": row[0],
            "mode_id": row[1],
            "content": content,
            "time": row[3],
        })
    return results


async def get_recent_content_hashes(mac: str, mode_id: str, limit: int = 20) -> list[str]:
    """Get recent content hashes for deduplication."""
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT content_hash FROM content_history
           WHERE mac = ? AND mode_id = ? AND content_hash != ''
           ORDER BY created_at DESC LIMIT ?""",
        (mac, mode_id, limit),
    )
    return [row[0] for row in await cursor.fetchall()]


async def get_recent_content_summaries(mac: str, mode_id: str, limit: int = 3) -> list[str]:
    """Get short summaries of recent content for LLM dedup hints."""
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT content FROM content_history
           WHERE mac = ? AND mode_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (mac, mode_id, limit),
    )
    summaries = []
    for row in await cursor.fetchall():
        try:
            data = json.loads(row[0]) if row[0] else {}
            for key in ("quote", "question", "challenge", "body", "word", "event_title", "name_cn", "text"):
                if key in data and data[key]:
                    summaries.append(str(data[key])[:80])
                    break
        except Exception:
            pass
    return summaries


async def check_habit(mac: str, habit_name: str, date: str | None = None):
    """Record a habit check for a given date (defaults to today)."""
    now = datetime.now()
    if not date:
        date = now.strftime("%Y-%m-%d")
    db = await get_main_db()
    await db.execute(
        """INSERT INTO habit_records (mac, habit_name, date, completed, created_at)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(mac, habit_name, date) DO UPDATE SET completed = 1""",
        (mac, habit_name, date, now.isoformat()),
    )
    await db.commit()


async def get_habit_status(mac: str) -> list[dict]:
    """Get habit completion status for the current week."""
    from datetime import timedelta
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT DISTINCT habit_name FROM habit_records
           WHERE mac = ? ORDER BY habit_name""",
        (mac,),
    )
    habit_names = [row[0] for row in await cursor.fetchall()]
    if not habit_names:
        return []

    results = []
    for name in habit_names:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM habit_records
               WHERE mac = ? AND habit_name = ? AND date >= ? AND completed = 1""",
            (mac, name, week_start),
        )
        count = (await cursor.fetchone())[0]
        cursor = await db.execute(
            """SELECT completed FROM habit_records
               WHERE mac = ? AND habit_name = ? AND date = ?""",
            (mac, name, today),
        )
        today_row = await cursor.fetchone()
        today_done = bool(today_row and today_row[0])
        results.append({
            "name": name,
            "week_count": count,
            "today": today_done,
            "status": "✓" if today_done else "○",
        })
    return results
