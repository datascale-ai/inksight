from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Cookie, Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from api.shared import ensure_web_or_device_access
from core.auth import optional_user, require_user
from core.config import (
    DEFAULT_CITY,
    DEFAULT_CONTENT_TONE,
    DEFAULT_LANGUAGE,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_MODES,
)
from core.config_store import (
    get_active_config,
    get_user_preferences,
    register_push_token,
    save_user_preferences,
    unregister_push_token,
)
from core.context import get_date_context, get_weather
from core.mode_registry import get_registry
from core.pipeline import generate_content_only
from core.schemas import PushRegistrationRequest, UserPreferencesRequest
from core.stats_store import get_content_history, get_latest_render_content

router = APIRouter(tags=["mobile"])


def _first_text(value) -> str:
    if isinstance(value, str):
        text = value.strip()
        return text
    if isinstance(value, dict):
        for candidate in value.values():
            text = _first_text(candidate)
            if text:
                return text
    if isinstance(value, list):
        for candidate in value:
            text = _first_text(candidate)
            if text:
                return text
    return ""


def _pick_summary(content: dict) -> str:
    for key in (
        "quote",
        "text",
        "question",
        "challenge",
        "body",
        "interpretation",
        "summary",
        "daily_word",
        "event_title",
        "advice",
    ):
        text = _first_text(content.get(key))
        if text:
            return text[:120]
    return ""


def _fallback_content(mode_id: str, city: str) -> dict:
    return {
        "title": f"{mode_id} fallback",
        "text": "InkSight 正在等待可用的 LLM 配置。",
        "summary": f"当前未配置 API key，先返回 {mode_id} 的占位内容。",
        "city": city,
    }


def _pick_title(content: dict, fallback: str) -> str:
    for key in ("title", "question", "quote", "text", "summary"):
        text = _first_text(content.get(key))
        if text:
            return text[:40]
    return fallback


def _build_recommendation_reason(mode_id: str, date_ctx: dict, weather: dict) -> str:
    hour = int(date_ctx.get("hour") or 0)
    daily_word = str(date_ctx.get("daily_word") or "").strip()
    weather_summary = str(weather.get("weather_str") or "").strip()
    festival = str(date_ctx.get("festival") or "").strip()

    if mode_id == "WEATHER":
        return f"根据今天的天气 {weather_summary}，先把实用安排放到前面。".strip()
    if mode_id == "POETRY":
        return "今天的节奏适合留一点安静给自己。"
    if mode_id == "LETTER":
        return "今天适合读一段更有陪伴感的内容。"
    if hour < 10:
        return f"用一句有方向感的话开始今天。{daily_word[:12] if daily_word else ''}".strip()
    if festival:
        return f"临近 {festival}，这条内容会更有当下感。"
    return "这是一条适合今天先看到的慢信息。"


def _build_header_meta(city: str, date_ctx: dict, weather: dict) -> dict:
    upcoming_holiday = str(date_ctx.get("upcoming_holiday") or "").strip()
    days_until = int(date_ctx.get("days_until_holiday") or 0)
    season_label = (
        f"{upcoming_holiday}还有{days_until}天"
        if upcoming_holiday and days_until > 0
        else str(date_ctx.get("festival") or date_ctx.get("month_cn") or "").strip()
    )
    return {
        "date_label": str(date_ctx.get("date_str") or "").strip(),
        "weather_summary": f"{city} · {str(weather.get('weather_str') or '--°C').strip()}",
        "season_label": season_label,
        "daily_keyword": str(date_ctx.get("daily_word") or "").strip()[:14],
    }


def _normalize_modes(raw_modes: str, limit: int) -> list[str]:
    registry = get_registry()
    items = [item.strip().upper() for item in raw_modes.split(",") if item.strip()]
    if not items:
        items = list(DEFAULT_MODES)
    deduped: list[str] = []
    for mode in items:
        if mode in deduped or not registry.is_supported(mode):
            continue
        deduped.append(mode)
    return deduped[:limit]


def _preview_url(mode_id: str, *, city: str | None = None, mac: str | None = None) -> str:
    params: dict[str, str] = {"persona": mode_id}
    if city:
        params["city_override"] = city
    if mac:
        params["mac"] = mac
    return f"/api/preview?{urlencode(params)}"


def _base_mobile_config(*, city: str, locale: str, widget_mode: str = "STOIC") -> dict:
    return {
        "modes": [widget_mode],
        "city": city,
        "language": locale,
        "content_tone": DEFAULT_CONTENT_TONE,
        "llm_provider": DEFAULT_LLM_PROVIDER,
        "llm_model": DEFAULT_LLM_MODEL,
    }


