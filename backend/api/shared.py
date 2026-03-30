from __future__ import annotations

import asyncio
import copy
import io
import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont
from core.patterns.utils import load_font

try:  # pragma: no cover - exercised implicitly at import time
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover
    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def get_remote_address(request: Request) -> str:
        client = getattr(request, "client", None)
        return getattr(client, "host", "unknown") if client else "unknown"

    class RateLimitExceeded(Exception):
        """Fallback rate limit exception (never actually raised without slowapi)."""

    async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_unavailable",
                "message": "Rate limiting is not enabled on this server.",
            },
        )

    Limiter = _DummyLimiter  # type: ignore

from core.auth import (
    optional_user,
    require_device_token,
    validate_mac_param,
)
from core.cache import content_cache
from core.config import (
    DEFAULT_CITY,
    DEFAULT_MODES,
    DEFAULT_REFRESH_INTERVAL,
    get_default_llm_model_for_provider,
)
from core.config_store import (
    get_active_config,
    get_cycle_index,
    get_device_membership,
    get_device_state,
    get_quota_owner_for_mac,
    get_user_api_quota,
    get_user_role,
    init_db,
    set_cycle_index,
    update_device_state,
    consume_user_free_quota,
)
from core.context import calc_battery_pct, extract_location_settings, get_date_context, get_weather
from core.pipeline import generate_and_render, get_effective_mode_config
from core.renderer import image_to_bmp_bytes
from core.stats_store import (
    get_latest_battery_voltage,
    init_stats_db,
    log_heartbeat,
    log_render,
    save_render_content,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DISCOVERY_WINDOW_MINUTES = 15
ONLINE_WINDOW_MINUTES = 15

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@asynccontextmanager
async def lifespan(app):
    await init_db()
    await init_stats_db()
    from core.cache import init_cache_db
    from core.db import close_all

    await init_cache_db()
    yield
    await close_all()


def _rate_limit_key(request: Request) -> str:
    mac = request.query_params.get("mac")
    if mac:
        return f"mac:{mac}"
    return get_remote_address(request)


class _NoopLimiter:
    def __init__(self, *args, **kwargs):
        pass

    def limit(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


try:
    limiter = Limiter(key_func=_rate_limit_key)
except Exception as exc:  # pragma: no cover - depends on optional runtime dependency
    logger.warning("Rate limiter disabled due to init error: %s", exc)
    limiter = _NoopLimiter()


async def inksight_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.message},
    )


def build_claim_url(request: Request, token: str) -> str:
    override = os.environ.get("INKSIGHT_WEB_BASE_URL", "").rstrip("/")
    if override:
        return f"{override}/claim?token={token}"
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
        or ""
    ).strip()
    if "inksight.site" not in host.lower():
        return ""
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").strip()
    return f"{scheme}://{host}/claim?token={token}"


async def resolve_user_id(request: Request, ink_session: Optional[str]) -> int | None:
    return await optional_user(request, ink_session)


async def require_membership_access(
    request: Request,
    mac: str,
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
) -> dict:
    from core.i18n import detect_lang_from_request, msg

    lang = detect_lang_from_request(request)
    mac = validate_mac_param(mac, lang)
    user_id = await resolve_user_id(request, ink_session)
    if user_id is None:
        raise HTTPException(status_code=401, detail=msg("auth.login_required", lang))
    membership = await get_device_membership(mac, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail=msg("auth.no_device_access", lang))
    if owner_only and membership.get("role") != "owner":
        raise HTTPException(status_code=403, detail=msg("auth.owner_only", lang))
    return membership


async def ensure_web_or_device_access(
    request: Request,
    mac: str,
    x_device_token: Optional[str],
    ink_session: Optional[str],
    *,
    owner_only: bool = False,
    allow_device_token: bool = True,
) -> dict:
    mac = validate_mac_param(mac)
    if allow_device_token and x_device_token:
        await require_device_token(mac, x_device_token)
        return {"mode": "device", "role": "device"}
    membership = await require_membership_access(request, mac, ink_session, owner_only=owner_only)
    return {"mode": "user", **membership}


FIRMWARE_CHIP_FAMILY = "ESP32-C3"
FIRMWARE_RELEASE_CACHE_TTL = int(os.getenv("FIRMWARE_RELEASE_CACHE_TTL", "120"))
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "datascale-ai")
GITHUB_REPO = os.getenv("GITHUB_REPO", "inksight")
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
_firmware_release_cache = {
    "expires_at": 0.0,
    "payload": None,
}
_firmware_release_cache_lock = asyncio.Lock()
_preview_push_queue: dict[str, dict] = {}
_preview_push_queue_lock = asyncio.Lock()

_SMART_TIME_SLOTS = [
    (6, 9, ["RECIPE", "DAILY"]),
    (9, 12, ["BRIEFING", "STOIC"]),
    (12, 14, ["ZEN", "POETRY"]),
    (14, 18, ["STOIC", "ROAST"]),
    (18, 21, ["FITNESS", "RECIPE"]),
    (21, 24, ["ZEN", "POETRY"]),
    (0, 6, ["ZEN", "POETRY"]),
]


