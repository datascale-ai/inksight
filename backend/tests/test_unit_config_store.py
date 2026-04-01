"""
Unit tests for config_store (SQLite operations).
Uses an in-memory DB by patching DB_PATH.
"""
import pytest
from unittest.mock import patch

from core.config_store import (
    init_db,
    save_config,
    get_active_config,
    get_config_history,
    activate_config,
    create_claim_token,
    get_or_create_claim_token,
    remove_mode_from_all_configs,
)


@pytest.fixture(autouse=True)
async def use_memory_db(tmp_path):
    """Redirect all DB operations to an isolated temp file per test."""
    from core import db as db_mod

    db_path = str(tmp_path / "test.db")
    await db_mod.close_all()
    with patch.object(db_mod, "_MAIN_DB_PATH", db_path), \
         patch("core.config_store.DB_PATH", db_path), \
         patch("core.stats_store.DB_PATH", db_path):
        # Ensure base schema exists and add any missing columns used by current code
        await init_db()
        from core.db import get_main_db
        db = await get_main_db()
        cur = await db.execute("PRAGMA table_info(configs)")
        cols = {row[1] for row in await cur.fetchall()}
        async def _add(col: str, ddl: str):
            if col not in cols:
                await db.execute(f"ALTER TABLE configs ADD COLUMN {col} {ddl}")
        await _add("focus_listening", "INTEGER DEFAULT 0")
        await _add("always_active", "INTEGER DEFAULT 0")
        await _add("latitude", "REAL")
        await _add("longitude", "REAL")
        await _add("timezone", "TEXT DEFAULT ''")
        await _add("admin1", "TEXT DEFAULT ''")
        await _add("country", "TEXT DEFAULT ''")
        await _add("is_active", "INTEGER DEFAULT 1")
        await db.commit()
        yield db_path
    await db_mod.close_all()


class TestConfigStore:
    @pytest.mark.asyncio
    async def test_init_db(self):
        await init_db()

    @pytest.mark.asyncio
    async def test_save_and_get_config(self):
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        data = {
            "mac": mac,
            "nickname": "Test",
            "modes": ["STOIC", "ZEN"],
            "refreshStrategy": "cycle",
            "refreshInterval": 30,
            "always_active": True,
            "language": "zh",
            "contentTone": "neutral",
            "city": "北京",
            "latitude": 39.9042,
            "longitude": 116.4074,
            "timezone": "Asia/Shanghai",
            "admin1": "北京市",
            "country": "中国",
            "llmProvider": "deepseek",
            "llmModel": "deepseek-chat",
        }
        config_id = await save_config(mac, data)
        assert config_id > 0

        config = await get_active_config(mac)
        assert config is not None
        assert config["nickname"] == "Test"
        assert "STOIC" in config["modes"]
        assert config["refresh_strategy"] == "cycle"
        assert config["always_active"] == 1
        assert config["is_always_active"] is True
        assert config["latitude"] == pytest.approx(39.9042)
        assert config["country"] == "中国"
        assert isinstance(config["countdown_events"], list)
        assert isinstance(config["countdownEvents"], list)

    @pytest.mark.asyncio
    async def test_save_deactivates_old(self):
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        data1 = {"modes": ["STOIC"], "refreshStrategy": "random"}
        data2 = {"modes": ["ZEN"], "refreshStrategy": "cycle"}

        id1 = await save_config(mac, data1)
        id2 = await save_config(mac, data2)

        config = await get_active_config(mac)
        assert config["id"] == id2
        assert "ZEN" in config["modes"]

    @pytest.mark.asyncio
    async def test_get_active_config_missing(self):
        await init_db()
        result = await get_active_config("XX:XX:XX:XX:XX:XX")
        assert result is None

    @pytest.mark.asyncio
    async def test_config_history(self):
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        await save_config(mac, {"modes": ["STOIC"], "refreshStrategy": "random"})
        await save_config(mac, {"modes": ["ZEN"], "refreshStrategy": "cycle"})

        history = await get_config_history(mac)
        assert len(history) >= 2

    @pytest.mark.asyncio
    async def test_activate_config(self):
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        id1 = await save_config(mac, {"modes": ["STOIC"], "refreshStrategy": "random"})
        id2 = await save_config(mac, {"modes": ["ZEN"], "refreshStrategy": "cycle"})

        # Activate the old one
        ok = await activate_config(mac, id1)
        assert ok is True

        config = await get_active_config(mac)
        assert config["id"] == id1

    @pytest.mark.asyncio
    async def test_activate_nonexistent(self):
        await init_db()
        ok = await activate_config("AA:BB:CC:DD:EE:FF", 9999)
        assert ok is False

    @pytest.mark.asyncio
    async def test_get_config_parses_legacy_json_string_fields(self):
        await init_db()
        mac = "11:22:33:44:55:66"
        await save_config(
            mac,
            {
                "modes": ["COUNTDOWN"],
                "refreshStrategy": "random",
                "countdownEvents": [{"name": "测试日", "date": "2030-01-01", "type": "countdown"}],
                "timeSlotRules": [{"startHour": 9, "endHour": 12, "modes": ["DAILY"]}],
            },
        )

        config = await get_active_config(mac)
        assert isinstance(config["countdown_events"], list)
        assert isinstance(config["countdownEvents"], list)
        assert config["countdown_events"][0]["name"] == "测试日"
        assert isinstance(config["time_slot_rules"], list)
        assert config["time_slot_rules"][0]["modes"] == ["DAILY"]

    @pytest.mark.asyncio
    async def test_get_or_create_claim_token_reuses_active_pair_code(self):
        await init_db()
        mac = "33:44:55:66:77:88"

        created = await create_claim_token(mac, source="portal")
        reused = await get_or_create_claim_token(mac, source="render")

        assert created is not None
        assert reused is not None
        assert reused["pair_code"] == created["pair_code"]
        assert reused["expires_at"] == created["expires_at"]

    # 设备配置层面的 API key 行为已完全迁移到用户级配置（user_llm_config），
    # 不再在 config_store 里做单元测试，相关旧用例已移除。

    async def test_remove_mode_from_all_configs_cleans_modes_and_overrides(self):
        await init_db()
        mac = "22:33:44:55:66:77"
        await save_config(
            mac,
            {
                "modes": ["STOIC", "CUSTOM_DELETED"],
                "refreshStrategy": "random",
                "modeOverrides": {
                    "CUSTOM_DELETED": {"city": "上海"},
                    "STOIC": {"city": "杭州"},
                },
            },
        )

        updated = await remove_mode_from_all_configs("custom_deleted")
        assert updated >= 1

        config = await get_active_config(mac)
        assert config is not None
        assert "CUSTOM_DELETED" not in config["modes"]
        assert "STOIC" in config["modes"]
        assert "CUSTOM_DELETED" not in config["mode_overrides"]
        assert config["mode_overrides"]["STOIC"]["city"] == "杭州"
