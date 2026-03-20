from __future__ import annotations

import aiosqlite
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import JSONResponse

from api.shared import require_membership_access
from core.auth import require_user, validate_mac_param
from core.config_store import (
    approve_access_request,
    bind_device,
    delete_user_llm_config,
    get_device_members,
    get_device_owner,
    get_pending_requests_for_owner,
    get_user_api_quota,
    get_user_by_username,
    get_user_devices,
    get_user_llm_config,
    reject_access_request,
    revoke_device_member,
    save_user_llm_config,
    share_device_with_user,
    unbind_device,
)
from core.db import get_main_db

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


@router.get("/user/profile")
async def get_user_profile(user_id: int = Depends(require_user)):
    """获取当前用户的个人信息，包括额度、角色和 LLM 配置。"""
    from core.db import get_main_db
    
    db = await get_main_db()
    
    # 获取用户基本信息
    cursor = await db.execute(
        "SELECT id, username, phone, email, role FROM users WHERE id = ?",
        (user_id,),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    
    # 获取额度信息
    quota = await get_user_api_quota(user_id)
    
    # 获取 LLM 配置
    llm_config = await get_user_llm_config(user_id)
    
    return {
        "user_id": user_row[0],
        "username": user_row[1],
        "phone": user_row[2] or "",
        "email": user_row[3] or "",
        "role": user_row[4] or "user",
        "free_quota_remaining": quota.get("free_quota_remaining", 0) if quota else 0,
        "llm_config": llm_config,
    }


@router.put("/user/profile/llm")
async def save_user_llm_config_route(body: dict, user_id: int = Depends(require_user)):
    """保存用户级别的 LLM 配置。"""
    llm_access_mode = (body.get("llm_access_mode") or "preset").strip().lower()
    provider = (body.get("provider") or "deepseek").strip()
    model = (body.get("model") or "").strip()
    api_key = (body.get("api_key") or "").strip()
    base_url = (body.get("base_url") or "").strip()
    image_provider = (body.get("image_provider") or "aliyun").strip()
    image_model = (body.get("image_model") or "").strip()
    image_api_key = (body.get("image_api_key") or "").strip()

    # 表单校验：
    # - preset：provider/model/api_key 必填，base_url 可空
    # - custom_openai：model/api_key/base_url 必填，provider 忽略（统一存为 openai_compat）
    # 图像配置保持原样：必填（image_provider/image_model/image_api_key）
    allowed_modes = {"preset", "custom_openai"}
    if llm_access_mode not in allowed_modes:
        return JSONResponse({"error": f"llm_access_mode 无效：{llm_access_mode}"}, status_code=400)

    missing: list[str] = []
    if llm_access_mode == "preset":
        if not provider:
            missing.append("provider")
        if not model:
            missing.append("model")
        if not api_key:
            missing.append("api_key")
        # base_url 可为空
    else:
        # custom_openai
        if not model:
            missing.append("model")
        if not api_key:
            missing.append("api_key")
        if not base_url:
            missing.append("base_url")
        provider = "openai_compat"

    if not image_provider:
        missing.append("image_provider")
    if not image_model:
        missing.append("image_model")
    if not image_api_key:
        missing.append("image_api_key")
    if missing:
        extra = "（base_url 可为空）" if llm_access_mode == "preset" else ""
        return JSONResponse({"error": f"缺少必填字段：{', '.join(missing)}{extra}"}, status_code=400)

    # minimal URL sanity check for custom base_url
    if llm_access_mode == "custom_openai" and not (base_url.startswith("http://") or base_url.startswith("https://")):
        return JSONResponse({"error": "base_url 必须以 http:// 或 https:// 开头"}, status_code=400)
    
    ok = await save_user_llm_config(
        user_id,
        llm_access_mode,
        provider,
        model,
        api_key,
        base_url,
        image_provider,
        image_model,
        image_api_key,
    )
    if not ok:
        return JSONResponse({"error": "保存配置失败"}, status_code=500)
    
    return {"ok": True, "message": "配置已保存"}


@router.delete("/user/profile/llm")
async def delete_user_llm_config_route(user_id: int = Depends(require_user)):
    """删除用户级别的 LLM 配置（BYOK）。"""
    deleted = await delete_user_llm_config(user_id)
    # 幂等：即使本来就没有配置，也返回 ok，避免前端交互分叉
    return {"ok": True, "deleted": bool(deleted), "message": "配置已删除"}


@router.post("/user/redeem")
async def redeem_invite_code(body: dict, user_id: int = Depends(require_user)):
    """兑换邀请码，为当前用户增加 50 次免费 LLM 调用额度。"""
    invite_code = (body.get("invite_code") or "").strip()
    
    if not invite_code:
        return JSONResponse({"error": "邀请码不能为空"}, status_code=400)
    
    db = await get_main_db()
    
    try:
        # 显式开启事务，确保「校验邀请码 -> 标记邀请码 -> 增加额度」原子完成
        await db.execute("BEGIN")
        
        # 1) 校验邀请码是否存在且未使用
        cursor = await db.execute(
            "SELECT id, code, is_used FROM invitation_codes WHERE code = ? LIMIT 1",
            (invite_code,),
        )
        row = await cursor.fetchone()
        if not row:
            await db.rollback()
            return JSONResponse({"error": "邀请码无效"}, status_code=400)
        if row[2]:  # is_used
            await db.rollback()
            return JSONResponse({"error": "邀请码已被使用"}, status_code=409)
        
        # 2) 标记邀请码已被当前用户使用
        await db.execute(
            """
            UPDATE invitation_codes
            SET is_used = 1, used_by_user_id = ?
            WHERE code = ?
            """,
            (user_id, invite_code),
        )
        
        # 3) 增加用户的免费额度（+50 次）
        # 先确保 api_quotas 记录存在
        await db.execute(
            """
            INSERT OR IGNORE INTO api_quotas (user_id, total_calls_made, free_quota_remaining)
            VALUES (?, 0, 0)
            """,
            (user_id,),
        )
        # 增加额度（使用原子更新，避免并发问题）
        await db.execute(
            """
            UPDATE api_quotas
            SET free_quota_remaining = free_quota_remaining + 50
            WHERE user_id = ?
            """,
            (user_id,),
        )
        
        await db.commit()
        
        # 获取更新后的额度信息
        quota = await get_user_api_quota(user_id)
        return {
            "ok": True,
            "message": "邀请码兑换成功，已获得 50 次免费 LLM 调用额度",
            "free_quota_remaining": quota.get("free_quota_remaining", 0) if quota else 0,
        }
    except aiosqlite.IntegrityError:
        await db.rollback()
        return JSONResponse({"error": "邀请码已被使用"}, status_code=409)
    except Exception as e:
        await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[REDEEM_INVITE] Failed to redeem invite code: {e}", exc_info=True)
        return JSONResponse({"error": "兑换失败，请稍后重试"}, status_code=500)
