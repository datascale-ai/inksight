"""Shared aiosqlite connection helpers with per-loop health checks."""
from __future__ import annotations

import asyncio
import logging
import os
import weakref
from dataclasses import dataclass
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..")
_MAIN_DB_PATH = os.path.join(_DB_DIR, "inksight.db")
_CACHE_DB_PATH = os.path.join(_DB_DIR, "cache.db")
_live_connections: "weakref.WeakSet[_ManagedConnection]" = weakref.WeakSet()


@dataclass
class _LoopState:
    loop: Any = None
    lock: asyncio.Lock | None = None
    conn: _ManagedConnection | None = None


_main_state = _LoopState()
_cache_state = _LoopState()

# Backward-compatible aliases for existing tests/patches.
_main_conn: _ManagedConnection | None = None
_cache_conn: _ManagedConnection | None = None


class _ManagedConnection:
    """Proxy around a shared sqlite connection.

    Callers may still invoke ``close()`` in ``finally`` blocks, but for shared
    connections that is treated as a release no-op. Actual shutdown is handled by
    ``close_all()`` or when an unhealthy singleton is replaced.
    """

    def __init__(self, conn: aiosqlite.Connection, label: str):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_closed", False)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._conn, name, value)

    async def close(self):
        logger.debug("[DB] Ignoring caller close() on shared %s connection", self._label)

    async def _force_close(self):
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        await self._conn.close()

    def __del__(self):  # pragma: no cover - best-effort cleanup
        if self._closed:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._force_close())


async def _open_db(path: str, label: str) -> _ManagedConnection:
    conn = await aiosqlite.connect(path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    managed = _ManagedConnection(conn, label)
    _live_connections.add(managed)
    logger.debug("[DB] Opened %s connection", label)
    return managed


async def _is_connection_healthy(conn: Any) -> bool:
    if conn is None or getattr(conn, "_closed", False):
        return False
    cursor = None
    try:
        cursor = await conn.execute("SELECT 1")
        if hasattr(cursor, "fetchone"):
            await cursor.fetchone()
        return True
    except Exception:
        logger.warning("[DB] Existing connection failed health check", exc_info=True)
        return False
    finally:
        if cursor is not None and hasattr(cursor, "close"):
            try:
                await cursor.close()
            except Exception:
                logger.debug("[DB] Ignoring cursor close failure during health check", exc_info=True)


async def _force_close_connection(conn: Any):
    if conn is None:
        return
    if isinstance(conn, _ManagedConnection):
        await conn._force_close()
        return
    close = getattr(conn, "close", None)
    if close is None:
        return
    await close()


def _get_state(current: str) -> _LoopState:
    return _main_state if current == "main" else _cache_state


def _sync_conn_aliases():
    global _main_conn, _cache_conn
    _main_conn = _main_state.conn
    _cache_conn = _cache_state.conn


async def _ensure_state_for_current_loop(current: str) -> _LoopState:
    state = _get_state(current)
    loop = asyncio.get_running_loop()

    if state.loop is loop and state.lock is not None:
        return state

    alias_conn = _main_conn if current == "main" else _cache_conn
    stale_conn = state.conn or alias_conn
    state.loop = loop
    state.lock = asyncio.Lock()
    state.conn = None
    _sync_conn_aliases()

    if stale_conn is not None:
        await _force_close_connection(stale_conn)

    return state


async def _get_or_reopen(path: str, label: str, current: str) -> _ManagedConnection:
    state = await _ensure_state_for_current_loop(current)

    async with state.lock:
        conn = state.conn
        if conn is None:
            conn = _main_conn if current == "main" else _cache_conn
            if conn is not None:
                state.conn = conn

        if await _is_connection_healthy(state.conn):
            _sync_conn_aliases()
            return state.conn

        if state.conn is not None:
            await _force_close_connection(state.conn)

        state.conn = await _open_db(path, label)
        _sync_conn_aliases()
        return state.conn


async def get_main_db() -> _ManagedConnection:
    return await _get_or_reopen(_MAIN_DB_PATH, "main", "main")


async def get_cache_db() -> _ManagedConnection:
    return await _get_or_reopen(_CACHE_DB_PATH, "cache", "cache")


async def close_all():
    global _main_state, _cache_state, _main_conn, _cache_conn

    pending = [_force_close_connection(conn) for conn in list(_live_connections)]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _live_connections.clear()

    _main_state = _LoopState()
    _cache_state = _LoopState()
    _main_conn = None
    _cache_conn = None
