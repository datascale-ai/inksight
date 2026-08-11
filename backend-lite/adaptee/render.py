"""渲染适配层：模式选择 + 调 core.pipeline.generate_and_render + BMP 编码。

刻意不复用上游 api/shared.build_image（耦合多用户 store）。这里自己实现
单用户单设备的极薄渲染路径：每次请求直接生成，不做缓存（单设备刷图
频率低，LLM 调用本就该新鲜；后续如需省调用再加 cache）。
"""
from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any

from PIL import Image

from core.context import calc_battery_pct
from core.mode_registry import get_registry
from core.pipeline import generate_and_render
from core.renderer import image_to_bmp_bytes, image_to_raw_2bpp

from .context import build_context
from store import config_store, secret_store

logger = logging.getLogger("backend-lite.render")

# 与上游 api/shared._SMART_TIME_SLOTS 一致
_SMART_TIME_SLOTS = [
    (6, 9, ["RECIPE", "DAILY"]),
    (9, 12, ["BRIEFING", "STOIC"]),
    (12, 14, ["ZEN", "POETRY"]),
    (14, 18, ["STOIC", "ROAST"]),
    (18, 21, ["FITNESS", "RECIPE"]),
    (21, 24, ["ZEN", "POETRY"]),
    (0, 6, ["ZEN", "POETRY"]),
]

DEFAULT_MODES = ["STOIC", "ROAST", "ZEN", "DAILY"]


def _choose_persona(config: dict[str, Any], mac: str) -> str:
    """单用户模式选择：random / cycle / time_slot / smart。"""
    registry = get_registry()
    modes = config.get("modes") or DEFAULT_MODES
    strategy = config.get("refresh_strategy", "random")

    # pending_mode 优先
    pending = config_store.consume_pending_mode(mac)
    if pending and registry.is_supported(pending.upper()):
        return pending.upper()

    def _supported(cands: list[str]) -> list[str]:
        return [c for c in cands if registry.is_supported(c.upper())]

    if strategy == "cycle" and modes:
        idx, persona = config_store.advance_cycle(mac, [m.upper() for m in modes])
        return persona.upper() if registry.is_supported(persona.upper()) else (modes[0].upper() if modes else "STOIC")

    if strategy == "time_slot":
        hour = datetime.now().hour
        for rule in (config.get("time_slot_rules") or []):
            sh = rule.get("startHour", 0)
            eh = rule.get("endHour", 24)
            rm = rule.get("modes", [])
            if sh <= hour < eh and rm:
                avail = _supported([m.upper() for m in rm if m in modes])
                if avail:
                    return random.choice(avail)
        return random.choice(_supported([m.upper() for m in modes]) or DEFAULT_MODES)

    if strategy == "smart":
        hour = datetime.now().hour
        for sh, eh, cands in _SMART_TIME_SLOTS:
            if sh <= hour < eh:
                avail = _supported([c for c in cands if c in modes])
                if avail:
                    return random.choice(avail)
        return random.choice(_supported([m.upper() for m in modes]) or DEFAULT_MODES)

    # random
    avail = _supported([m.upper() for m in modes]) or DEFAULT_MODES
    persona = random.choice(avail)
    # 记录 last_persona（非 cycle 也记，便于观察）
    config_store.upsert_state(mac, last_persona=persona,
                              last_refresh_at=datetime.now().isoformat(timespec="seconds"))
    return persona


def _inject_llm_key(config: dict[str, Any]) -> dict[str, Any]:
    """把解密后的 key/provider 塞进 cfg，走 core 的 caller-supplied 优先路径。

    对 openai_compat：动态把当前模型注册到 core.content.LLM_CONFIGS，
    给它一个更稳妥的默认 max_tokens，避免 llm_json 模式在未知模型名时
    回落到 120 tokens 而被截断。
    """
    cfg = dict(config)
    key = secret_store.get_llm_key()
    provider = (key.get("provider") or "").strip()
    if provider:
        cfg["llm_provider"] = provider
        if provider == "openai_compat":
            if key.get("base_url"):
                cfg["llm_base_url"] = key["base_url"]
            model = (cfg.get("llm_model") or "").strip()
            if model:
                try:
                    from core.content import LLM_CONFIGS
                    models = LLM_CONFIGS.setdefault("openai_compat", {}).setdefault("models", {})
                    models.setdefault(model, {"name": model, "max_tokens": 1024})
                except Exception:
                    logger.warning("[render] failed to register openai_compat model %s", model, exc_info=True)
    if key.get("api_key"):
        cfg["user_api_key"] = key["api_key"]
    if key.get("image_api_key"):
        cfg["user_image_api_key"] = key["image_api_key"]
    return cfg


async def render_for_device(
    mac: str,
    *,
    battery_voltage: float,
    screen_w: int = 400,
    screen_h: int = 300,
    colors: int = 4,
) -> dict[str, Any]:
    """渲染一张图。返回 {image, persona, fallback, refresh_minutes}。

    fallback=True 表示走了降级内容（LLM 失败等）。
    """
    config = config_store.get_config()
    cfg = _inject_llm_key(config)
    date_ctx, weather = await build_context(cfg)
    persona = _choose_persona(cfg, mac)
    battery_pct = calc_battery_pct(battery_voltage) if battery_voltage else 0

    refresh_min = int(config.get("refresh_interval") or 60)
    if refresh_min < 10:
        refresh_min = 10
    if refresh_min > 1440:
        refresh_min = 1440

    try:
        img, content = await generate_and_render(
            persona,
            cfg,
            date_ctx,
            weather,
            battery_pct,
            screen_w=screen_w,
            screen_h=screen_h,
            mac=mac,
            colors=colors,
        )
        fallback = bool(content is None)
    except Exception:
        logger.exception("[render] generate_and_render failed for persona=%s", persona)
        # 极端兜底：空白图
        img = Image.new("P", (screen_w, screen_h), 1)
        fallback = True
        content = None

    return {
        "image": img,
        "persona": persona,
        "fallback": fallback,
        "refresh_minutes": refresh_min,
    }


async def render_for_preview(
    persona: str,
    *,
    screen_w: int = 400,
    screen_h: int = 300,
    colors: int = 4,
) -> Image.Image:
    """预览：不碰 device_state，不消费 pending_mode。"""
    config = config_store.get_config()
    cfg = _inject_llm_key(config)
    date_ctx, weather = await build_context(cfg)
    registry = get_registry()
    p = persona.upper()
    if not registry.is_supported(p):
        p = (config.get("modes") or DEFAULT_MODES)[0].upper()
    img, _ = await generate_and_render(
        p, cfg, date_ctx, weather, 0,
        screen_w=screen_w, screen_h=screen_h, mac="", colors=colors,
    )
    return img


def encode_image(img: Image.Image, colors: int) -> bytes:
    """colors>=3 → raw 2bpp（4 色 e-ink）；否则标准 BMP。"""
    if colors >= 3:
        return image_to_raw_2bpp(img)
    return image_to_bmp_bytes(img)


def encode_png(img: Image.Image) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()