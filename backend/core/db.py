"""Short-lived aiosqlite connection helpers with WAL mode."""
from __future__ import annotations

import asyncio
import logging
import os
import weakref

import aiosqlite

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..")
_MAIN_DB_PATH = os.path.join(_DB_DIR, "inksight.db")
_CACHE_DB_PATH = os.path.join(_DB_DIR, "cache.db")
_live_connections: "weakref.WeakSet[_ManagedConnection]" = weakref.WeakSet()


class _ManagedConnection:
    """Proxy that closes the underlying sqlite connection when released."""

    def __init__(self, conn: aiosqlite.Connection, label: str):
        self._conn = conn
        self._label = label
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        await self._conn.close()

    def __del__(self):  # pragma: no cover - best-effort cleanup
        if self._closed:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.close())


async def _open_db(path: str, label: str) -> _ManagedConnection:
    conn = await aiosqlite.connect(path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    managed = _ManagedConnection(conn, label)
    _live_connections.add(managed)
    logger.debug("[DB] Opened %s connection", label)
    return managed


async def get_main_db() -> _ManagedConnection:
    return await _open_db(_MAIN_DB_PATH, "main")


async def get_cache_db() -> _ManagedConnection:
    return await _open_db(_CACHE_DB_PATH, "cache")


async def close_all():
    pending = [conn.close() for conn in list(_live_connections)]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _live_connections.clear()
