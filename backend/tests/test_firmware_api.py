import pytest
from httpx import AsyncClient

from api import shared as shared_api
from api.index import app
from api.routes import firmware as firmware_routes


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    # httpx compatibility wrapper for different versions
    try:
        from httpx import ASGITransport  # type: ignore

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    except Exception:
        async with AsyncClient(app=app, base_url="http://test") as c:
            yield c


def _sample_payload() -> dict:
    return {
        "source": "github_releases",
        "repo": "datascale-ai/inksight",
        "cached": False,
        "count": 1,
        "releases": [
            {
                "version": "1.2.3",
                "tag": "v1.2.3",
                "download_url": "https://example.com/inksight-firmware-v1.2.3.bin",
                "chip_family": "ESP32-C3",
                "manifest": {
                    "name": "InkSight",
                    "version": "1.2.3",
                    "builds": [],
                },
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
async def test_firmware_releases_success(client, monkeypatch, prefix):
    async def _fake_loader(force_refresh: bool = False):
        assert force_refresh is False
        return _sample_payload()

    monkeypatch.setattr(firmware_routes, "load_firmware_releases", _fake_loader)
    resp = await client.get(f"{prefix}/firmware/releases")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["releases"][0]["tag"] == "v1.2.3"


@pytest.mark.asyncio
async def test_firmware_releases_latest_success(client, monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        payload = _sample_payload()
        payload["cached"] = True
        payload["releases"].append({"version": "1.2.2", "tag": "v1.2.2"})
        payload["count"] = 2
        return payload

    monkeypatch.setattr(firmware_routes, "load_firmware_releases", _fake_loader)
    resp = await client.get("/api/firmware/releases/latest")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["latest"]["version"] == "1.2.3"
    assert payload["cached"] is True


@pytest.mark.asyncio
async def test_firmware_releases_latest_not_found(client, monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        return {
            "source": "github_releases",
            "repo": "datascale-ai/inksight",
            "cached": False,
            "count": 0,
            "releases": [],
        }

    monkeypatch.setattr(firmware_routes, "load_firmware_releases", _fake_loader)
    resp = await client.get("/api/firmware/releases/latest")
    assert resp.status_code == 404
    assert resp.json()["error"] == "firmware_release_not_found"


@pytest.mark.asyncio
async def test_firmware_releases_fetch_failed(client, monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(firmware_routes, "load_firmware_releases", _fake_loader)
    resp = await client.get("/api/firmware/releases")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"] == "firmware_release_fetch_failed"
    assert body["message"] == "rate limited"


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
async def test_firmware_validate_url_success(client, monkeypatch, prefix):
    async def _fake_validate(url: str):
        assert url == "https://example.com/fw.bin"
        return {"ok": True, "reachable": True, "status_code": 200}

    monkeypatch.setattr(firmware_routes, "validate_firmware_url", _fake_validate)
    resp = await client.get(f"{prefix}/firmware/validate-url", params={"url": "https://example.com/fw.bin"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["reachable"] is True


@pytest.mark.asyncio
async def test_firmware_validate_url_invalid(client, monkeypatch):
    async def _fake_validate(url: str):
        raise ValueError("firmware URL should point to a .bin file")

    monkeypatch.setattr(firmware_routes, "validate_firmware_url", _fake_validate)
    resp = await client.get("/api/firmware/validate-url", params={"url": "https://example.com/fw.txt"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_firmware_url"


@pytest.mark.asyncio
async def test_firmware_validate_url_unreachable(client, monkeypatch):
    async def _fake_validate(url: str):
        raise RuntimeError("firmware URL is not reachable: 404")

    monkeypatch.setattr(firmware_routes, "validate_firmware_url", _fake_validate)
    resp = await client.get("/api/firmware/validate-url", params={"url": "https://example.com/fw.bin"})
    assert resp.status_code == 503
    assert resp.json()["error"] == "firmware_url_unreachable"


def test_expand_release_assets_returns_multiple_bin_entries():
    release = {
        "tag_name": "v0.3",
        "published_at": "2026-03-14T10:15:04Z",
        "assets": [
            {
                "name": "epd_42_c3.bin",
                "size": 1148832,
                "browser_download_url": "https://example.com/epd_42_c3.bin",
            },
            {
                "name": "epd_42_wroom32e.bin",
                "size": 1140784,
                "browser_download_url": "https://example.com/epd_42_wroom32e.bin",
            },
        ],
    }

    items = shared_api.expand_firmware_release_assets(release)

    assert len(items) == 2
    assert items[0]["asset_name"] == "epd_42_c3.bin"
    assert items[0]["chip_family"] == "ESP32-C3"
    assert items[1]["asset_name"] == "epd_42_wroom32e.bin"
    assert items[1]["chip_family"] == "ESP32"


def test_render_api_key_invalid_image_uses_project_font_loader(monkeypatch):
    calls = []

    def _fake_load_font(font_key: str, size: int):
        calls.append((font_key, size))
        from PIL import ImageFont

        return ImageFont.load_default()

    monkeypatch.setattr(shared_api, "load_font", _fake_load_font, raising=False)

    shared_api._render_api_key_invalid_image(400, 300)

    assert calls


def test_render_quota_exhausted_image_uses_project_font_loader(monkeypatch):
    calls = []

    def _fake_load_font(font_key: str, size: int):
        calls.append((font_key, size))
        from PIL import ImageFont

        return ImageFont.load_default()

    monkeypatch.setattr(shared_api, "load_font", _fake_load_font, raising=False)

    shared_api._render_quota_exhausted_image(400, 300)

    assert calls


def test_render_device_unbound_image_uses_project_font_loader(monkeypatch):
    calls = []

    def _fake_load_font(font_key: str, size: int):
        calls.append((font_key, size))
        from PIL import ImageFont

        return ImageFont.load_default()

    monkeypatch.setattr(shared_api, "load_font", _fake_load_font, raising=False)

    shared_api._render_device_unbound_image(400, 300, "AB12CD34")

    assert calls
