"""Shared aiosqlite connection manager with WAL mode."""
from __future__ import annotations

import asyncio
import logging
import os

import aiosqlite

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..")
_MAIN_DB_PATH = os.path.join(_DB_DIR, "inksight.db")
_CACHE_DB_PATH = os.path.join(_DB_DIR, "cache.db")

_main_conn: aiosqlite.Connection | None = None
_cache_conn: aiosqlite.Connection | None = None
_main_lock = asyncio.Lock()
_cache_lock = asyncio.Lock()


async def get_main_db() -> aiosqlite.Connection:
    """Get or create the shared main database connection."""
    global _main_conn
    async with _main_lock:
        if _main_conn is None:
            _main_conn = await aiosqlite.connect(_MAIN_DB_PATH)
            await _main_conn.execute("PRAGMA journal_mode=WAL")
            await _main_conn.execute("PRAGMA busy_timeout=5000")
            logger.info("[DB] Main database connection established (WAL mode)")
        return _main_conn


async def get_cache_db() -> aiosqlite.Connection:
    """Get or create the shared cache database connection."""
    global _cache_conn
    async with _cache_lock:
        if _cache_conn is None:
            _cache_conn = await aiosqlite.connect(_CACHE_DB_PATH)
            await _cache_conn.execute("PRAGMA journal_mode=WAL")
            await _cache_conn.execute("PRAGMA busy_timeout=5000")
            logger.info("[DB] Cache database connection established (WAL mode)")
        return _cache_conn


async def close_all():
    """Close all database connections (called on shutdown)."""
    global _main_conn, _cache_conn
    async with _main_lock:
        if _main_conn:
            await _main_conn.close()
            _main_conn = None
            logger.info("[DB] Main database connection closed")
    async with _cache_lock:
        if _cache_conn:
            await _cache_conn.close()
            _cache_conn = None
            logger.info("[DB] Cache database connection closed")
