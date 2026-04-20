from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response, StreamingResponse

from api.shared import ensure_web_or_device_access, limiter
from core.auth import get_current_user_optional, require_device_token, require_user, validate_mac_param
from core.config import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER, get_default_llm_model_for_provider
from core.config_store import get_device_owner, get_user_llm_config
from core.i18n import detect_lang_from_request, msg
from core.voice_service import (
    VoiceRuntimeSettings,
    create_voice_turn,
    create_voice_ws_session,
    append_voice_ws_audio,
    close_voice_ws_session,
    commit_voice_ws_audio,
    get_pending_voice_turn,
    get_pending_voice_turn_audio_stream,
    get_pending_voice_turn_event_stream,
    get_voice_turn,
    interrupt_voice_ws_session,
    iter_voice_ws_events,
    render_ai_chat_bmp,
    start_voice_ws_session,
    synthesize_prompt_pcm,
)

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)

VOICE_READY_PROMPT = "已经准备好和你对话了。"
VOICE_THINKING_PROMPT = "我思考一下。"
VOICE_FOLLOWUP_PROMPT = "还有什么问题吗？"


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def _load_user_llm_cfg(user_id: int | None) -> dict | None:
    if user_id is None:
        return None
    try:
        return await get_user_llm_config(user_id)
    except Exception:
        logger.warning("[VOICE] Failed to load user_llm_config for user_id=%s", user_id, exc_info=True)
        return None


def _runtime_settings_from_user_cfg(user_cfg: dict | None) -> VoiceRuntimeSettings:
    llm_access_mode = (user_cfg.get("llm_access_mode") if user_cfg else "preset") or "preset"
    llm_access_mode = llm_access_mode.strip().lower()

    provider = (user_cfg.get("provider") if user_cfg else DEFAULT_LLM_PROVIDER) or DEFAULT_LLM_PROVIDER
    provider = str(provider).strip() or DEFAULT_LLM_PROVIDER
    model = (user_cfg.get("model") if user_cfg else DEFAULT_LLM_MODEL) or ""
    model = str(model).strip() or get_default_llm_model_for_provider(provider)
    api_key = (user_cfg.get("api_key") if user_cfg else "") or ""
    base_url = (user_cfg.get("base_url") if user_cfg else "") or ""

    if llm_access_mode == "custom_openai":
        provider = "openai_compat"
        model = model or DEFAULT_LLM_MODEL
        base_url = str(base_url).strip()
    else:
        base_url = ""

    return VoiceRuntimeSettings.from_llm(
        llm_provider=provider,
        llm_model=model,
        llm_api_key=str(api_key).strip() or None,
        llm_base_url=base_url or None,
    )


async def _resolve_voice_runtime_settings(
    request: Request,
    *,
    mac: str | None,
    x_device_token: Optional[str],
    ink_session: Optional[str],
) -> tuple[VoiceRuntimeSettings, int | None, str | None]:
    current_user = await get_current_user_optional(request, ink_session)
    current_user_id = current_user.get("user_id") if current_user else None
    owner_user_id: int | None = None

    if mac:
        await ensure_web_or_device_access(
            request,
            mac,
            x_device_token,
            ink_session,
            allow_device_token=True,
        )
        owner = await get_device_owner(mac)
        if owner:
            try:
                owner_user_id = int(owner.get("user_id"))
            except (TypeError, ValueError):
                owner_user_id = None
    elif current_user_id is None:
        await require_user(request, ink_session)
        current_user = await get_current_user_optional(request, ink_session)
        current_user_id = current_user.get("user_id") if current_user else None

    current_user_cfg = await _load_user_llm_cfg(current_user_id)
    owner_user_cfg = current_user_cfg if owner_user_id == current_user_id else await _load_user_llm_cfg(owner_user_id)
    selected_cfg = current_user_cfg or owner_user_cfg

    return _runtime_settings_from_user_cfg(selected_cfg), current_user_id, mac


async def _resolve_device_voice_runtime_settings(mac: str) -> VoiceRuntimeSettings:
    owner = await get_device_owner(mac)
    owner_user_id: int | None = None
    if owner:
        try:
            owner_user_id = int(owner.get("user_id"))
        except (TypeError, ValueError):
            owner_user_id = None
    owner_cfg = await _load_user_llm_cfg(owner_user_id)
    return _runtime_settings_from_user_cfg(owner_cfg)


