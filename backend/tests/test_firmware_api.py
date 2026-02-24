import pytest

from api import index


@pytest.mark.asyncio
async def test_firmware_releases_success(monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        assert force_refresh is False
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

    monkeypatch.setattr(index, "_load_firmware_releases", _fake_loader)
    payload = await index.firmware_releases(refresh=False)
    assert payload["count"] == 1
    assert payload["releases"][0]["tag"] == "v1.2.3"


@pytest.mark.asyncio
async def test_firmware_releases_latest_success(monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        assert force_refresh is False
        return {
            "source": "github_releases",
            "repo": "datascale-ai/inksight",
            "cached": True,
            "count": 2,
            "releases": [
                {"version": "1.2.3", "tag": "v1.2.3"},
                {"version": "1.2.2", "tag": "v1.2.2"},
            ],
        }

    monkeypatch.setattr(index, "_load_firmware_releases", _fake_loader)
    payload = await index.firmware_releases_latest(refresh=False)
    assert payload["latest"]["version"] == "1.2.3"
    assert payload["cached"] is True


@pytest.mark.asyncio
async def test_firmware_releases_latest_not_found(monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        return {
            "source": "github_releases",
            "repo": "datascale-ai/inksight",
            "cached": False,
            "count": 0,
            "releases": [],
        }

    monkeypatch.setattr(index, "_load_firmware_releases", _fake_loader)
    resp = await index.firmware_releases_latest(refresh=False)
    assert resp.status_code == 404
    assert b"firmware_release_not_found" in resp.body


@pytest.mark.asyncio
async def test_firmware_releases_fetch_failed(monkeypatch):
    async def _fake_loader(force_refresh: bool = False):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(index, "_load_firmware_releases", _fake_loader)
    resp = await index.firmware_releases(refresh=False)
    assert resp.status_code == 503
    assert b"firmware_release_fetch_failed" in resp.body


@pytest.mark.asyncio
async def test_firmware_validate_url_success(monkeypatch):
    async def _fake_validate(url: str):
        assert url == "https://example.com/fw.bin"
        return {"ok": True, "reachable": True, "status_code": 200}

    monkeypatch.setattr(index, "_validate_firmware_url", _fake_validate)
    payload = await index.firmware_validate_url(url="https://example.com/fw.bin")
    assert payload["ok"] is True
    assert payload["reachable"] is True


@pytest.mark.asyncio
async def test_firmware_validate_url_invalid(monkeypatch):
    async def _fake_validate(url: str):
        raise ValueError("firmware URL should point to a .bin file")

    monkeypatch.setattr(index, "_validate_firmware_url", _fake_validate)
    resp = await index.firmware_validate_url(url="https://example.com/fw.txt")
    assert resp.status_code == 400
    assert b"invalid_firmware_url" in resp.body


@pytest.mark.asyncio
async def test_firmware_validate_url_unreachable(monkeypatch):
    async def _fake_validate(url: str):
        raise RuntimeError("firmware URL is not reachable: 404")

    monkeypatch.setattr(index, "_validate_firmware_url", _fake_validate)
    resp = await index.firmware_validate_url(url="https://example.com/fw.bin")
    assert resp.status_code == 503
    assert b"firmware_url_unreachable" in resp.body
