import base64
import io
import json
import time
from datetime import datetime
from json import JSONDecodeError
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError

from api.shared import (
    _preview_push_queue,
    _preview_push_queue_lock,
    build_image,
    content_cache,
    ensure_web_or_device_access,
    limiter,
    log_render_stats,
    logger,
    reconnect_threshold_seconds,
    resolve_preview_voltage,
    resolve_refresh_minutes_for_device_state,
)
from core.auth import require_device_token, validate_mac_param
from core.config import SCREEN_HEIGHT, SCREEN_WIDTH
from core.config_store import consume_pending_refresh, get_active_config, get_device_state, update_device_state
from core.context import get_date_context, get_weather
from core.pipeline import generate_and_render
from core.renderer import image_to_bmp_bytes, image_to_png_bytes, render_error
from core.schemas import RenderQuery
from core.stats_store import get_latest_heartbeat

router = APIRouter(tags=["render"])


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/render")
@limiter.limit("10/minute")
async def render(
    request: Request,
    params: Annotated[RenderQuery, Depends()],
    x_device_token: Optional[str] = Header(default=None),
):
    mac = params.mac
    if mac:
        mac = validate_mac_param(mac)
        await require_device_token(mac, x_device_token)

    start_time = time.time()
    force_next = params.next_mode == 1

    try:
        if mac:
            async with _preview_push_queue_lock:
                pushed_payload = _preview_push_queue.pop(mac, None)
            if pushed_payload and pushed_payload.get("image"):
                try:
                    with Image.open(io.BytesIO(pushed_payload["image"])) as pushed_img:
                        img = pushed_img.convert("1")
                        if img.size != (params.w, params.h):
                            img = img.resize((params.w, params.h), Image.NEAREST)
                    bmp_bytes = image_to_bmp_bytes(img)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    resolved_persona = pushed_payload.get("mode") or params.persona or "PUSH_PREVIEW"
                    await log_render_stats(
                        mac,
                        resolved_persona,
                        False,
                        elapsed_ms,
                        voltage=params.v,
                        rssi=params.rssi,
                    )
                    if params.refresh_min is not None:
                        await update_device_state(mac, expected_refresh_min=params.refresh_min)
                    headers = {"X-Preview-Push": "1"}
                    if await consume_pending_refresh(mac):
                        headers["X-Pending-Refresh"] = "1"
                    return Response(content=bmp_bytes, media_type="image/bmp", headers=headers)
                except (OSError, TypeError, UnidentifiedImageError, ValueError) as exc:
                    logger.warning("[RENDER] Failed to deliver pushed preview for %s: %s", mac, exc)

        skip_cache_for_this_render = False
        if mac:
            cfg = await get_active_config(mac)
            if cfg:
                state = await get_device_state(mac)
                refresh_minutes = resolve_refresh_minutes_for_device_state(cfg, state)
                latest_heartbeat = await get_latest_heartbeat(mac)
                if latest_heartbeat and latest_heartbeat.get("created_at"):
                    try:
                        now_dt = datetime.now()
                        delta_seconds = (
                            now_dt - datetime.fromisoformat(latest_heartbeat["created_at"])
                        ).total_seconds()
                        threshold_seconds = reconnect_threshold_seconds(refresh_minutes)
                        last_regen_raw = state.get("last_reconnect_regen_at", "") if state else ""
                        regen_cooldown_ok = True
                        if isinstance(last_regen_raw, str) and last_regen_raw:
                            since_last_regen = (
                                now_dt - datetime.fromisoformat(last_regen_raw)
                            ).total_seconds()
                            regen_cooldown_ok = since_last_regen > threshold_seconds
                        if delta_seconds > threshold_seconds and regen_cooldown_ok:
                            skip_cache_for_this_render = True
                            await update_device_state(
                                mac, last_reconnect_regen_at=now_dt.isoformat()
                            )
                            await content_cache.force_regenerate_all(
                                mac, cfg, params.v, params.w, params.h
                            )
                    except (TypeError, ValueError, OSError):
                        logger.warning("[RECONNECT] Failed to evaluate reconnect policy for %s", mac, exc_info=True)

        img, resolved_persona, cache_hit, content_fallback, quota_exhausted, api_key_invalid = await build_image(
            params.v,
            mac,
            params.persona,
            screen_w=params.w,
            screen_h=params.h,
            force_next=force_next,
            skip_cache=skip_cache_for_this_render,
        )

        if img.size != (params.w, params.h):
            logger.warning(
                "[RENDER] Image size mismatch for %s:%s: got %sx%s, expected %sx%s. Resizing.",
                mac,
                resolved_persona,
                img.size[0],
                img.size[1],
                params.w,
                params.h,
            )
            img = img.resize((params.w, params.h), Image.NEAREST)

        bmp_bytes = image_to_bmp_bytes(img)
        elapsed_ms = int((time.time() - start_time) * 1000)
        if mac:
            await log_render_stats(
                mac,
                resolved_persona,
                cache_hit,
                elapsed_ms,
                voltage=params.v,
                rssi=params.rssi,
            )
            if params.refresh_min is not None:
                await update_device_state(mac, expected_refresh_min=params.refresh_min)

        headers: dict[str, str] = {}
        if mac and await consume_pending_refresh(mac):
            headers["X-Pending-Refresh"] = "1"
        if content_fallback:
            headers["X-Content-Fallback"] = "1"

        return Response(content=bmp_bytes, media_type="image/bmp", headers=headers)
    except (OSError, RuntimeError, TypeError, UnidentifiedImageError, ValueError) as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error("[RENDER] Failed: %s", exc, exc_info=True)
        if mac:
            await log_render_stats(
                mac,
                params.persona or "unknown",
                False,
                elapsed_ms,
                voltage=params.v,
                rssi=params.rssi,
                status="error",
            )
        err_img = render_error(mac=mac or "unknown", screen_w=params.w, screen_h=params.h)
        return Response(
            content=image_to_bmp_bytes(err_img),
            media_type="image/bmp",
            status_code=500,
        )


