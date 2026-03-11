from __future__ import annotations

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from api.shared import GITHUB_OWNER, GITHUB_REPO, load_firmware_releases, validate_firmware_url

router = APIRouter(tags=["firmware"])


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
