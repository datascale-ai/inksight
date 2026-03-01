"""Tests for habit API endpoints."""
from unittest.mock import patch

import pytest
from core.stats_store import init_stats_db, check_habit, get_habit_status, delete_habit


@pytest.fixture(autouse=True)
async def isolate_stats_db(tmp_path):
    """Use an isolated DB file per test and reset shared connections."""
    from core import db as db_mod

    test_db = str(tmp_path / "stats_test.db")
    await db_mod.close_all()

    with patch.object(db_mod, "_MAIN_DB_PATH", test_db), \
         patch("core.stats_store.DB_PATH", test_db), \
         patch("core.config_store.DB_PATH", test_db):
        yield

    await db_mod.close_all()


@pytest.mark.asyncio
async def test_habit_lifecycle():
    """Test create -> check -> status -> delete workflow."""
    await init_stats_db()

    mac = "AA:BB:CC:DD:EE:FF"

    # Check a habit (creates it)
    await check_habit(mac, "Morning Run", "2026-02-28")

    # Verify it appears
    status = await get_habit_status(mac)
    assert any(h["name"] == "Morning Run" for h in status)

    # Delete
    deleted = await delete_habit(mac, "Morning Run")
    assert deleted is True

    # Verify gone
    status = await get_habit_status(mac)
    assert not any(h["name"] == "Morning Run" for h in status)


@pytest.mark.asyncio
async def test_delete_nonexistent():
    await init_stats_db()
    deleted = await delete_habit("AA:BB:CC:DD:EE:FF", "Nonexistent")
    assert deleted is False
