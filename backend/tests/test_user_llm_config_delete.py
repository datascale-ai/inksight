from __future__ import annotations

import secrets
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from api.index import app
from core.config_store import init_db
from core.db import get_main_db
from core.stats_store import init_stats_db
from core.cache import init_cache_db


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

        # httpx compatibility wrapper for different versions
        try:
            from httpx import ASGITransport  # type: ignore

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c
        except Exception:
            async with AsyncClient(app=app, base_url="http://test") as c:
                yield c

        # Clean up connections after each test
        await db_mod.close_all()


async def _register_and_login(client: AsyncClient) -> dict:
    username = f"byok_del_{secrets.token_hex(4)}"
    password = "pass1234"
    # register requires phone or email
    reg = await client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "email": f"{username}@example.com"},
    )
    assert reg.status_code in (200, 409)
    # login to get token deterministically (register may conflict in rare cases)
    login = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = int(me.json()["user_id"])

    return {"username": username, "user_id": user_id, "headers": headers}


async def _cleanup_user_data(user_id: int) -> None:
    """Best-effort cleanup to keep the test DB in a pristine state."""
    from core.db import get_main_db

    db = await get_main_db()
    try:
        await db.execute("BEGIN")
        await db.execute("DELETE FROM user_llm_config WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM api_quotas WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
    except Exception:
        await db.rollback()
        # Don't fail tests because cleanup failed; but surface in logs if needed.


@pytest.mark.asyncio
async def test_delete_user_llm_config_clears_profile_and_is_idempotent(client: AsyncClient):
    auth = await _register_and_login(client)
    headers = auth["headers"]
    user_id = auth["user_id"]

    try:
        # 1) Save BYOK config
        put = await client.put(
            "/api/user/profile/llm",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "llm_access_mode": "preset",
                "provider": "deepseek",
                "model": "deepseek-chat",
                "api_key": "sk-user-test-key",
                "base_url": "",
                "image_provider": "aliyun",
                "image_model": "qwen-image-max",
                "image_api_key": "sk-user-image-test-key",
            },
        )
        assert put.status_code == 200
        assert put.json().get("ok") is True

        # 2) Profile should include llm_config with api_key
        prof1 = await client.get("/api/user/profile", headers=headers)
        assert prof1.status_code == 200
        llm1 = prof1.json().get("llm_config")
        assert isinstance(llm1, dict)
        assert (llm1.get("api_key") or "").strip() != ""
        assert llm1.get("llm_access_mode") == "preset"

        # 3) Delete config
        delete1 = await client.delete("/api/user/profile/llm", headers=headers)
        assert delete1.status_code == 200
        assert delete1.json().get("ok") is True

        # 4) Profile should no longer return llm_config
        prof2 = await client.get("/api/user/profile", headers=headers)
        assert prof2.status_code == 200
        assert prof2.json().get("llm_config") is None

        # 5) Delete again should be idempotent (still ok)
        delete2 = await client.delete("/api/user/profile/llm", headers=headers)
        assert delete2.status_code == 200
        assert delete2.json().get("ok") is True
    finally:
        await _cleanup_user_data(user_id)


@pytest.mark.asyncio
async def test_save_user_llm_config_allows_partial_preset_updates(client: AsyncClient):
    auth = await _register_and_login(client)
    headers = auth["headers"]
    user_id = auth["user_id"]

    try:
        ok = await client.put(
            "/api/user/profile/llm",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "llm_access_mode": "preset",
                "provider": "deepseek",
                "model": "",
                "api_key": "",
                "base_url": "",
                "image_provider": "aliyun",
                "image_model": "",
                "image_api_key": "",
            },
        )
        assert ok.status_code == 200
        assert ok.json().get("ok") is True

        prof = await client.get("/api/user/profile", headers=headers)
        assert prof.status_code == 200
        cfg = prof.json().get("llm_config")
        assert isinstance(cfg, dict)
        assert cfg.get("llm_access_mode") == "preset"
        assert cfg.get("provider") == "deepseek"
        assert (cfg.get("model") or "") == ""
        assert (cfg.get("api_key") or "") == ""
        assert (cfg.get("image_model") or "") == ""
        assert (cfg.get("image_api_key") or "") == ""
    finally:
        await _cleanup_user_data(user_id)


@pytest.mark.asyncio
async def test_save_user_llm_config_custom_openai_allows_partial_updates(client: AsyncClient):
    auth = await _register_and_login(client)
    headers = auth["headers"]
    user_id = auth["user_id"]

    try:
        ok = await client.put(
            "/api/user/profile/llm",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "llm_access_mode": "custom_openai",
                "provider": "ignored",
                "model": "gpt-4o-mini",
                "api_key": "",
                "base_url": "",
                "image_provider": "aliyun",
                "image_model": "",
                "image_api_key": "",
            },
        )
        assert ok.status_code == 200

        prof = await client.get("/api/user/profile", headers=headers)
        assert prof.status_code == 200
        cfg = prof.json().get("llm_config")
        assert isinstance(cfg, dict)
        assert cfg.get("llm_access_mode") == "custom_openai"
        assert cfg.get("provider") == "openai_compat"
        assert (cfg.get("model") or "").strip() == "gpt-4o-mini"
        assert (cfg.get("api_key") or "") == ""
        assert (cfg.get("base_url") or "") == ""

        ok2 = await client.put(
            "/api/user/profile/llm",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "llm_access_mode": "custom_openai",
                "provider": "ignored",
                "model": "gpt-4o-mini",
                "api_key": "sk-user-test-key",
                "base_url": "https://api.openai.com/v1",
                "image_provider": "aliyun",
                "image_model": "qwen-image-max",
                "image_api_key": "sk-user-image-test-key",
            },
        )
        assert ok2.status_code == 200

        prof2 = await client.get("/api/user/profile", headers=headers)
        assert prof2.status_code == 200
        cfg = prof2.json().get("llm_config")
        assert isinstance(cfg, dict)
        assert cfg.get("llm_access_mode") == "custom_openai"
        assert (cfg.get("base_url") or "").strip() != ""
    finally:
        await _cleanup_user_data(user_id)