def _extract_turn_access(turn_id: str) -> tuple[int | None, str | None]:
    pending = get_pending_voice_turn(turn_id)
    if pending is not None:
        return pending.access_user_id, pending.access_mac
    turn = get_voice_turn(turn_id)
    if turn is not None:
        return turn.get("access_user_id"), turn.get("access_mac")
    raise HTTPException(status_code=404, detail="voice turn not found")


async def _authorize_turn_access(
    request: Request,
    *,
    turn_id: str,
    x_device_token: Optional[str],
    ink_session: Optional[str],
) -> None:
    access_user_id, access_mac = _extract_turn_access(turn_id)
    current_user = await get_current_user_optional(request, ink_session)
    current_user_id = current_user.get("user_id") if current_user else None

    if access_mac and x_device_token:
        await require_device_token(access_mac, x_device_token)
        return

    if current_user_id is not None and access_user_id is not None and current_user_id == access_user_id:
        return

    if access_mac and current_user_id is not None:
        await ensure_web_or_device_access(
            request,
            access_mac,
            None,
            ink_session,
            allow_device_token=False,
        )
        return

    lang = detect_lang_from_request(request)
    if current_user_id is None:
        raise HTTPException(status_code=401, detail=msg("auth.login_required", lang))
    raise HTTPException(status_code=403, detail="voice turn access denied")


def _validate_audio_payload(pcm_bytes: bytes) -> JSONResponse | None:
    if not pcm_bytes:
        return JSONResponse({"error": "empty audio payload"}, status_code=400)
    if len(pcm_bytes) > 1024 * 1024:
        return JSONResponse({"error": "audio payload too large"}, status_code=413)
    return None


