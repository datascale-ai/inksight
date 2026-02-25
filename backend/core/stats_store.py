"""
Statistics data collection and querying.
Stores render logs and device heartbeats in SQLite.
"""
from __future__ import annotations

import os
import logging
import aiosqlite
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "inksight.db")


async def init_stats_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
            CREATE TABLE IF NOT EXISTS render_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                mode_id TEXT NOT NULL,
                content TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                mode_id TEXT NOT NULL,
                content_snapshot TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_render_logs_mac ON render_logs(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_render_logs_created ON render_logs(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_mac ON device_heartbeats(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_render_content_mac ON render_content(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_favorites_mac ON content_favorites(mac)")
        await db.commit()


async def log_render(
    mac: str,
    persona: str,
    cache_hit: bool,
    render_time_ms: int,
    status: str = "success",
):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO render_logs (mac, persona, cache_hit, render_time_ms, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mac, persona, int(cache_hit), render_time_ms, status, now),
        )
        await db.commit()


async def log_heartbeat(mac: str, battery_voltage: float, wifi_rssi: int | None = None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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


async def save_render_content(mac: str, mode_id: str, content: dict):
    """Save rendered content snapshot for history."""
    import json
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO render_content (mac, mode_id, content, created_at)
               VALUES (?, ?, ?, ?)""",
            (mac, mode_id, json.dumps(content, ensure_ascii=False), now),
        )
        # Keep only latest 200 per device
        await db.execute(
            """DELETE FROM render_content
               WHERE mac = ? AND id NOT IN (
                   SELECT id FROM render_content WHERE mac = ?
                   ORDER BY created_at DESC LIMIT 200
               )""",
            (mac, mac),
        )
        await db.commit()


async def get_content_history(
    mac: str, limit: int = 30, offset: int = 0, mode: str | None = None
) -> list[dict]:
    """Get content history for a device with optional mode filter."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        if mode:
            cursor = await db.execute(
                """SELECT id, mode_id, content, is_favorite, created_at
                   FROM render_content WHERE mac = ? AND mode_id = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (mac, mode.upper(), limit, offset),
            )
        else:
            cursor = await db.execute(
                """SELECT id, mode_id, content, is_favorite, created_at
                   FROM render_content WHERE mac = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (mac, limit, offset),
            )
        results = []
        for row in await cursor.fetchall():
            try:
                content = json.loads(row[2])
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


# ── Favorites ────────────────────────────────────────────────


async def add_favorite(mac: str, mode_id: str, content_snapshot: str | None = None):
    """Add current content to favorites."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO content_favorites (mac, mode_id, content_snapshot, created_at)
               VALUES (?, ?, ?, ?)""",
            (mac, mode_id, content_snapshot, now),
        )
        # Also mark in render_content if the latest entry matches
        await db.execute(
            """UPDATE render_content SET is_favorite = 1
               WHERE id = (
                   SELECT id FROM render_content
                   WHERE mac = ? AND mode_id = ?
                   ORDER BY created_at DESC LIMIT 1
               )""",
            (mac, mode_id),
        )
        await db.commit()


async def get_favorites(mac: str, limit: int = 30) -> list[dict]:
    """Get favorites for a device."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, mode_id, content_snapshot, created_at
               FROM content_favorites WHERE mac = ?
               ORDER BY created_at DESC LIMIT ?""",
            (mac, limit),
        )
        results = []
        for row in await cursor.fetchall():
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


async def get_latest_render_content(mac: str) -> dict | None:
    """Get the most recent render content for a device (used for favorites)."""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT mode_id, content FROM render_content
               WHERE mac = ? ORDER BY created_at DESC LIMIT 1""",
            (mac,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            content = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            content = {}
        return {"mode_id": row[0], "content": content}