@router.get("/content/today")
async def get_today_content(
    request: Request,
    modes: str = Query(default="DAILY,POETRY,WEATHER"),
    city: str = Query(default=DEFAULT_CITY),
    locale: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=10),
    user_id: Optional[int] = Depends(optional_user),
):
    prefs = await get_user_preferences(user_id) if user_id else None
    resolved_locale = (locale or (prefs or {}).get("locale") or DEFAULT_LANGUAGE).lower()
    selected_modes = _normalize_modes(modes, limit)
    date_ctx = await get_date_context()
    weather = await get_weather(city=city)
    registry = get_registry()

    items: list[dict] = []
    for mode_id in selected_modes:
        try:
            content = await generate_content_only(
                mode_id,
                _base_mobile_config(city=city, locale=resolved_locale, widget_mode=mode_id),
                date_ctx,
                weather,
            )
        except Exception:
            content = _fallback_content(mode_id, city)
        info = registry.get_mode_info(mode_id)
        items.append(
            {
                "mode_id": mode_id,
                "display_name": info.display_name if info else mode_id,
                "icon": info.icon if info else "star",
                "title": _pick_title(content, info.display_name if info else mode_id),
                "summary": _pick_summary(content),
                "content": content,
                "preview_url": _preview_url(mode_id, city=city),
                "image_url": _preview_url(mode_id, city=city),
                "recommendation_reason": _build_recommendation_reason(mode_id, date_ctx, weather),
            }
        )

    hero_item = items[0] if items else None
    secondary_items = items[1:3] if len(items) > 1 else []

    return {
        "generated_at": datetime.now().isoformat(),
        "date": date_ctx,
        "weather": weather,
        "header_meta": _build_header_meta(city, date_ctx, weather),
        "hero_item": hero_item,
        "secondary_items": secondary_items,
        "items": items,
    }


@router.get("/user/preferences")
async def read_user_preferences(user_id: int = Depends(require_user)):
    return await get_user_preferences(user_id)


@router.put("/user/preferences")
async def update_user_preferences(
    body: UserPreferencesRequest,
    user_id: int = Depends(require_user),
):
    prefs = await save_user_preferences(user_id, body.model_dump())
    return {"ok": True, "preferences": prefs}


@router.post("/push/register")
async def push_register(
    body: PushRegistrationRequest,
    user_id: int = Depends(require_user),
):
    record = await register_push_token(
        user_id,
        body.push_token,
        body.platform,
        body.timezone,
        push_time=body.push_time,
    )
    return {"ok": True, "registration": record}


@router.delete("/push/unregister")
async def push_unregister(
    body: dict = Body(default_factory=dict),
    user_id: int = Depends(require_user),
):
    push_token = str(body.get("push_token") or "").strip()
    if not push_token:
        return JSONResponse({"error": "push_token is required"}, status_code=400)
    deleted = await unregister_push_token(user_id, push_token)
    return {"ok": True, "deleted": deleted}


@router.get("/widget/{mac}/data")
async def get_widget_data(
    mac: str,
    request: Request,
    mode: str = Query(default=""),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await ensure_web_or_device_access(request, mac.upper(), x_device_token, ink_session)
    config = await get_active_config(mac.upper())
    available_modes = config.get("modes", DEFAULT_MODES) if config else DEFAULT_MODES
    selected_mode = (mode.strip().upper() or available_modes[0]).upper()
    if selected_mode not in get_registry().get_supported_ids():
        return JSONResponse({"error": f"unsupported mode: {selected_mode}"}, status_code=400)

    latest = await get_latest_render_content(mac.upper())
    latest_history = await get_content_history(mac.upper(), limit=1, mode=selected_mode)
    if latest and latest.get("mode_id", "").upper() == selected_mode:
        content = latest["content"]
        updated_at = latest_history[0]["time"] if latest_history else ""
    else:
        city = (config or {}).get("city", DEFAULT_CITY)
        locale = (config or {}).get("language", DEFAULT_LANGUAGE)
        date_ctx = await get_date_context()
        weather = await get_weather(city=city)
        try:
            content = await generate_content_only(
                selected_mode,
                (config or _base_mobile_config(city=city, locale=locale, widget_mode=selected_mode)),
                date_ctx,
                weather,
                mac=mac.upper(),
            )
        except Exception:
            content = _fallback_content(selected_mode, city)
        updated_at = datetime.now().isoformat()

    info = get_registry().get_mode_info(selected_mode)
    return {
        "mac": mac.upper(),
        "mode_id": selected_mode,
        "display_name": info.display_name if info else selected_mode,
        "icon": info.icon if info else "star",
        "updated_at": updated_at,
        "preview_url": _preview_url(selected_mode, mac=mac.upper(), city=(config or {}).get("city")),
        "content": content,
    }
