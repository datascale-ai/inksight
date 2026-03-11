from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse

from api.shared import require_membership_access
from core.auth import require_user, validate_mac_param
from core.config_store import (
    approve_access_request,
    bind_device,
    get_device_members,
    get_device_owner,
    get_pending_requests_for_owner,
    get_user_by_username,
    get_user_devices,
    reject_access_request,
    revoke_device_member,
    share_device_with_user,
    unbind_device,
)

router = APIRouter(tags=["user"])


@router.get("/user/devices")
async def list_user_devices(user_id: int = Depends(require_user)):
    return {"devices": await get_user_devices(user_id)}


@router.post("/user/devices")
async def bind_user_device(body: dict, user_id: int = Depends(require_user)):
    mac = validate_mac_param((body.get("mac") or "").strip().upper())
    nickname = (body.get("nickname") or "").strip()
    if not mac:
        return JSONResponse({"error": "MAC 地址不能为空"}, status_code=400)
    return {"ok": True, **await bind_device(user_id, mac, nickname)}


@router.delete("/user/devices/{mac}")
async def unbind_user_device(mac: str, user_id: int = Depends(require_user)):
    result = await unbind_device(user_id, mac.upper())
    if result == "not_found":
        return JSONResponse({"error": "设备未绑定"}, status_code=404)
    if result == "owner_has_members":
        return JSONResponse({"error": "owner 仍有共享成员，无法解绑"}, status_code=409)
    return {"ok": True}


@router.get("/user/devices/requests")
async def list_device_requests(user_id: int = Depends(require_user)):
    return {"requests": await get_pending_requests_for_owner(user_id)}


@router.post("/user/devices/requests/{request_id}/approve")
async def approve_device_request(request_id: int, user_id: int = Depends(require_user)):
    membership = await approve_access_request(request_id, user_id)
    if not membership:
        return JSONResponse({"error": "请求不存在或无法批准"}, status_code=404)
    return {"ok": True, "membership": membership}


@router.post("/user/devices/requests/{request_id}/reject")
async def reject_device_request(request_id: int, user_id: int = Depends(require_user)):
    ok = await reject_access_request(request_id, user_id)
    if not ok:
        return JSONResponse({"error": "请求不存在或无法拒绝"}, status_code=404)
    return {"ok": True}


@router.get("/user/devices/{mac}/members")
async def list_device_members_route(
    mac: str,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    await require_membership_access(request, mac.upper(), ink_session)
    members = await get_device_members(mac.upper())
    owner = await get_device_owner(mac.upper())
    return {"mac": mac.upper(), "members": members, "owner_user_id": owner["user_id"] if owner else None}


@router.post("/user/devices/{mac}/share")
async def share_device_access(
    mac: str,
    body: dict,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    owner = await require_membership_access(request, mac.upper(), ink_session, owner_only=True)
    username = str(body.get("username") or "").strip()
    if not username:
        return JSONResponse({"error": "用户名不能为空"}, status_code=400)
    target_user = await get_user_by_username(username)
    if not target_user:
        return JSONResponse({"error": "目标用户不存在"}, status_code=404)
    return {"ok": True, **await share_device_with_user(owner["user_id"], mac.upper(), target_user["id"])}


@router.delete("/user/devices/{mac}/members/{target_user_id}")
async def remove_device_member(
    mac: str,
    target_user_id: int,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    owner = await require_membership_access(request, mac.upper(), ink_session, owner_only=True)
    ok = await revoke_device_member(owner["user_id"], mac.upper(), target_user_id)
    if not ok:
        return JSONResponse({"error": "成员不存在或无法移除"}, status_code=404)
    return {"ok": True}
