"""
Integration tests for InkSight API -> render pipeline.
Uses httpx.AsyncClient with FastAPI TestClient, mocking LLM calls.
"""
import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from api.index import app
from core.cache import content_cache
from core.config_store import init_db
from core.stats_store import init_stats_db
from core.cache import init_cache_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path):
    """Create an async client with isolated temp databases for each test."""
    # Close existing db connections so we can redirect paths
    from core import db as db_mod
    await db_mod.close_all()

    # Redirect all database paths to temp files
    test_main_db = str(tmp_path / "test_inksight.db")
    test_cache_db = str(tmp_path / "test_cache.db")

    with patch.object(db_mod, "_MAIN_DB_PATH", test_main_db), \
         patch.object(db_mod, "_CACHE_DB_PATH", test_cache_db), \
         patch("core.config_store.DB_PATH", test_main_db), \
         patch("core.stats_store.DB_PATH", test_main_db), \
         patch("core.cache._CACHE_DB_PATH", test_cache_db):
        # Initialize the databases with the temp paths
        await init_db()
        await init_stats_db()
        await init_cache_db()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

        # Clean up connections after each test
        await db_mod.close_all()


# The STOIC mode uses llm_json content type with output_schema:
# {"quote": ..., "author": ..., "interpretation": ...}
MOCK_LLM_RESPONSE = json.dumps({
    "quote": "Test quote",
    "author": "Test Author",
    "interpretation": "Test interpretation",
})


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the in-memory image cache before each test."""
    content_cache._cache.clear()
    yield
    content_cache._cache.clear()


@pytest.fixture(autouse=True)
def _disable_dedup():
    """Disable content dedup lookups so LLM mock is not bypassed by stats_store."""
    with patch("core.stats_store.get_recent_content_hashes", new_callable=AsyncMock, return_value=[]), \
         patch("core.stats_store.get_recent_content_summaries", new_callable=AsyncMock, return_value=[]):
        yield


# ---------------------------------------------------------------------------
# Render endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_returns_bmp(client):
    """Test that /api/render returns a valid BMP image."""
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get("/api/render", params={
            "mac": "AA:BB:CC:DD:EE:FF",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/bmp"
        # BMP magic bytes
        assert resp.content[:2] == b"BM"


@pytest.mark.asyncio
@pytest.mark.parametrize("w,h", [("296", "128"), ("400", "300"), ("800", "480")])
async def test_render_multi_resolution(client, w, h):
    """Test rendering works for all supported resolutions."""
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get("/api/render", params={
            "mac": "AA:BB:CC:DD:EE:FF",
            "persona": "STOIC",
            "v": "3.85",
            "w": w,
            "h": h,
        })
        assert resp.status_code == 200
        assert resp.content[:2] == b"BM"


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_save_and_load(client):
    """Test saving and loading device configuration."""
    config_data = {
        "mac": "AA:BB:CC:DD:EE:FF",
        "modes": ["STOIC", "ZEN"],
        "refreshInterval": 30,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }
    resp = await client.post("/api/config", json=config_data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True

    resp = await client.get("/api/config/AA:BB:CC:DD:EE:FF")
    assert resp.status_code == 200
    data = resp.json()
    assert "STOIC" in data["modes"]
    assert "ZEN" in data["modes"]


# ---------------------------------------------------------------------------
# Habit workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_habit_workflow(client):
    """Test habit create -> check -> status -> delete lifecycle."""
    mac = "AA:BB:CC:DD:EE:FF"

    # Check habit (creates it)
    resp = await client.post(f"/api/device/{mac}/habit/check", json={
        "habit": "Exercise",
        "date": "2026-02-28",
    })
    assert resp.status_code == 200

    # Get status
    resp = await client.get(f"/api/device/{mac}/habit/status")
    assert resp.status_code == 200
    data = resp.json()
    assert any(h["name"] == "Exercise" for h in data["habits"])

    # Delete habit
    resp = await client.delete(f"/api/device/{mac}/habit/Exercise")
    assert resp.status_code == 200

    # Verify deleted
    resp = await client.get(f"/api/device/{mac}/habit/status")
    data = resp.json()
    assert not any(h["name"] == "Exercise" for h in data["habits"])


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit(client):
    """Test that second render hits cache (returns BMP without calling LLM again)."""
    mock_llm = AsyncMock(return_value=MOCK_LLM_RESPONSE)

    # First, save a config so the cache path is activated
    config_data = {
        "mac": "BB:CC:DD:EE:FF:00",
        "modes": ["STOIC"],
        "refreshInterval": 60,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }
    await client.post("/api/config", json=config_data)

    with patch("core.json_content._call_llm", mock_llm):
        # First render - should call LLM
        resp1 = await client.get("/api/render", params={
            "mac": "BB:CC:DD:EE:FF:00",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        })
        assert resp1.status_code == 200
        assert resp1.content[:2] == b"BM"
        first_call_count = mock_llm.call_count

        # Second render - should hit in-memory cache
        resp2 = await client.get("/api/render", params={
            "mac": "BB:CC:DD:EE:FF:00",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        })
        assert resp2.status_code == 200
        assert resp2.content[:2] == b"BM"
        # LLM should NOT have been called again for the second render
        assert mock_llm.call_count == first_call_count


# ---------------------------------------------------------------------------
# Health endpoint (quick smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test the /api/health endpoint returns ok."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
