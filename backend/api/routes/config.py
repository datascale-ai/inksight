from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, Request
from fastapi.responses import JSONResponse

from api.shared import ensure_web_or_device_access, logger
from core.auth import is_admin_authorized, require_admin
from core.config_store import activate_config, get_active_config, get_config_history, save_config, update_device_state
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
    ok = await activate_config(mac, config_id)
    if not ok:
        return JSONResponse({"error": "config not found"}, status_code=404)
    return {"ok": True}
