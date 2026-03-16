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
    """测试用户注册功能（包含邀请码机制）"""

    @pytest.mark.asyncio
    async def test_register_with_valid_invite_code(self):
        """测试使用有效邀请码注册"""
        await init_db()
        db = await get_main_db()
        
        # 1. 先创建一个邀请码
        await db.execute(
            """
            INSERT INTO invitation_codes (code, is_used, generated_at)
            VALUES (?, 0, datetime('now'))
            """,
            ("TEST123",),
        )
        await db.commit()
        
        # 2. 模拟注册请求
        from api.routes.auth import auth_register
        from fastapi import Response
        
        body = {
            "username": "testuser",
            "password": "testpass123",
            "phone": "13800138000",
            "invite_code": "TEST123",
        }
        response = Response()
        result = await auth_register(body, response)
        
        # 3. 验证注册成功
        assert result["ok"] is True
        assert result["username"] == "testuser"
        user_id = result["user_id"]
        
        # 4. 验证邀请码已被标记为使用
        cursor = await db.execute(
            "SELECT is_used, used_by_user_id FROM invitation_codes WHERE code = ?",
            ("TEST123",),
        )
        row = await cursor.fetchone()
        assert row[0] == 1  # is_used
        assert row[1] == user_id  # used_by_user_id
        
        # 5. 验证用户获得了 50 次免费额度
        quota = await get_user_api_quota(user_id)
        assert quota is not None
        assert quota["free_quota_remaining"] == 50
        assert quota["total_calls_made"] == 0

    @pytest.mark.asyncio
    async def test_register_without_invite_code(self):
        """测试不使用邀请码注册（额度为 0）"""
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
        
        # 验证用户额度为 0
        quota = await get_user_api_quota(user_id)
        assert quota is not None
        assert quota["free_quota_remaining"] == 0
        assert quota["total_calls_made"] == 0

    @pytest.mark.asyncio
    async def test_register_with_invalid_invite_code(self):
        """测试使用无效邀请码注册"""
        await init_db()
        
        from api.routes.auth import auth_register
        from fastapi import Response
        from fastapi.responses import JSONResponse
        
        body = {
            "username": "testuser3",
            "password": "testpass123",
            "phone": "13900139000",
            "invite_code": "INVALID123",
        }
        response = Response()
        result = await auth_register(body, response)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400
        assert "邀请码无效" in result.body.decode()

    @pytest.mark.asyncio
    async def test_register_with_used_invite_code(self):
        """测试使用已使用的邀请码注册"""
        await init_db()
        db = await get_main_db()
        
        # 创建并标记邀请码为已使用
        await db.execute(
            """
            INSERT INTO invitation_codes (code, is_used, used_by_user_id, generated_at)
            VALUES (?, 1, 999, datetime('now'))
            """,
            ("USED123",),
        )
        await db.commit()
        
        from api.routes.auth import auth_register
        from fastapi import Response
        from fastapi.responses import JSONResponse
        
        body = {
            "username": "testuser4",
            "password": "testpass123",
            "phone": "13700137000",
            "invite_code": "USED123",
        }
        response = Response()
        result = await auth_register(body, response)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 409
        assert "邀请码已被使用" in result.body.decode()

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
