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
from core.context import extract_location_settings, get_date_context, get_weather
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
        "note",
        "title",
    ):
        text = _first_text(content.get(key))
        if text:
            # For poetry: prefer "title — author" when only title matches,
            # otherwise show title or first poem line (truncated at 120 chars).
            if key == "title" and content.get("author"):
                author = _first_text(content.get("author"))
                if author:
                    return f"{text} — {author}"
            return text[:120]
    # Poetry stores lines as a list; fall back to first line.
    lines = content.get("lines")
    if isinstance(lines, list) and lines:
        first = _first_text(lines[0])
        if first:
            return first[:120]
    return ""


def _fallback_content(mode_id: str, city: str) -> dict:
    return {
        "title": f"{mode_id} fallback",
        "text": "InkSight 正在等待可用的 LLM 配置。",
        "summary": f"当前未配置 API key，先返回 {mode_id} 的占位内容。",
        "city": city,
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
    weather = await get_weather(**extract_location_settings({"city": city}, fallback_city=DEFAULT_CITY))
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
                "summary": _pick_summary(content),
                "content": content,
                "preview_url": _preview_url(mode_id, city=city),
                "image_url": _preview_url(mode_id, city=city),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "date": date_ctx,
        "weather": weather,
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
        effective_cfg = config or {}
        city = effective_cfg.get("city", DEFAULT_CITY)
        locale = (config or {}).get("language", DEFAULT_LANGUAGE)
        date_ctx = await get_date_context()
        weather = await get_weather(**extract_location_settings(effective_cfg, fallback_city=DEFAULT_CITY))
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