async def choose_persona_from_config(config: dict, peek_next: bool = False) -> str:
    modes = config.get("modes", DEFAULT_MODES) or DEFAULT_MODES
    strategy = config.get("refresh_strategy", "random")

    if strategy == "cycle":
        mac = config.get("mac", "default")
        idx = await get_cycle_index(mac)
        persona = modes[idx % len(modes)]
        if not peek_next:
            await set_cycle_index(mac, idx + 1)
        return persona

    if strategy == "time_slot":
        hour = datetime.now().hour
        rules = config.get("time_slot_rules", [])
        for rule in rules:
            start_h = rule.get("startHour", 0)
            end_h = rule.get("endHour", 24)
            rule_modes = rule.get("modes", [])
            if start_h <= hour < end_h and rule_modes:
                available = [mode for mode in rule_modes if mode in modes]
                if available:
                    return random.choice(available)
        return random.choice(modes)

    if strategy == "smart":
        hour = datetime.now().hour
        for start_h, end_h, candidates in _SMART_TIME_SLOTS:
            if start_h <= hour < end_h:
                available = [mode for mode in candidates if mode in modes]
                if available:
                    return random.choice(available)
        return random.choice(modes)

    return random.choice(modes)


async def advance_to_next_mode(mac: Optional[str], config: dict) -> str:
    modes = config.get("modes", DEFAULT_MODES)
    if not modes:
        return "STOIC"

    state = await get_device_state(mac) if mac else None
    current = state.get("last_persona", "") if state else ""
    idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
    persona = modes[idx]
    if mac:
        await set_cycle_index(mac, idx + 1)
    return persona


async def consume_pending_mode(mac: str) -> Optional[str]:
    try:
        state = await get_device_state(mac)
        if state and state.get("pending_mode"):
            mode = state["pending_mode"]
            await update_device_state(mac, pending_mode="")
            return mode
    except (OSError, ValueError, TypeError):
        logger.warning("[PENDING_MODE] Failed to consume for %s", mac, exc_info=True)
    return None


async def resolve_mode(
    mac: Optional[str],
    config: Optional[dict],
    persona_override: Optional[str],
    *,
    force_next: bool = False,
) -> str:
    from core.mode_registry import get_registry

    registry = get_registry()
    # Always pass mac to is_supported to ensure device isolation
    if mac and not persona_override:
        pending = await consume_pending_mode(mac)
        if pending and registry.is_supported(pending.upper(), mac):
            return pending.upper()

    if persona_override and registry.is_supported(persona_override.upper(), mac):
        return persona_override.upper()

    if config:
        if force_next:
            return await advance_to_next_mode(mac, config)
        return await choose_persona_from_config(config)

    return random.choice(["STOIC", "ROAST", "ZEN", "DAILY"])


