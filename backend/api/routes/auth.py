from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from core.auth import clear_session_cookie, create_session_token, require_user, set_session_cookie
from core.config_store import authenticate_user, create_user

router = APIRouter(tags=["auth"])


@router.post("/auth/register")
async def auth_register(body: dict, response: Response):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or len(username) < 2 or len(username) > 30:
        return JSONResponse({"error": "用户名长度须为 2-30 字符"}, status_code=400)
    if len(password) < 4:
        return JSONResponse({"error": "密码至少 4 位"}, status_code=400)
    user_id = await create_user(username, password)
    if user_id is None:
        return JSONResponse({"error": "用户名已存在"}, status_code=409)
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