@router.get("/widget/{mac}")
async def get_widget(
    mac: str,
    mode: str = "",
    w: int = 400,
    h: int = 300,
    size: str = "",
    x_device_token: Optional[str] = Header(default=None),
):
    await require_device_token(mac, x_device_token)
    if size == "small":
        w, h = 200, 150
    elif size == "medium":
        w, h = 400, 300
    elif size == "large":
        w, h = 800, 480

    config = await get_active_config(mac) or {}
    persona = mode.upper() if mode else config.get("modes", ["STOIC"])[0] if config.get("modes") else "STOIC"
    city = config.get("city")
    date_ctx = await get_date_context()
    weather = await get_weather(city=city)
    img, _ = await generate_and_render(
        persona,
        config,
        date_ctx,
        weather,
        100.0,
        screen_w=w,
        screen_h=h,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300", "X-InkSight-Mode": persona},
    )


@router.get("/preview")
@limiter.limit("20/minute")
async def preview(
    request: Request,
    v: Optional[float] = Query(default=None),
    mac: Optional[str] = Query(default=None),
    persona: Optional[str] = Query(default=None),
    city_override: Optional[str] = Query(default=None),
    mode_override: Optional[str] = Query(default=None),
    memo_text: Optional[str] = Query(default=None),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200),
    no_cache: Optional[int] = Query(default=None),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    if mac:
        mac = validate_mac_param(mac)
        await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    
    # 获取当前登录用户 ID（用于 Web 预览的额度检查）
    current_user_id = None
    if not mac:  # 只在 Web 预览时获取用户 ID
        from core.auth import get_current_user_optional
        current_user = await get_current_user_optional(request, ink_session)
        if current_user:
            current_user_id = current_user.get("user_id")
            logger.debug("[PREVIEW] Current user_id=%s for Web preview", current_user_id)
    
    try:
        effective_v = await resolve_preview_voltage(v, mac)
        parsed_mode_override = None
        if mode_override:
            try:
                candidate = json.loads(mode_override)
                if isinstance(candidate, dict):
                    parsed_mode_override = candidate
            except JSONDecodeError:
                logger.warning("[PREVIEW] Failed to parse mode_override JSON", exc_info=True)
        img, resolved_persona, cache_hit, _content_fallback, quota_exhausted, api_key_invalid = await build_image(
            effective_v,
            mac,
            persona,
            screen_w=w,
            screen_h=h,
            skip_cache=(no_cache == 1),
            preview_city_override=(city_override.strip() if city_override else None),
            preview_mode_override=parsed_mode_override,
            preview_memo_text=(memo_text if isinstance(memo_text, str) else None),
            current_user_id=current_user_id,
        )
        # 如果 API key 无效，返回 JSON 响应，提醒用户
        if api_key_invalid:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,  # Bad Request
                content={
                    "error": "api_key_invalid",
                    "message": "您提供的 API key 无效或已过期，请检查设备配置中的 AI 配置",
                },
            )
        # 如果额度耗尽，返回 JSON 响应，让前端显示邀请码输入弹窗
        if quota_exhausted:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=402,  # Payment Required
                content={
                    "error": "quota_exhausted",
                    "message": "您的免费额度已用完，请输入邀请码获取更多额度",
                    "requires_invite_code": True,
                },
            )
        # 如果 img 为 None（不应该发生，但为了安全起见）
        if img is None:
            logger.error("[PREVIEW] img is None but quota_exhausted is False")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"error": "image_generation_failed", "message": "图片生成失败"},
            )
        png_bytes = image_to_png_bytes(img)
        logger.info("[PREVIEW] Generated PNG persona=%s size=%sx%s", resolved_persona, w, h)
        
        # 确定生成状态（使用英文避免编码问题）
        status_msg = "model_generated" if not _content_fallback else "fallback_used"
        
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "X-Cache-Hit": "1" if cache_hit else "0",
                "X-Preview-Bypass": "1" if no_cache == 1 else "0",
                "X-Preview-Status": status_msg,
            },
        )
    except (OSError, RuntimeError, TypeError, ValueError, UnidentifiedImageError):
        logger.exception("Exception occurred during preview")
        err_img = render_error(mac=mac or "unknown", screen_w=w, screen_h=h)
        return Response(
            content=image_to_png_bytes(err_img),
            media_type="image/png",
            status_code=500,
        )