async def build_image(
    v: float,
    mac: Optional[str],
    persona_override: Optional[str] = None,
    *,
    screen_w: int,
    screen_h: int,
    force_next: bool = False,
    skip_cache: bool = False,
    preview_city_override: Optional[str] = None,
    preview_mode_override: Optional[dict] = None,
    preview_memo_text: Optional[str] = None,
    preview_ui_language: Optional[str] = None,
    current_user_id: Optional[int] = None,
    user_api_key: Optional[str] = None,
    intent_only: bool = False,
    colors: int = 2,
):
    from core.mode_registry import get_registry

    battery_pct = calc_battery_pct(v)
    config = await get_active_config(mac) if mac else None
    persona = await resolve_mode(mac, config, persona_override, force_next=force_next)
    owner_user_id: int | None = None
    if mac:
        from core.config_store import get_device_owner

        owner = await get_device_owner(mac)
        if owner:
            try:
                owner_user_id = int(owner.get("user_id"))
            except (TypeError, ValueError):
                owner_user_id = None

    registry = get_registry()
    
    # Load device owner's custom modes if needed (for device rendering)
    # Only load modes for the specific device to avoid loading modes from other devices
    if mac and not registry.is_supported(persona, mac):
        if owner_user_id:
            await registry.load_user_custom_modes(owner_user_id, mac)
            logger.debug(f"[BUILD_IMAGE] Loaded custom modes for device owner {owner_user_id} (device {mac})")
        # Fallback: configured persona may reference a deleted/missing custom mode.
        if not registry.is_supported(persona, mac):
            cfg_modes = config.get("modes", []) if isinstance(config, dict) else []
            fallback_persona = None
            if isinstance(cfg_modes, list):
                for m in cfg_modes:
                    cand = str(m).upper().strip()
                    if registry.is_supported(cand, mac):
                        fallback_persona = cand
                        break
            persona = fallback_persona or "STOIC"
            logger.warning(
                "[BUILD_IMAGE] Unsupported persona for %s, fallback to %s",
                mac,
                persona,
            )
    
    # For Web preview without mac: load all custom modes for the current user
    # Note: This may cause conflicts if user has same mode_id on different devices
    # but we unregister before loading, so the last loaded will take precedence
    if not mac and current_user_id is not None and not registry.is_supported(persona):
        await registry.load_user_custom_modes(current_user_id, None)
        logger.debug(f"[BUILD_IMAGE] Loaded all custom modes for user {current_user_id} (Web preview without device)")
    
    mode_info = registry.get_mode_info(persona)
    is_mode_cacheable = bool(mode_info.cacheable) if mode_info else True

    # ── 合入用户级别的 LLM / 图像 API 配置 ─────────────────────────────
    selected_config_user_id: int | None = None
    usage_source = "server_api_key"
    current_user_llm_cfg = None
    owner_user_llm_cfg = None

    if current_user_id is not None:
        try:
            from core.config_store import get_user_llm_config

            current_user_llm_cfg = await get_user_llm_config(current_user_id)
        except Exception:
            current_user_llm_cfg = None
            logger.warning(
                "[BUILD_IMAGE] Failed to load user_llm_config for current_user_id=%s (mac=%s)",
                current_user_id,
                mac,
                exc_info=True,
            )

    if owner_user_id is not None and owner_user_id != current_user_id:
        try:
            from core.config_store import get_user_llm_config

            owner_user_llm_cfg = await get_user_llm_config(owner_user_id)
        except Exception:
            owner_user_llm_cfg = None
            logger.warning(
                "[BUILD_IMAGE] Failed to load user_llm_config for owner_user_id=%s (mac=%s)",
                owner_user_id,
                mac,
                exc_info=True,
            )
    elif owner_user_id is not None:
        owner_user_llm_cfg = current_user_llm_cfg

    def apply_user_llm_cfg(user_llm_cfg: dict) -> None:
        llm_access_mode = (user_llm_cfg.get("llm_access_mode") or "preset").strip().lower()
        provider = (user_llm_cfg.get("provider") or "").strip()
        model = (user_llm_cfg.get("model") or "").strip()
        api_key_plain = (user_llm_cfg.get("api_key") or "").strip()
        base_url = (user_llm_cfg.get("base_url") or "").strip()
        image_provider = (user_llm_cfg.get("image_provider") or "").strip()
        image_model = (user_llm_cfg.get("image_model") or "").strip()
        image_api_key_plain = (user_llm_cfg.get("image_api_key") or "").strip()
        config["llm_access_mode"] = llm_access_mode
        if provider:
            config["llm_provider"] = provider
            if model:
                config["llm_model"] = model
        if api_key_plain:
            config["user_api_key"] = api_key_plain
        # base_url only matters for custom_openai. Keep it isolated to avoid affecting preset providers.
        if llm_access_mode == "custom_openai" and base_url:
            config["llm_base_url"] = base_url
        if image_provider:
            config["image_provider"] = image_provider
        if image_model:
            config["image_model"] = image_model
        if image_api_key_plain:
            config["user_image_api_key"] = image_api_key_plain

    if (
        user_api_key and user_api_key.strip()
    ) or (
        current_user_llm_cfg and (current_user_llm_cfg.get("api_key") or "").strip()
    ) or (
        owner_user_llm_cfg and (owner_user_llm_cfg.get("api_key") or "").strip()
    ):
        config = dict(config or {})

    if user_api_key and user_api_key.strip():
        config["user_api_key"] = user_api_key.strip()
        selected_config_user_id = current_user_id
        usage_source = "current_user_api_key"
        logger.debug("[BUILD_IMAGE] Using user_api_key from request header for user_id=%s", selected_config_user_id)
    elif current_user_id is not None and current_user_llm_cfg and (current_user_llm_cfg.get("api_key") or "").strip():
        apply_user_llm_cfg(current_user_llm_cfg)
        selected_config_user_id = current_user_id
        usage_source = "current_user_api_key"
    elif owner_user_llm_cfg and (owner_user_llm_cfg.get("api_key") or "").strip():
        apply_user_llm_cfg(owner_user_llm_cfg)
        selected_config_user_id = owner_user_id
        usage_source = "owner_api_key"
    elif not mac and current_user_id is not None:
        usage_source = "current_user_free_quota"
    elif mac:
        usage_source = "owner_free_quota"

    # 是否为需要 LLM 的 JSON 模式（需要额度管控的类型）
    # 需要检查顶层 content 类型，以及 composite 模式中的 steps
    # 涉及 LLM 调用的类型：
    # - llm: 直接调用 LLM
    # - llm_json: 调用 LLM 并解析 JSON
    # - image_gen: 调用 LLM 生成标题（在 generate_artwall_content 中）
    # - external_data: 如果 provider 是 "briefing" 且配置了 summarize 或 include_insight，会调用 LLM
    # - composite: 递归检查 steps 中是否包含上述类型
    llm_mode_requires_quota = False
    json_mode = registry.get_json_mode(persona, mac)
    if json_mode and isinstance(json_mode.definition, dict):
        content_def = json_mode.definition.get("content", {}) or {}
        ctype = content_def.get("type")
        logger.debug(
            "[QUOTA DEBUG] Checking mode %s: ctype=%s, json_mode exists=%s",
            persona,
            ctype,
            json_mode is not None,
        )
        if ctype in ("llm", "llm_json", "image_gen"):
            llm_mode_requires_quota = True
            logger.debug("[QUOTA DEBUG] Mode %s requires quota (direct type: %s)", persona, ctype)
        elif ctype == "external_data":
            # external_data 类型中，briefing provider 会调用 LLM（如果配置了 summarize 或 include_insight）
            provider = content_def.get("provider", "")
            if provider == "briefing":
                summarize = content_def.get("summarize", True)
                include_insight = content_def.get("include_insight", True)
                if summarize or include_insight:
                    llm_mode_requires_quota = True
                    logger.debug("[QUOTA DEBUG] Mode %s requires quota (external_data briefing)", persona)
        elif ctype == "composite":
            # 递归检查 composite 模式中的 steps 是否包含需要 LLM 的类型
            steps = content_def.get("steps", [])
            logger.debug("[QUOTA DEBUG] Mode %s is composite, checking %d steps", persona, len(steps) if isinstance(steps, list) else 0)
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        step_type = step.get("type")
                        logger.debug("[QUOTA DEBUG] Checking step type: %s", step_type)
                        if step_type in ("llm", "llm_json", "image_gen"):
                            llm_mode_requires_quota = True
                            logger.debug("[QUOTA DEBUG] Mode %s requires quota (composite step: %s)", persona, step_type)
                            break
                        elif step_type == "external_data":
                            # 检查 external_data step 是否调用 LLM
                            step_provider = step.get("provider", "")
                            if step_provider == "briefing":
                                step_summarize = step.get("summarize", True)
                                step_include_insight = step.get("include_insight", True)
                                if step_summarize or step_include_insight:
                                    llm_mode_requires_quota = True
                                    logger.debug("[QUOTA DEBUG] Mode %s requires quota (composite external_data briefing)", persona)
                                    break
                        # 如果 step 本身也是 composite，需要递归检查（虽然当前没有这种嵌套，但为了完整性）
                        elif step_type == "composite":
                            nested_steps = step.get("steps", [])
                            if isinstance(nested_steps, list):
                                for nested_step in nested_steps:
                                    if isinstance(nested_step, dict):
                                        nested_type = nested_step.get("type")
                                        if nested_type in ("llm", "llm_json", "image_gen"):
                                            llm_mode_requires_quota = True
                                            logger.debug("[QUOTA DEBUG] Mode %s requires quota (nested composite step: %s)", persona, nested_type)
                                            break
                                        elif nested_type == "external_data":
                                            nested_provider = nested_step.get("provider", "")
                                            if nested_provider == "briefing":
                                                nested_summarize = nested_step.get("summarize", True)
                                                nested_include_insight = nested_step.get("include_insight", True)
                                                if nested_summarize or nested_include_insight:
                                                    llm_mode_requires_quota = True
                                                    logger.debug("[QUOTA DEBUG] Mode %s requires quota (nested composite external_data briefing)", persona)
                                                    break
                                if llm_mode_requires_quota:
                                    break
    if not llm_mode_requires_quota:
        logger.debug("[QUOTA DEBUG] Mode %s does NOT require quota", persona)

    # 检查用户是否提供了自己的 API key（如果提供了，则无需额度检查）
    # 注意：API key 现在只从用户级别配置（user_llm_config 表）获取，不再从设备配置读取
    user_provided_api_key = False
    if config:
        # BYOK 有效性判定：
        # - preset：必须有 user_api_key
        # - custom_openai：必须有 user_api_key + llm_base_url
        llm_access_mode = (config.get("llm_access_mode") or "preset").strip().lower()
        override_key = config.get("user_api_key")
        base_url = config.get("llm_base_url")
        has_key = isinstance(override_key, str) and override_key.strip()
        has_base = isinstance(base_url, str) and base_url.strip()
        if (llm_access_mode == "custom_openai" and has_key and has_base) or (
            llm_access_mode != "custom_openai" and has_key
        ):
            user_provided_api_key = True
            logger.debug(
                "[QUOTA] BYOK active (mode=%s), skipping quota check (mac=%s, user_id=%s)",
                llm_access_mode,
                mac,
                selected_config_user_id,
            )

    # 当前设备对应的计费用户（策略：owner）
    # 对于设备端：使用设备 owner 的 user_id
    # 对于 Web 预览：使用当前登录用户的 user_id（如果提供了 current_user_id）
    quota_user_id: int | None = None
    if mac:
        try:
            quota_user_id = await get_quota_owner_for_mac(mac)
        except Exception:
            logger.warning("[QUOTA] Failed to resolve quota owner for %s", mac, exc_info=True)
    elif current_user_id is not None:
        # Web 预览场景：使用当前登录用户的 user_id
        quota_user_id = current_user_id
        logger.debug("[QUOTA] Using current_user_id=%s for Web preview", current_user_id)

    if preview_city_override or preview_mode_override or preview_memo_text:
        config = copy.deepcopy(config or {})
        mode_overrides = dict(config.get("mode_overrides") or {})
        current_mode_override = dict(mode_overrides.get(persona) or {})
        if preview_city_override:
            config["city"] = preview_city_override
            current_mode_override["city"] = preview_city_override
        if isinstance(preview_mode_override, dict) and preview_mode_override:
            current_mode_override.update(preview_mode_override)
        mode_overrides[persona] = current_mode_override
        config["mode_overrides"] = mode_overrides
        config["modeOverrides"] = mode_overrides
        if persona == "MEMO":
            memo_text = current_mode_override.get("memo_text")
            if isinstance(memo_text, str) and memo_text.strip():
                config["memo_text"] = memo_text.strip()
                config["memoText"] = memo_text.strip()
            if isinstance(preview_memo_text, str) and preview_memo_text.strip():
                memo_clean = preview_memo_text.strip()
                current_mode_override["memo_text"] = memo_clean
                mode_overrides[persona] = current_mode_override
                config["mode_overrides"] = mode_overrides
                config["modeOverrides"] = mode_overrides
                config["memo_text"] = memo_clean
                config["memoText"] = memo_clean

    # 无设备预览（/preview 等）：按页面站点语言（中/英）决定 mode_language。
    # 设备配置页预览（有 mac）：沿用 configs 中保存的 mode_language，不被 ui_language 覆盖。
    if not mac and preview_ui_language in ("zh", "en"):
        config = copy.deepcopy(config or {})
        config["mode_language"] = preview_ui_language
        config["modeLanguage"] = preview_ui_language

    cache_hit = False
    quota_exhausted = False
    billing_enabled = os.getenv("INKSIGHT_BILLING_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    if mac and config and is_mode_cacheable and not skip_cache:
        if not intent_only:
            await content_cache.check_and_regenerate_all(mac, config, v, screen_w, screen_h, colors=colors)
        cached_img = await content_cache.get(
            mac,
            persona,
            config,
            screen_w=screen_w,
            screen_h=screen_h,
        )
        if cached_img:
            cache_hit = True
            img = cached_img
            # 即使缓存命中，如果这是需要 LLM 的模式且用户额度为0，也应该检查并返回兜底图
            # 避免用户通过缓存绕过额度限制
            # Root 用户无需检查额度
            # 如果用户提供了自己的 API key，也无需检查额度
            if (
                billing_enabled
                and quota_user_id is not None
                and llm_mode_requires_quota
                and (mac or current_user_id is not None)  # 设备端或 Web 预览都需要检查
                and not user_provided_api_key  # 用户提供了自己的 API key，无需检查额度
            ):
                try:
                    # 检查用户是否为 root，root 用户无需检查额度
                    user_role = await get_user_role(quota_user_id)
                    if user_role == "root":
                        logger.debug(
                            "[QUOTA] User %s is root, skipping quota check on cache hit",
                            quota_user_id,
                        )
                    else:
                        quota = await get_user_api_quota(quota_user_id)
                        if quota is None:
                            logger.warning(
                                "[QUOTA] Quota query returned None for user_id=%s (mac=%s, mode=%s) on cache hit, treating as exhausted",
                                quota_user_id,
                                mac,
                                persona,
                            )
                            quota_exhausted = True
                            # 对于设备端，返回兜底图；对于 Web 预览，返回 quota_exhausted 标志让接口处理
                            if mac:
                                img = _render_quota_exhausted_image(screen_w, screen_h)
                                await update_device_state(
                                    mac,
                                    last_persona=persona,
                                    last_refresh_at=datetime.now().isoformat(),
                                )
                                return img, persona, False, True, quota_exhausted, False, False, usage_source
                            # Web 预览：不返回图片，让接口返回 JSON 响应
                            return None, persona, False, True, quota_exhausted, False, False, usage_source
                        if int(quota.get("free_quota_remaining") or 0) <= 0:
                            quota_exhausted = True
                            logger.info(
                                "[QUOTA] Free quota exhausted for user_id=%s (mac=%s, mode=%s) on cache hit",
                                quota_user_id,
                                mac,
                                persona,
                            )
                            # 对于设备端，返回兜底图；对于 Web 预览，返回 quota_exhausted 标志让接口处理
                            if mac:
                                img = _render_quota_exhausted_image(screen_w, screen_h)
                                await update_device_state(
                                    mac,
                                    last_persona=persona,
                                    last_refresh_at=datetime.now().isoformat(),
                                )
                                return img, persona, False, True, quota_exhausted, False, False, usage_source
                            # Web 预览：不返回图片，让接口返回 JSON 响应
                            return None, persona, False, True, quota_exhausted, False, False, usage_source
                except Exception:
                    logger.warning(
                        "[QUOTA] Failed to check quota on cache hit for user_id=%s (mac=%s, mode=%s), allowing cache",
                        quota_user_id,
                        mac,
                        persona,
                        exc_info=True,
                    )
        else:
            logger.info("[CACHE MISS] %s:%s - Generating content", mac, persona)
    else:
        if skip_cache:
            logger.info("[PREVIEW] Skip cache for %s:%s", mac, persona)
        img = None

    content_data = None
    content_fallback = False

    # Cache Miss + 需要 LLM + 找到了计费用户：先检查剩余额度
    quota_exhausted = False
    # 添加调试日志，确认额度检查条件
    if not cache_hit:
        logger.info(
            "[QUOTA DEBUG] cache_hit=%s, mac=%s, quota_user_id=%s, llm_mode_requires_quota=%s, persona=%s",
            cache_hit,
            mac,
            quota_user_id,
            llm_mode_requires_quota,
            persona,
        )
    # 额度检查：需要满足以下条件之一：
    # 1. 有 mac（设备端）：检查设备 owner 的额度
    # 2. 有 current_user_id（Web 预览）：检查当前登录用户的额度
    # Root 用户无需检查额度
    # 如果用户提供了自己的 API key，也无需检查额度
    if (
        billing_enabled
        and not cache_hit
        and quota_user_id is not None
        and llm_mode_requires_quota
        and (mac or current_user_id is not None)  # 设备端或 Web 预览都需要检查
        and not user_provided_api_key  # 用户提供了自己的 API key，无需检查额度
    ):
        try:
            # 检查用户是否为 root，root 用户无需检查额度
            user_role = await get_user_role(quota_user_id)
            if user_role == "root":
                logger.debug(
                    "[QUOTA] User %s is root, skipping quota check",
                    quota_user_id,
                )
            else:
                quota = await get_user_api_quota(quota_user_id)
                if quota is None:
                    logger.warning(
                        "[QUOTA] Quota query returned None for user_id=%s (mac=%s, mode=%s), treating as exhausted",
                        quota_user_id,
                        mac,
                        persona,
                    )
                    quota_exhausted = True
                    img = _render_quota_exhausted_image(screen_w, screen_h)
                    await update_device_state(
                        mac,
                        last_persona=persona,
                        last_refresh_at=datetime.now().isoformat(),
                    )
                    return img, persona, False, True, quota_exhausted, False, False, usage_source
                if int(quota.get("free_quota_remaining") or 0) <= 0:
                    quota_exhausted = True
                    logger.info(
                        "[QUOTA] Free quota exhausted for user_id=%s (mac=%s, mode=%s)",
                        quota_user_id,
                        mac,
                        persona,
                    )
                    # 对于设备端，仍然返回1-bit兜底图（设备无法显示弹窗）
                    # 对于Web端，会在 preview 接口中检测并返回 JSON 响应
                    img = _render_quota_exhausted_image(screen_w, screen_h)
                    if mac:
                        await update_device_state(
                            mac,
                            last_persona=persona,
                            last_refresh_at=datetime.now().isoformat(),
                        )
                        return img, persona, False, True, quota_exhausted, False, False, usage_source
                    return None, persona, False, True, quota_exhausted, False, False, usage_source
        except Exception:
            quota = None
            logger.warning(
                "[QUOTA] Failed to load quota for user_id=%s (mac=%s, mode=%s)",
                quota_user_id,
                mac,
                persona,
                exc_info=True,
            )
            # 如果查询失败且不是 root 用户，为了安全起见，也视为额度耗尽并拦截
            try:
                user_role = await get_user_role(quota_user_id)
                if user_role != "root":
                    logger.warning(
                        "[QUOTA] Quota query failed for user_id=%s (mac=%s, mode=%s), treating as exhausted",
                        quota_user_id,
                        mac,
                        persona,
                    )
                    quota_exhausted = True
                    img = _render_quota_exhausted_image(screen_w, screen_h)
                    await update_device_state(
                        mac,
                        last_persona=persona,
                        last_refresh_at=datetime.now().isoformat(),
                    )
                    return img, persona, False, True, quota_exhausted, False, False, usage_source
            except Exception:
                # 如果连 role 都查不到，为了安全起见，也视为额度耗尽
                logger.warning(
                    "[QUOTA] Failed to check user role for user_id=%s (mac=%s, mode=%s), treating as exhausted",
                    quota_user_id,
                    mac,
                    persona,
                )
                quota_exhausted = True
                img = _render_quota_exhausted_image(screen_w, screen_h)
                await update_device_state(
                    mac,
                    last_persona=persona,
                    last_refresh_at=datetime.now().isoformat(),
                )
                return img, persona, False, True, quota_exhausted, False, False, usage_source
            # 更新设备状态，但不写入内容缓存，避免后续充值后仍命中"额度耗尽"图片
            await update_device_state(
                mac,
                last_persona=persona,
                last_refresh_at=datetime.now().isoformat(),
            )
            return img, persona, False, True, quota_exhausted, False, False, usage_source

    if intent_only:
        return img, persona, cache_hit, content_fallback, quota_exhausted, False, llm_mode_requires_quota, usage_source

    if not cache_hit:
        effective_cfg = get_effective_mode_config(config, persona)
        location_args = extract_location_settings(effective_cfg, fallback_city=DEFAULT_CITY)
        date_ctx, weather = await asyncio.gather(
            get_date_context(),
            get_weather(**location_args),
        )
        img, content_data = await generate_and_render(
            persona,
            config,
            date_ctx,
            weather,
            battery_pct,
            screen_w=screen_w,
            screen_h=screen_h,
            mac=mac or "",
            colors=colors,
        )
        if isinstance(content_data, dict):
            logger.debug(
                "[BUILD_IMAGE] content_data keys: %s, _is_fallback=%s, _used_fallback=%s, _llm_ok=%s",
                list(content_data.keys()),
                content_data.get("_is_fallback"),
                content_data.get("_used_fallback"),
                content_data.get("_llm_ok"),
            )
            if content_data.get("_is_fallback") is True:
                content_fallback = True
            elif content_data.get("_used_fallback") is True:
                content_fallback = True
            else:
                jm = get_registry().get_json_mode(persona, mac)
                if jm and jm.definition.get("content", {}).get("type") == "image_gen":
                    content_fallback = not bool(content_data.get("image_url"))

        if mac and config and is_mode_cacheable:
            await content_cache.set(mac, persona, img, screen_w, screen_h)

    if mac:
        await update_device_state(
            mac,
            last_persona=persona,
            last_refresh_at=datetime.now().isoformat(),
        )

    if mac and content_data:
        try:
            await save_render_content(mac, persona, content_data)
        except (OSError, ValueError, TypeError):
            logger.warning("[CONTENT] Failed to save content for %s:%s", mac, persona, exc_info=True)

    # 精准扣费：仅在 Cache Miss 且确实发生了一次成功的 LLM 调用时扣减额度
    # 支持设备端（mac）和 Web 预览（current_user_id）
    # Root 用户无需扣费
    # 如果用户提供了自己的 API key，也无需扣费
    if (
        billing_enabled
        and not cache_hit
        and quota_user_id is not None
        and (mac or current_user_id is not None)  # 设备端或 Web 预览都需要扣费
        and isinstance(content_data, dict)
        and content_data.get("_llm_used") is True
        and content_data.get("_llm_ok") is True
        and not user_provided_api_key  # 用户提供了自己的 API key，无需扣费
    ):
        try:
            # 检查用户是否为 root，root 用户无需扣费
            user_role = await get_user_role(quota_user_id)
            if user_role == "root":
                logger.debug(
                    "[QUOTA] User %s is root, skipping quota deduction",
                    quota_user_id,
                )
            else:
                deducted = await consume_user_free_quota(quota_user_id, amount=1)
                if not deducted:
                    logger.info(
                        "[QUOTA] Consume failed (no remaining free quota) for user_id=%s, mac=%s, mode=%s",
                        quota_user_id,
                        mac,
                        persona,
                    )
        except Exception:
            logger.warning(
                "[QUOTA] Failed to consume quota for user_id=%s (mac=%s, mode=%s)",
                quota_user_id,
                mac,
                persona,
                exc_info=True,
            )

    # 检查 API key 是否无效
    api_key_invalid = False
    if isinstance(content_data, dict) and content_data.get("_api_key_invalid") is True:
        api_key_invalid = True
        logger.warning(
            "[API_KEY] User provided API key is invalid or expired for mac=%s, mode=%s",
            mac,
            persona,
        )
        # 对于设备端，返回提示图片；对于 Web 预览，返回 api_key_invalid 标志让接口处理
        if mac:
            img = _render_api_key_invalid_image(screen_w, screen_h)
            await update_device_state(
                mac,
                last_persona=persona,
                last_refresh_at=datetime.now().isoformat(),
            )

    return img, persona, cache_hit, content_fallback, quota_exhausted, api_key_invalid, llm_mode_requires_quota, usage_source


async def log_render_stats(
    mac: str,
    persona: str,
    cache_hit: bool,
    elapsed_ms: int,
    *,
    voltage: float = 3.3,
    rssi: Optional[int] = None,
    status: str = "success",
    is_fallback: bool = False,
):
    try:
        await log_render(mac, persona, cache_hit, elapsed_ms, status, is_fallback=is_fallback)
        await log_heartbeat(mac, voltage, rssi)
    except (OSError, ValueError, TypeError):
        logger.warning("[STATS] Failed to log render stats for %s", mac, exc_info=True)


async def resolve_preview_voltage(v: Optional[float], mac: Optional[str]) -> float:
    if v is not None:
        return v
    if mac:
        latest_voltage = await get_latest_battery_voltage(mac)
        if latest_voltage is not None:
            return latest_voltage
    return 3.3


def resolve_refresh_minutes_for_device_state(config: Optional[dict], state: Optional[dict]) -> int:
    refresh_minutes_raw = config.get("refresh_interval") if config else DEFAULT_REFRESH_INTERVAL
    try:
        refresh_minutes = int(refresh_minutes_raw)
    except (TypeError, ValueError):
        refresh_minutes = DEFAULT_REFRESH_INTERVAL
    if refresh_minutes <= 0:
        refresh_minutes = DEFAULT_REFRESH_INTERVAL

    expected_refresh_raw = state.get("expected_refresh_min", 0) if state else 0
    try:
        expected_refresh = int(expected_refresh_raw)
    except (TypeError, ValueError):
        expected_refresh = 0
    if expected_refresh > 0:
        refresh_minutes = expected_refresh
    return refresh_minutes


def reconnect_threshold_seconds(refresh_minutes: int) -> int:
    base_seconds = max(1, int(refresh_minutes)) * 60
    return max(base_seconds + 30, int(base_seconds * 1.5))


def build_firmware_manifest(version: str, download_url: str, chip_family: str = FIRMWARE_CHIP_FAMILY) -> dict:
    return {
        "name": "InkSight",
        "version": version,
        "builds": [
            {
                "chipFamily": chip_family,
                "parts": [{"path": download_url, "offset": 0}],
            }
        ],
    }


def chip_family_from_asset_name(asset_name: str) -> str:
    name = (asset_name or "").lower()
    if "wroom32e" in name or "_esp32" in name:
        return "ESP32"
    if "_c3" in name or "esp32c3" in name:
        return "ESP32-C3"
    return FIRMWARE_CHIP_FAMILY


def pick_firmware_asset(assets: list[dict]) -> Optional[dict]:
    preferred = [
        asset
        for asset in assets
        if asset.get("name", "").endswith(".bin")
        and "inksight-firmware-" in asset.get("name", "")
    ]
    if preferred:
        return preferred[0]
    fallback = [asset for asset in assets if asset.get("name", "").endswith(".bin")]
    return fallback[0] if fallback else None


def expand_firmware_release_assets(release: dict) -> list[dict]:
    tag_name = release.get("tag_name", "")
    version = tag_name.lstrip("v") if tag_name else "unknown"
    published_at = release.get("published_at")
    items = []
    for asset in release.get("assets", []):
        asset_name = asset.get("name", "")
        if not asset_name.endswith(".bin"):
            continue
        download_url = asset.get("browser_download_url")
        if not download_url:
            continue
        chip_family = chip_family_from_asset_name(asset_name)
        items.append(
            {
                "version": version,
                "tag": tag_name,
                "published_at": published_at,
                "download_url": download_url,
                "size_bytes": asset.get("size"),
                "chip_family": chip_family,
                "asset_name": asset_name,
                "manifest": build_firmware_manifest(version, download_url, chip_family),
            }
        )
    preferred = [item for item in items if "inksight-firmware-" in item["asset_name"]]
    return preferred or items


async def load_firmware_releases(force_refresh: bool = False) -> dict:
    now = time.time()
    async with _firmware_release_cache_lock:
        if (
            not force_refresh
            and _firmware_release_cache["payload"] is not None
            and _firmware_release_cache["expires_at"] > now
        ):
            cached_payload = dict(_firmware_release_cache["payload"])
            cached_payload["cached"] = True
            return cached_payload

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "inksight-firmware-api",
        }
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GITHUB_RELEASES_API, headers=headers)
        if resp.status_code >= 400:
            message = f"GitHub releases API error: {resp.status_code}"
            try:
                details = resp.json().get("message")
                if details:
                    message = f"{message} - {details}"
            except (ValueError, TypeError, json.JSONDecodeError):
                logger.warning("[FIRMWARE] Failed to parse GitHub error payload", exc_info=True)
            raise RuntimeError(message)

        releases = []
        for release in resp.json():
            if release.get("draft"):
                continue
            releases.extend(expand_firmware_release_assets(release))

        payload = {
            "source": "github_releases",
            "repo": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            "cached": False,
            "count": len(releases),
            "releases": releases,
        }
        _firmware_release_cache["payload"] = payload
        _firmware_release_cache["expires_at"] = now + FIRMWARE_RELEASE_CACHE_TTL
        return payload


