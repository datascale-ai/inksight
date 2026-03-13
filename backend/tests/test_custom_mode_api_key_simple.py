"""
测试自定义模式的 API key 传递逻辑（简化版，专注于核心逻辑）

测试场景：
1. _get_client 正确处理用户配置的 api_key
2. _get_client 正确处理空字符串和 None
3. pipeline.py 正确解密和传递 api_key
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.errors import LLMKeyMissingError
from core.content import _get_client
from core.crypto import encrypt_api_key, decrypt_api_key


class TestGetClientApiKeyLogic:
    """测试 _get_client 中的 api_key 处理逻辑"""

    def test_get_client_uses_user_api_key(self):
        """测试 _get_client 使用用户配置的 api_key"""
        user_api_key = "sk-user-key-12345"
        
        # 应该能正常创建 client，不会抛出异常
        client, max_tokens = _get_client("deepseek", "deepseek-chat", api_key=user_api_key)
        
        assert client is not None
        assert max_tokens > 0

    def test_get_client_uses_env_var_when_api_key_is_none(self):
        """测试 _get_client 在 api_key 为 None 时使用环境变量"""
        env_api_key = "sk-env-key-67890"
        
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}, clear=False):
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

    def test_get_client_distinguishes_user_key_from_env_key(self):
        """测试 _get_client 能区分用户配置的 api_key 和环境变量"""
        user_api_key = "sk-user-key-12345"
        env_api_key = "sk-env-key-67890"
        
        # 测试1: 用户配置了 api_key，应该使用用户的
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}, clear=False):
            client1, _ = _get_client("deepseek", "deepseek-chat", api_key=user_api_key)
            assert client1 is not None
        
        # 测试2: 用户没有配置，应该使用环境变量
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}, clear=False):
            client2, _ = _get_client("deepseek", "deepseek-chat", api_key=None)
            assert client2 is not None
        
        # 测试3: 用户配置了但为空，应该报错（即使环境变量有值）
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}, clear=False):
            with pytest.raises(LLMKeyMissingError) as exc_info:
                _get_client("deepseek", "deepseek-chat", api_key="")
            assert "您配置的" in str(exc_info.value)


class TestPipelineApiKeyDecryption:
    """测试 pipeline.py 中的 api_key 解密逻辑"""

    def test_pipeline_decrypts_valid_api_key(self):
        """测试 pipeline 正确解密有效的 api_key"""
        user_api_key = "sk-user-key-12345"
        encrypted_key = encrypt_api_key(user_api_key)
        
        # 模拟 pipeline.py 中的解密逻辑
        from core.crypto import decrypt_api_key
        decrypted = decrypt_api_key(encrypted_key)
        
        assert decrypted == user_api_key
        assert decrypted and decrypted.strip()  # 应该非空

    def test_pipeline_handles_decryption_failure(self):
        """测试 pipeline 处理解密失败的情况"""
        # 模拟解密失败（返回空字符串）
        invalid_encrypted = "invalid-encrypted-key"
        
        from core.crypto import decrypt_api_key
        decrypted = decrypt_api_key(invalid_encrypted)
        
        # 解密失败应该返回空字符串
        assert decrypted == ""
        
        # 模拟 pipeline.py 中的逻辑
        device_api_key = decrypted if decrypted and decrypted.strip() else ""
        assert device_api_key == ""  # 应该被设置为空字符串

    def test_pipeline_handles_empty_encrypted_key(self):
        """测试 pipeline 处理空加密 key 的情况"""
        # 模拟没有配置的情况
        encrypted_key = ""
        
        # 模拟 pipeline.py 中的逻辑
        device_api_key = None
        if encrypted_key:
            from core.crypto import decrypt_api_key
            decrypted = decrypt_api_key(encrypted_key)
            device_api_key = decrypted if decrypted and decrypted.strip() else ""
        
        assert device_api_key is None  # 应该保持为 None


class TestApiKeyFlow:
    """测试完整的 api_key 流程"""

    def test_user_key_flow(self):
        """测试用户配置 api_key 的完整流程"""
        user_api_key = "sk-user-key-12345"
        
        # 1. 加密
        encrypted = encrypt_api_key(user_api_key)
        assert encrypted != user_api_key
        assert encrypted != ""
        
        # 2. 解密
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == user_api_key
        
        # 3. 传递给 _get_client
        client, max_tokens = _get_client("deepseek", "deepseek-chat", api_key=decrypted)
        assert client is not None
        assert max_tokens > 0

    def test_empty_key_flow(self):
        """测试空 api_key 的流程"""
        # 1. 加密空字符串
        encrypted = encrypt_api_key("")
        # 空字符串加密后可能返回空字符串
        assert encrypted == ""
        
        # 2. 解密
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == ""
        
        # 3. 传递给 _get_client 应该报错
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMKeyMissingError) as exc_info:
                _get_client("deepseek", "deepseek-chat", api_key=decrypted)
            assert "您配置的" in str(exc_info.value)

    def test_none_key_flow(self):
        """测试 None api_key 的流程"""
        # 1. 没有配置，device_api_key 应该是 None
        device_api_key = None
        
        # 2. 传递给 _get_client，应该从环境变量获取
        env_api_key = "sk-env-key-67890"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": env_api_key}, clear=False):
            client, max_tokens = _get_client("deepseek", "deepseek-chat", api_key=device_api_key)
            assert client is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
