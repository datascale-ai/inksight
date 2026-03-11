from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request

from api.shared import ensure_web_or_device_access
from core.auth import require_admin
from core.stats_store import get_device_stats, get_render_history, get_stats_overview

router = APIRouter(tags=["stats"])


@router.get("/stats/overview")
async def stats_overview(admin_auth: None = Depends(require_admin)):
    return await get_stats_overview()


@router.get("/stats/{mac}")
async def stats_device(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return await get_device_stats(mac)


@router.get("/stats/{mac}/renders")
async def stats_renders(
    mac: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    return {"mac": mac, "renders": await get_render_history(mac, limit, offset)}
