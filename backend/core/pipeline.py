"""
统一的内容生成 + 渲染管道
支持内置 Python 模式和 JSON 定义模式的统一分发
"""
from __future__ import annotations

import logging
from PIL import Image

from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_IMAGE_PROVIDER,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_CONTENT_TONE,
)

logger = logging.getLogger(__name__)


def get_effective_mode_config(cfg: dict | None, persona: str) -> dict:
    base = dict(cfg or {})
    mode_overrides = base.get("mode_overrides", {})
    if not isinstance(mode_overrides, dict):
        return base
    override = mode_overrides.get((persona or "").upper(), {})
    if not isinstance(override, dict):
        return base
    for key in ("city", "llm_provider", "llm_model"):
        value = override.get(key)
        if isinstance(value, str) and value.strip():
            base[key] = value.strip()
    reserved = {"city", "llm_provider", "llm_model", "llmProvider", "llmModel"}
    mode_settings = {k: v for k, v in override.items() if k not in reserved}
    if mode_settings:
        base["mode_settings"] = mode_settings
    return base


async def generate_and_render(
    persona: str,
    config: dict | None,
    date_ctx: dict,
    weather: dict,
    battery_pct: float,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
    mac: str = "",
) -> tuple[Image.Image, dict | None]:
    """Generate content for a persona and render to an e-ink image.

    Dispatches to either a builtin Python mode or a JSON-defined mode
    via the mode registry.

    Returns:
        Tuple of (rendered image, content dict).
    """
    date_str = date_ctx["date_str"]
    time_str = date_ctx.get("time_str", "")
    weather_str = weather["weather_str"]
    weather_code = weather.get("weather_code", -1)
    cfg = get_effective_mode_config(config, persona)

    content = await _generate_content_for_persona(
        persona,
        cfg,
        date_ctx,
        weather_str,
        mac=mac,
        screen_w=screen_w,
        screen_h=screen_h,
    )

    img = _render_for_persona(
        persona,
        content,
        date_str=date_str,
        weather_str=weather_str,
        battery_pct=battery_pct,
        weather_code=weather_code,
        time_str=time_str,
        date_ctx=date_ctx,
        screen_w=screen_w,
        screen_h=screen_h,
        mac=mac or "",
    )
    return img, content


async def generate_content_only(
    persona: str,
    config: dict | None,
    date_ctx: dict,
    weather: dict,
    *,
    mac: str = "",
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
) -> dict:
    cfg = get_effective_mode_config(config, persona)
    return await _generate_content_for_persona(
        persona,
        cfg,
        date_ctx,
        weather.get("weather_str", ""),
        mac=mac,
        screen_w=screen_w,
        screen_h=screen_h,
    )