@router.get("/preview/stream")
@limiter.limit("20/minute")
async def preview_stream(
    request: Request,
    v: Optional[float] = Query(default=None),
    mac: Optional[str] = Query(default=None),
    persona: Optional[str] = Query(default=None),
    city_override: Optional[str] = Query(default=None),
    mode_override: Optional[str] = Query(default=None),
    memo_text: Optional[str] = Query(default=None),
    w: int = Query(default=SCREEN_WIDTH, ge=100, le=1600),
    h: int = Query(default=SCREEN_HEIGHT, ge=100, le=1200),
    no_cache: Optional[int] = Query(default=None),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    if mac:
        mac = validate_mac_param(mac)
        await ensure_web_or_device_access(request, mac, x_device_token, ink_session)
    
    # 获取当前登录用户 ID（用于 Web 预览的额度检查）
    current_user_id = None
    if not mac:  # 只在 Web 预览时获取用户 ID
        from core.auth import get_current_user_optional
        current_user = await get_current_user_optional(request, ink_session)
        if current_user:
            current_user_id = current_user.get("user_id")
            logger.debug("[PREVIEW_STREAM] Current user_id=%s for Web preview", current_user_id)

    async def stream():
        try:
            yield _sse_event("status", {"stage": "generating", "message": "正在生成..."})
            effective_v = await resolve_preview_voltage(v, mac)
            parsed_mode_override = None
            if mode_override:
                try:
                    candidate = json.loads(mode_override)
                    if isinstance(candidate, dict):
                        parsed_mode_override = candidate
                except JSONDecodeError:
                    logger.warning("[PREVIEW_STREAM] Failed to parse mode_override JSON", exc_info=True)

            img, resolved_persona, cache_hit, _content_fallback, quota_exhausted, api_key_invalid = await build_image(
                effective_v,
                mac,
                persona,
                screen_w=w,
                screen_h=h,
                skip_cache=(no_cache == 1),
                preview_city_override=(city_override.strip() if city_override else None),
                preview_mode_override=parsed_mode_override,
                preview_memo_text=(memo_text if isinstance(memo_text, str) else None),
                current_user_id=current_user_id,
            )
            # 如果 API key 无效，返回错误事件
            if api_key_invalid:
                yield _sse_event("error", {
                    "error": "api_key_invalid",
                    "message": "您提供的 API key 无效或已过期，请检查设备配置中的 AI 配置",
                })
                return
            # 如果额度耗尽，返回错误事件
            if quota_exhausted:
                yield _sse_event("error", {
                    "error": "quota_exhausted",
                    "message": "您的免费额度已用完，请输入邀请码获取更多额度",
                    "requires_invite_code": True,
                })
                return
            yield _sse_event("status", {"stage": "rendering", "message": "正在渲染..."})
            png_bytes = image_to_png_bytes(img)
            data_url = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
            yield _sse_event(
                "result",
                {
                    "stage": "done",
                    "message": "完成",
                    "persona": resolved_persona,
                    "cache_hit": cache_hit,
                    "image_url": data_url,
                },
            )
        except (OSError, RuntimeError, TypeError, ValueError, UnidentifiedImageError) as exc:
            logger.exception("[PREVIEW_STREAM] Streaming preview failed")
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
