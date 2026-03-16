from __future__ import annotations

import io
import json as jsonlib
from pathlib import Path
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAIError

from api.shared import logger
from core.auth import require_admin, require_user, optional_user
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.config_store import remove_mode_from_all_configs
from core.context import get_date_context, get_weather
from core.mode_registry import CUSTOM_JSON_DIR, _validate_mode_def, get_registry
from core.config_store import (
    get_user_custom_modes,
    get_custom_mode,
    save_custom_mode,
    delete_custom_mode,
    consume_user_free_quota,
    ensure_user_api_quota,
    get_quota_owner_for_mac,
    get_user_role,
)

router = APIRouter(tags=["modes"])


@router.get("/modes")
async def list_modes(
    mac: str = Query(None, description="Device MAC address to filter custom modes"),
    user_id: int = Depends(optional_user),
):
    """
    List all modes. If user is authenticated, return builtin modes + that user's custom modes for the specified device.
    Otherwise, return all builtin modes + legacy file-based custom modes (for backward compatibility).
    """
    
    registry = get_registry()
    modes = []
    
    # Add custom modes first (before listing from registry to ensure device isolation)
    if user_id is not None:
        # If mac is provided, validate device ownership
        if mac:
            from core.config_store import has_active_membership
            mac = mac.upper()
            if not await has_active_membership(mac, user_id):
                # Device doesn't belong to user, return only builtin modes
                # Still need to list builtin modes
                for info in registry.list_modes(mac):
                    if info.source != "custom":
                        modes.append({
                            "mode_id": info.mode_id,
                            "display_name": info.display_name,
                            "icon": info.icon,
                            "cacheable": info.cacheable,
                            "description": info.description,
                            "source": info.source,
                            "settings_schema": info.settings_schema,
                        })
                return {"modes": modes}
        
        # IMPORTANT: Before loading modes for this device, we need to ensure clean state
        # The registry is global, so we need to unregister all modes for this device first
        # to prevent seeing modes from other devices that were previously loaded
        if mac:
            # Unregister all modes for this device to ensure clean state
            registry.unregister_device_modes(mac)
        
        # Load user's custom modes into registry (for immediate use in rendering)
        # Only load modes for the specific device if mac is provided, to avoid loading modes from other devices
        await registry.load_user_custom_modes(user_id, mac)

        # Return only this user's custom modes from database (filtered by device if mac provided)
        # 这里打印一下用于排查设备隔离：实际传入的 user_id 和 mac 是什么
        logger.info(
            "[MODES] list_modes DB query get_user_custom_modes(user_id=%s, mac=%s)",
            user_id,
            (mac or "").upper() if mac else None,
        )
        user_custom_modes = await get_user_custom_modes(user_id, mac)
        for mode_data in user_custom_modes:
            definition = mode_data["definition"]
            modes.append({
                "mode_id": mode_data["mode_id"],
                "display_name": definition.get("display_name", mode_data["mode_id"]),
                "icon": definition.get("icon", "star"),
                "cacheable": definition.get("cacheable", True),
                "description": definition.get("description", ""),
                "source": "custom",
                "settings_schema": definition.get("settings_schema", []),
            })
    
    # Always include builtin modes (and any custom modes now in registry for this device)
    # After loading user's custom modes, list_modes will only return modes for this device
    for info in registry.list_modes(mac):
        if info.source != "custom":
            modes.append({
                "mode_id": info.mode_id,
                "display_name": info.display_name,
                "icon": info.icon,
                "cacheable": info.cacheable,
                "description": info.description,
                "source": info.source,
                "settings_schema": info.settings_schema,
            })
    # Custom modes are now stored in database only, not loaded from files
    # Removed backward compatibility for file-based custom modes
    
    return {"modes": modes}