async def _generate_content_for_persona(
    persona: str,
    cfg: dict,
    date_ctx: dict,
    weather_str: str,
    mac: str = "",
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
) -> dict:
    """Dispatch content generation to the appropriate handler."""
    from .mode_registry import ContentContext, get_registry

    registry = get_registry()
    date_str = date_ctx["date_str"]

    # 解析 API key 来源（用户级别优先，其次设备配置，最后环境变量）
    # 使用 None 表示「未提供 key，将在下游从环境变量读取」；
    # 使用空字符串 "" 表示「用户提供了但无效」，便于上游给出明确提示。
    device_api_key: str | None = None
    device_image_api_key: str | None = None

    # 使用用户级别的 API key 配置（不再从设备配置读取）
    # 用户级别的配置通过 shared.py 中的 get_user_llm_config 获取并设置到 config["user_api_key"]
    user_api_key = cfg.get("user_api_key")
    if isinstance(user_api_key, str):
        device_api_key = user_api_key
        logger.info(
            "[Pipeline] Using user_api_key for persona=%s (mac=%s), length=%s",
            persona,
            mac,
            len(user_api_key) if user_api_key else 0,
        )
    else:
        logger.info("[Pipeline] No user_api_key in config, will use env var")
    
    user_image_api_key = cfg.get("user_image_api_key")
    if isinstance(user_image_api_key, str):
        device_image_api_key = user_image_api_key
        logger.info(
            "[Pipeline] Using user_image_api_key for persona=%s (mac=%s), length=%s",
            persona,
            mac,
            len(user_image_api_key) if user_image_api_key else 0,
        )

    ctx = ContentContext(
        config=cfg,
        date_ctx=date_ctx,
        weather_str=weather_str,
        date_str=date_str,
        festival=date_ctx.get("festival", ""),
        daily_word=date_ctx.get("daily_word", ""),
        upcoming_holiday=date_ctx.get("upcoming_holiday", ""),
        days_until_holiday=date_ctx.get("days_until_holiday", 0),
        character_tones=cfg.get("character_tones", []),
        language=cfg.get("language", DEFAULT_LANGUAGE),
        content_tone=cfg.get("content_tone", DEFAULT_CONTENT_TONE),
        llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
        llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
        api_key=device_api_key,
        image_api_key=device_image_api_key,
        llm_base_url=cfg.get("llm_base_url"),
    )

    # JSON-defined mode
    if registry.is_json_mode(persona):
        from .json_content import generate_json_mode_content
        jm = registry.get_json_mode(persona, mac)
        if not jm:
            # Try to load from database if mode not in registry
            # This can happen for user-specific custom modes
            if mac:
                from .config_store import get_device_owner, get_custom_mode as get_user_custom_mode_from_db
                owner = await get_device_owner(mac)
                if owner:
                    user_id = owner.get("user_id")
                    if user_id:
                        # Load mode from database for the specific device
                        mode_data = await get_user_custom_mode_from_db(user_id, persona, mac)
                        if mode_data:
                            # Load into registry for this request
                            mode_mac = mode_data.get("mac")
                            registry.load_custom_mode_from_dict(persona, mode_data["definition"], source="custom", mac=mode_mac)
                            jm = registry.get_json_mode(persona, mac)
        if not jm:
            raise ValueError(f"JSON mode {persona} not found in registry")
        return await generate_json_mode_content(
            jm.definition,
            config=cfg,
            date_ctx=date_ctx,
            date_str=date_str,
            weather_str=weather_str,
            festival=date_ctx.get("festival", ""),
            daily_word=date_ctx.get("daily_word", ""),
            upcoming_holiday=date_ctx.get("upcoming_holiday", ""),
            days_until_holiday=date_ctx.get("days_until_holiday", 0),
            character_tones=cfg.get("character_tones", []),
            language=cfg.get("language", DEFAULT_LANGUAGE),
            content_tone=cfg.get("content_tone", DEFAULT_CONTENT_TONE),
            llm_provider=cfg.get("llm_provider", DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", DEFAULT_LLM_MODEL),
            llm_base_url=cfg.get("llm_base_url"),
            image_provider=cfg.get("image_provider", DEFAULT_IMAGE_PROVIDER),
            image_model=cfg.get("image_model", DEFAULT_IMAGE_MODEL),
            mac=mac,
            screen_w=screen_w,
            screen_h=screen_h,
            api_key=device_api_key,
            image_api_key=device_image_api_key,
        )

    # Builtin Python mode - use specialized content functions
    bm = registry.get_builtin(persona)
    if bm:
        return await bm.content_fn(ctx)

    raise ValueError(f"Unknown persona: {persona}")


def _render_for_persona(
    persona: str,
    content: dict,
    *,
    date_str: str,
    weather_str: str,
    battery_pct: float,
    weather_code: int = -1,
    time_str: str = "",
    date_ctx: dict | None = None,
    screen_w: int = SCREEN_WIDTH,
    screen_h: int = SCREEN_HEIGHT,
    mac: str = "",
) -> Image.Image:
    """Dispatch rendering to the appropriate handler."""
    from .mode_registry import get_registry
    from .renderer import render_mode
    from .json_renderer import render_json_mode

    registry = get_registry()

    # JSON-defined mode
    if registry.is_json_mode(persona):
        # mac 为空字符串表示 Web 预览等无设备场景，此时只根据 persona 取 JSON 模式
        jm = registry.get_json_mode(persona, mac or None)
        # Weather 模式下不在状态栏中间重复显示简略天气（只保留日期、电量等）
        if persona.upper() == "WEATHER":
            weather_str_for_bar = ""
            weather_code_for_bar = -1
        else:
            weather_str_for_bar = weather_str
            weather_code_for_bar = weather_code
        return render_json_mode(
            jm.definition, content,
            date_str=date_str, weather_str=weather_str_for_bar, battery_pct=battery_pct,
            weather_code=weather_code_for_bar, time_str=time_str,
            screen_w=screen_w, screen_h=screen_h,
        )

    # Builtin Python mode - use original render_mode dispatcher
    return render_mode(
        persona, content,
        date_str=date_str, weather_str=weather_str, battery_pct=battery_pct,
        weather_code=weather_code, time_str=time_str, date_ctx=date_ctx,
        screen_w=screen_w, screen_h=screen_h,
    )
