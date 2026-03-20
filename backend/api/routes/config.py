from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, Request
from fastapi.responses import JSONResponse

from api.shared import ensure_web_or_device_access, logger
from core.auth import is_admin_authorized, require_admin, validate_mac_param
from core.config_store import (
    activate_config,
    get_active_config,
    get_or_create_alert_token,
    get_config_history,
    save_config,
    set_pending_refresh,
    update_focus_listening,
    update_device_state,
)
from core.schemas import ConfigRequest, ConfigSaveResponse

router = APIRouter(tags=["config"])


@router.post("/config", response_model=ConfigSaveResponse)
async def post_config(
    request: Request,
    body: ConfigRequest,
    x_inksight_client: Optional[str] = Header(default=None),
    x_device_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    data = body.model_dump()
    mac = data["mac"]
    if not is_admin_authorized(authorization):
        await ensure_web_or_device_access(
            request,
            mac,
            x_device_token,
            ink_session,
            allow_device_token=True,
        )
    modes = data.get("modes", [])
    logger.info(
        "[CONFIG SAVE REQUEST] source=%s mac=%s modes=%s refresh_strategy=%s",
        x_inksight_client or "unknown",
        mac,
        len(modes) if isinstance(modes, list) else 0,
        data.get("refresh_strategy"),
    )
    config_id = await save_config(mac, data)
    await update_device_state(mac, runtime_mode="interval")
    await set_pending_refresh(mac, True)

    saved_config = await get_active_config(mac)
    if saved_config:
        logger.info(
            "[CONFIG VERIFY] Saved config id=%s refresh_strategy=%s",
            saved_config.get("id"),
            saved_config.get("refresh_strategy"),
        )

    return ConfigSaveResponse(ok=True, config_id=config_id)


@router.get("/config/{mac}")
async def get_config(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    # FastAPI 会自动解码 URL 编码的路径参数，但需要验证 MAC 格式
    logger.debug(f"[CONFIG GET] Received MAC: {mac} (raw)")
    try:
        mac = validate_mac_param(mac)
        logger.debug(f"[CONFIG GET] Validated MAC: {mac}")
    except Exception as e:
        logger.warning(f"[CONFIG GET] Invalid MAC format: {mac}, error: {e}")
        raise
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    config = await get_active_config(mac)
    if not config:
        return JSONResponse({"error": "no config found"}, status_code=404)
    config.pop("llm_api_key", None)
    config.pop("image_api_key", None)
    return config


@router.get("/config/{mac}/history")
async def get_config_history_route(
    mac: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    mac = validate_mac_param(mac)
    await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    history = await get_config_history(mac)
    for cfg in history:
        cfg.pop("llm_api_key", None)
        cfg.pop("image_api_key", None)
    return {"mac": mac, "configs": history}


@router.put("/config/{mac}/activate/{config_id}")
async def activate_config_route(
    mac: str,
    config_id: int,
    admin_auth: None = Depends(require_admin),
):
    mac = validate_mac_param(mac)
    ok = await activate_config(mac, config_id)
    if not ok:
        return JSONResponse({"error": "config not found"}, status_code=404)
    return {"ok": True}


@router.patch("/config/{mac}/focus-listening")
async def patch_focus_listening(
    mac: str,
    request: Request,
    enabled: bool = True,
    x_device_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    """轻量级端点：仅更新 focus_listening；开启时如无 alert_token 则自动生成并返回。"""
    mac = validate_mac_param(mac)
    if not is_admin_authorized(authorization):
        await ensure_web_or_device_access(
            request,
            mac,
            x_device_token,
            ink_session,
            allow_device_token=True,
        )

    ok = await update_focus_listening(mac, bool(enabled))
    if not ok:
        return JSONResponse({"error": "no_active_config"}, status_code=404)

    token = None
    if enabled:
        token = await get_or_create_alert_token(mac, regenerate=False)

    return {"ok": True, "is_focus_listening": bool(enabled), "alert_token": token}
