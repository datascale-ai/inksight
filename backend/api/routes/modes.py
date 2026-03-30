from __future__ import annotations

import io
import json as jsonlib
from pathlib import Path
import os
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAIError

from api.shared import logger
from core.auth import require_admin, require_user, optional_user
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH, get_default_llm_model_for_provider
from core.config_store import remove_mode_from_all_configs
from core.context import get_date_context, get_weather
from core.mode_registry import CUSTOM_JSON_DIR, _validate_mode_def, get_registry
from core.mode_catalog import BUILTIN_CATALOG, builtin_catalog_map
from core.config_store import (
    get_user_custom_modes,
    get_custom_mode,
    save_custom_mode,
    delete_custom_mode,
    get_user_api_quota,
    consume_user_free_quota,
    get_quota_owner_for_mac,
    get_user_role,
)

router = APIRouter(tags=["modes"])


def _billing_enabled() -> bool:
    """全局计费开关：INKSIGHT_BILLING_ENABLED=0 时关闭额度检查与扣费。"""
    value = os.getenv("INKSIGHT_BILLING_ENABLED", "1").strip().lower()
    return value not in ("0", "false", "no", "off")


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
                "mac": mode_data.get("mac"),
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


@router.get("/modes/catalog")
async def mode_catalog(
    mac: str = Query(None, description="Device MAC address to filter custom modes"),
    user_id: int = Depends(optional_user),
):
    """
    Unified mode catalog for UIs (preview/config).

    - Builtin modes: grouped by a single source of truth in `core.mode_catalog`.
    - Custom modes: dynamic, always category="custom".
    """
    try:
        catalog = builtin_catalog_map()
        registry = get_registry()

        # Normalize mac if provided
        if mac:
            mac = mac.upper()

        # Reuse list_modes logic (including device isolation) by loading custom modes here.
        if user_id is not None and mac:
            from core.config_store import has_active_membership

            if not await has_active_membership(mac, user_id):
                # Not a member: only builtin modes
                items = []
                for info in registry.list_modes(mac):
                    if info.source == "custom":
                        continue
                    cat = catalog.get(info.mode_id)
                    items.append(
                        {
                            "mode_id": info.mode_id,
                            "source": info.source,
                            "category": (cat.category if cat else "more"),
                            "display_name": info.display_name,
                            "description": info.description,
                            "settings_schema": info.settings_schema or [],
                            "i18n": {
                                "zh": {
                                    "name": (cat.zh.name if cat else info.display_name),
                                    "tip": (cat.zh.tip if cat else info.description),
                                },
                                "en": {
                                    "name": (cat.en.name if cat else info.display_name),
                                    "tip": (cat.en.tip if cat else info.description),
                                },
                            },
                        }
                    )
                return {"items": items}

            # User has access: load their custom modes
            registry.unregister_device_modes(mac)
            await registry.load_user_custom_modes(user_id, mac)

        def _item_from_info(info):
            mid = info.mode_id
            if info.source == "custom":
                return {
                    "mode_id": mid,
                    "source": info.source,
                    "category": "custom",
                    "display_name": info.display_name,
                    "description": info.description,
                    "settings_schema": info.settings_schema or [],
                    "i18n": {
                        "zh": {"name": info.display_name, "tip": info.description},
                        "en": {"name": info.display_name, "tip": info.description},
                    },
                }
            cat = catalog.get(mid)
            return {
                "mode_id": mid,
                "source": info.source,
                "category": (cat.category if cat else "more"),
                "display_name": info.display_name,
                "description": info.description,
                "settings_schema": info.settings_schema or [],
                "i18n": {
                    "zh": {
                        "name": (cat.zh.name if cat else info.display_name),
                        "tip": (cat.zh.tip if cat else info.description),
                    },
                    "en": {
                        "name": (cat.en.name if cat else info.display_name),
                        "tip": (cat.en.tip if cat else info.description),
                    },
                },
            }

        items: list[dict] = []

        # 1) Builtin modes in catalog order (stable UX)
        for cat_item in BUILTIN_CATALOG:
            info = registry.get_mode_info(cat_item.mode_id.upper())
            if not info or info.source == "custom":
                continue
            items.append(_item_from_info(info))

        emitted = {x["mode_id"] for x in items}

        # 2) Remaining non-custom modes not in catalog (fallback)
        for info in registry.list_modes(mac):
            if info.source == "custom":
                continue
            if info.mode_id in emitted:
                continue
            items.append(_item_from_info(info))
            emitted.add(info.mode_id)

        # 3) Custom modes (dynamic)
        if mac:
            for info in registry.list_modes(mac):
                if info.source != "custom":
                    continue
                items.append(_item_from_info(info))
        elif user_id is not None:
            # Device-free preview should only show the current user's actual
            # saved/installed custom modes from DB, not whatever custom entries
            # happen to remain in the global registry from other requests.
            user_custom_modes = await get_user_custom_modes(user_id, None)
            latest_by_mode_id: dict[str, dict] = {}
            for mode_data in user_custom_modes:
                mode_id = str(mode_data.get("mode_id") or "").upper().strip()
                definition = mode_data.get("definition") or {}
                if not mode_id or not isinstance(definition, dict):
                    continue
                existing = latest_by_mode_id.get(mode_id)
                updated_at = str(mode_data.get("updated_at") or "")
                if existing is None or updated_at > str(existing.get("updated_at") or ""):
                    latest_by_mode_id[mode_id] = mode_data

            for mode_id, mode_data in sorted(
                latest_by_mode_id.items(),
                key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""),
                reverse=True,
            ):
                definition = mode_data["definition"]
                display_name = str(definition.get("display_name") or mode_id)
                description = str(definition.get("description") or "")
                settings_schema = definition.get("settings_schema") or []
                items.append(
                    {
                        "mode_id": mode_id,
                        "source": "custom",
                        "category": "custom",
                        "display_name": display_name,
                        "description": description,
                        "settings_schema": settings_schema if isinstance(settings_schema, list) else [],
                        "i18n": {
                            "zh": {"name": display_name, "tip": description},
                            "en": {"name": display_name, "tip": description},
                        },
                    }
                )

        return {"items": items}
    except Exception as e:
        logger.exception("[CATALOG] Error in mode_catalog endpoint")
        return JSONResponse({"error": str(e), "items": []}, status_code=500)


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
):
    mode_def = body.get("mode_def", body)
    if not mode_def.get("mode_id"):
        mode_def = dict(mode_def, mode_id="PREVIEW")
    screen_w = body.get("w", SCREEN_WIDTH)
    screen_h = body.get("h", SCREEN_HEIGHT)
    colors = int(body.get("colors", 2))
    response_type = str(body.get("responseType", body.get("response_type", "image"))).strip().lower()

    # 解析 API key：优先使用用户级别配置，其次使用设备配置中的加密 key
    user_api_key = None
    user_image_api_key = None
    user_llm_provider = None
    user_llm_model = None
    user_llm_base_url = None
    user_llm_access_mode = "preset"
    if user_id is not None:
        try:
            from core.config_store import get_user_llm_config

            user_cfg = await get_user_llm_config(user_id)
        except Exception:
            user_cfg = None
            logger.warning("[CUSTOM_PREVIEW] Failed to load user_llm_config for user_id=%s", user_id, exc_info=True)
        if user_cfg:
            user_llm_access_mode = (user_cfg.get("llm_access_mode") or "preset").strip().lower()
            user_api_key = (user_cfg.get("api_key") or "").strip() or None
            user_image_api_key = (user_cfg.get("image_api_key") or "").strip() or None
            user_llm_provider = (user_cfg.get("provider") or "").strip() or None
            user_llm_model = (user_cfg.get("model") or "").strip() or None
            if user_llm_access_mode == "custom_openai":
                user_llm_base_url = (user_cfg.get("base_url") or "").strip() or None

    # 注意：不再从设备配置读取 API key，只使用用户级别的配置（user_llm_config 表）
    device_api_key = None
    device_image_api_key = None

    try:
        from core.json_content import generate_json_mode_content
        from core.json_renderer import render_json_mode

        # ── 额度检查（按照 BILLING.md，custom preview 也算一次计费调用） ──────────────
        # 按“登录用户”计费：优先用 user_id，其次 mac owner，缺省则不计费
        quota_user_id: int | None = None
        if user_id is not None:
            quota_user_id = user_id

        # 是否使用用户自带 API Key（profile / 设备配置），为 True 时不扣费不拦截额度
        # effective_api_key 为 None 表示将会走环境变量中的“平台 Key”，此时需要按照免费额度计费
        effective_api_key = user_api_key if user_api_key is not None else device_api_key
        effective_image_api_key = user_image_api_key if user_image_api_key is not None else device_image_api_key
        using_user_key = effective_api_key is not None

        # 解析当前自定义模式是否“需要 LLM”（与 shared.build_image 中的判定保持一致）
        llm_mode_requires_quota = False
        try:
            content_def = (mode_def.get("content") or {}) if isinstance(mode_def, dict) else {}
            ctype = content_def.get("type")
            if ctype in ("llm", "llm_json", "image_gen"):
                llm_mode_requires_quota = True
            elif ctype == "external_data":
                provider = content_def.get("provider", "")
                if provider == "briefing":
                    summarize = content_def.get("summarize", True)
                    include_insight = content_def.get("include_insight", True)
                    if summarize or include_insight:
                        llm_mode_requires_quota = True
            elif ctype == "composite":
                steps = content_def.get("steps", [])
                if isinstance(steps, list):
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        step_type = step.get("type")
                        if step_type in ("llm", "llm_json", "image_gen"):
                            llm_mode_requires_quota = True
                            break
                        if step_type == "external_data":
                            step_provider = step.get("provider", "")
                            if step_provider == "briefing":
                                step_summarize = step.get("summarize", True)
                                step_include_insight = step.get("include_insight", True)
                                if step_summarize or step_include_insight:
                                    llm_mode_requires_quota = True
                                    break
        except Exception:
            logger.warning("[CUSTOM_PREVIEW] Failed to detect llm requirements for custom mode", exc_info=True)

        # 额度不足拦截：只有在使用平台 Key 且存在 quota_user_id 时才检查
        if (
            _billing_enabled()
            and quota_user_id is not None
            and not using_user_key
            and llm_mode_requires_quota
        ):
            try:
                user_role = await get_user_role(quota_user_id)
            except Exception:
                user_role = None
            if user_role != "root":
                quota = await get_user_api_quota(quota_user_id)
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
            # 自定义模式预览中的 LLM 调用也优先使用用户配置的 provider + API key
            llm_provider=user_llm_provider,
            llm_model=user_llm_model,
            llm_base_url=user_llm_base_url,
            api_key=effective_api_key,
            image_api_key=effective_image_api_key,
        )

        # 额度扣减：仅在使用平台 Key、模式需要 LLM 且本次确实成功调用 LLM 时扣费，root 用户豁免
        if (
            _billing_enabled()
            and quota_user_id is not None
            and not using_user_key
            and llm_mode_requires_quota
            and isinstance(content, dict)
            and content.get("_llm_used") is True
            and content.get("_llm_ok") is True
        ):
            try:
                user_role = await get_user_role(quota_user_id)
            except Exception:
                user_role = None
            if user_role != "root":
                await consume_user_free_quota(quota_user_id, amount=1)

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
            colors=colors,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="image/png")
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.exception("[CUSTOM_PREVIEW] Preview failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


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

    # 解析 API key & provider：优先使用用户级别配置，其次使用 body 中的显式指定
    user_api_key = None
    user_llm_provider = None
    user_llm_model = None
    user_llm_base_url = None
    user_llm_access_mode = "preset"
    if user_id is not None:
        try:
            from core.config_store import get_user_llm_config

            user_cfg = await get_user_llm_config(user_id)
        except Exception:
            user_cfg = None
            logger.warning("[MODE_GEN] Failed to load user_llm_config for user_id=%s", user_id, exc_info=True)
        if user_cfg:
            user_llm_access_mode = (user_cfg.get("llm_access_mode") or "preset").strip().lower()
            user_api_key = (user_cfg.get("api_key") or "").strip() or None
            user_llm_provider = (user_cfg.get("provider") or "").strip() or None
            # 这里不再根据 provider 推默认模型，而是尊重用户在 profile 中配置的 model；
            # 如果用户没有配置 model，则在后面通过 base_model 统一回退到默认。
            user_llm_model = (user_cfg.get("model") or "").strip() or None
            if user_llm_access_mode == "custom_openai":
                user_llm_base_url = (user_cfg.get("base_url") or "").strip() or None

    # 注意：不再从设备配置读取 API key，只使用用户级别的配置（user_llm_config 表）
    effective_api_key = user_api_key
    using_user_key = effective_api_key is not None

    # ── 额度检查（AI 生成模式同样按照 BILLING.md 计费） ──────────────────────────
    quota_user_id: int | None = None
    if user_id is not None:
        quota_user_id = user_id

    if _billing_enabled() and quota_user_id is not None and not using_user_key:
        try:
            user_role = await get_user_role(quota_user_id)
        except Exception:
            user_role = None
        if user_role != "root":
            quota = await get_user_api_quota(quota_user_id)
            remaining = int(quota.get("free_quota_remaining") or 0) if quota else 0
            if remaining <= 0:
                return JSONResponse(
                    {"error": "您的免费额度已用完，请输入邀请码获取更多额度"},
                    status_code=402,
                )

    from core.mode_generator import generate_mode_definition

    try:
        # 生成模式定义时，LLM provider/model **必须用户优先**：
        # 1. 优先使用用户级配置（profile 中的 provider / model）
        # 2. 其次 body 中显式指定的 provider / model
        # 3. 最后根据最终 provider 选择默认模型
        provider_from_body = (body.get("provider") or "").strip() or None
        model_from_body = (body.get("model") or "").strip() or None

        # provider：custom_openai 固定走 openai_compat；否则 用户配置 > body > 默认 "deepseek"
        if user_llm_access_mode == "custom_openai":
            effective_provider = "openai_compat"
        else:
            effective_provider = user_llm_provider or provider_from_body or "deepseek"

        # model：用户配置 > body > 根据最终 provider 选择默认模型
        base_model = get_default_llm_model_for_provider(effective_provider)
        effective_model = user_llm_model or model_from_body or base_model
        if effective_provider == "openai_compat" and not (effective_model or "").strip():
            return JSONResponse({"error": "自定义 OpenAI 模式下 model 必填"}, status_code=400)

        # 临时调试日志：查看实际使用的 provider/model 以及 user_cfg
        logger.info(
            "[GENERATE_MODE_DEBUG] user_id=%s user_cfg=%s body_provider=%s body_model=%s "
            "effective_provider=%s effective_model=%s using_user_key=%s",
            user_id,
            user_cfg,
            provider_from_body,
            model_from_body,
            effective_provider,
            effective_model,
            using_user_key,
        )

        result = await generate_mode_definition(
            description=description,
            image_base64=image_base64,
            provider=effective_provider,
            model=effective_model,
            api_key=effective_api_key,
            base_url=(user_llm_base_url if user_llm_access_mode == "custom_openai" else None),
        )
        # 成功后扣费（仅平台 Key，root 用户豁免）
        if _billing_enabled() and quota_user_id is not None and not using_user_key:
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