def _preview_payload(content: dict) -> dict:
    for key in ("quote", "text", "body", "summary", "question", "challenge", "interpretation"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return {"preview_text": value.strip()[:200], "content": content}
    return {"preview_text": "", "content": content}


@router.post("/modes/custom/preview")
async def custom_mode_preview(
    body: dict,
    user_id: int = Depends(optional_user),
    admin_auth: None = Depends(require_admin),
):
    mode_def = body.get("mode_def", body)
    if not mode_def.get("mode_id"):
        mode_def = dict(mode_def, mode_id="PREVIEW")
    screen_w = body.get("w", SCREEN_WIDTH)
    screen_h = body.get("h", SCREEN_HEIGHT)
    response_type = str(body.get("responseType", body.get("response_type", "image"))).strip().lower()

    # 解析 API key：优先使用用户级别配置，其次使用设备配置中的加密 key
    user_api_key = None
    user_image_api_key = None
    if user_id is not None:
        try:
            from core.config_store import get_user_llm_config

            user_cfg = await get_user_llm_config(user_id)
        except Exception:
            user_cfg = None
            logger.warning("[CUSTOM_PREVIEW] Failed to load user_llm_config for user_id=%s", user_id, exc_info=True)
        if user_cfg:
            user_api_key = (user_cfg.get("api_key") or "").strip() or None
            user_image_api_key = (user_cfg.get("image_api_key") or "").strip() or None

    device_api_key = None
    device_image_api_key = None
    mac = body.get("mac")

    from core.config_store import get_active_config

    if mac:
        config = await get_active_config(mac)
        if config:
            encrypted_key = config.get("llm_api_key", "")
            if encrypted_key:
                from core.crypto import decrypt_api_key

                decrypted = decrypt_api_key(encrypted_key)
                device_api_key = (decrypted or "").strip() or ""
            encrypted_image_key = config.get("image_api_key", "")
            if encrypted_image_key:
                from core.crypto import decrypt_api_key

                decrypted = decrypt_api_key(encrypted_image_key)
                device_image_api_key = (decrypted or "").strip() or ""

    try:
        from core.json_content import generate_json_mode_content
        from core.json_renderer import render_json_mode

        # ── 额度检查（按照 BILLING.md，custom preview 也算一次计费调用） ──────────────
        # 按“登录用户”计费：优先用 user_id，其次 mac owner，缺省则不计费
        quota_user_id: int | None = None
        if user_id is not None:
            quota_user_id = user_id
        elif mac:
            try:
                quota_user_id = await get_quota_owner_for_mac(mac)
            except Exception:
                quota_user_id = None

        # 是否使用用户自带 API Key（profile / 设备配置），为 True 时不扣费不拦截额度
        # effective_api_key 为 None 表示将会走环境变量中的“平台 Key”，此时需要按照免费额度计费
        effective_api_key = user_api_key if user_api_key is not None else device_api_key
        effective_image_api_key = user_image_api_key if user_image_api_key is not None else device_image_api_key
        using_user_key = effective_api_key is not None

        # 额度不足拦截：只有在使用平台 Key 且存在 quota_user_id 时才检查
        if quota_user_id is not None and not using_user_key:
            try:
                user_role = await get_user_role(quota_user_id)
            except Exception:
                user_role = None
            if user_role != "root":
                quota = await ensure_user_api_quota(quota_user_id)
                remaining = int(quota.get("free_quota_remaining") or 0) if quota else 0
                if remaining <= 0:
                    return JSONResponse(
                        {"error": "您的免费额度已用完，请输入邀请码获取更多额度"},
                        status_code=402,
                    )

        date_ctx = await get_date_context()
        weather = await get_weather()
        content = await generate_json_mode_content(
            mode_def,
            date_ctx=date_ctx,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            screen_w=screen_w,
            screen_h=screen_h,
            api_key=effective_api_key,
            image_api_key=effective_image_api_key,
        )
        if response_type == "json":
            return {
                "ok": True,
                "mode_id": mode_def.get("mode_id", "PREVIEW"),
                **_preview_payload(content),
            }
        img = render_json_mode(
            mode_def,
            content,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            battery_pct=100.0,
            screen_w=screen_w,
            screen_h=screen_h,
        )

        # 额度扣减：仅在使用平台 Key 时扣费，且 root 用户豁免
        if quota_user_id is not None and not using_user_key:
            try:
                user_role = await get_user_role(quota_user_id)
            except Exception:
                user_role = None
            if user_role != "root":
                await consume_user_free_quota(quota_user_id, amount=1)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        # 检查是否使用了默认值（使用英文避免编码问题）
        used_fallback = content.get("_used_fallback", False)
        status_msg = "model_generated" if not used_fallback else "fallback_used"
        
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="image/png",
            headers={"X-Preview-Status": status_msg}
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.exception("[CUSTOM_PREVIEW] Preview failed")
        return JSONResponse({"error": str(exc), "status": "生成失败"}, status_code=500)


@router.post("/modes/custom")
async def create_custom_mode(body: dict, user_id: int = Depends(require_user)):
    """Create a custom mode.

    - With `mac`: persist to DB with user+device isolation.
    - Without `mac`: fallback to legacy file-based custom mode (mobile editor compatibility).
    """
    mode_id = body.get("mode_id", "").upper()
    mac = body.get("mac", "").strip().upper()
    if not mode_id:
        return JSONResponse({"error": "mode_id is required"}, status_code=400)
    if not _validate_mode_def(body):
        return JSONResponse({"error": "Invalid mode definition"}, status_code=400)

    body["mode_id"] = mode_id
    registry = get_registry()
    if registry.is_builtin(mode_id):
        return JSONResponse(
            {"error": f"Cannot override builtin mode: {mode_id}"},
            status_code=409,
        )

    # Legacy path: no mac means file-based custom mode.
    if not mac:
        file_path = Path(CUSTOM_JSON_DIR) / f"{mode_id.lower()}.json"
        file_path.write_text(jsonlib.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        registry.unregister_custom(mode_id)
        loaded = registry.load_json_mode(str(file_path), source="custom")
        if not loaded:
            file_path.unlink(missing_ok=True)
            return JSONResponse({"error": "Failed to load mode definition"}, status_code=400)
        logger.info("[MODES] Created legacy custom mode %s for user %s", mode_id, user_id)
        return {"ok": True, "mode_id": mode_id}

    # Validate device ownership for DB path
    from core.config_store import has_active_membership
    if not await has_active_membership(mac, user_id):
        return JSONResponse(
            {"error": "设备不存在或无权访问"},
            status_code=403
        )

    # Save to database (with device)
    success = await save_custom_mode(user_id, mode_id, body, mac)
    if not success:
        return JSONResponse({"error": "Failed to save custom mode"}, status_code=500)

    # Load into registry for immediate use
    registry.unregister_custom(mode_id, mac)
    loaded = registry.load_custom_mode_from_dict(mode_id, body, source="custom", mac=mac)
    if not loaded:
        # Rollback database entry
        await delete_custom_mode(user_id, mode_id, mac)
        return JSONResponse({"error": "Failed to load mode definition"}, status_code=400)

    logger.info(f"[MODES] Created custom mode {mode_id} for user {user_id} on device {mac}")
    return {"ok": True, "mode_id": mode_id}


@router.get("/modes/custom/{mode_id}")
async def get_custom_mode_endpoint(
    mode_id: str,
    mac: str = Query(None, description="Device MAC address to filter custom modes"),
    user_id: int = Depends(require_user),
):
    """Get a custom mode for the current user and device.

    为了保证设备隔离：
    - 必须同时提供 mac；
    - 不再从全局注册表或本地文件中回退加载“同名模式”。
    """
    # Legacy path: no mac -> file-based custom mode.
    if not mac:
        registry = get_registry()
        mode = registry.get_json_mode(mode_id.upper())
        if not mode or mode.info.source != "custom":
            return JSONResponse({"error": "Custom mode not found"}, status_code=404)
        return mode.definition

    mode_data = await get_custom_mode(user_id, mode_id, mac)
    if not mode_data:
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)
    return mode_data["definition"]


@router.delete("/modes/custom/{mode_id}")
async def delete_custom_mode_endpoint(
    mode_id: str,
    mac: str = Query(None, description="Device MAC address to filter custom modes"),
    user_id: int = Depends(require_user),
):
    """Delete a custom mode for the current user, optionally filtered by device."""
    normalized = mode_id.upper()
    
    registry = get_registry()

    # Legacy path: no mac -> file-based custom mode.
    if not mac:
        mode = registry.get_json_mode(normalized)
        if not mode or mode.info.source != "custom":
            return JSONResponse({"error": "Custom mode not found"}, status_code=404)
        registry.unregister_custom(normalized)
        if mode.file_path:
            Path(mode.file_path).unlink(missing_ok=True)
        cleaned_configs = await remove_mode_from_all_configs(normalized, None)
        logger.info(
            "[MODES] Deleted legacy custom mode %s for user %s, cleaned_configs=%s",
            normalized,
            user_id,
            cleaned_configs,
        )
        return {"ok": True, "mode_id": normalized, "cleaned_configs": cleaned_configs}

    # DB path
    deleted = await delete_custom_mode(user_id, normalized, mac)
    if not deleted:
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)

    registry.unregister_custom(normalized, mac)
    cleaned_configs = await remove_mode_from_all_configs(normalized, mac)
    logger.info(
        "[MODES] Deleted custom mode %s for user %s on device %s, cleaned_configs=%s",
        normalized,
        user_id,
        mac,
        cleaned_configs,
    )
    return {"ok": True, "mode_id": normalized, "cleaned_configs": cleaned_configs}