@router.post("/voice/turn")
@limiter.limit("20/minute")
async def create_user_voice_turn(
    request: Request,
    sample_rate: int = Query(default=16000, ge=8000, le=48000),
    w: int = Query(default=400, ge=128, le=1200),
    h: int = Query(default=300, ge=128, le=1200),
    include_image: bool = Query(default=True),
    mac: Optional[str] = Query(default=None),
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    started_at = time.perf_counter()
    normalized_mac = validate_mac_param(mac) if mac else None
    settings, current_user_id, access_mac = await _resolve_voice_runtime_settings(
        request,
        mac=normalized_mac,
        x_device_token=x_device_token,
        ink_session=ink_session,
    )
    pcm_bytes = await request.body()
    payload_error = _validate_audio_payload(pcm_bytes)
    if payload_error is not None:
        return payload_error

    try:
        result = await create_voice_turn(
            pcm_bytes,
            sample_rate=sample_rate,
            screen_w=w,
            screen_h=h,
            include_image=include_image,
            access_user_id=current_user_id,
            access_mac=access_mac,
            settings=settings,
        )
    except Exception as exc:
        logger.exception("[VOICE_API] create user turn failed mac=%s", normalized_mac)
        return JSONResponse({"error": str(exc)}, status_code=500)

    logger.info(
        "[VOICE_API] user turn ok mac=%s turn_id=%s transcript=%s streaming=%s total_ms=%d",
        normalized_mac,
        result.get("turn_id", ""),
        result.get("transcript", ""),
        result.get("streaming", False),
        int((time.perf_counter() - started_at) * 1000),
    )
    return {"ok": True, **result}


@router.get("/voice/{turn_id}/events")
async def get_voice_turn_events(
    turn_id: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await _authorize_turn_access(
        request,
        turn_id=turn_id,
        x_device_token=x_device_token,
        ink_session=ink_session,
    )

    pending_stream = get_pending_voice_turn_event_stream(turn_id)
    if pending_stream is not None:
        async def _stream():
            async for event in pending_stream:
                event_name = str(event.get("event", "message"))
                payload = {k: v for k, v in event.items() if k != "event"}
                yield _sse_event(event_name, payload)

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    turn = get_voice_turn(turn_id)
    if not turn:
        return JSONResponse({"error": "voice turn not found"}, status_code=404)

    async def _final_stream():
        yield _sse_event("transcript", {"transcript": turn["transcript"]})
        if turn["reply_text"]:
            yield _sse_event("reply_segment", {"text": turn["reply_text"]})
        yield _sse_event(
            "done",
            {
                "turn_id": turn_id,
                "reply_text": turn["reply_text"],
                "exit_conversation": False,
            },
        )

    return StreamingResponse(
        _final_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/voice/{turn_id}/audio")
async def get_voice_turn_audio(
    turn_id: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await _authorize_turn_access(
        request,
        turn_id=turn_id,
        x_device_token=x_device_token,
        ink_session=ink_session,
    )
    pending_stream = get_pending_voice_turn_audio_stream(turn_id)
    if pending_stream is not None:
        return StreamingResponse(
            pending_stream,
            media_type="application/octet-stream",
            headers={"X-Voice-Streaming": "1"},
        )

    turn = get_voice_turn(turn_id)
    if not turn:
        return JSONResponse({"error": "voice turn not found"}, status_code=404)
    return Response(content=turn["audio_pcm"], media_type="application/octet-stream")


@router.get("/voice/{turn_id}/image")
async def get_voice_turn_image(
    turn_id: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
    ink_session: Optional[str] = Cookie(default=None),
):
    await _authorize_turn_access(
        request,
        turn_id=turn_id,
        x_device_token=x_device_token,
        ink_session=ink_session,
    )
    turn = get_voice_turn(turn_id)
    if not turn:
        return JSONResponse({"error": "voice turn not found"}, status_code=404)
    if not turn["image_bmp"]:
        return JSONResponse({"error": "voice turn image not available"}, status_code=404)
    return Response(content=turn["image_bmp"], media_type="image/bmp")


@router.post("/device/{mac}/voice/turn")
@limiter.limit("10/minute")
async def create_device_voice_turn(
    request: Request,
    mac: str,
    sample_rate: int = Query(default=16000, ge=8000, le=48000),
    w: int = Query(default=400, ge=128, le=1200),
    h: int = Query(default=300, ge=128, le=1200),
    include_image: bool = Query(default=True),
    x_device_token: Optional[str] = Header(default=None),
):
    started_at = time.perf_counter()
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    settings = await _resolve_device_voice_runtime_settings(mac)

    pcm_bytes = await request.body()
    payload_error = _validate_audio_payload(pcm_bytes)
    if payload_error is not None:
        return payload_error

    try:
        result = await create_voice_turn(
            pcm_bytes,
            sample_rate=sample_rate,
            screen_w=w,
            screen_h=h,
            include_image=include_image,
            access_user_id=None,
            access_mac=mac,
            settings=settings,
        )
    except Exception as exc:
        logger.exception("[VOICE_API] create device turn failed mac=%s", mac)
        return JSONResponse({"error": str(exc)}, status_code=500)

    logger.info(
        "[VOICE_API] device turn ok mac=%s turn_id=%s transcript=%s streaming=%s total_ms=%d",
        mac,
        result.get("turn_id", ""),
        result.get("transcript", ""),
        result.get("streaming", False),
        int((time.perf_counter() - started_at) * 1000),
    )
    return {"ok": True, **result}


@router.websocket("/device/{mac}/voice/ws")
async def device_voice_ws(
    websocket: WebSocket,
    mac: str,
):
    mac = validate_mac_param(mac)
    x_device_token = websocket.headers.get("x-device-token") or websocket.query_params.get("token")
    try:
        await require_device_token(mac, x_device_token, websocket.headers.get("accept-language"))
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail)[:120])
        return

    settings = await _resolve_device_voice_runtime_settings(mac)
    session = create_voice_ws_session(
        settings=settings,
        access_user_id=None,
        access_mac=mac,
    )
    await websocket.accept()

    async def _sender() -> None:
        async for event in iter_voice_ws_events(session):
            if event.get("__binary__"):
                await websocket.send_bytes(event["data"])
            else:
                await websocket.send_text(json.dumps(event, ensure_ascii=False, separators=(",", ":")))

    sender_task = asyncio.create_task(_sender())
    try:
        while True:
            ws_message = await websocket.receive()
            if ws_message.get("type") == "websocket.disconnect":
                break

            if "bytes" in ws_message and ws_message["bytes"]:
                await append_voice_ws_audio(session, ws_message["bytes"])
                continue

            message = ws_message.get("text", "")
            if not message:
                continue
            payload = json.loads(message)
            event_type = str(payload.get("type", "")).strip()
            if event_type == "session.start":
                await start_voice_ws_session(
                    session,
                    sample_rate=int(payload.get("sample_rate") or 16000),
                    screen_w=int(payload.get("w") or 400),
                    screen_h=int(payload.get("h") or 300),
                    include_image=bool(payload.get("include_image", True)),
                    protocol_version=int(payload.get("protocol") or 1),
                    audio_codec=str(payload.get("audio_codec") or "pcm"),
                )
                continue
            if event_type == "audio.append":
                audio_b64 = str(payload.get("audio", "")).strip()
                if not audio_b64:
                    continue
                await append_voice_ws_audio(session, base64.b64decode(audio_b64))
                continue
            if event_type == "audio.commit":
                await commit_voice_ws_audio(session)
                continue
            if event_type == "interrupt":
                await interrupt_voice_ws_session(session)
                continue
            if event_type == "close":
                break
            await websocket.send_text(json.dumps({"event": "error", "message": f"unsupported event: {event_type}"}))
    except WebSocketDisconnect:
        logger.info("[VOICE_WS] disconnected mac=%s session_id=%s", mac, session.session_id)
    except Exception as exc:
        logger.exception("[VOICE_WS] device session failed mac=%s session_id=%s", mac, session.session_id)
        with contextlib.suppress(Exception):
            await websocket.send_text(json.dumps({"event": "error", "message": str(exc)}, ensure_ascii=False, separators=(",", ":")))
    finally:
        await close_voice_ws_session(session)
        sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender_task


@router.get("/device/{mac}/voice/ready/audio")
async def get_device_voice_ready_audio(
    mac: str,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    settings = await _resolve_device_voice_runtime_settings(mac)
    try:
        audio_pcm = await synthesize_prompt_pcm(VOICE_READY_PROMPT, settings=settings)
    except Exception as exc:
        logger.exception("[VOICE_READY] failed for mac=%s", mac)
        return JSONResponse({"error": str(exc)}, status_code=500)
    return Response(content=audio_pcm, media_type="application/octet-stream")


@router.get("/device/{mac}/voice/prompt/audio")
async def get_device_voice_prompt_audio(
    mac: str,
    kind: str = Query(default="thinking"),
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    settings = await _resolve_device_voice_runtime_settings(mac)
    prompts = {
        "thinking": VOICE_THINKING_PROMPT,
        "followup": VOICE_FOLLOWUP_PROMPT,
    }
    prompt_text = prompts.get(kind.lower().strip())
    if not prompt_text:
        return JSONResponse({"error": "unsupported prompt kind"}, status_code=400)
    try:
        audio_pcm = await synthesize_prompt_pcm(prompt_text, settings=settings)
    except Exception as exc:
        logger.exception("[VOICE_PROMPT] failed mac=%s kind=%s", mac, kind)
        return JSONResponse({"error": str(exc)}, status_code=500)
    return Response(content=audio_pcm, media_type="application/octet-stream")


@router.get("/device/{mac}/voice/{turn_id}/audio")
async def get_device_voice_audio(
    mac: str,
    turn_id: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    return await get_voice_turn_audio(turn_id, request, x_device_token=x_device_token, ink_session=None)


@router.get("/device/{mac}/voice/{turn_id}/image")
async def get_device_voice_image(
    mac: str,
    turn_id: str,
    request: Request,
    w: int = Query(default=400, ge=128, le=1200),
    h: int = Query(default=300, ge=128, le=1200),
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    if turn_id == "intro":
        image_bmp = await render_ai_chat_bmp(screen_w=w, screen_h=h, user_text="", reply_text="")
        return Response(content=image_bmp, media_type="image/bmp")
    return await get_voice_turn_image(turn_id, request, x_device_token=x_device_token, ink_session=None)


@router.get("/device/{mac}/voice/{turn_id}/events")
async def get_device_voice_events(
    mac: str,
    turn_id: str,
    request: Request,
    x_device_token: Optional[str] = Header(default=None),
):
    mac = validate_mac_param(mac)
    await require_device_token(mac, x_device_token)
    return await get_voice_turn_events(turn_id, request, x_device_token=x_device_token, ink_session=None)
