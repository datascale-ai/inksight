"""
测试新增的 chip_family 字段和 OTA URL 存储功能（对应 device_ota.py 实际逻辑）。
"""
import pytest
from unittest.mock import patch

from core.config_store import (
    init_db,
    update_device_state,
    get_device_state,
)
from core.db import get_main_db, close_all


@pytest.fixture
async def use_memory_db(tmp_path):
    """Redirect all DB operations to an isolated temp file per test."""
    from core import db as db_mod

    db_path = str(tmp_path / "test.db")
    await db_mod.close_all()
    with patch.object(db_mod, "_MAIN_DB_PATH", db_path), \
         patch("core.config_store.DB_PATH", db_path), \
         patch("core.stats_store.DB_PATH", db_path):
        await init_db()
        yield db_path
    await db_mod.close_all()


@pytest.mark.asyncio
async def test_chip_family_column_exists(use_memory_db):
    """验证 device_state 表包含 chip_family 列"""
    db = await get_main_db()
    cursor = await db.execute("PRAGMA table_info(device_state)")
    columns = {row[1] for row in await cursor.fetchall()}

    assert "chip_family" in columns, "device_state 表应该包含 chip_family 列"
    assert "pending_ota" in columns
    assert "ota_version" in columns
    assert "ota_url" in columns
    assert "ota_progress" in columns
    assert "ota_result" in columns
    assert "ota_original_url" in columns


@pytest.mark.asyncio
async def test_update_device_state_allows_chip_family(use_memory_db):
    """验证 update_device_state 允许更新 chip_family 字段"""
    mac = "AA:BB:CC:DD:EE:FF"

    await update_device_state(mac, chip_family="ESP32-C3")
    state = await get_device_state(mac)
    assert state is not None
    assert state.get("chip_family") == "ESP32-C3"

    await update_device_state(
        mac,
        pending_ota=1,
        ota_version="1.2.3",
        ota_url="http://example.com/proxy.bin",
        ota_original_url="https://github.com/example/fw.bin",
        ota_progress=50,
        ota_result="downloading",
        chip_family="ESP32-S3",
    )

    state = await get_device_state(mac)
    assert state["pending_ota"] == 1
    assert state["ota_version"] == "1.2.3"
    assert state["ota_url"] == "http://example.com/proxy.bin"
    assert state["ota_original_url"] == "https://github.com/example/fw.bin"
    assert state["ota_progress"] == 50
    assert state["ota_result"] == "downloading"
    assert state["chip_family"] == "ESP32-S3"


@pytest.mark.asyncio
async def test_trigger_ota_stores_both_urls(use_memory_db):
    """
    模拟 device_ota.py trigger_ota 的存储逻辑：
    - ota_url 存后端代理 URL
    - ota_original_url 存 GitHub CDN 原始 URL
    """
    mac = "11:22:33:44:55:66"
    github_url = "https://github.com/datascale-ai/inksight/releases/download/v1.2.3/inksight-ESP32-C3-v1.2.3.bin"
    proxy_url = f"http://backend.example.com/api/firmware/download/v1.2.3?mac={mac}"

    await update_device_state(
        mac,
        pending_ota=1,
        ota_version="1.2.3",
        ota_url=proxy_url,
        ota_original_url=github_url,
        ota_progress=0,
        ota_result="",
    )

    state = await get_device_state(mac)
    assert state is not None
    # ota_url = 代理 URL（设备实际请求的地址）
    assert state["ota_url"] == proxy_url
    # ota_original_url = GitHub CDN 原始地址（后端下载固件的真实来源）
    assert state["ota_original_url"] == github_url
    assert state["pending_ota"] == 1
    assert state["ota_version"] == "1.2.3"


@pytest.mark.asyncio
async def test_firmware_download_uses_original_url_with_fallback(use_memory_db):
    """
    模拟 firmware_download 的 URL 解析逻辑：
    - 优先使用 ota_original_url
    - 旧记录没有 ota_original_url 时 fallback 到 ota_url
    """
    mac = "AA:BB:CC:DD:EE:FF"
    github_url = "https://github.com/datascale-ai/inksight/releases/download/v1.2.3/firmware-ESP32-C3.bin"
    proxy_url = f"http://backend.example.com/api/firmware/download/v1.2.3?mac={mac}"

    # Case 1: 新记录，有 ota_original_url
    await update_device_state(
        mac,
        pending_ota=1,
        ota_version="1.2.3",
        ota_url=proxy_url,
        ota_original_url=github_url,
        ota_progress=0,
        ota_result="",
    )

    state = await get_device_state(mac)
    # 模拟 firmware_download 的逻辑
    ota_original_url = state.get("ota_original_url", "") if state else ""
    download_url = ota_original_url or state.get("ota_url", "") if state else ""

    assert download_url == github_url, "应优先使用 ota_original_url"

    # Case 2: 旧记录，ota_original_url 为空（向后兼容）
    await update_device_state(
        mac,
        pending_ota=1,
        ota_version="1.1.0",
        ota_url=proxy_url,
        ota_original_url="",  # 模拟旧记录没有 ota_original_url
        ota_progress=0,
        ota_result="",
    )

    state = await get_device_state(mac)
    ota_original_url = state.get("ota_original_url", "") if state else ""
    download_url = ota_original_url or state.get("ota_url", "") if state else ""

    assert download_url == proxy_url, "无 ota_original_url 时 fallback 到 ota_url"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
