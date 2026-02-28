"""API 鉴权依赖的单元测试。"""
import os
import pytest

from core.auth import validate_mac_param, require_device_token, require_admin


class TestValidateMacParam:
    def test_valid_mac(self):
        result = validate_mac_param("AA:BB:CC:DD:EE:FF")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_valid_mac_lowercase(self):
        result = validate_mac_param("aa:bb:cc:dd:ee:ff")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_invalid_mac(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_mac_param("not-a-mac")
        assert exc_info.value.status_code == 400

    def test_empty_mac(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_mac_param("")
        assert exc_info.value.status_code == 400


class TestRequireAdmin:
    def test_no_admin_token_configured_allows_access(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        require_admin(authorization=None)

    def test_valid_admin_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        require_admin(authorization="Bearer secret123")

    def test_invalid_admin_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization="Bearer wrong")
        assert exc_info.value.status_code == 403

    def test_missing_admin_token_when_required(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization=None)
        assert exc_info.value.status_code == 403

    def test_malformed_auth_header(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret123")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization="Basic secret123")
        assert exc_info.value.status_code == 403


class TestRequireDeviceToken:
    @pytest.mark.asyncio
    async def test_no_token_stored_allows_access(self, monkeypatch):
        """新设备无 Token 时应放行（宽限期）。"""
        from core import auth as _auth_mod
        async def _fake_validate(mac, token):
            return False
        async def _fake_get_state(mac):
            return None
        monkeypatch.setattr(_auth_mod, "validate_device_token", _fake_validate)
        monkeypatch.setattr(_auth_mod, "get_device_state", _fake_get_state)

        result = await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_valid_token(self, monkeypatch):
        from core import auth as _auth_mod
        async def _fake_validate(mac, token):
            return True
        monkeypatch.setattr(_auth_mod, "validate_device_token", _fake_validate)

        result = await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token="valid-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_token_when_device_has_token(self, monkeypatch):
        from core import auth as _auth_mod
        async def _fake_validate(mac, token):
            return False
        async def _fake_get_state(mac):
            return {"auth_token": "real-token"}
        monkeypatch.setattr(_auth_mod, "validate_device_token", _fake_validate)
        monkeypatch.setattr(_auth_mod, "get_device_state", _fake_get_state)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await require_device_token(mac="AA:BB:CC:DD:EE:FF", x_device_token="wrong-token")
        assert exc_info.value.status_code == 401


class TestTokenProvisioning:
    @pytest.mark.asyncio
    async def test_provision_new_device(self, monkeypatch):
        """新设备首次请求时获得 Token。"""
        from api import index

        generated_token = "test-token-abc"
        async def _fake_get_state(mac):
            return None
        async def _fake_generate(mac):
            return generated_token
        monkeypatch.setattr(index, "get_device_state", _fake_get_state)
        monkeypatch.setattr(index, "generate_device_token", _fake_generate)

        resp = await index.provision_device_token("AA:BB:CC:DD:EE:FF")
        assert resp["token"] == generated_token

    @pytest.mark.asyncio
    async def test_provision_existing_device_returns_existing(self, monkeypatch):
        """已有 Token 的设备返回已有 Token。"""
        from api import index

        async def _fake_get_state(mac):
            return {"auth_token": "existing-token"}
        monkeypatch.setattr(index, "get_device_state", _fake_get_state)

        resp = await index.provision_device_token("AA:BB:CC:DD:EE:FF")
        assert resp["token"] == "existing-token"


class TestAdminProtection:
    def test_admin_blocks_without_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
        from core.auth import require_admin
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(authorization=None)
        assert exc_info.value.status_code == 403

    def test_admin_allows_with_correct_token(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
        from core.auth import require_admin
        require_admin(authorization="Bearer admin-secret")

    def test_admin_skips_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        from core.auth import require_admin
        require_admin(authorization=None)
