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
            "language": "zh",
            "contentTone": "neutral",
            "city": "北京",
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
    async def test_save_config_with_api_key(self):
        """测试保存配置时设置 API key"""
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        from core.crypto import decrypt_api_key

        # 第一次保存：设置 API key
        data1 = {
            "modes": ["STOIC"],
            "refreshStrategy": "random",
            "llmApiKey": "sk-test-key-12345",
            "imageApiKey": "sk-test-image-key-67890",
        }
        await save_config(mac, data1)

        config1 = await get_active_config(mac)
        assert config1["has_api_key"] is True
        assert config1["has_image_api_key"] is True
        # 验证 API key 已加密保存
        encrypted_llm = config1.get("llm_api_key", "")
        encrypted_image = config1.get("image_api_key", "")
        assert encrypted_llm != ""
        assert encrypted_image != ""
        # 验证可以正确解密
        assert decrypt_api_key(encrypted_llm) == "sk-test-key-12345"
        assert decrypt_api_key(encrypted_image) == "sk-test-image-key-67890"

    @pytest.mark.asyncio
    async def test_save_config_clear_api_key(self):
        """测试清空 API key（发送空字符串）"""
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        from core.crypto import decrypt_api_key

        # 第一次保存：设置 API key
        await save_config(mac, {
            "modes": ["STOIC"],
            "llmApiKey": "sk-test-key-12345",
            "imageApiKey": "sk-test-image-key-67890",
        })

        config1 = await get_active_config(mac)
        assert config1["has_api_key"] is True
        assert config1["has_image_api_key"] is True

        # 第二次保存：清空 API key（发送空字符串）
        await save_config(mac, {
            "modes": ["STOIC"],
            "llmApiKey": "",  # 发送空字符串表示清空
            "imageApiKey": "",  # 发送空字符串表示清空
        })

        config2 = await get_active_config(mac)
        assert config2["has_api_key"] is False
        assert config2["has_image_api_key"] is False
        assert config2.get("llm_api_key", "") == ""
        assert config2.get("image_api_key", "") == ""

    @pytest.mark.asyncio
    async def test_save_config_preserve_api_key_when_not_sent(self):
        """测试不发送 API key 字段时保留旧值"""
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        from core.crypto import decrypt_api_key

        # 第一次保存：设置 API key
        await save_config(mac, {
            "modes": ["STOIC"],
            "llmApiKey": "sk-test-key-12345",
            "imageApiKey": "sk-test-image-key-67890",
        })

        config1 = await get_active_config(mac)
        original_llm_key = config1.get("llm_api_key", "")
        original_image_key = config1.get("image_api_key", "")
        assert original_llm_key != ""
        assert original_image_key != ""

        # 第二次保存：不发送 API key 字段（模拟用户未修改）
        await save_config(mac, {
            "modes": ["ZEN"],  # 只修改其他字段
            # 不包含 llmApiKey 和 imageApiKey
        })

        config2 = await get_active_config(mac)
        # 验证 API key 被保留
        assert config2.get("llm_api_key", "") == original_llm_key
        assert config2.get("image_api_key", "") == original_image_key
        assert config2["has_api_key"] is True
        assert config2["has_image_api_key"] is True
        # 验证其他字段已更新
        assert "ZEN" in config2["modes"]

    @pytest.mark.asyncio
    async def test_save_config_update_api_key(self):
        """测试更新 API key（发送新值）"""
        await init_db()
        mac = "AA:BB:CC:DD:EE:FF"
        from core.crypto import decrypt_api_key

        # 第一次保存：设置 API key
        await save_config(mac, {
            "modes": ["STOIC"],
            "llmApiKey": "sk-old-key-12345",
        })

        # 第二次保存：更新 API key
        await save_config(mac, {
            "modes": ["STOIC"],
            "llmApiKey": "sk-new-key-67890",
        })

        config = await get_active_config(mac)
        encrypted_key = config.get("llm_api_key", "")
        assert decrypt_api_key(encrypted_key) == "sk-new-key-67890"
        assert decrypt_api_key(encrypted_key) != "sk-old-key-12345"

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