@router.post("/modes/generate")
async def generate_mode(
    body: dict,
    user_id: int = Depends(optional_user),
    admin_auth: None = Depends(require_admin),
):
    description = body.get("description", "").strip()
    if not description:
        return JSONResponse({"error": "description is required"}, status_code=400)
    if len(description) > 2000:
        return JSONResponse({"error": "description too long (max 2000 chars)"}, status_code=400)

    image_base64 = body.get("image_base64")
    if image_base64 and len(image_base64) > 5 * 1024 * 1024:
        return JSONResponse({"error": "image too large (max 4MB)"}, status_code=400)

    # 解析 API key：优先使用用户级别配置，其次使用设备配置中的加密 key
    user_api_key = None
    if user_id is not None:
        try:
            from core.config_store import get_user_llm_config

            user_cfg = await get_user_llm_config(user_id)
        except Exception:
            user_cfg = None
            logger.warning("[MODE_GEN] Failed to load user_llm_config for user_id=%s", user_id, exc_info=True)
        if user_cfg:
            user_api_key = (user_cfg.get("api_key") or "").strip() or None

    device_api_key = None
    mac = body.get("mac")
    if mac:
        from core.config_store import get_active_config

        config = await get_active_config(mac)
        if config:
            encrypted_key = config.get("llm_api_key", "")
            if encrypted_key:
                from core.crypto import decrypt_api_key

                decrypted = decrypt_api_key(encrypted_key)
                # 如果解密成功且非空，使用解密后的值；如果解密失败或为空，使用空字符串表示用户配置了但无效
                device_api_key = (decrypted or "").strip() or ""

    effective_api_key = user_api_key if user_api_key is not None else device_api_key
    using_user_key = effective_api_key is not None

    # ── 额度检查（AI 生成模式同样按照 BILLING.md 计费） ──────────────────────────
    quota_user_id: int | None = None
    if user_id is not None:
        quota_user_id = user_id
    elif mac:
        try:
            quota_user_id = await get_quota_owner_for_mac(mac)
        except Exception:
            quota_user_id = None

    if quota_user_id is not None and not using_user_key:
        try:
            user_role = await get_user_role(quota_user_id)
        except Exception:
            user_role = None
        if user_role != "root":
            quota = await ensure_user_api_quota(quota_user_id)
            remaining = int(quota.get("free_quota_remaining") or 0) if quota else 0
            if remaining <= 0:
                return JSONResponse(
                    {"error": "您的免费额度已用完，请输入邀请码获取更多额度"},
                    status_code=402,
                )

    from core.mode_generator import generate_mode_definition

    try:
        result = await generate_mode_definition(
            description=description,
            image_base64=image_base64,
            provider=body.get("provider", "deepseek"),
            model=body.get("model", "deepseek-chat"),
            api_key=effective_api_key,
        )
        # 成功后扣费（仅平台 Key，root 用户豁免）
        if quota_user_id is not None and not using_user_key:
            try:
                user_role = await get_user_role(quota_user_id)
            except Exception:
                user_role = None
            if user_role != "root":
                await consume_user_free_quota(quota_user_id, amount=1)
        return result
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except (jsonlib.JSONDecodeError, OSError, OpenAIError, RuntimeError, TypeError) as exc:
        logger.exception("[MODE_GEN] Failed to generate mode")
        return JSONResponse(
            {"error": f"生成失败: {type(exc).__name__}: {str(exc)[:200]}"},
            status_code=500,
        )
