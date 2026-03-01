"""Tests for API key encryption utility."""
import os
import pytest
from core.crypto import encrypt_api_key, decrypt_api_key


def test_encrypt_decrypt_roundtrip():
    key = "sk-test-1234567890abcdef"
    encrypted = encrypt_api_key(key)
    assert encrypted != key
    assert decrypt_api_key(encrypted) == key


def test_encrypt_empty_string():
    assert encrypt_api_key("") == ""
    assert decrypt_api_key("") == ""


def test_decrypt_invalid_token():
    result = decrypt_api_key("not-a-valid-token")
    assert result == ""


def test_uses_env_key_when_available():
    os.environ["ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3OA=="
    try:
        key = "sk-secret"
        encrypted = encrypt_api_key(key)
        assert decrypt_api_key(encrypted) == key
    finally:
        del os.environ["ENCRYPTION_KEY"]
