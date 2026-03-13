from __future__ import annotations

import io
import json as jsonlib
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAIError

from api.shared import logger
from core.auth import require_admin
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.context import get_date_context, get_weather
from core.mode_registry import CUSTOM_JSON_DIR, _validate_mode_def, get_registry

router = APIRouter(tags=["modes"])


@router.get("/modes")
async def list_modes():
    registry = get_registry()
    return {
        "modes": [
            {
                "mode_id": info.mode_id,
                "display_name": info.display_name,
                "icon": info.icon,
                "cacheable": info.cacheable,
                "description": info.description,
                "source": info.source,
                "settings_schema": info.settings_schema,
            }
            for info in registry.list_modes()
        ]
    }


@router.post("/modes/custom/preview")
async def custom_mode_preview(body: dict, admin_auth: None = Depends(require_admin)):
    mode_def = body.get("mode_def", body)
    if not mode_def.get("mode_id"):
        mode_def = dict(mode_def, mode_id="PREVIEW")
    screen_w = body.get("w", SCREEN_WIDTH)
    screen_h = body.get("h", SCREEN_HEIGHT)
    
    # 获取设备配置以获取 api_key
    device_api_key = None
    device_image_api_key = None
    mac = body.get("mac")
    
    # 如果没有 mac，尝试从请求中获取（前端可能通过其他方式传递）
    # 或者从当前用户的默认配置获取
    from core.config_store import get_active_config
    config = None
    if mac:
        config = await get_active_config(mac)
    else:
        # 如果没有 mac，尝试获取第一个设备的配置（用于预览）
        # 或者从环境变量获取（作为后备）
        pass
    
    if config:
        encrypted_key = config.get("llm_api_key", "")
        if encrypted_key:
            from core.crypto import decrypt_api_key
            decrypted = decrypt_api_key(encrypted_key)
            # 如果解密成功且非空，使用解密后的值；如果解密失败或为空，使用空字符串表示用户配置了但无效
            device_api_key = decrypted if decrypted and decrypted.strip() else ""
        encrypted_image_key = config.get("image_api_key", "")
        if encrypted_image_key:
            from core.crypto import decrypt_api_key
            decrypted = decrypt_api_key(encrypted_image_key)
            # 如果解密成功且非空，使用解密后的值；如果解密失败或为空，使用空字符串表示用户配置了但无效
            device_image_api_key = decrypted if decrypted and decrypted.strip() else ""
    
    try:
        from core.json_content import generate_json_mode_content
        from core.json_renderer import render_json_mode

        date_ctx = await get_date_context()
        weather = await get_weather()
        content = await generate_json_mode_content(
            mode_def,
            date_ctx=date_ctx,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            screen_w=screen_w,
            screen_h=screen_h,
            api_key=device_api_key,
            image_api_key=device_image_api_key,
        )
        img = render_json_mode(
            mode_def,
            content,
            date_str=date_ctx["date_str"],
            weather_str=weather["weather_str"],
            battery_pct=100.0,
            screen_w=screen_w,
            screen_h=screen_h,
        )
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
async def create_custom_mode(body: dict, admin_auth: None = Depends(require_admin)):
    mode_id = body.get("mode_id", "").upper()
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

    file_path = Path(CUSTOM_JSON_DIR) / f"{mode_id.lower()}.json"
    file_path.write_text(jsonlib.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    registry.unregister_custom(mode_id)
    loaded = registry.load_json_mode(str(file_path), source="custom")
    if not loaded:
        file_path.unlink(missing_ok=True)
        return JSONResponse({"error": "Failed to load mode definition"}, status_code=400)

    logger.info("[MODES] Created custom mode: %s", mode_id)
    return {"ok": True, "mode_id": mode_id}


@router.get("/modes/custom/{mode_id}")
async def get_custom_mode(mode_id: str):
    registry = get_registry()
    mode = registry.get_json_mode(mode_id.upper())
    if not mode or mode.info.source != "custom":
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)
    return mode.definition


@router.delete("/modes/custom/{mode_id}")
async def delete_custom_mode(mode_id: str, admin_auth: None = Depends(require_admin)):
    normalized = mode_id.upper()
    registry = get_registry()
    mode = registry.get_json_mode(normalized)
    if not mode or mode.info.source != "custom":
        return JSONResponse({"error": "Custom mode not found"}, status_code=404)
    registry.unregister_custom(normalized)
    if mode.file_path:
        Path(mode.file_path).unlink(missing_ok=True)
    logger.info("[MODES] Deleted custom mode: %s", normalized)
    return {"ok": True, "mode_id": normalized}


@router.post("/modes/generate")
async def generate_mode(body: dict, admin_auth: None = Depends(require_admin)):
    description = body.get("description", "").strip()
    if not description:
        return JSONResponse({"error": "description is required"}, status_code=400)
    if len(description) > 2000:
        return JSONResponse({"error": "description too long (max 2000 chars)"}, status_code=400)

    image_base64 = body.get("image_base64")
    if image_base64 and len(image_base64) > 5 * 1024 * 1024:
        return JSONResponse({"error": "image too large (max 4MB)"}, status_code=400)

    # 获取设备配置以获取 api_key（如果有 mac）
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
                if decrypted and decrypted.strip():
                    device_api_key = decrypted
                    logger.info(f"[MODE_GEN] Using device api_key for mac={mac} (length: {len(device_api_key)})")
                else:
                    logger.warning(f"[MODE_GEN] Failed to decrypt api_key for mac={mac}")

    from core.mode_generator import generate_mode_definition

    try:
        return await generate_mode_definition(
            description=description,
            image_base64=image_base64,
            provider=body.get("provider", "deepseek"),
            model=body.get("model", "deepseek-chat"),
            api_key=device_api_key,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except (jsonlib.JSONDecodeError, OSError, OpenAIError, RuntimeError, TypeError) as exc:
        logger.exception("[MODE_GEN] Failed to generate mode")
        return JSONResponse(
            {"error": f"生成失败: {type(exc).__name__}: {str(exc)[:200]}"},
            status_code=500,
        )
