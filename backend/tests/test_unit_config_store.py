"""
Unit tests for config_store (SQLite operations).
Uses an in-memory DB by patching DB_PATH.
"""
import pytest
from unittest.mock import patch

from core.config_store import init_db, save_config, get_active_config, get_config_history, activate_config


@pytest.fixture(autouse=True)
def use_memory_db(tmp_path):
    """Redirect all DB operations to a temp file."""
    db_path = str(tmp_path / "test.db")
    with patch("core.config_store.DB_PATH", db_path):
        yield db_path


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
