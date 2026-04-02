import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional

from api.shared import (
    GITHUB_OWNER,
    GITHUB_REPO,
    load_firmware_releases,
    validate_firmware_url,
)

router = APIRouter(tags=["firmware"])
logger = logging.getLogger(__name__)

# ── Concurrent OTA download limiter ─────────────────────────
OTA_MAX_CONCURRENT = int(os.getenv("OTA_MAX_CONCURRENT", "3"))
_ota_semaphore: Optional[asyncio.Semaphore] = None


def _get_ota_semaphore() -> asyncio.Semaphore:
    global _ota_semaphore
    if _ota_semaphore is None:
        _ota_semaphore = asyncio.Semaphore(OTA_MAX_CONCURRENT)
    return _ota_semaphore


def _build_backend_base(request: Request) -> str:
    """Build the backend base URL for firmware proxy endpoints."""
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
        or ""
    ).strip()
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip()
    return f"{scheme}://{host}"


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}


@router.get("/firmware/releases")
async def firmware_releases(refresh: bool = Query(default=False)):
    try:
        return await load_firmware_releases(force_refresh=refresh)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": "firmware_release_fetch_failed",
                "message": str(exc),
                "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            },
            status_code=503,
        )


@router.get("/firmware/releases/latest")
async def firmware_releases_latest(refresh: bool = Query(default=False)):
    try:
        data = await load_firmware_releases(force_refresh=refresh)
        releases = data.get("releases", [])
        if not releases:
            return JSONResponse(
                {
                    "error": "firmware_release_not_found",
                    "message": "No published firmware release with .bin asset found",
                    "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
                },
                status_code=404,
            )
        return {
            "source": data.get("source"),
            "repo": data.get("repo"),
            "cached": data.get("cached", False),
            "latest": releases[0],
        }
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return JSONResponse(
            {
                "error": "firmware_release_fetch_failed",
                "message": str(exc),
                "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            },
            status_code=503,
        )


@router.get("/firmware/validate-url")
async def firmware_validate_url(url: str = Query(..., description="Firmware .bin URL")):
    try:
        return await validate_firmware_url(url)
    except ValueError as exc:
        return JSONResponse(
            {"error": "invalid_firmware_url", "message": str(exc), "url": url},
            status_code=400,
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        return JSONResponse(
            {"error": "firmware_url_unreachable", "message": str(exc), "url": url},
            status_code=503,
        )


# ── Firmware download proxy (GitHub CDN → ESP32) ─────────────

@router.get("/firmware/download/{version}")
async def firmware_download(
    version: str,
    request: Request,
    mac: str = Query(..., description="Device MAC address"),
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
):
    """
    Proxy firmware download from GitHub CDN to the ESP32 device.

    The ESP32 may fail TLS handshake with GitHub's DigiCert chain because it
    only has Let's Encrypt CA built-in. This endpoint streams the binary
    through the backend so the ESP32 only needs to trust one server certificate.

    Concurrency is limited by OTA_MAX_CONCURRENT (default 3) to protect the
    backend from simultaneous large outbound transfers. If the limit is hit,
    the device's OTA state is cleared so the mobile app can show a retry prompt.
    """
    sem = _get_ota_semaphore()
    is_zh = (accept_language or "").lower().startswith("zh")

    # Try to grab a concurrent slot (wait up to 0.5s before giving up)
    try:
        await asyncio.wait_for(sem.acquire(), timeout=0.5)
    except asyncio.TimeoutError:
        logger.warning(
            "[OTA DOWNLOAD] Concurrency limit (%d) reached, rejecting version=%s mac=%s",
            OTA_MAX_CONCURRENT,
            version,
            mac,
        )
        # Clear device OTA state so the app can prompt a retry
        from core.config_store import update_device_state

        await update_device_state(
            mac,
            pending_ota=0,
            ota_version="",
            ota_url="",
            ota_progress=0,
            ota_result="failed:concurrent_limit",
        )
        # Return a JSON response so both ESP32 and mobile polling can parse it
        return JSONResponse(
            status_code=503,
            content={
                "error": "concurrent_limit_reached",
                "detail": (
                    "服务器同时刷机人数已达上限，请稍后重试"
                    if is_zh
                    else "Too many firmware updates in progress. Please try again shortly."
                ),
            },
            headers={"Content-Type": "application/json"},
        )

    # Find the firmware asset for this version
    try:
        data = await load_firmware_releases(force_refresh=False)
    except Exception as exc:
        sem.release()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to load firmware releases: {exc}",
        )

    releases: list[dict] = data.get("releases", [])
    asset: Optional[dict] = None
    for r in releases:
        if r.get("version") == version.lstrip("v"):
            asset = r
            break

    if not asset:
        sem.release()
        raise HTTPException(status_code=404, detail=f"Firmware version '{version}' not found")

    download_url = asset.get("download_url")
    if not download_url:
        sem.release()
        raise HTTPException(status_code=500, detail="Firmware asset has no download URL")

    # Fetch Content-Length first so the ESP32 always knows the download size.
    # A plain HEAD request (without following redirects) lands on the CDN redirect
    # page which returns 0 bytes and no Content-Length.  Use max_redirects=0 to
    # get the Location header, then HEAD the final URL.
    content_length: Optional[int] = None
    asset_size = asset.get("size_bytes")
    if isinstance(asset_size, int) and asset_size > 0:
        content_length = asset_size
    else:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), max_redirects=10) as client:
                redirected_url = download_url
                for _ in range(10):
                    head_resp = await client.head(redirected_url)
                    if head_resp.status_code in (301, 302, 303, 307, 308):
                        redirected_url = str(head_resp.headers.get("location", ""))
                        if not redirected_url:
                            break
                        if not redirected_url.startswith("http"):
                            from urllib.parse import urljoin
                            redirected_url = urljoin(redirected_url, redirected_url)
                    else:
                        break
                cl = head_resp.headers.get("content-length")
                if cl:
                    content_length = int(cl)
        except Exception as exc:
            logger.warning("[OTA DOWNLOAD] Could not determine Content-Length for %s: %s", download_url, exc)

    async def stream_and_release():
        """Stream firmware from GitHub CDN to the ESP32 as chunks arrive.

        Do NOT use client.stream() because it does not follow 302 redirects in
        httpx 0.11.1.  Instead, manually follow redirects and stream the final
        URL with a plain GET, yielding data as soon as each chunk arrives.
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                max_redirects=10,
            ) as client:
                # Follow redirects manually so we can stream the final response.
                url = download_url
                for _ in range(10):
                    resp = await client.get(url)
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location", "")
                        if not location:
                            break
                        if not location.startswith("http"):
                            from urllib.parse import urljoin
                            url = urljoin(url, location)
                        else:
                            url = location
                        # Release connection before following next hop.
                        await resp.aclose()
                    else:
                        break

                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    yield chunk
        except httpx.HTTPError as exc:
            logger.error(
                "[OTA DOWNLOAD] Upstream fetch failed version=%s mac=%s: %s",
                version,
                mac,
                exc,
            )
        except Exception as exc:
            logger.error(
                "[OTA DOWNLOAD] Unexpected streaming error version=%s mac=%s: %s",
                version,
                mac,
                exc,
            )
        finally:
            sem.release()
            logger.info(
                "[OTA DOWNLOAD] Stream done — slot released (version=%s mac=%s)",
                version,
                mac,
            )

    filename = asset.get("asset_name") or f"inksight-firmware-{version}.bin"
    response_headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Firmware-Version": version.lstrip("v"),
        "X-Device-MAC": mac,
    }
    if content_length is not None:
        response_headers["Content-Length"] = str(content_length)

    return StreamingResponse(
        stream_and_release(),
        media_type="application/octet-stream",
        headers=response_headers,
    )
