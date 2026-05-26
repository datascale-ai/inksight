from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from api.index import app
from core.config_store import get_device_state
from core.config_store import init_db
from core.db import get_main_db
from core.vocab_store import get_vocab_content, handle_vocab_event


@pytest.fixture
async def isolated_db(tmp_path):
    from core import db as db_mod

    await db_mod.close_all()
    test_main_db = str(tmp_path / "test_inksight.db")
    test_cache_db = str(tmp_path / "test_cache.db")
    with patch.object(db_mod, "_MAIN_DB_PATH", test_main_db), \
         patch.object(db_mod, "_CACHE_DB_PATH", test_cache_db), \
         patch("core.config_store.DB_PATH", test_main_db), \
         patch("core.stats_store.DB_PATH", test_main_db), \
         patch("core.cache._CACHE_DB_PATH", test_cache_db):
        await init_db()
        yield
        await db_mod.close_all()


@pytest.fixture
async def client(isolated_db):
    try:
        from httpx import ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    except Exception:
        async with AsyncClient(app=app, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_vocab_tables_seeded_by_init_db(isolated_db):
    db = await get_main_db()
    for table in ("vocab_items", "vocab_progress", "vocab_session_state"):
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        assert await cursor.fetchone()
    cursor = await db.execute("SELECT COUNT(*) FROM vocab_items WHERE deck_id = 'core_en'")
    assert (await cursor.fetchone())[0] >= 10


@pytest.mark.asyncio
async def test_vocab_session_flip_rating_and_submit(isolated_db):
    mac = "AA:BB:CC:DD:EE:01"
    content = await get_vocab_content(mac, {"mode_overrides": {"VOCAB_REVIEW": {"daily_limit": 5, "new_cards_per_day": 2}}})
    assert content["state"] == "front"
    assert content["word"]

    await handle_vocab_event(mac, "flip", {})
    content = await get_vocab_content(mac, {})
    assert content["state"] == "back"
    assert content["rating_label"] == "忘了"

    await handle_vocab_event(mac, "next_rating", {})
    content = await get_vocab_content(mac, {})
    assert content["rating_label"] == "模糊"

    previous_word = content["word"]
    await handle_vocab_event(mac, "submit_rating", {}, rating="remember")
    content = await get_vocab_content(mac, {})
    assert content["state"] == "front"
    assert content["progress"].startswith("1/")
    assert content["word"] != previous_word

    db = await get_main_db()
    cursor = await db.execute("SELECT interval_days, repetitions, last_grade FROM vocab_progress WHERE mac = ?", (mac,))
    row = await cursor.fetchone()
    assert row[0] == 1
    assert row[1] == 1
    assert row[2] == "remember"


@pytest.mark.asyncio
async def test_vocab_event_api_requires_token_and_sets_pending_mode(client):
    mac = "AA:BB:CC:DD:EE:02"
    unauthorized = await client.post(f"/api/device/{mac}/vocab/event", json={"action": "enter"})
    assert unauthorized.status_code == 401

    token_resp = await client.post(f"/api/device/{mac}/token")
    token = token_resp.json()["token"]
    headers = {"X-Device-Token": token}
    resp = await client.post(f"/api/device/{mac}/vocab/event", json={"action": "enter"}, headers=headers)
    assert resp.status_code == 200
    state = await get_device_state(mac)
    assert state["pending_mode"] == "VOCAB_REVIEW"
    assert state["pending_refresh"] == 1

    resp = await client.post(f"/api/device/{mac}/vocab/event", json={"action": "flip"}, headers=headers)
    assert resp.status_code == 200
    state = await get_device_state(mac)
    assert state["pending_refresh"] == 1
