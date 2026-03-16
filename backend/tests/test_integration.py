"""
Integration tests for InkSight API -> render pipeline.
Uses httpx.AsyncClient with FastAPI TestClient, mocking LLM calls.
"""
import io
import json
import pytest
from PIL import Image
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from api.index import app
from api import shared as shared_api
from core.cache import content_cache
from core.config_store import init_db
from core.db import get_main_db
from core.mode_registry import reset_registry
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


async def provision_device_headers(client: AsyncClient, mac: str) -> dict[str, str]:
    resp = await client.post(f"/api/device/{mac}/token")
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"X-Device-Token": token}


async def register_user(client: AsyncClient, username: str, password: str = "pass1234") -> dict:
    # Register validates invite_code (optional). If provided, it must exist and be unused.
    # We generate a unique code per user and seed it into the test DB to keep tests isolated.
    invite_code = f"TEST_CODE_{username.upper()}"
    db = await get_main_db()
    await db.execute(
        "INSERT OR IGNORE INTO invitation_codes (code, is_used, used_by_user_id) VALUES (?, 0, NULL)",
        (invite_code,),
    )
    await db.commit()
    resp = await client.post(
        "/api/auth/register",
        # New register contract: must provide a valid phone or email; invite_code is optional but
        # integration tests seed a per-user code to exercise the full flow.
        json={
            "username": username,  # display nickname
            "password": password,
            "email": f"{username}@example.com",
            "invite_code": invite_code,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def png_payload(width: int = 48, height: int = 48) -> bytes:
    buf = io.BytesIO()
    Image.new("1", (width, height), 1).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Render endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_returns_bmp(client):
    """Test that /api/render returns a valid BMP image."""
    headers = await provision_device_headers(client, "AA:BB:CC:DD:EE:FF")
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get("/api/render", params={
            "mac": "AA:BB:CC:DD:EE:FF",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/bmp"
        # BMP magic bytes
        assert resp.content[:2] == b"BM"


@pytest.mark.asyncio
async def test_render_returns_binding_prompt_when_device_has_no_owner(client, monkeypatch):
    headers = await provision_device_headers(client, "AA:BB:CC:DD:EE:99")

    async def _fake_get_device_owner(mac: str):
        assert mac == "AA:BB:CC:DD:EE:99"
        return None

    async def _fake_get_or_create_claim_token(mac: str, source: str = "render"):
        assert mac == "AA:BB:CC:DD:EE:99"
        assert source == "render"
        return {
            "token": "claim-token",
            "pair_code": "AB12CD34",
            "expires_at": "2099-01-01T00:00:00",
        }

    async def _unexpected_build_image(*args, **kwargs):
        raise AssertionError("build_image should not run for unbound devices")

    async def _unexpected_log_render_stats(*args, **kwargs):
        raise AssertionError("log_render_stats should not run for unbound devices")

    async def _unexpected_get_latest_heartbeat(*args, **kwargs):
        raise AssertionError("heartbeat lookup should not run for unbound devices")

    monkeypatch.setattr("api.routes.render.get_device_owner", _fake_get_device_owner)
    monkeypatch.setattr("api.routes.render.get_or_create_claim_token", _fake_get_or_create_claim_token)
    monkeypatch.setattr("api.routes.render.build_image", _unexpected_build_image)
    monkeypatch.setattr("api.routes.render.log_render_stats", _unexpected_log_render_stats)
    monkeypatch.setattr("api.routes.render.get_latest_heartbeat", _unexpected_get_latest_heartbeat)

    resp = await client.get("/api/render", params={
        "mac": "AA:BB:CC:DD:EE:99",
        "v": "3.85",
        "w": "400",
        "h": "300",
    }, headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/bmp"
    assert resp.content[:2] == b"BM"


@pytest.mark.asyncio
async def test_build_image_prefers_owner_image_provider_over_device_config(sample_date_ctx, sample_weather):
    captured = {}
    mock_reg = MagicMock()
    mock_reg.is_supported.return_value = True
    mock_reg.get_mode_info.return_value = MagicMock(cacheable=False)
    mock_reg.get_json_mode.return_value = None

    async def _fake_generate_and_render(persona, config, date_ctx, weather, battery_pct, **kwargs):
        captured["config"] = config
        return Image.new("1", (400, 300), 1), {"quote": "ok"}

    async def _fake_get_active_config(mac):
        assert mac == "AA:BB:CC:DD:EE:88"
        return {
            "mac": mac,
            "modes": ["ARTWALL"],
            "llm_provider": "deepseek",
            "llm_model": "deepseek-chat",
            "image_provider": "aliyun",
        }

    async def _fake_resolve_mode(mac, config, persona_override, force_next=False):
        return "ARTWALL"

    async def _fake_get_device_owner(mac):
        assert mac == "AA:BB:CC:DD:EE:88"
        return {"user_id": 123}

    async def _fake_get_user_llm_config(user_id):
        assert user_id == 123
        return {
            "provider": "moonshot",
            "model": "moonshot-v1-8k",
            "api_key": "sk-user-key",
            "image_provider": "owner-image-provider",
            "image_api_key": "img-key",
        }

    with (
        patch("core.mode_registry.get_registry", return_value=mock_reg),
        patch("api.shared.get_active_config", new_callable=AsyncMock, side_effect=_fake_get_active_config),
        patch("api.shared.resolve_mode", new_callable=AsyncMock, side_effect=_fake_resolve_mode),
        patch("core.config_store.get_device_owner", new_callable=AsyncMock, side_effect=_fake_get_device_owner),
        patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, side_effect=_fake_get_user_llm_config),
        patch("api.shared.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx),
        patch("api.shared.get_weather", new_callable=AsyncMock, return_value=sample_weather),
        patch("api.shared.generate_and_render", new_callable=AsyncMock, side_effect=_fake_generate_and_render),
        patch("api.shared.update_device_state", new_callable=AsyncMock),
        patch("api.shared.save_render_content", new_callable=AsyncMock),
    ):
        await shared_api.build_image(
            3.85,
            "AA:BB:CC:DD:EE:88",
            "ARTWALL",
            screen_w=400,
            screen_h=300,
        )

    assert captured["config"]["llm_provider"] == "moonshot"
    assert captured["config"]["llm_model"] == "moonshot-v1-8k"
    assert captured["config"]["image_provider"] == "owner-image-provider"


@pytest.mark.asyncio
async def test_render_v1_alias_returns_bmp(client):
    headers = await provision_device_headers(client, "AA:BB:CC:DD:EE:01")
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get("/api/v1/render", params={
            "mac": "AA:BB:CC:DD:EE:01",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/bmp"
        assert resp.content[:2] == b"BM"


@pytest.mark.asyncio
@pytest.mark.parametrize("w,h", [("296", "128"), ("400", "300"), ("800", "480")])
async def test_render_multi_resolution(client, w, h):
    """Test rendering works for all supported resolutions."""
    headers = await provision_device_headers(client, "AA:BB:CC:DD:EE:FF")
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get("/api/render", params={
            "mac": "AA:BB:CC:DD:EE:FF",
            "persona": "STOIC",
            "v": "3.85",
            "w": w,
            "h": h,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.content[:2] == b"BM"


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_save_and_load(client):
    """Test saving and loading device configuration."""
    headers = await provision_device_headers(client, "AA:BB:CC:DD:EE:FF")
    config_data = {
        "mac": "AA:BB:CC:DD:EE:FF",
        "modes": ["STOIC", "ZEN"],
        "refreshInterval": 30,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }
    resp = await client.post("/api/config", json=config_data, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True

    resp = await client.get("/api/config/AA:BB:CC:DD:EE:FF", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "STOIC" in data["modes"]
    assert "ZEN" in data["modes"]

    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        render_resp = await client.get("/api/render", params={
            "mac": "AA:BB:CC:DD:EE:FF",
            "persona": "STOIC",
            "v": "3.85",
            "refresh_min": "60",
            "w": "400",
            "h": "300",
        }, headers=headers)
    assert render_resp.status_code == 200
    assert render_resp.headers["x-refresh-minutes"] == "30"


@pytest.mark.asyncio
async def test_cors_allows_local_expo_web(client):
    resp = await client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://127.0.0.1:8081",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://127.0.0.1:8081"


@pytest.mark.asyncio
async def test_config_history_and_activate_flow(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    mac = "AA:BB:CC:DD:EE:10"
    headers = await provision_device_headers(client, mac)

    config_a = {
        "mac": mac,
        "modes": ["STOIC"],
        "refreshInterval": 30,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }
    config_b = {
        "mac": mac,
        "modes": ["ZEN"],
        "refreshInterval": 45,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }

    resp_a = await client.post("/api/config", json=config_a, headers=headers)
    resp_b = await client.post("/api/v1/config", json=config_b, headers=headers)
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    config_a_id = resp_a.json()["config_id"]

    history_resp = await client.get(f"/api/v1/config/{mac}/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()["configs"]
    assert len(history) >= 2
    assert any(cfg["id"] == config_a_id for cfg in history)

    activate_resp = await client.put(
        f"/api/v1/config/{mac}/activate/{config_a_id}",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["ok"] is True

    active_resp = await client.get(f"/api/config/{mac}", headers=headers)
    assert active_resp.status_code == 200
    active = active_resp.json()
    assert active["id"] == config_a_id
    assert active["modes"] == ["STOIC"]


# ---------------------------------------------------------------------------
# Habit workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_habit_workflow(client):
    """Test habit create -> check -> status -> delete lifecycle."""
    mac = "AA:BB:CC:DD:EE:FF"
    headers = await provision_device_headers(client, mac)

    # Check habit (creates it)
    resp = await client.post(f"/api/device/{mac}/habit/check", json={
        "habit": "Exercise",
        "date": "2026-02-28",
    }, headers=headers)
    assert resp.status_code == 200

    # Get status
    resp = await client.get(f"/api/device/{mac}/habit/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(h["name"] == "Exercise" for h in data["habits"])

    # Delete habit
    resp = await client.delete(f"/api/device/{mac}/habit/Exercise", headers=headers)
    assert resp.status_code == 200

    # Verify deleted
    resp = await client.get(f"/api/device/{mac}/habit/status", headers=headers)
    data = resp.json()
    assert not any(h["name"] == "Exercise" for h in data["habits"])


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit(client):
    """Test that second render hits cache (returns BMP without calling LLM again)."""
    mock_llm = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    headers = await provision_device_headers(client, "BB:CC:DD:EE:FF:00")

    # First, save a config so the cache path is activated
    config_data = {
        "mac": "BB:CC:DD:EE:FF:00",
        "modes": ["STOIC"],
        "refreshInterval": 60,
        "llmProvider": "deepseek",
        "llmModel": "deepseek-chat",
    }
    await client.post("/api/config", json=config_data, headers=headers)

    with patch("core.json_content._call_llm", mock_llm):
        # First render - should call LLM
        resp1 = await client.get("/api/render", params={
            "mac": "BB:CC:DD:EE:FF:00",
            "persona": "STOIC",
            "v": "3.85",
            "w": "400",
            "h": "300",
        }, headers=headers)
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
        }, headers=headers)
        assert resp2.status_code == 200
        assert resp2.content[:2] == b"BM"
        # LLM should NOT have been called again for the second render
        assert mock_llm.call_count == first_call_count


@pytest.mark.asyncio
async def test_widget_returns_png(client):
    mac = "BB:CC:DD:EE:FF:11"
    headers = await provision_device_headers(client, mac)
    await client.post(
        "/api/config",
        json={
            "mac": mac,
            "modes": ["STOIC"],
            "refreshInterval": 60,
            "llmProvider": "deepseek",
            "llmModel": "deepseek-chat",
        },
        headers=headers,
    )
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get(f"/api/v1/widget/{mac}", params={"size": "small"}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


@pytest.mark.asyncio
async def test_preview_stream_returns_sse_events(client):
    headers = await provision_device_headers(client, "CC:DD:EE:FF:00:11")
    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        resp = await client.get(
            "/api/preview/stream",
            params={
                "mac": "CC:DD:EE:FF:00:11",
                "persona": "STOIC",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        assert 'event: status' in body
        assert 'event: result' in body
        assert '"stage": "done"' in body


@pytest.mark.asyncio
async def test_preview_stream_returns_error_event_on_render_failure(client):
    headers = await provision_device_headers(client, "CC:DD:EE:FF:00:12")
    with patch("api.routes.render.build_image", new_callable=AsyncMock, side_effect=RuntimeError("render boom")):
        resp = await client.get(
            "/api/preview/stream",
            params={
                "mac": "CC:DD:EE:FF:00:12",
                "persona": "STOIC",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        assert 'event: status' in body
        assert 'event: error' in body
        assert 'render boom' in body


@pytest.mark.asyncio
async def test_device_preview_stats_and_share_flow(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    mac = "CC:DD:EE:FF:11:22"
    headers = await provision_device_headers(client, mac)

    claim_resp = await client.post(f"/api/device/{mac}/claim-token", headers=headers)
    assert claim_resp.status_code == 200
    claim = claim_resp.json()
    assert claim["ok"] is True

    await register_user(client, "preview_owner")
    consume_resp = await client.post("/api/claim/consume", json={"token": claim["token"]})
    assert consume_resp.status_code == 200
    assert consume_resp.json()["status"] == "claimed"

    config_resp = await client.post(
        "/api/config",
        json={
            "mac": mac,
            "modes": ["STOIC"],
            "refreshInterval": 60,
            "llmProvider": "deepseek",
            "llmModel": "deepseek-chat",
        },
        headers=headers,
    )
    assert config_resp.status_code == 200

    runtime_resp = await client.post(
        f"/api/device/{mac}/runtime",
        json={"mode": "active"},
        headers=headers,
    )
    assert runtime_resp.status_code == 200
    assert runtime_resp.json()["runtime_mode"] == "active"

    heartbeat_resp = await client.post(
        f"/api/v1/device/{mac}/heartbeat",
        json={"battery_voltage": 3.91, "wifi_rssi": -42},
        headers=headers,
    )
    assert heartbeat_resp.status_code == 200

    state_resp = await client.get(f"/api/device/{mac}/state", headers=headers)
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["runtime_mode"] == "active"
    assert state["is_online"] is True
    assert state["refresh_minutes"] == 60
    assert state["last_seen"]

    preview_resp = await client.post(
        f"/api/device/{mac}/apply-preview",
        params={"mode": "STOIC"},
        content=png_payload(),
        headers={**headers, "Content-Type": "image/png"},
    )
    assert preview_resp.status_code == 200

    render_resp = await client.get("/api/render", params={"mac": mac, "v": "3.91"}, headers=headers)
    assert render_resp.status_code == 200
    assert render_resp.headers["x-preview-push"] == "1"
    assert render_resp.content[:2] == b"BM"

    favorite_resp = await client.post(
        f"/api/device/{mac}/favorite",
        json={"mode": "STOIC"},
        headers=headers,
    )
    assert favorite_resp.status_code == 200
    assert favorite_resp.json()["ok"] is True

    favorites_resp = await client.get(f"/api/device/{mac}/favorites", headers=headers)
    assert favorites_resp.status_code == 200
    favorites = favorites_resp.json()["favorites"]
    assert favorites
    assert favorites[0]["mode_id"] == "STOIC"

    history_resp = await client.get(f"/api/device/{mac}/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()["history"]
    assert history

    share_resp = await client.get(f"/api/device/{mac}/share", headers=headers)
    assert share_resp.status_code == 200
    assert share_resp.headers["content-type"].startswith("image/png")

    stats_resp = await client.get(f"/api/stats/{mac}", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_renders"] >= 1
    assert stats["heartbeats"]

    renders_resp = await client.get(f"/api/v1/stats/{mac}/renders", headers=headers)
    assert renders_resp.status_code == 200
    assert renders_resp.json()["renders"]

    recent_resp = await client.get(
        "/api/devices/recent",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert recent_resp.status_code == 200
    assert any(device["mac"] == mac for device in recent_resp.json()["devices"])

    overview_resp = await client.get(
        "/api/v1/stats/overview",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["total_devices"] >= 1
    assert overview["total_renders"] >= 1


@pytest.mark.asyncio
async def test_auth_claim_and_membership_approval_flow(client):
    mac = "DD:EE:FF:00:11:22"
    headers = await provision_device_headers(client, mac)

    claim_resp = await client.post(f"/api/device/{mac}/claim-token", headers=headers)
    assert claim_resp.status_code == 200
    claim = claim_resp.json()
    assert claim["ok"] is True

    owner = await register_user(client, "owner_user")
    consume_resp = await client.post("/api/claim/consume", json={"token": claim["token"]})
    assert consume_resp.status_code == 200
    consume = consume_resp.json()
    assert consume["status"] == "claimed"
    assert consume["mac"] == mac

    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == owner["user_id"]

    devices_resp = await client.get("/api/user/devices")
    assert devices_resp.status_code == 200
    devices = devices_resp.json()["devices"]
    assert any(device["mac"] == mac for device in devices)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as member_client:
        member = await register_user(member_client, "member_user")

        bind_resp = await member_client.post("/api/user/devices", json={"mac": mac, "nickname": "Shared"})
        assert bind_resp.status_code == 200
        assert bind_resp.json()["status"] == "pending_approval"

        requests_resp = await client.get("/api/user/devices/requests")
        assert requests_resp.status_code == 200
        requests = requests_resp.json()["requests"]
        assert len(requests) == 1
        request_id = requests[0]["id"]

        approve_resp = await client.post(f"/api/user/devices/requests/{request_id}/approve")
        assert approve_resp.status_code == 200
        assert approve_resp.json()["ok"] is True

        member_devices_resp = await member_client.get("/api/user/devices")
        assert member_devices_resp.status_code == 200
        member_devices = member_devices_resp.json()["devices"]
        assert any(device["mac"] == mac and device["role"] == "member" for device in member_devices)

        members_resp = await client.get(f"/api/user/devices/{mac}/members")
        assert members_resp.status_code == 200
        members = members_resp.json()["members"]
        assert len(members) == 2
        assert any(item["user_id"] == owner["user_id"] and item["role"] == "owner" for item in members)
        assert any(item["user_id"] == member["user_id"] and item["role"] == "member" for item in members)

        remove_resp = await client.delete(f"/api/user/devices/{mac}/members/{member['user_id']}")
        assert remove_resp.status_code == 200
        assert remove_resp.json()["ok"] is True

        member_devices_after_resp = await member_client.get("/api/user/devices")
        assert member_devices_after_resp.status_code == 200
        assert not any(device["mac"] == mac for device in member_devices_after_resp.json()["devices"])

    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    me_after_logout = await client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_mobile_preferences_and_push_registration_flow(client):
    user = await register_user(client, "mobile_user")

    prefs_resp = await client.get("/api/user/preferences")
    assert prefs_resp.status_code == 200
    prefs = prefs_resp.json()
    assert prefs["user_id"] == user["user_id"]
    assert prefs["push_enabled"] is False

    update_resp = await client.put(
        "/api/user/preferences",
        json={
            "push_enabled": True,
            "push_time": "09:30",
            "push_modes": ["DAILY", "POETRY"],
            "widget_mode": "POETRY",
            "locale": "en",
            "timezone": "Asia/Shanghai",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["preferences"]
    assert updated["push_enabled"] is True
    assert updated["widget_mode"] == "POETRY"
    assert updated["locale"] == "en"

    register_resp = await client.post(
        "/api/push/register",
        json={
            "push_token": "ExponentPushToken[test-mobile-token]",
            "platform": "expo",
            "timezone": "Asia/Shanghai",
            "push_time": "09:30",
        },
    )
    assert register_resp.status_code == 200
    registration = register_resp.json()["registration"]
    assert registration["push_token"] == "ExponentPushToken[test-mobile-token]"

    unregister_resp = await client.request(
        "DELETE",
        "/api/push/unregister",
        json={"push_token": "ExponentPushToken[test-mobile-token]"},
    )
    assert unregister_resp.status_code == 200
    assert unregister_resp.json()["deleted"] == 1


@pytest.mark.asyncio
async def test_mobile_content_today_and_widget_data(client):
    mac = "EE:FF:00:11:22:33"
    headers = await provision_device_headers(client, mac)
    await client.post(
        "/api/config",
        json={
            "mac": mac,
            "modes": ["POETRY", "DAILY"],
            "refreshInterval": 60,
            "llmProvider": "deepseek",
            "llmModel": "deepseek-chat",
            "city": "杭州",
        },
        headers=headers,
    )

    with patch("core.json_content._call_llm", new_callable=AsyncMock, return_value=MOCK_LLM_RESPONSE):
        today_resp = await client.get("/api/content/today", params={"modes": "POETRY,DAILY", "limit": 2})
        assert today_resp.status_code == 200
        today_payload = today_resp.json()
        assert len(today_payload["items"]) == 2
        assert today_payload["items"][0]["preview_url"].startswith("/api/preview?")

        widget_resp = await client.get(f"/api/widget/{mac}/data", params={"mode": "POETRY"}, headers=headers)
        assert widget_resp.status_code == 200
        widget_payload = widget_resp.json()
        assert widget_payload["mode_id"] == "POETRY"
        assert "content" in widget_payload
        assert widget_payload["preview_url"].startswith("/api/preview?")


@pytest.mark.asyncio
async def test_user_can_preview_and_create_custom_mode(client):
    await register_user(client, "creator_user")

    mode_def = {
        "mode_id": "MOBILE_NOTE",
        "display_name": "Mobile Note",
        "icon": "star",
        "cacheable": True,
        "description": "created from mobile editor",
        "content": {
            "type": "static",
            "static_data": {"text": "Write with calm intent."},
        },
        "layout": {
            "status_bar": {"line_width": 1},
            "body": [
                {
                    "type": "centered_text",
                    "field": "text",
                    "font": "noto_serif_regular",
                    "font_size": 18,
                    "vertical_center": True,
                }
            ],
            "footer": {"label": "MOBILE"},
        },
    }

    preview_resp = await client.post(
        "/api/modes/custom/preview",
        json={"mode_def": mode_def, "responseType": "json"},
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["ok"] is True
    assert preview["preview_text"] == "Write with calm intent."

    create_resp = await client.post("/api/modes/custom", json=mode_def)
    assert create_resp.status_code == 200
    assert create_resp.json()["mode_id"] == "MOBILE_NOTE"

    get_resp = await client.get("/api/modes/custom/MOBILE_NOTE")
    assert get_resp.status_code == 200
    assert get_resp.json()["display_name"] == "Mobile Note"


# ---------------------------------------------------------------------------
# Modes routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modes_v1_alias_returns_mode_list(client):
    resp = await client.get("/api/v1/modes")
    assert resp.status_code == 200
    payload = resp.json()
    assert "modes" in payload
    assert isinstance(payload["modes"], list)
    assert payload["modes"]
    assert "mode_id" in payload["modes"][0]


@pytest.mark.asyncio
async def test_custom_modes_end_to_end(client, monkeypatch):
    """
    自定义模式从生成 -> 保存到数据库(按 user_id + mac) -> 获取 -> 删除 的完整流程。

    注意：当前实现中自定义模式完全存储在数据库中，并且通过 (user_id, mac) 做设备隔离，
    所以这里显式地为测试用户绑定一台设备，并在所有接口调用中传递 mac。
    """

    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    reset_registry()

    mac = "AA:BB:CC:DD:EE:01"

    # 1. 注册一个普通用户，并为其绑定一台设备（owner, active）
    owner = await register_user(client, "custom_mode_owner")
    user_id = owner["user_id"]

    from core.config_store import upsert_device_membership

    membership = await upsert_device_membership(
        mac,
        user_id,
        role="owner",
        status="active",
        nickname="CustomModeDevice",
    )
    assert membership["status"] == "active"

    # 2. 准备一个最小可用的自定义模式定义
    mode_def = {
        "mode_id": "E2E_CUSTOM",
        "display_name": "E2E Custom",
        "icon": "star",
        "cacheable": True,
        "description": "integration test custom mode",
        "content": {
            "type": "static",
            "static_data": {"text": "hello custom"},
        },
        "layout": {
            "body": [
                {
                    "type": "centered_text",
                    "field": "text",
                    "font_size": 16,
                    "vertical_center": True,
                }
            ],
        },
    }

    # 3. 预览接口仍然由 admin_token 控制，只验证能返回 PNG
    preview_resp = await client.post(
        "/api/v1/modes/custom/preview",
        json={"mode_def": mode_def, "w": 400, "h": 300},
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert preview_resp.status_code == 200
    assert preview_resp.headers["content-type"].startswith("image/png")

    # 4. 生成接口使用 admin_token + mock，验证返回的 mode_id
    with patch("core.mode_generator.generate_mode_definition", new_callable=AsyncMock, return_value=mode_def):
        generate_resp = await client.post(
            "/api/modes/generate",
            json={"description": "generate a custom mode"},
            headers={"Authorization": "Bearer admin-secret"},
        )
    assert generate_resp.status_code == 200
    assert generate_resp.json()["mode_id"] == "E2E_CUSTOM"

    # 5. 以普通用户身份创建自定义模式（必须带 mac，写入数据库）
    create_body = dict(mode_def)
    create_body["mac"] = mac
    create_resp = await client.post(
        "/api/modes/custom",
        json=create_body,
        # 使用 register_user 建立的会话 cookie 作为用户身份，无需 admin token
    )
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body.get("ok") is True
    assert body.get("mode_id") == "E2E_CUSTOM"

    # 6. 按 user_id + mac 获取自定义模式
    get_resp = await client.get(f"/api/modes/custom/E2E_CUSTOM?mac={mac}")
    assert get_resp.status_code == 200
    get_payload = get_resp.json()
    assert get_payload["display_name"] == "E2E Custom"
    assert get_payload["content"]["static_data"]["text"] == "hello custom"

    # 7. 删除该设备上的自定义模式（必须带 mac，不能影响其他设备）
    delete_resp = await client.delete(f"/api/v1/modes/custom/E2E_CUSTOM?mac={mac}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True

    # 8. 再次获取应返回 404
    missing_resp = await client.get(f"/api/modes/custom/E2E_CUSTOM?mac={mac}")
    assert missing_resp.status_code == 404

    reset_registry()


# ---------------------------------------------------------------------------
# Legacy pages routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_page_bridge_and_legacy_page(client):
    bridge_resp = await client.get("/config")
    assert bridge_resp.status_code == 200
    assert "Device configuration moved to the web app." in bridge_resp.text
    assert "/legacy/config" in bridge_resp.text

    legacy_resp = await client.get("/legacy/config")
    assert legacy_resp.status_code == 200
    assert "legacy-console-banner" not in legacy_resp.text
    assert "/webconfig/role-banner.js" in legacy_resp.text


@pytest.mark.asyncio
async def test_config_page_redirects_to_primary_webapp_when_configured(client, monkeypatch):
    monkeypatch.setenv("INKSIGHT_PRIMARY_WEBAPP_URL", "https://app.example.com")
    resp = await client.get("/config", params={"mac": "AA:BB:CC:DD:EE:FF"})
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://app.example.com/config?mac=AA:BB:CC:DD:EE:FF"


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
