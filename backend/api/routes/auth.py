from __future__ import annotations

import re
from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from core.auth import clear_session_cookie, create_session_token, require_user, set_session_cookie
from core.config_store import authenticate_user, _hash_password, get_user_api_quota
from core.db import get_main_db

router = APIRouter(tags=["auth"])


_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@router.post("/auth/register")
async def auth_register(body: dict, response: Response):
    """
    用户注册接口。

    说明：
    - 注册时不再支持输入邀请码，邀请码仅通过单独的兑换接口使用（/api/user/redeem）
    - 新用户注册后统一获得 50 次免费 LLM 调用额度
    """
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    phone = (body.get("phone") or "").strip()
    email = (body.get("email") or "").strip()

    if not username or len(username) < 2 or len(username) > 30:
        return JSONResponse({"error": "用户名长度须为 2-30 字符"}, status_code=400)
    if len(password) < 4:
        return JSONResponse({"error": "密码至少 4 位"}, status_code=400)

    # 至少提供一个合法的手机号或邮箱
    if not phone and not email:
        return JSONResponse({"error": "手机号或邮箱至少填写一个"}, status_code=400)
    if phone and not _PHONE_RE.match(phone):
        return JSONResponse({"error": "手机号格式不正确"}, status_code=400)
    if email and not _EMAIL_RE.match(email):
        return JSONResponse({"error": "邮箱格式不正确"}, status_code=400)

    db = await get_main_db()
    now = datetime.now().isoformat()
    pw_hash, _ = _hash_password(password)

    try:
        # 显式开启事务，确保「创建用户 -> 初始化额度」原子完成
        await db.execute("BEGIN")

        # 1) 创建用户记录（用户名 + 手机/邮箱）
        cursor = await db.execute(
            """
            INSERT INTO users (username, password_hash, phone, email, role, created_at)
            VALUES (?, ?, ?, ?, 'user', ?)
            """,
            (
                username,
                pw_hash,
                phone or None,
                email or None,
                now,
            ),
        )
        user_id = cursor.lastrowid

        # 2) 初始化 API 调用额度（统一给 50 次）
        initial_quota = 50
        await db.execute(
            """
            INSERT OR IGNORE INTO api_quotas (user_id, total_calls_made, free_quota_remaining)
            VALUES (?, 0, ?)
            """,
            (user_id, initial_quota),
        )

        await db.commit()
    except aiosqlite.IntegrityError:
        # 用户名 / 手机号 / 邮箱任一唯一字段冲突
        await db.rollback()
        return JSONResponse({"error": "用户名或手机号/邮箱已存在"}, status_code=409)
    except Exception:
        await db.rollback()
        raise

    token = create_session_token(user_id, username)
    set_session_cookie(response, token)
    return {"ok": True, "user_id": user_id, "username": username, "token": token}


@router.post("/auth/login")
async def auth_login(body: dict, response: Response):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = await authenticate_user(username, password)
    if not user:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    token = create_session_token(user["id"], user["username"])
    set_session_cookie(response, token)
    return {"ok": True, "user_id": user["id"], "username": user["username"], "token": token}


@router.get("/auth/me")
async def auth_me(user_id: int = Depends(require_user)):
    from core.db import get_main_db

    db = await get_main_db()
    cursor = await db.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return {"user_id": row[0], "username": row[1], "created_at": row[2]}


@router.post("/auth/logout")
async def auth_logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.post("/auth/redeem-invite-code")
async def auth_redeem_invite_code(body: dict, user_id: int = Depends(require_user)):
    """兑换邀请码，为当前用户增加 50 次免费 LLM 调用额度"""
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
        logger = __import__("logging").getLogger(__name__)
        logger.error(f"[REDEEM_INVITE] Failed to redeem invite code: {e}", exc_info=True)
        return JSONResponse({"error": "兑换失败，请稍后重试"}, status_code=500)