async def validate_firmware_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("firmware URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("firmware URL host is missing")
    if not parsed.path.lower().endswith(".bin"):
        raise ValueError("firmware URL should point to a .bin file")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            resp = await client.head(url)
        except httpx.HTTPError:
            logger.warning("[FIRMWARE] HEAD failed for %s, falling back to ranged GET", url, exc_info=True)
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
    if resp.status_code >= 400:
        raise RuntimeError(f"firmware URL is not reachable: {resp.status_code}")

    return {
        "ok": True,
        "reachable": True,
        "status_code": resp.status_code,
        "final_url": str(resp.url),
        "content_type": resp.headers.get("content-type"),
        "content_length": resp.headers.get("content-length"),
    }


def normalize_pushed_preview(image_bytes: bytes, *, width: int, height: int) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as incoming:
        img = incoming.convert("1")
        if img.size != (width, height):
            img = img.resize((width, height), Image.NEAREST)
        return image_to_bmp_bytes(img)


def _render_api_key_invalid_image(screen_w: int, screen_h: int) -> Image.Image:
    """渲染 API key 无效提示图（1-bit），对 ESP32 固件保持兼容。

    始终返回 mode=\"1\" 的黑白图像，调用方按 BMP 返回给设备（HTTP 200）。
    """
    img = Image.new("1", (screen_w, screen_h), 1)  # 1 = 白色背景
    draw = ImageDraw.Draw(img)
    message = "API key 无效或已过期，请检查设备配置"
    try:
        font = load_font("noto_serif_regular", 12)
    except Exception:  # pragma: no cover - 极端环境下回退
        font = None
    try:
        if font:
            bbox = draw.textbbox((0, 0), message, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            text_w = len(message) * 6
            text_h = 10
        x = (screen_w - text_w) // 2
        y = (screen_h - text_h) // 2
        draw.text((x, y), message, fill=0, font=font)  # 0 = 黑色文字
    except Exception:
        logger.warning("[RENDER] Failed to render API key invalid message", exc_info=True)
    return img


def _render_quota_exhausted_image(screen_w: int, screen_h: int) -> Image.Image:
    """渲染额度耗尽提示图（1-bit），对 ESP32 固件保持兼容。

    始终返回 mode=\"1\" 的黑白图像，调用方按 BMP 返回给设备（HTTP 200）。
    """
    img = Image.new("1", (screen_w, screen_h), 1)  # 1 = 白色背景
    draw = ImageDraw.Draw(img)
    message = "您的免费额度已用完，请联系管理员"
    try:
        font = load_font("noto_serif_regular", 12)
    except Exception:  # pragma: no cover - 极端环境下回退
        font = None
    try:
        if font:
            bbox = draw.textbbox((0, 0), message, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            text_w = len(message) * 6
            text_h = 10
        x = max(0, (screen_w - text_w) // 2)
        y = max(0, (screen_h - text_h) // 2)
        draw.text((x, y), message, fill=0, font=font)
    except Exception:
        logger.warning("[RENDER] Failed to render quota exhausted message", exc_info=True)
    return img


def _render_device_unbound_image(screen_w: int, screen_h: int, pair_code: str) -> Image.Image:
    img = Image.new("1", (screen_w, screen_h), 1)
    draw = ImageDraw.Draw(img)
    title = "欢迎使用 InkSight"
    pair_line = f"配对码：{pair_code}" if pair_code else "正在生成配对码..."
    hint = "请在设备配置页输入配对码完成绑定"
    try:
        title_font = load_font("noto_serif_regular", 20)
        body_font = load_font("noto_serif_regular", 14)
    except Exception:
        title_font = None
        body_font = None
    try:
        if title_font:
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_w = title_bbox[2] - title_bbox[0]
            title_h = title_bbox[3] - title_bbox[1]
        else:
            title_w = len(title) * 10
            title_h = 18
        if body_font:
            pair_bbox = draw.textbbox((0, 0), pair_line, font=body_font)
            hint_bbox = draw.textbbox((0, 0), hint, font=body_font)
            pair_w = pair_bbox[2] - pair_bbox[0]
            pair_h = pair_bbox[3] - pair_bbox[1]
            hint_w = hint_bbox[2] - hint_bbox[0]
            hint_h = hint_bbox[3] - hint_bbox[1]
        else:
            pair_w = len(pair_line) * 7
            pair_h = 12
            hint_w = len(hint) * 7
            hint_h = 12
        spacing = 18
        total_h = title_h + pair_h + hint_h + spacing * 2
        y = max(16, (screen_h - total_h) // 2)
        draw.text((max(0, (screen_w - title_w) // 2), y), title, fill=0, font=title_font)
        y += title_h + spacing
        draw.text((max(0, (screen_w - pair_w) // 2), y), pair_line, fill=0, font=body_font)
        y += pair_h + spacing
        draw.text((max(0, (screen_w - hint_w) // 2), y), hint, fill=0, font=body_font)
    except Exception:
        logger.warning("[RENDER] Failed to render device unbound message", exc_info=True)
    return img
