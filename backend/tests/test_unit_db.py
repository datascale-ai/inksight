from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core import db as db_mod


@pytest.fixture(autouse=True)
async def _cleanup_db_singletons():
    await db_mod.close_all()
    yield
    await db_mod.close_all()


@pytest.mark.asyncio
async def test_get_main_db_reuses_singleton_connection():
    conn = AsyncMock()
    conn._closed = False
    conn.execute = AsyncMock(return_value=AsyncMock())

    with patch.object(db_mod, "_open_db", new=AsyncMock(return_value=conn)) as mock_open:
        first = await db_mod.get_main_db()
        second = await db_mod.get_main_db()

    assert first is conn
    assert second is conn
    assert mock_open.await_count == 1


@pytest.mark.asyncio
async def test_get_main_db_reopens_when_existing_singleton_is_unhealthy(monkeypatch):
    stale = AsyncMock()
    stale._closed = False
    stale.execute = AsyncMock(side_effect=RuntimeError("broken"))
    stale.close = AsyncMock()

    fresh = AsyncMock()
    fresh._closed = False
    fresh.execute = AsyncMock(return_value=AsyncMock())

    monkeypatch.setattr(db_mod, "_main_conn", stale, raising=False)

    with patch.object(db_mod, "_open_db", new=AsyncMock(return_value=fresh)) as mock_open:
        result = await db_mod.get_main_db()

    assert result is fresh
    stale.close.assert_awaited_once()
    assert mock_open.await_count == 1


@pytest.mark.asyncio
async def test_get_main_db_recreates_state_for_new_event_loop():
    first = AsyncMock()
    first._closed = False
    first.execute = AsyncMock(return_value=AsyncMock())

    second = AsyncMock()
    second._closed = False
    second.execute = AsyncMock(return_value=AsyncMock())

    original_loop = asyncio.get_running_loop()

    class OtherLoop:
        pass

    other_loop = OtherLoop()

    with patch.object(db_mod, "_open_db", new=AsyncMock(side_effect=[first, second])) as mock_open:
        same_loop_conn = await db_mod.get_main_db()
        assert same_loop_conn is first

        with patch("core.db.asyncio.get_running_loop", side_effect=[other_loop, other_loop]):
            new_loop_conn = await db_mod.get_main_db()

    assert new_loop_conn is second
    assert mock_open.await_count == 2
