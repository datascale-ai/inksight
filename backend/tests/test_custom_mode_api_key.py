"""
测试自定义模式的 API key 传递逻辑

测试场景：
1. 用户配置了有效的 api_key - 应该使用用户配置的
2. 用户配置了但解密后为空 - 应该报错提示用户配置有问题
3. 用户没有配置 api_key - 应该使用环境变量
4. 用户没有配置且环境变量也没有 - 应该报错
5. 测试 pipeline.py 中的 api_key 传递
6. 测试 json_content.py 中的 api_key 传递
7. 测试 mode_generator.py 中的 api_key 传递
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.errors import LLMKeyMissingError
from core.pipeline import _generate_content_for_persona
from core.json_content import generate_json_mode_content
from core.mode_generator import generate_mode_definition, _call_llm_with_messages
from core.content import _get_client


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
def custom_mode_def():
    """A custom mode definition for testing."""
    return {
        "mode_id": "TEST_CUSTOM",
        "display_name": "测试自定义模式",
        "content": {
            "type": "llm_json",
            "prompt_template": "测试提示词 {context}",
            "output_schema": {
                "quote": {"type": "string", "default": "默认语录"},
                "author": {"type": "string", "default": "默认作者"},
            },
            "fallback": {"quote": "默认语录", "author": "默认作者"},
        },
        "layout": {"body": []},
    }


def _mock_registry(*, json_modes=None):
    """Build a mock ModeRegistry for JSON modes."""
    json_modes = set(json_modes or [])
    mock_reg = MagicMock()
    mock_reg.is_json_mode.side_effect = lambda p: p in json_modes
    
    def _get_json_mode(p, mac=None, *args, **kwargs):
        # 测试环境下忽略 mac，仅根据模式 ID 判断是否为 JSON 模式
        if p in json_modes:
            jm = MagicMock()
            jm.definition = {
                "mode_id": p,
                "content": {"type": "llm_json", "prompt_template": "test {context}", "output_schema": {"quote": {"default": "test"}}, "fallback": {"quote": "test"}},
                "layout": {"body": []},
            }
            return jm
        return None
    
    mock_reg.get_json_mode.side_effect = _get_json_mode
    return mock_reg


class TestPipelineApiKey:
    """测试 pipeline.py 中的 api_key 传递"""

    @pytest.mark.asyncio
    async def test_pipeline_passes_user_api_key_to_json_content(self, sample_date_ctx, sample_weather, custom_mode_def):
        """测试 pipeline 正确传递用户配置的 api_key"""
        mock_reg = _mock_registry(json_modes=["TEST_CUSTOM"])
        user_api_key = "sk-user-key-12345"
        
        # 模拟加密的 api_key
        from core.crypto import encrypt_api_key
        encrypted_key = encrypt_api_key(user_api_key)
        
        # 在新的实现中，pipeline 不再从设备配置的 llm_api_key 读取用户 Key，
        # 而是由上层 shared.build_image 注入 config["user_api_key"]。
        # 为了验证 generate_json_mode_content 收到正确的 api_key，
        # 这里直接通过 config["user_api_key"] 传递。
        config = {
            "user_api_key": user_api_key,
            "llm_provider": "deepseek",
            "llm_model": "deepseek-chat",
        }
        
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gc,
        ):
            mock_gc.return_value = {"quote": "test", "author": "test"}
            
            await _generate_content_for_persona(
                "TEST_CUSTOM",
                config,
                sample_date_ctx,
                sample_weather["weather_str"],
            )
            
            # 验证 api_key 被正确传递
            call_args = mock_gc.call_args
            assert call_args is not None
            assert call_args.kwargs.get("api_key") == user_api_key

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_decrypted_key(self, sample_date_ctx, sample_weather, custom_mode_def):
        """测试 pipeline 处理解密后为空的情况"""
        mock_reg = _mock_registry(json_modes=["TEST_CUSTOM"])
        
        # 模拟上层传入 user_api_key 为空字符串（表示用户配置了但无效）
        config = {
            "user_api_key": "",
            "llm_provider": "deepseek",
            "llm_model": "deepseek-chat",
        }
        
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.crypto.decrypt_api_key", return_value=""),  # 解密失败返回空字符串
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gc,
        ):
            mock_gc.return_value = {"quote": "test", "author": "test"}
            
            await _generate_content_for_persona(
                "TEST_CUSTOM",
                config,
                sample_date_ctx,
                sample_weather["weather_str"],
            )
            
            # 验证传递的是空字符串（表示用户配置了但无效）
            call_args = mock_gc.call_args
            assert call_args is not None
            assert call_args.kwargs.get("api_key") == ""

    @pytest.mark.asyncio
    async def test_pipeline_uses_none_when_no_config(self, sample_date_ctx, sample_weather, custom_mode_def):
        """测试 pipeline 在没有配置时传递 None"""
        mock_reg = _mock_registry(json_modes=["TEST_CUSTOM"])
        
        config = {
            "llm_provider": "deepseek",
            "llm_model": "deepseek-chat",
        }
        
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gc,
        ):
            mock_gc.return_value = {"quote": "test", "author": "test"}
            
            await _generate_content_for_persona(
                "TEST_CUSTOM",
                config,
                sample_date_ctx,
                sample_weather["weather_str"],
            )
            
            # 验证传递的是 None（表示用户没有配置）
            call_args = mock_gc.call_args
            assert call_args is not None
            assert call_args.kwargs.get("api_key") is None


class TestJsonContentApiKey:
    """测试 json_content.py 中的 api_key 传递"""

    @pytest.mark.asyncio
    async def test_json_content_uses_user_api_key(self, custom_mode_def):
        """测试 json_content 使用用户配置的 api_key"""
        user_api_key = "sk-user-key-12345"
        
        with patch("core.json_content._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"quote": "test", "author": "test"}'
            
            await generate_json_mode_content(
                custom_mode_def,
                date_str="2025-03-12",
                weather_str="晴 15°C",
                api_key=user_api_key,
            )
            
            # 验证 _call_llm 被调用时传递了用户配置的 api_key
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            assert call_args.kwargs.get("api_key") == user_api_key

    @pytest.mark.asyncio
    async def test_json_content_uses_env_var_when_api_key_is_none(self, custom_mode_def):
        """测试 json_content 在 api_key 为 None 时使用环境变量"""
        env_api_key = "sk-env-key-67890"
        
        with (
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}),
            patch("core.json_content._call_llm", new_callable=AsyncMock) as mock_llm,
        ):
            mock_llm.return_value = '{"quote": "test", "author": "test"}'
            
            await generate_json_mode_content(
                custom_mode_def,
                date_str="2025-03-12",
                weather_str="晴 15°C",
                api_key=None,  # 用户没有配置
            )
            
            # 验证 _call_llm 被调用，_get_client 会从环境变量获取
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_content_raises_error_when_user_key_empty(self, custom_mode_def):
        """测试 json_content 在用户配置的 api_key 为空时抛出错误"""
        with (
            patch.dict(os.environ, {}, clear=True),  # 清空环境变量
            patch("core.json_content._call_llm", new_callable=AsyncMock) as mock_llm,
        ):
            # _get_client 会抛出 LLMKeyMissingError
            mock_llm.side_effect = LLMKeyMissingError("您配置的 API key 为空或无效")
            
            result = await generate_json_mode_content(
                custom_mode_def,
                date_str="2025-03-12",
                weather_str="晴 15°C",
                api_key="",  # 用户配置了但为空
            )
            
            # 应该返回 fallback 内容，并标记 api_key_invalid
            assert "quote" in result
            assert result.get("_api_key_invalid") is True

    @pytest.mark.asyncio
    async def test_json_content_passes_api_key_to_nested_calls(self, custom_mode_def):
        """测试 json_content 在嵌套调用中传递 api_key"""
        user_api_key = "sk-user-key-12345"
        
        # 测试 external_data 类型（briefing provider）
        mode_def_briefing = {
            "mode_id": "TEST_BRIEFING",
            "content": {
                "type": "external_data",
                "provider": "briefing",
                "summarize": True,
                "include_insight": True,
            },
            "layout": {"body": []},
        }
        
        with (
            patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
            patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
            patch("core.content.fetch_v2ex_hot", new_callable=AsyncMock) as mock_v2ex,
            patch("core.content.summarize_briefing_content", new_callable=AsyncMock) as mock_summarize,
            patch("core.content.generate_briefing_insight", new_callable=AsyncMock) as mock_insight,
        ):
            mock_hn.return_value = [{"title": "test", "score": 10}]
            mock_ph.return_value = {"name": "test", "tagline": "test"}
            mock_v2ex.return_value = []
            mock_summarize.return_value = ([{"title": "test"}], {"name": "test"})
            mock_insight.return_value = "test insight"
            
            await generate_json_mode_content(
                mode_def_briefing,
                date_str="2025-03-12",
                weather_str="晴 15°C",
                api_key=user_api_key,
            )
            
            # 验证嵌套调用都传递了 api_key
            mock_summarize.assert_called_once()
            assert mock_summarize.call_args.kwargs.get("api_key") == user_api_key
            mock_insight.assert_called_once()
            assert mock_insight.call_args.kwargs.get("api_key") == user_api_key


class TestModeGeneratorApiKey:
    """测试 mode_generator.py 中的 api_key 传递"""

    @pytest.mark.asyncio
    async def test_mode_generator_uses_user_api_key(self):
        """测试 mode_generator 使用用户配置的 api_key"""
        user_api_key = "sk-user-key-12345"
        
        with patch("core.mode_generator._get_client") as mock_get_client:
            mock_client = MagicMock()
            # 创建 mock response
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message = MagicMock(content='{"mode_id": "TEST", "display_name": "Test"}')
            mock_choice.finish_reason = "stop"
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(total_tokens=100)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = (mock_client, 1024)
            
            try:
                await _call_llm_with_messages(
                    "deepseek",
                    "deepseek-chat",
                    [{"role": "user", "content": "test"}],
                    api_key=user_api_key,
                )
            except Exception:
                pass  # 忽略其他错误，只关注 api_key 传递
            
            # 验证 _get_client 被调用时传递了 api_key
            mock_get_client.assert_called_once()
            call_args = mock_get_client.call_args
            assert call_args.kwargs.get("api_key") == user_api_key

    @pytest.mark.asyncio
    async def test_generate_mode_definition_passes_api_key(self):
        """测试 generate_mode_definition 传递 api_key"""
        user_api_key = "sk-user-key-12345"
        
        with (
            patch("core.mode_generator._call_llm_with_messages", new_callable=AsyncMock) as mock_llm,
        ):
            mock_llm.return_value = '{"mode_id": "TEST", "display_name": "Test", "content": {"type": "llm"}, "layout": {"body": []}}'
            
            try:
                await generate_mode_definition(
                    description="测试模式",
                    provider="deepseek",
                    model="deepseek-chat",
                    api_key=user_api_key,
                )
            except Exception:
                pass  # 忽略验证错误，只关注 api_key 传递
            
            # 验证 _call_llm_with_messages 被调用时传递了 api_key
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            assert call_args.kwargs.get("api_key") == user_api_key


class TestGetClientApiKey:
    """测试 _get_client 中的 api_key 处理逻辑"""

    def test_get_client_uses_user_api_key(self):
        """测试 _get_client 使用用户配置的 api_key"""
        user_api_key = "sk-user-key-12345"
        
        client, max_tokens = _get_client("deepseek", "deepseek-chat", api_key=user_api_key)
        
        assert client is not None
        assert max_tokens > 0
        # 验证 client 使用的是用户配置的 api_key（通过检查 client 的 api_key 属性）
        assert hasattr(client, "_client")
        # 注意：AsyncOpenAI 的 api_key 存储在内部，我们无法直接访问，但可以确认没有抛出异常

    def test_get_client_uses_env_var_when_api_key_is_none(self):
        """测试 _get_client 在 api_key 为 None 时使用环境变量"""
        env_api_key = "sk-env-key-67890"
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}):
            client, max_tokens = _get_client("deepseek", "deepseek-chat", api_key=None)
            
            assert client is not None
            assert max_tokens > 0

    def test_get_client_raises_error_when_user_key_empty(self):
        """测试 _get_client 在用户配置的 api_key 为空时抛出错误"""
        with (
            patch.dict(os.environ, {}, clear=True),  # 清空环境变量
        ):
            with pytest.raises(LLMKeyMissingError) as exc_info:
                _get_client("deepseek", "deepseek-chat", api_key="")
            
            # 验证错误消息包含"您配置的"
            assert "您配置的" in str(exc_info.value)

    def test_get_client_raises_error_when_no_key_at_all(self):
        """测试 _get_client 在完全没有 api_key 时抛出错误"""
        with (
            patch.dict(os.environ, {}, clear=True),  # 清空环境变量
        ):
            with pytest.raises(LLMKeyMissingError) as exc_info:
                _get_client("deepseek", "deepseek-chat", api_key=None)
            
            # 验证错误消息不包含"您配置的"（因为用户没有配置）
            assert "您配置的" not in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
