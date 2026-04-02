from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.shared import GITHUB_OWNER, GITHUB_REPO, load_firmware_releases, validate_firmware_url

router = APIRouter(tags=["firmware"])
logger = logging.getLogger("inksight")


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


async def _stream_firmware_chunk(httpx_client: httpx.AsyncClient, github_url: str):
    """Yield chunks from the GitHub CDN as they arrive (streaming passthrough)."""
    async with httpx_client.stream("GET", github_url, follow_redirects=True) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes(chunk_size=8192):
            if chunk:
                yield chunk


@router.get("/firmware/download/{version}")
async def firmware_download(version: str, mac: str = Query(...)):
    """
    Proxy firmware .bin download from GitHub CDN to ESP32.
    The ESP32 cannot reach GitHub CDN directly (especially in Mainland China), so this
    endpoint streams the GitHub response through to the device.
    """
    # Find the matching release by version tag
    try:
        releases_data = await load_firmware_releases()
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.error("[FIRMWARE] download proxy: failed to load releases: %s", exc)
        return JSONResponse(
            {"error": "release_list_unavailable", "message": str(exc)},
            status_code=503,
        )

    releases = releases_data.get("releases", [])
    target = None
    for rel in releases:
        if rel.get("version") == version or rel.get("tag").lstrip("v") == version.lstrip("v"):
            target = rel
            break

    if not target:
        # Fallback: search by tag name (some releases may share the same numeric version)
        for rel in releases:
            if rel.get("tag") == version or rel.get("tag") == f"v{version}":
                target = rel
                break

    if not target:
        return JSONResponse(
            {
                "error": "firmware_version_not_found",
                "message": f"No firmware release found for version '{version}'",
                "available": [r.get("version") for r in releases[:5]],
            },
            status_code=404,
        )

    github_url = target.get("download_url", "")
    if not github_url:
        return JSONResponse(
            {"error": "download_url_missing", "message": "Release has no download_url"},
            status_code=500,
        )

    logger.info("[FIRMWARE] download proxy: streaming %s to device %s", github_url, mac)

    client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0), follow_redirects=True)

    try:
        return StreamingResponse(
            _stream_firmware_chunk(client, github_url),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{target.get("asset_name", "firmware.bin")}"',
                "X-Firmware-Version": target.get("version", version),
                "X-Firmware-Size": str(target.get("size_bytes", "")),
                "Cache-Control": "no-store",
            },
        )
    except httpx.HTTPStatusError as exc:
        logger.error("[FIRMWARE] download proxy: GitHub returned %s: %s", exc.response.status_code, exc)
        await client.aclose()
        return JSONResponse(
            {"error": "github_fetch_failed", "message": f"GitHub returned {exc.response.status_code}"},
            status_code=502,
        )
    except httpx.HTTPError as exc:
        logger.error("[FIRMWARE] download proxy: network error: %s", exc)
        await client.aclose()
        return JSONResponse(
            {"error": "proxy_error", "message": str(exc)},
            status_code=502,
        )
    except Exception as exc:
        logger.error("[FIRMWARE] download proxy: unexpected error: %s", exc)
        await client.aclose()
        return JSONResponse(
            {"error": "proxy_error", "message": str(exc)},
            status_code=500,
        )
