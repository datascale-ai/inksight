from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from api.shared import (
    require_membership_access,
    validate_firmware_url,
)
from core.auth import require_device_token
from core.config_store import get_device_state as _get_device_state_row, update_device_state
from core.stats_store import get_latest_heartbeat


router = APIRouter(tags=["device-ota"])


def _build_firmware_proxy_url(request: Request, version: str, mac: str) -> str:
    """Build the backend firmware proxy URL for a given version and device MAC."""
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
        or ""
    ).strip()
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip()
    base = f"{scheme}://{host}"
    return f"{base}/api/firmware/download/{version.lstrip('v')}?mac={mac}"


class OTATriggerRequest(BaseModel):
    download_url: str = Field(..., description="Firmware .bin download URL")
    version: str = Field(..., description="Target firmware version")


class OTAProgressRequest(BaseModel):
    progress: int = Field(..., ge=0, le=100, description="OTA progress percentage")
    result: Optional[str] = Field(default=None, description="OTA result: 'downloading', 'flashing', 'success', 'failed:reason'")


@router.post("/device/{mac}/ota")
async def trigger_ota(
    mac: str,
    req: OTATriggerRequest,
    request: Request,
    ink_session: Optional[str] = None,
):
    # 1. Owner authentication
    await require_membership_access(request, mac, ink_session, owner_only=True)

    # 2. Check device is online and in active mode
    state = await _get_device_state_row(mac)
    latest_heartbeat = await get_latest_heartbeat(mac)
    is_online = await _is_device_online(state, latest_heartbeat)
    runtime_mode = (state.get("runtime_mode") or "interval").strip().lower()

    if not is_online:
        raise HTTPException(
            status_code=403,
            detail="设备不在线，请确保设备已连接 Wi-Fi 后重试",
        )

    if runtime_mode != "active":
        raise HTTPException(
            status_code=403,
            detail="设备未处于活跃模式，请在设备旁按一次按钮唤醒设备后重试",
        )

    # 3. Validate the GitHub CDN URL so we can confirm it's reachable before
    #    sending a task to the device.  The proxy endpoint uses this to fetch.
    #    We only validate if it looks like a GitHub URL; proxy URLs bypass this.
    ota_url = _build_firmware_proxy_url(request, req.version, mac)
    if req.download_url and not req.download_url.startswith("/"):
        try:
            url_check = await validate_firmware_url(req.download_url)
            if not url_check.get("reachable"):
                raise HTTPException(status_code=400, detail="固件 URL 不可达")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except (RuntimeError, Exception) as exc:
            raise HTTPException(status_code=503, detail=f"固件 URL 校验失败: {exc}")

    # 4. Write OTA task
    await update_device_state(
        mac,
        pending_ota=1,
        ota_version=req.version,
        ota_url=ota_url,
        ota_progress=0,
        ota_result="",
    )

    return {
        "ok": True,
        "message": "已下发刷机指令，设备即将开始升级",
    }


@router.get("/device/{mac}/ota/status")
async def get_ota_status(
    mac: str,
    request: Request,
    ink_session: Optional[str] = None,
):
    await require_membership_access(request, mac, ink_session)
    state = await _get_device_state_row(mac)
    latest_heartbeat = await get_latest_heartbeat(mac)
    is_online = await _is_device_online(state, latest_heartbeat)
    return {
        "pending_ota": state.get("pending_ota", 0),
        "ota_version": state.get("ota_version", ""),
        "ota_url": state.get("ota_url", ""),
        "ota_progress": state.get("ota_progress", 0),
        "ota_result": state.get("ota_result", ""),
        "is_online": is_online,
        "runtime_mode": state.get("runtime_mode", "interval"),
    }


@router.post("/device/{mac}/ota/cancel")
async def cancel_ota(
    mac: str,
    request: Request,
    ink_session: Optional[str] = None,
):
    await require_membership_access(request, mac, ink_session, owner_only=True)
    state = await _get_device_state_row(mac)
    ota_result = state.get("ota_result", "")
    if ota_result in ("downloading", "flashing"):
        raise HTTPException(status_code=403, detail="刷机已开始，无法取消")
    await update_device_state(
        mac,
        pending_ota=0,
        ota_version="",
        ota_url="",
        ota_progress=0,
        ota_result="",
    )
    return {"ok": True}


@router.post("/device/{mac}/ota/progress")
async def report_ota_progress(
    mac: str,
    req: OTAProgressRequest,
    request: Request,
    x_device_token: Optional[str] = Header(None),
):
    # Device token auth
    await require_device_token(mac, x_device_token)

    ota_result = req.result if req.result else ""

    # Once the device reports "downloading", the OTA has started on the device.
    # Clear pending_ota immediately so a failed/flashed OTA can never re-trigger,
    # even if the device retries its poll loop before the final result is posted.
    clear_pending = (
        ota_result in ("downloading", "flashing")
        or (ota_result.startswith("failed:") and req.progress == 0)
    )
    if clear_pending:
        await update_device_state(
            mac,
            pending_ota=0,
            ota_progress=req.progress,
            ota_result=ota_result if ota_result else None,
        )
    else:
        await update_device_state(
            mac,
            ota_progress=req.progress,
            ota_result=ota_result if ota_result else None,
        )
    return {"ok": True}


async def _is_device_online(state: Optional[dict], latest_heartbeat: Optional[dict]) -> bool:
    """Determine if a device is online based on heartbeat (primary) or state poll (fallback)."""
    if not state:
        return False

    from datetime import datetime

    # Primary: check heartbeat table (updated every render/poll cycle)
    if latest_heartbeat:
        last_seen = latest_heartbeat.get("created_at") or ""
        if last_seen:
            try:
                last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                delta = datetime.now(last_dt.tzinfo) - last_dt if last_dt.tzinfo else datetime.now() - last_dt
                if delta.total_seconds() < 120:  # Online if seen within 2 minutes
                    return True
            except (ValueError, TypeError):
                pass

    # Fallback: check last_state_poll_at (device-to-server state polling)
    last_poll = state.get("last_state_poll_at") or ""
    if last_poll:
        try:
            last_dt = datetime.fromisoformat(last_poll.replace("Z", "+00:00"))
            delta = datetime.now(last_dt.tzinfo) - last_dt if last_dt.tzinfo else datetime.now() - last_dt
            return delta.total_seconds() < 120
        except (ValueError, TypeError):
            pass

    return False
