"""
Discover (模式分享广场) 功能的集成测试
"""
import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

from api.index import app
from core.config_store import get_main_db, init_db, upsert_device_membership
from core.mode_registry import get_registry, CUSTOM_JSON_DIR
from core.stats_store import init_stats_db
from core.cache import init_cache_db

TEST_MAC = "AA:BB:CC:DD:EE:01"


@pytest.fixture
async def client(tmp_path):
    """Create an async client with isolated temp databases for each test."""
    from core import db as db_mod
    await db_mod.close_all()

    async def _normalize_configs_table():
        db = await get_main_db()
        cur = await db.execute("PRAGMA table_info(configs)")
        cols = {row[1] for row in await cur.fetchall()}
        async def _add(col: str, ddl: str):
            if col not in cols:
                await db.execute(f"ALTER TABLE configs ADD COLUMN {col} {ddl}")
        await _add("focus_listening", "INTEGER DEFAULT 0")
        await _add("latitude", "REAL")
        await _add("longitude", "REAL")
        await _add("timezone", "TEXT DEFAULT ''")
        await _add("admin1", "TEXT DEFAULT ''")
        await _add("country", "TEXT DEFAULT ''")
        await _add("is_active", "INTEGER DEFAULT 1")
        await db.commit()

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
        await _normalize_configs_table()

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


@pytest.fixture
def sample_date_ctx():
    """A typical date context dict."""
    return {
        "date_str": "2月16日 周一",
        "time_str": "09:30:00",
        "weekday": 0,
        "hour": 9,
        "is_weekend": False,
        "year": 2026,
        "day": 16,
        "month_cn": "二月",
        "weekday_cn": "周一",
        "day_of_year": 47,
        "days_in_year": 365,
        "festival": "",
        "is_holiday": False,
        "is_workday": True,
        "upcoming_holiday": "清明节",
        "days_until_holiday": 48,
        "holiday_date": "04月05日",
        "daily_word": "春风化雨",
    }


@pytest.fixture
def sample_weather():
    """A typical weather dict."""
    return {
        "temp": 12,
        "weather_code": 1,
        "weather_str": "12°C",
    }


