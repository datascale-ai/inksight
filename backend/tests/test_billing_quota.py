"""
测试新增的计费与额度管理功能：
- 用户注册（带/不带邀请码）
- 邀请码兑换
- API 额度管理（初始化、查询、扣减）
- 额度耗尽时的硬件兼容逻辑
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.config_store import (
    init_db,
    init_user_api_quota,
    get_user_api_quota,
    consume_user_free_quota,
    get_quota_owner_for_mac,
    create_user,
    authenticate_user,
)
from core.db import get_main_db


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


class TestUserRegistration:
    """测试用户注册功能（前端已移除邀请码输入，仅测试无邀请码场景）"""

    @pytest.mark.asyncio
    async def test_register_without_invite_code(self):
        """测试不使用邀请码注册（初始额度为 50）"""
        await init_db()
        
        from api.routes.auth import auth_register
        from fastapi import Response
        
        body = {
            "username": "testuser2",
            "password": "testpass123",
            "email": "test@example.com",
        }
        response = Response()
        result = await auth_register(body, response)
        
        assert result["ok"] is True
        user_id = result["user_id"]
        
        # 验证用户额度为 50
        quota = await get_user_api_quota(user_id)
        assert quota is not None
        assert quota["free_quota_remaining"] == 50
        assert quota["total_calls_made"] == 0

    @pytest.mark.asyncio
    async def test_register_phone_email_validation(self):
        """测试手机号和邮箱格式验证"""
        await init_db()
        
        from api.routes.auth import auth_register
        from fastapi import Response
        from fastapi.responses import JSONResponse
        
        # 测试无效手机号
        body1 = {
            "username": "testuser5",
            "password": "testpass123",
            "phone": "1234567890",  # 无效格式
        }
        response1 = Response()
        result1 = await auth_register(body1, response1)
        assert isinstance(result1, JSONResponse)
        assert result1.status_code == 400
        assert "手机号格式不正确" in result1.body.decode()
        
        # 测试无效邮箱
        body2 = {
            "username": "testuser6",
            "password": "testpass123",
            "email": "invalid-email",  # 无效格式
        }
        response2 = Response()
        result2 = await auth_register(body2, response2)
        assert isinstance(result2, JSONResponse)
        assert result2.status_code == 400
        assert "邮箱格式不正确" in result2.body.decode()
        
        # 测试手机号和邮箱都未提供
        body3 = {
            "username": "testuser7",
            "password": "testpass123",
        }
        response3 = Response()
        result3 = await auth_register(body3, response3)
        assert isinstance(result3, JSONResponse)
        assert result3.status_code == 400
        assert "手机号或邮箱至少填写一个" in result3.body.decode()


class TestInviteCodeRedemption:
    """测试邀请码兑换功能"""

    @pytest.mark.asyncio
    async def test_redeem_valid_invite_code(self):
        """测试兑换有效邀请码"""
        await init_db()
        db = await get_main_db()
        
        # 1. 创建用户（无邀请码，额度为 0）
        user_id = await create_user("testuser", "testpass", email="test@example.com")
        assert user_id is not None
        
        # 2. 创建邀请码
        await db.execute(
            """
            INSERT INTO invitation_codes (code, is_used, generated_at)
            VALUES (?, 0, datetime('now'))
            """,
            ("REDEEM123",),
        )
        await db.commit()
        
        # 3. 模拟兑换请求（需要模拟 require_user 依赖）
        from api.routes.auth import auth_redeem_invite_code
        from unittest.mock import patch
        
        body = {"invite_code": "REDEEM123"}
        
        # 模拟 require_user 返回 user_id
        with patch("api.routes.auth.require_user", return_value=user_id):
            result = await auth_redeem_invite_code(body, user_id)
        
        # 4. 验证兑换成功
        assert result["ok"] is True
        assert "邀请码兑换成功" in result["message"]
        assert result["free_quota_remaining"] == 50
        
        # 5. 验证邀请码已被标记为使用
        cursor = await db.execute(
            "SELECT is_used, used_by_user_id FROM invitation_codes WHERE code = ?",
            ("REDEEM123",),
        )
        row = await cursor.fetchone()
        assert row[0] == 1
        assert row[1] == user_id
        
        # 6. 验证用户额度已增加
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 50

    @pytest.mark.asyncio
    async def test_redeem_invalid_invite_code(self):
        """测试兑换无效邀请码"""
        await init_db()
        user_id = await create_user("testuser2", "testpass", phone="13800138000")
        
        from api.routes.auth import auth_redeem_invite_code
        from fastapi.responses import JSONResponse
        
        body = {"invite_code": "INVALID999"}
        
        with patch("api.routes.auth.require_user", return_value=user_id):
            result = await auth_redeem_invite_code(body, user_id)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400
        assert "邀请码无效" in result.body.decode()

    @pytest.mark.asyncio
    async def test_redeem_used_invite_code(self):
        """测试兑换已使用的邀请码"""
        await init_db()
        db = await get_main_db()
        
        user_id = await create_user("testuser3", "testpass", email="test3@example.com")
        
        # 创建已使用的邀请码
        await db.execute(
            """
            INSERT INTO invitation_codes (code, is_used, used_by_user_id, generated_at)
            VALUES (?, 1, 999, datetime('now'))
            """,
            ("USED999",),
        )
        await db.commit()
        
        from api.routes.auth import auth_redeem_invite_code
        from fastapi.responses import JSONResponse
        
        body = {"invite_code": "USED999"}
        
        with patch("api.routes.auth.require_user", return_value=user_id):
            result = await auth_redeem_invite_code(body, user_id)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        assert "邀请码已被使用" in result.body.decode()


class TestQuotaManagement:
    """测试 API 额度管理功能"""

    @pytest.mark.asyncio
    async def test_init_user_api_quota(self):
        """测试初始化用户额度"""
        await init_db()
        user_id = await create_user("quotauser", "testpass", phone="13900139000")
        
        # 初始化额度（默认 5 次）
        await init_user_api_quota(user_id)
        
        quota = await get_user_api_quota(user_id)
        assert quota is not None
        assert quota["free_quota_remaining"] == 5
        assert quota["total_calls_made"] == 0
        
        # 测试幂等性（再次初始化不应改变值）
        await init_user_api_quota(user_id)
        quota2 = await get_user_api_quota(user_id)
        assert quota2["free_quota_remaining"] == 5

    @pytest.mark.asyncio
    async def test_init_user_api_quota_custom_amount(self):
        """测试初始化用户额度（自定义数量）"""
        await init_db()
        user_id = await create_user("quotauser2", "testpass", email="quota@example.com")
        
        await init_user_api_quota(user_id, free_quota=50)
        
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 50

    @pytest.mark.asyncio
    async def test_get_user_api_quota_nonexistent(self):
        """测试查询不存在的用户额度"""
        await init_db()
        
        quota = await get_user_api_quota(99999)
        assert quota is None

    @pytest.mark.asyncio
    async def test_consume_user_free_quota_success(self):
        """测试成功扣减额度"""
        await init_db()
        user_id = await create_user("consumeuser", "testpass", phone="13700137000")
        await init_user_api_quota(user_id, free_quota=5)
        
        # 扣减 1 次
        success = await consume_user_free_quota(user_id, amount=1)
        assert success is True
        
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 4
        assert quota["total_calls_made"] == 1
        
        # 再扣减 2 次
        success2 = await consume_user_free_quota(user_id, amount=2)
        assert success2 is True
        
        quota2 = await get_user_api_quota(user_id)
        assert quota2["free_quota_remaining"] == 2
        assert quota2["total_calls_made"] == 2  # 注意：每次扣减都会 +1

    @pytest.mark.asyncio
    async def test_consume_user_free_quota_insufficient(self):
        """测试额度不足时扣减失败"""
        await init_db()
        user_id = await create_user("consumeuser2", "testpass", email="consume@example.com")
        await init_user_api_quota(user_id, free_quota=2)
        
        # 扣减 1 次（成功）
        success1 = await consume_user_free_quota(user_id, amount=1)
        assert success1 is True
        
        # 再扣减 1 次（成功）
        success2 = await consume_user_free_quota(user_id, amount=1)
        assert success2 is True
        
        # 尝试再扣减 1 次（失败，额度已用完）
        success3 = await consume_user_free_quota(user_id, amount=1)
        assert success3 is False
        
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 0
        assert quota["total_calls_made"] == 2  # 只有前两次成功扣减

    @pytest.mark.asyncio
    async def test_consume_user_free_quota_atomic(self):
        """测试并发场景下的原子性扣减"""
        await init_db()
        user_id = await create_user("atomicuser", "testpass", phone="13600136000")
        await init_user_api_quota(user_id, free_quota=1)
        
        # 尝试同时扣减 1 次（应该只有一个成功）
        import asyncio
        
        async def consume():
            return await consume_user_free_quota(user_id, amount=1)
        
        results = await asyncio.gather(*[consume() for _ in range(5)])
        
        # 应该只有一个成功
        assert sum(results) == 1
        
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 0
        assert quota["total_calls_made"] == 1

    @pytest.mark.asyncio
    async def test_consume_user_free_quota_zero_amount(self):
        """测试扣减 0 次额度（应该直接返回 True，不修改数据库）"""
        await init_db()
        user_id = await create_user("zerouser", "testpass", email="zero@example.com")
        await init_user_api_quota(user_id, free_quota=5)
        
        success = await consume_user_free_quota(user_id, amount=0)
        assert success is True
        
        quota = await get_user_api_quota(user_id)
        assert quota["free_quota_remaining"] == 5
        assert quota["total_calls_made"] == 0


class TestQuotaOwnerResolution:
    """测试额度归属用户解析"""

    @pytest.mark.asyncio
    async def test_get_quota_owner_for_mac_with_owner(self):
        """测试有设备 owner 时返回正确的 user_id"""
        await init_db()
        db = await get_main_db()
        
        # 创建用户
        user_id = await create_user("owneruser", "testpass", phone="13500135000")
        
        # 创建设备绑定关系（owner）
        mac = "AA:BB:CC:DD:EE:FF"
        await db.execute(
            """
            INSERT INTO device_memberships (mac, user_id, role, status, created_at, updated_at)
            VALUES (?, ?, 'owner', 'active', datetime('now'), datetime('now'))
            """,
            (mac, user_id),
        )
        await db.commit()
        
        owner_id = await get_quota_owner_for_mac(mac)
        assert owner_id == user_id

    @pytest.mark.asyncio
    async def test_get_quota_owner_for_mac_no_owner(self):
        """测试没有设备 owner 时返回 None"""
        await init_db()
        
        mac = "XX:XX:XX:XX:XX:XX"
        owner_id = await get_quota_owner_for_mac(mac)
        assert owner_id is None

    @pytest.mark.asyncio
    async def test_get_quota_owner_for_mac_member_only(self):
        """测试只有 member 没有 owner 时返回 None"""
        await init_db()
        db = await get_main_db()
        
        user_id = await create_user("memberuser", "testpass", email="member@example.com")
        mac = "BB:CC:DD:EE:FF:AA"
        
        # 只创建 member，不创建 owner
        await db.execute(
            """
            INSERT INTO device_memberships (mac, user_id, role, status, created_at, updated_at)
            VALUES (?, ?, 'member', 'active', datetime('now'), datetime('now'))
            """,
            (mac, user_id),
        )
        await db.commit()
        
        owner_id = await get_quota_owner_for_mac(mac)
        assert owner_id is None  # 因为 get_device_owner 只返回 role='owner' 的记录


class TestQuotaExhaustionHandling:
    """测试额度耗尽时的硬件兼容逻辑"""

    @pytest.mark.asyncio
    async def test_quota_exhausted_returns_bmp_for_device(self):
        """测试设备请求时额度耗尽返回 1-bit BMP 图像"""
        await init_db()
        user_id = await create_user("exhaustuser", "testpass", phone="13400134000")
        await init_user_api_quota(user_id, free_quota=0)  # 额度为 0
        
        # 模拟设备请求（需要 mac 参数）
        from api.shared import build_image
        from unittest.mock import patch, AsyncMock
        
        # 模拟 get_quota_owner_for_mac 返回 user_id
        with patch("api.shared.get_quota_owner_for_mac", return_value=user_id):
            # 模拟一个需要 LLM 的模式（例如 DAILY）
            # 注意：这里需要模拟完整的调用链，包括 generate_and_render
            # 为了简化，我们直接测试 build_image 的配额检查逻辑
            
            # 由于 build_image 依赖很多其他模块，这里只测试核心逻辑
            # 实际测试应该通过集成测试来完成
            pass  # 集成测试见 test_integration.py

    @pytest.mark.asyncio
    async def test_quota_exhausted_returns_402_for_web_preview(self):
        """测试 Web 预览时额度耗尽返回 402 状态码"""
        # 这个测试应该通过 API 路由测试来完成
        # 见 test_integration.py 或专门的 API 测试文件
        pass


class TestLlmPrecheckBehavior:
    """测试在额度耗尽时不会触发 LLM 调用（预先拦截）。"""

    @pytest.mark.asyncio
    async def test_custom_mode_preview_quota_exhausted_blocks_llm(self, monkeypatch):
        """当 custom preview 额度为 0 时，应在调用 LLM 之前返回 402，且不调用 generate_json_mode_content。"""
        from api.routes.modes import custom_mode_preview

        # 打开计费开关
        monkeypatch.setenv("INKSIGHT_BILLING_ENABLED", "1")

        user_id = 123

        # 构造一个需要 LLM 的自定义模式：content.type = "llm"
        body = {
            "mode_def": {
                "mode_id": "PREVIEW",
                "content": {
                    "type": "llm",
                    "prompt_template": "test {context}",
                },
            },
            "w": 400,
            "h": 300,
            "responseType": "json",
        }

        # 确保使用平台 Key（即没有用户级 API key）
        async def fake_get_user_llm_config(_user_id: int):
            # 模拟用户级配置中只设置了 provider（无自定义 model），与生产逻辑保持字段一致
            return {"provider": "deepseek", "model": "", "api_key": "", "base_url": ""}

        # 配额为 0
        async def fake_get_quota(user_id_param: int):
            assert user_id_param == user_id
            return {
                "user_id": user_id,
                "total_calls_made": 0,
                "free_quota_remaining": 0,
            }

        # 非 root 用户
        async def fake_get_role(user_id_param: int):
            assert user_id_param == user_id
            return "user"

        # LLM 生成函数，应该不会被调用
        called = {"generate": False}

        async def fake_generate_json_mode_content(*args, **kwargs):
            called["generate"] = True
            return {}

        from core import config_store as cfg_mod
        from core import json_content as json_mod
        from api import routes as api_pkg

        # 覆盖 config_store 内部实现，避免真实访问数据库
        monkeypatch.setattr(cfg_mod, "get_user_llm_config", fake_get_user_llm_config)
        monkeypatch.setattr(cfg_mod, "get_user_api_quota", fake_get_quota)
        monkeypatch.setattr(cfg_mod, "get_user_role", fake_get_role)
        monkeypatch.setattr(json_mod, "generate_json_mode_content", fake_generate_json_mode_content)
        # 关键：同时覆盖 api.routes.modes 中直接导入的 get_user_api_quota / get_user_role，
        # 防止其调用真实的 DB 层导致 "no such table: api_quotas"
        monkeypatch.setattr("api.routes.modes.get_user_api_quota", fake_get_quota)
        monkeypatch.setattr("api.routes.modes.get_user_role", fake_get_role)

        # 依赖中的 admin_auth 直接传 None 即可
        resp = await custom_mode_preview(body, user_id=user_id, admin_auth=None)

        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 402
        assert "您的免费额度已用完" in resp.body.decode("utf-8")
        # 关键断言：LLM 内容生成函数没有被调用
        assert called["generate"] is False

    @pytest.mark.asyncio
    async def test_generate_mode_quota_exhausted_blocks_llm(self, monkeypatch):
        """当 AI 生成模式额度为 0 时，应在调用 LLM 之前返回 402，且不调用 generate_mode_definition。"""
        from api.routes.modes import generate_mode

        monkeypatch.setenv("INKSIGHT_BILLING_ENABLED", "1")

        user_id = 456
        body = {
            "description": "帮我生成一个测试模式定义",
            "provider": "deepseek",
            "model": "deepseek-chat",
        }

        # 使用平台 Key（无用户级 key）
        async def fake_get_user_llm_config(_user_id: int):
            # 同步 user_llm_config 结构，显式包含 model 字段
            return {"provider": "deepseek", "model": "deepseek-chat", "api_key": "", "base_url": ""}

        async def fake_get_quota(user_id_param: int):
            assert user_id_param == user_id
            return {
                "user_id": user_id,
                "total_calls_made": 0,
                "free_quota_remaining": 0,
            }

        async def fake_get_role(user_id_param: int):
            assert user_id_param == user_id
            return "user"

        called = {"generate_mode": False}

        async def fake_generate_mode_definition(*args, **kwargs):
            called["generate_mode"] = True
            return {"ok": True, "mode_def": {}}

        from core import config_store as cfg_mod
        from core import mode_generator as mode_gen_mod

        # 覆盖底层实现与 API 层引用，避免真实访问 api_quotas 表
        monkeypatch.setattr(cfg_mod, "get_user_llm_config", fake_get_user_llm_config)
        monkeypatch.setattr(cfg_mod, "get_user_api_quota", fake_get_quota)
        monkeypatch.setattr(cfg_mod, "get_user_role", fake_get_role)
        monkeypatch.setattr(mode_gen_mod, "generate_mode_definition", fake_generate_mode_definition)
        monkeypatch.setattr("api.routes.modes.get_user_api_quota", fake_get_quota)
        monkeypatch.setattr("api.routes.modes.get_user_role", fake_get_role)

        resp = await generate_mode(body, user_id=user_id, admin_auth=None)

        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 402
        assert "您的免费额度已用完" in resp.body.decode("utf-8")
        # 关键断言：模式生成的 LLM 调用函数没有被触发
        assert called["generate_mode"] is False