@pytest.fixture
async def test_user(client: AsyncClient):
    """创建测试用户并返回认证信息"""
    username = "test_discover_user"
    password = "testpass123"
    
    # 注册用户（不再需要邀请码）
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.com",
        },
    )
    assert resp.status_code == 200
    
    # 登录获取 token
    resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    
    # 获取用户 ID
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    user_data = resp.json()

    # 为该用户绑定一台测试设备，保证 Discover 相关接口中的 mac 校验通过
    membership = await upsert_device_membership(
        TEST_MAC,
        user_data["user_id"],
        role="owner",
        status="active",
        nickname="DiscoverTestDevice",
    )
    assert membership["status"] == "active"

    return {
        "username": username,
        "token": token,
        "user_id": user_data["user_id"],
        "mac": TEST_MAC,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
async def test_custom_mode(tmp_path, client: AsyncClient, test_user):
    """创建一个测试用的自定义模式"""
    from pathlib import Path
    
    # 创建自定义模式文件
    mode_def = {
        "mode_id": "TEST_MODE",
        "display_name": "测试模式",
        "icon": "star",
        "cacheable": True,
        "description": "这是一个测试模式",
        "content": {
            "type": "static",
            "static_data": {
                "text": "测试内容",
                "title": "测试标题",
            },
        },
        "layout": {
            "body": [
                {
                    "type": "text",
                    "field": "title",
                    "font_size": 16,
                    "align": "center",
                },
                {
                    "type": "text",
                    "field": "text",
                    "font_size": 12,
                    "align": "left",
                },
            ],
        },
    }
    
    # 保存到临时目录
    custom_dir = tmp_path / "custom_modes"
    custom_dir.mkdir(exist_ok=True)
    
    with patch("core.mode_registry.CUSTOM_JSON_DIR", str(custom_dir)):
        mode_file = custom_dir / "test_mode.json"
        mode_file.write_text(json.dumps(mode_def, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # 重新加载注册表
        registry = get_registry()
        registry.load_json_mode(str(mode_file), source="custom")
        
        yield {
            "mode_id": "TEST_MODE",
            "mode_def": mode_def,
            "file_path": str(mode_file),
        }


class TestDiscoverAPI:
    """Discover API 接口测试"""

    @pytest.mark.asyncio
    async def test_list_modes_empty(self, client: AsyncClient):
        """测试空列表"""
        resp = await client.get("/api/discover/modes")
        assert resp.status_code == 200
        data = resp.json()
        assert "modes" in data
        assert "pagination" in data
        assert len(data["modes"]) == 0
        assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_modes_with_category_filter(self, client: AsyncClient, test_user, test_custom_mode):
        """测试分类过滤"""
        # 先发布一个模式
        resp = await client.post(
            "/api/discover/modes/publish",
            headers=test_user["headers"],
            json={
                "source_custom_mode_id": "TEST_MODE",
                "name": "测试模式",
                "description": "测试描述",
                "category": "效率",
                "mac": test_user["mac"],
            },
        )
        assert resp.status_code == 200
        
        # 测试分类过滤
        resp = await client.get("/api/discover/modes?category=效率")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modes"]) == 1
        assert data["modes"][0]["category"] == "效率"
        
        # 测试其他分类
        resp = await client.get("/api/discover/modes?category=学习")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modes"]) == 0

    @pytest.mark.asyncio
    async def test_list_modes_pagination(self, client: AsyncClient, test_user, test_custom_mode):
        """测试分页"""
        # 发布多个模式
        for i in range(5):
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": f"测试模式 {i}",
                    "description": f"测试描述 {i}",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            assert resp.status_code == 200
        
        # 测试第一页
        resp = await client.get("/api/discover/modes?page=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modes"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] == 5

    @pytest.mark.asyncio
    async def test_publish_mode_success(self, client: AsyncClient, test_user, test_custom_mode, sample_date_ctx, sample_weather):
        """测试成功发布模式"""
        with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
             patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
             patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
             patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gen, \
             patch("core.json_renderer.render_json_mode") as mock_render:
            
            # Mock 内容生成
            mock_gen.return_value = {
                "text": "测试内容",
                "title": "测试标题",
            }
            
            # Mock 图片渲染
            from PIL import Image
            mock_img = Image.new("RGB", (400, 300), color="white")
            mock_render.return_value = mock_img
            
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert "id" in data
            
            # 验证 generate_json_mode_content 被调用，且传入了 LLM 配置参数（即使为空）
            assert mock_gen.called
            call_kwargs = mock_gen.call_args[1] if mock_gen.call_args else {}
            assert "llm_provider" in call_kwargs
            assert "llm_model" in call_kwargs
            assert "api_key" in call_kwargs
            assert "image_provider" in call_kwargs
            assert "image_model" in call_kwargs
            assert "image_api_key" in call_kwargs
            
            # 验证数据库中有记录
            db = await get_main_db()
            cursor = await db.execute(
                "SELECT id, name, category, author_id FROM shared_modes WHERE id = ?",
                (data["id"],),
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[1] == "测试模式"
            assert row[2] == "效率"
            assert row[3] == test_user["user_id"]

    @pytest.mark.asyncio
    async def test_publish_mode_uses_user_llm_config(self, client: AsyncClient, test_user, test_custom_mode, sample_date_ctx, sample_weather):
        """测试发布模式时使用用户的 LLM 配置"""
        # Mock 用户 LLM 配置
        user_llm_config = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "sk-test-user-key-12345",
            "image_provider": "aliyun",
            "image_model": "qwen-image-max",
            "image_api_key": "sk-test-image-key-67890",
        }
        
        with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
             patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
             patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=user_llm_config), \
             patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gen, \
             patch("core.json_renderer.render_json_mode") as mock_render:
            
            # Mock 内容生成
            mock_gen.return_value = {
                "text": "测试内容",
                "title": "测试标题",
            }
            
            # Mock 图片渲染
            from PIL import Image
            mock_img = Image.new("RGB", (400, 300), color="white")
            mock_render.return_value = mock_img
            
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            
            # 验证 generate_json_mode_content 被调用，且传入了用户的 LLM 配置
            assert mock_gen.called
            call_kwargs = mock_gen.call_args[1] if mock_gen.call_args else {}
            assert call_kwargs.get("llm_provider") == "deepseek"
            assert call_kwargs.get("llm_model") == "deepseek-chat"
            assert call_kwargs.get("api_key") == "sk-test-user-key-12345"
            assert call_kwargs.get("image_provider") == "aliyun"
            assert call_kwargs.get("image_model") == "qwen-image-max"
            assert call_kwargs.get("image_api_key") == "sk-test-image-key-67890"

    @pytest.mark.asyncio
    async def test_publish_mode_requires_auth(self, client: AsyncClient, test_custom_mode):
        """测试发布需要认证"""
        # 确保没有认证信息（不传 headers，也不传 cookies）
        # 创建一个新的客户端实例，确保没有之前的 cookies
        try:
            from httpx import ASGITransport  # type: ignore
            _clean_ctx = AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={})
        except Exception:
            _clean_ctx = AsyncClient(app=app, base_url="http://test", cookies={})
        async with _clean_ctx as clean_client:
            resp = await clean_client.post(
                "/api/discover/modes/publish",
                headers={},  # 明确指定空的 headers
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                },
            )
            assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}, response: {resp.text}"

    @pytest.mark.asyncio
    async def test_publish_mode_invalid_mode(self, client: AsyncClient, test_user):
        """测试发布不存在的模式"""
        resp = await client.post(
            "/api/discover/modes/publish",
            headers=test_user["headers"],
            json={
                "source_custom_mode_id": "NONEXISTENT_MODE",
                "name": "测试模式",
                "description": "测试描述",
                "category": "效率",
                "mac": test_user["mac"],
            },
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert "不存在" in data["error"]

    @pytest.mark.asyncio
    async def test_publish_mode_missing_params(self, client: AsyncClient, test_user):
        """测试缺少必需参数"""
        resp = await client.post(
            "/api/discover/modes/publish",
            headers=test_user["headers"],
            json={
                "name": "测试模式",
                # 缺少 source_custom_mode_id 和 category
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_publish_mode_image_gen_waiting(self, client: AsyncClient, test_user, tmp_path, sample_date_ctx, sample_weather):
        """测试图片生成类型的等待逻辑"""
        from pathlib import Path
        
        # 创建图片生成类型的模式
        mode_def = {
            "mode_id": "TEST_IMAGE_GEN",
            "display_name": "测试图片生成",
            "content": {
                "type": "image_gen",
                "provider": "text2image",
                "fallback": {
                    "artwork_title": "测试",
                    "image_url": "",
                    "description": "图像生成中",
                },
            },
            "layout": {
                "body": [
                    {"type": "text", "field": "artwork_title"},
                    {"type": "image", "field": "image_url"},
                ],
            },
        }
        
        custom_dir = tmp_path / "custom_modes"
        custom_dir.mkdir(exist_ok=True)
        
        with patch("core.mode_registry.CUSTOM_JSON_DIR", str(custom_dir)):
            mode_file = custom_dir / "test_image_gen.json"
            mode_file.write_text(json.dumps(mode_def, ensure_ascii=False, indent=2), encoding="utf-8")
            
            registry = get_registry()
            registry.load_json_mode(str(mode_file), source="custom")
            
            # Mock 图片生成：前两次返回生成中，第三次返回成功
            call_count = [0]
            
            async def mock_generate_content(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] < 3:
                    # 前两次返回生成中状态
                    return {
                        "artwork_title": "测试",
                        "image_url": "",
                        "description": "图像生成中",
                    }
                else:
                    # 第三次返回成功
                    return {
                        "artwork_title": "测试",
                        "image_url": "https://example.com/image.png",
                        "description": "黑白线描作品",
                    }
            
            with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
                 patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
                 patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
                 patch("core.json_content.generate_json_mode_content", side_effect=mock_generate_content), \
                 patch("core.json_renderer.render_json_mode") as mock_render:
                
                from PIL import Image
                mock_img = Image.new("RGB", (400, 300), color="white")
                mock_render.return_value = mock_img
                
                resp = await client.post(
                    "/api/discover/modes/publish",
                    headers=test_user["headers"],
                    json={
                        "source_custom_mode_id": "TEST_IMAGE_GEN",
                        "name": "测试图片生成",
                        "description": "测试描述",
                        "category": "趣味",
                        "mac": test_user["mac"],
                    },
                )
                
                # 应该成功，因为会等待图片生成完成
                assert resp.status_code == 200
                assert call_count[0] == 3  # 应该重试了3次

    @pytest.mark.asyncio
    async def test_publish_mode_image_gen_timeout(self, client: AsyncClient, test_user, tmp_path, sample_date_ctx, sample_weather):
        """测试图片生成超时"""
        from pathlib import Path
        
        mode_def = {
            "mode_id": "TEST_IMAGE_GEN_TIMEOUT",
            "display_name": "测试超时",
            "content": {
                "type": "image_gen",
                "provider": "text2image",
                "fallback": {
                    "artwork_title": "测试",
                    "image_url": "",
                    "description": "图像生成中",
                },
            },
            "layout": {
                "body": [
                    {"type": "text", "field": "artwork_title"},
                    {"type": "image", "field": "image_url"},
                ],
            },
        }
        
        custom_dir = tmp_path / "custom_modes"
        custom_dir.mkdir(exist_ok=True)
        
        with patch("core.mode_registry.CUSTOM_JSON_DIR", str(custom_dir)):
            mode_file = custom_dir / "test_timeout.json"
            mode_file.write_text(json.dumps(mode_def, ensure_ascii=False, indent=2), encoding="utf-8")
            
            registry = get_registry()
            registry.load_json_mode(str(mode_file), source="custom")
            
            # Mock 始终返回生成中状态
            async def mock_generate_content(*args, **kwargs):
                return {
                    "artwork_title": "测试",
                    "image_url": "",
                    "description": "图像生成中",
                }
            
            with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
                 patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
                 patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
                 patch("core.json_content.generate_json_mode_content", side_effect=mock_generate_content):
                
                resp = await client.post(
                    "/api/discover/modes/publish",
                    headers=test_user["headers"],
                    json={
                        "source_custom_mode_id": "TEST_IMAGE_GEN_TIMEOUT",
                        "name": "测试超时",
                        "description": "测试描述",
                        "category": "趣味",
                        "mac": test_user["mac"],
                    },
                )
                
                # 应该返回超时错误
                assert resp.status_code == 408
                data = resp.json()
                assert "error" in data
                assert "超时" in data["error"]

    @pytest.mark.asyncio
    async def test_install_mode_success(self, client: AsyncClient, test_user, test_custom_mode, sample_date_ctx, sample_weather):
        """测试成功安装模式"""
        # 先发布一个模式
        with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
             patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
             patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
             patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gen, \
             patch("core.json_renderer.render_json_mode") as mock_render:
            
            mock_gen.return_value = {
                "text": "测试内容",
                "title": "测试标题",
            }
            
            from PIL import Image
            mock_img = Image.new("RGB", (400, 300), color="white")
            mock_render.return_value = mock_img
            
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            assert resp.status_code == 200
            shared_mode_id = resp.json()["id"]
            
            # 安装模式
            resp = await client.post(
                f"/api/discover/modes/{shared_mode_id}/install",
                headers=test_user["headers"],
                json={"mac": test_user["mac"]},
            )
            
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert "custom_mode_id" in data
            assert data["custom_mode_id"].startswith("CUSTOM_")
            
            # 验证模式已保存到文件系统
            registry = get_registry()
            installed_mode = registry.get_json_mode(data["custom_mode_id"])
            assert installed_mode is not None
            assert installed_mode.info.source == "custom"

    @pytest.mark.asyncio
    async def test_install_mode_requires_auth(self, client: AsyncClient, test_user, test_custom_mode, sample_date_ctx, sample_weather):
        """测试安装需要认证"""
        # 先发布一个模式
        with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
             patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
             patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
             patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gen, \
             patch("core.json_renderer.render_json_mode") as mock_render:
            
            mock_gen.return_value = {"text": "测试内容", "title": "测试标题"}
            from PIL import Image
            mock_img = Image.new("RGB", (400, 300), color="white")
            mock_render.return_value = mock_img
            
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            assert resp.status_code == 200
            shared_mode_id = resp.json()["id"]
            
            # 尝试不认证安装 - 创建新的客户端实例，确保没有之前的 cookies
            try:
                from httpx import ASGITransport  # type: ignore
                _clean_ctx = AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={})
            except Exception:
                _clean_ctx = AsyncClient(app=app, base_url="http://test", cookies={})
            async with _clean_ctx as clean_client:
                resp = await clean_client.post(
                    f"/api/discover/modes/{shared_mode_id}/install",
                    headers={},  # 明确指定空的 headers
                    json={"mac": TEST_MAC},
                )
                assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}, response: {resp.text}"

    @pytest.mark.asyncio
    async def test_install_mode_not_found(self, client: AsyncClient, test_user):
        """测试安装不存在的模式"""
        resp = await client.post(
            "/api/discover/modes/99999/install",
            headers=test_user["headers"],
            json={"mac": test_user["mac"]},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_modes_includes_author(self, client: AsyncClient, test_user, test_custom_mode, sample_date_ctx, sample_weather):
        """测试列表包含作者信息"""
        with patch("core.context.get_date_context", new_callable=AsyncMock, return_value=sample_date_ctx), \
             patch("core.context.get_weather", new_callable=AsyncMock, return_value=sample_weather), \
             patch("core.config_store.get_user_llm_config", new_callable=AsyncMock, return_value=None), \
             patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gen, \
             patch("core.json_renderer.render_json_mode") as mock_render:
            
            mock_gen.return_value = {"text": "测试内容", "title": "测试标题"}
            from PIL import Image
            mock_img = Image.new("RGB", (400, 300), color="white")
            mock_render.return_value = mock_img
            
            resp = await client.post(
                "/api/discover/modes/publish",
                headers=test_user["headers"],
                json={
                    "source_custom_mode_id": "TEST_MODE",
                    "name": "测试模式",
                    "description": "测试描述",
                    "category": "效率",
                    "mac": test_user["mac"],
                },
            )
            assert resp.status_code == 200
            
            # 获取列表
            resp = await client.get("/api/discover/modes")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["modes"]) == 1
            assert "author" in data["modes"][0]
            assert data["modes"][0]["author"] == f"@{test_user['username']}"
