from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, TypedDict

import websockets
from PIL import Image, ImageDraw

from core.content import _call_llm, _chat_completion_extra_body, _get_client
from core.patterns.utils import load_font, wrap_text
from core.renderer import image_to_bmp_bytes

try:
    import opuslib
    _HAS_OPUS = True
except Exception:
    _HAS_OPUS = False

logger = logging.getLogger(__name__)

def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


VOICE_TURN_TTL_SECONDS = _env_int("VOICE_TURN_TTL_SECONDS", 900)
VOICE_LLM_STREAMING = _env_bool("VOICE_LLM_STREAMING", True)
VOICE_TTS_STREAMING = _env_bool("VOICE_TTS_STREAMING", True)
VOICE_TTS_STREAM_MIN_CHARS = _env_int("VOICE_TTS_STREAM_MIN_CHARS", 12)
VOICE_TTS_STREAM_MAX_CHARS = _env_int("VOICE_TTS_STREAM_MAX_CHARS", 36)
VOICE_TTS_DELTA_MIN_CHARS = _env_int("VOICE_TTS_DELTA_MIN_CHARS", 6)
VOICE_TTS_DELTA_MAX_CHARS = _env_int("VOICE_TTS_DELTA_MAX_CHARS", 16)
VOICE_TTS_DELTA_IDLE_MS = _env_int("VOICE_TTS_DELTA_IDLE_MS", 320)
VOICE_WS_PARTIAL_WARMUP_MIN_CHARS = _env_int("VOICE_WS_PARTIAL_WARMUP_MIN_CHARS", 2)
VOICE_WS_PARTIAL_WARMUP_STABLE_MS = _env_int("VOICE_WS_PARTIAL_WARMUP_STABLE_MS", 180)
VOICE_WS_AUDIO_CHUNK_BYTES = _env_int("VOICE_WS_AUDIO_CHUNK_BYTES", 2048)
VOICE_SERVER_VAD_ENABLED = _env_bool("VOICE_SERVER_VAD_ENABLED", True)
VOICE_SERVER_VAD_SILENCE_MS = _env_int("VOICE_SERVER_VAD_SILENCE_MS", 800)
VOICE_STREAMING_TTS_ENABLED = _env_bool("VOICE_STREAMING_TTS_ENABLED", True)

VOICE_REALTIME_ASR_MODEL = _env_str("VOICE_REALTIME_ASR_MODEL", "qwen3-asr-flash-realtime")
VOICE_REALTIME_ASR_WS_URL = _env_str("VOICE_REALTIME_ASR_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")
VOICE_REALTIME_ASR_LANGUAGE = _env_str("VOICE_REALTIME_ASR_LANGUAGE", "zh") or "zh"
VOICE_REALTIME_ASR_IDLE_TIMEOUT_SECONDS = _env_float("VOICE_REALTIME_ASR_IDLE_TIMEOUT_SECONDS", 20.0)
VOICE_REALTIME_ASR_MAX_EVENT_BYTES = _env_int("VOICE_REALTIME_ASR_MAX_EVENT_BYTES", 15 * 1024 * 1024)

VOICE_STREAMING_TTS_MODEL = _env_str("VOICE_STREAMING_TTS_MODEL", "cosyvoice-v3-plus")
VOICE_STREAMING_TTS_VOICE = _env_str("VOICE_STREAMING_TTS_VOICE", "longanyang")
VOICE_STREAMING_TTS_SPEED = _env_float("VOICE_STREAMING_TTS_SPEED", 1.0)
VOICE_STREAMING_TTS_WS_URL = _env_str("VOICE_STREAMING_TTS_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/inference")
VOICE_STREAMING_TTS_SAMPLE_RATE = _env_int("VOICE_STREAMING_TTS_SAMPLE_RATE", 16000)
VOICE_STREAMING_TTS_VOLUME = _env_int("VOICE_STREAMING_TTS_VOLUME", 50)
VOICE_STREAMING_TTS_PITCH = _env_float("VOICE_STREAMING_TTS_PITCH", 1.0)
VOICE_STREAMING_TTS_MAX_EVENT_BYTES = _env_int("VOICE_STREAMING_TTS_MAX_EVENT_BYTES", 4 * 1024 * 1024)

VOICE_DASHSCOPE_API_KEY = _env_str("VOICE_DASHSCOPE_API_KEY", "")
VOICE_STT_API_KEY = _env_str("VOICE_STT_API_KEY", "")
VOICE_TTS_API_KEY = _env_str("VOICE_TTS_API_KEY", "")
VOICE_OPUS_FRAME_DURATION_MS = 60
VOICE_OPUS_FRAME_SIZE = 16000 * VOICE_OPUS_FRAME_DURATION_MS // 1000


class VoiceTurn(TypedDict):
    created_at: float
    transcript: str
    reply_text: str
    audio_pcm: bytes
    image_bmp: bytes
    access_user_id: int | None
    access_mac: str | None


@dataclass
class VoiceRuntimeSettings:
    llm_provider: str
    llm_model: str
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    stt_api_key: str | None = None
    tts_api_key: str | None = None

    @classmethod
    def from_llm(
        cls,
        *,
        llm_provider: str,
        llm_model: str,
        llm_api_key: str | None = None,
        llm_base_url: str | None = None,
    ) -> "VoiceRuntimeSettings":
        shared_voice_api_key = VOICE_DASHSCOPE_API_KEY or _env_str("DASHSCOPE_API_KEY", "") or None
        env_stt_key = VOICE_STT_API_KEY or shared_voice_api_key
        env_tts_key = VOICE_TTS_API_KEY or shared_voice_api_key
        user_aliyun_key = (
            str(llm_api_key).strip()
            if llm_provider == "aliyun" and llm_api_key and str(llm_api_key).strip()
            else ""
        )
        # 语音 STT/TTS 走百炼 WebSocket：若用户在 Profile 里为「通义/aliyun」配置了 BYOK，则优先用该 Key，再回退服务端环境变量。
        if user_aliyun_key:
            stt_api_key = user_aliyun_key or env_stt_key
            tts_api_key = user_aliyun_key or env_tts_key
        else:
            stt_api_key = env_stt_key
            tts_api_key = env_tts_key
        return cls(
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            stt_api_key=stt_api_key,
            tts_api_key=tts_api_key,
        )


@dataclass
class PendingVoiceTurn:
    created_at: float
    transcript: str
    screen_w: int
    screen_h: int
    include_image: bool
    access_user_id: int | None
    access_mac: str | None
    audio_queue: asyncio.Queue[bytes | None] = field(default_factory=asyncio.Queue)
    event_queue: asyncio.Queue[dict | None] = field(default_factory=asyncio.Queue)
    reply_parts: list[str] = field(default_factory=list)
    audio_parts: list[bytes] = field(default_factory=list)
    reply_text: str = ""
    error: str | None = None


@dataclass
class VoiceWsClientEvent:
    type: str
    payload: dict[str, Any]


@dataclass
class VoiceWsSessionState:
    session_id: str
    settings: VoiceRuntimeSettings
    access_user_id: int | None
    access_mac: str | None
    screen_w: int = 400
    screen_h: int = 300
    sample_rate: int = 16000
    include_image: bool = True
    conversation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    protocol_version: int = 1
    binary_audio: bool = False
    audio_codec: str = "pcm"
    opus_encoder: Any = None
    opus_decoder: Any = None
    started: bool = False
    closed: bool = False
    turn_index: int = 0
    generation_id: int = 0
    reply_parts: list[str] = field(default_factory=list)
    audio_parts: list[bytes] = field(default_factory=list)
    event_queue: asyncio.Queue[dict | None] = field(default_factory=asyncio.Queue)
    generation_task: asyncio.Task[None] | None = None
    asr_bridge: "RealtimeAsrTurnBridge | None" = None
    latest_partial_transcript: str = ""
    latest_partial_at: float = 0.0
    active_turn_id: str | None = None
    active_turn_transcript: str = ""
    turn_metrics: "VoiceWsTurnMetrics | None" = None
    pending_tts_bridge: "_StreamingTtsBridge | None" = None
    _auto_commit_task: asyncio.Task[None] | None = None


@dataclass
class VoiceWsTurnMetrics:
    turn_id: str = ""
    capture_started_at: float = 0.0
    first_audio_at: float = 0.0
    last_audio_at: float = 0.0
    audio_chunks: int = 0
    audio_bytes: int = 0
    commit_requested_at: float = 0.0
    asr_final_at: float = 0.0
    generation_started_at: float = 0.0
    first_llm_delta_at: float = 0.0
    first_tts_text_at: float = 0.0
    first_tts_audio_at: float = 0.0
    done_at: float = 0.0
    used_partial_warmup: bool = False


_voice_turns: dict[str, VoiceTurn] = {}
_pending_voice_turns: dict[str, PendingVoiceTurn] = {}
_voice_prompt_cache: dict[str, bytes] = {}


def _cleanup_voice_turns() -> None:
    now = time.time()
    expired_turn_ids = [
        turn_id
        for turn_id, turn in _voice_turns.items()
        if now - turn["created_at"] > VOICE_TURN_TTL_SECONDS
    ]
    for turn_id in expired_turn_ids:
        _voice_turns.pop(turn_id, None)


def _cleanup_pending_voice_turns() -> None:
    now = time.time()
    expired_turn_ids = [
        turn_id
        for turn_id, pending in _pending_voice_turns.items()
        if now - pending.created_at > VOICE_TURN_TTL_SECONDS
    ]
    for turn_id in expired_turn_ids:
        pending = _pending_voice_turns.pop(turn_id, None)
        if pending is None:
            continue
        try:
            pending.audio_queue.put_nowait(None)
            pending.event_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


def _preview_text(text: str, limit: int = 120) -> str:
    clean = (text or "").replace("\r", " ").replace("\n", " ").strip()
    return clean if len(clean) <= limit else clean[:limit] + "..."


def _ms_since(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _elapsed_ms_between(started_at: float, ended_at: float) -> int:
    if started_at <= 0 or ended_at <= 0:
        return -1
    return int((ended_at - started_at) * 1000)


def _normalize_exit_text(text: str) -> str:
    return (text or "").replace("\n", "").replace("\r", "").replace(" ", "").strip().lower()


def _normalize_transcript_for_compare(text: str) -> str:
    return (text or "").replace("\n", "").replace("\r", "").replace(" ", "").strip()


_MODE_SWITCH_KEYWORDS: dict[str, str] = {
    "天气": "WEATHER",
    "天气看板": "WEATHER",
    "日历": "CALENDAR",
    "月历": "CALENDAR",
    "诗词": "POETRY",
    "古诗": "POETRY",
    "古诗词": "POETRY",
    "斯多葛": "STOIC",
    "哲学": "STOIC",
    "吐槽": "ROAST",
    "毒舌": "ROAST",
    "禅": "ZEN",
    "禅意": "ZEN",
    "每日推荐": "DAILY",
    "每日": "DAILY",
    "推荐": "DAILY",
    "故事": "STORY",
    "微故事": "STORY",
    "谜语": "RIDDLE",
    "食谱": "RECIPE",
    "做菜": "RECIPE",
    "一问": "QUESTION",
    "提问": "QUESTION",
    "黄历": "ALMANAC",
    "老黄历": "ALMANAC",
    "进度条": "LIFEBAR",
    "人生进度": "LIFEBAR",
    "便签": "MEMO",
    "留言": "MEMO",
    "倒计时": "COUNTDOWN",
    "挑战": "CHALLENGE",
    "偏差": "BIAS",
    "认知偏差": "BIAS",
    "习惯": "HABIT",
    "打卡": "HABIT",
    "慢信": "LETTER",
    "健身": "FITNESS",
    "锻炼": "FITNESS",
    "单词": "WORD_OF_THE_DAY",
    "每日一词": "WORD_OF_THE_DAY",
    "课程表": "TIMETABLE",
    "简报": "BRIEFING",
    "科技简报": "BRIEFING",
    "历史上的今天": "THISDAY",
    "历史": "THISDAY",
    "艺术": "ARTWALL",
    "AI艺术": "ARTWALL",
    "相框": "MY_ADAPTIVE",
    "语录": "MY_QUOTE",
}

_MODE_SWITCH_TRIGGERS = ("切换", "换到", "打开", "显示", "看看", "帮我看", "来个", "给我")


def _detect_mode_switch(transcript: str) -> str | None:
    """Detect mode-switch intent from user transcript. Returns mode_id or None."""
    normalized = _normalize_exit_text(transcript)
    if not normalized:
        return None
    has_trigger = any(t in normalized for t in _MODE_SWITCH_TRIGGERS)
    # ASR sometimes truncates leading words (e.g. "切换到" → "到"), so also
    # treat "到<keyword>模式" as a trigger-bearing pattern.
    has_to_mode = "到" in normalized and "模式" in normalized
    for keyword, mode_id in _MODE_SWITCH_KEYWORDS.items():
        if keyword not in normalized:
            continue
        if has_trigger:
            return mode_id
        if has_to_mode and f"到{keyword}" in normalized:
            return mode_id
    return None


def _should_exit_ai_chat(transcript: str) -> bool:
    normalized = _normalize_exit_text(transcript)
    if not normalized:
        return False
    if normalized in {"退出", "结束", "关闭", "退出模式", "结束对话", "退出对话"}:
        return True
    has_exit_word = any(word in normalized for word in ("退出", "结束", "关闭"))
    has_chat_word = any(word in normalized for word in ("对话", "聊天", "会话", "模式", "功能"))
    has_ai_word = "ai" in normalized or "人工智能" in normalized
    return has_exit_word and (has_chat_word or has_ai_word)


def _resolve_turn_done_flags(transcript: str) -> tuple[bool, str | None]:
    """Return (exit_conversation, switch_to_mode) for a turn.done event."""
    switch_mode = _detect_mode_switch(transcript)
    exit_conv = _should_exit_ai_chat(transcript) or switch_mode is not None
    return exit_conv, switch_mode


async def _set_pending_mode_if_switch(session: VoiceWsSessionState, switch_to_mode: str | None) -> None:
    """If mode switch detected, set pending_mode + pending_refresh in device state."""
    if not switch_to_mode or not session.access_mac:
        return
    from core.config_store import update_device_state
    await update_device_state(session.access_mac, pending_mode=switch_to_mode, pending_refresh=1)
    logger.info("[VOICE] Mode switch queued: mac=%s mode=%s", session.access_mac, switch_to_mode)


def _should_warmup_voice_generation(session: VoiceWsSessionState, transcript: str) -> bool:
    normalized = _normalize_transcript_for_compare(transcript)
    if len(normalized) < VOICE_WS_PARTIAL_WARMUP_MIN_CHARS:
        return False
    if session.latest_partial_at <= 0:
        return False
    return _ms_since(session.latest_partial_at) >= VOICE_WS_PARTIAL_WARMUP_STABLE_MS


def _is_compatible_warmup_transcript(speculative: str, final: str) -> bool:
    speculative_normalized = _normalize_transcript_for_compare(speculative)
    final_normalized = _normalize_transcript_for_compare(final)
    if not speculative_normalized or not final_normalized:
        return False
    if speculative_normalized == final_normalized:
        return True
    if final_normalized.startswith(speculative_normalized):
        return len(final_normalized) - len(speculative_normalized) <= 8
    if speculative_normalized.startswith(final_normalized):
        return len(speculative_normalized) - len(final_normalized) <= 4
    return False


def _create_opus_encoder(sample_rate: int = 16000, channels: int = 1) -> Any:
    if not _HAS_OPUS:
        return None
    try:
        return opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)
    except Exception:
        logger.warning("[VOICE_OPUS] Failed to create encoder", exc_info=True)
        return None


def _create_opus_decoder(sample_rate: int = 16000, channels: int = 1) -> Any:
    if not _HAS_OPUS:
        return None
    try:
        return opuslib.Decoder(sample_rate, channels)
    except Exception:
        logger.warning("[VOICE_OPUS] Failed to create decoder", exc_info=True)
        return None


def _opus_encode_pcm(encoder: Any, pcm_bytes: bytes, frame_size: int = VOICE_OPUS_FRAME_SIZE) -> list[bytes]:
    if encoder is None or not pcm_bytes:
        return []
    frames: list[bytes] = []
    bytes_per_frame = frame_size * 2
    for offset in range(0, len(pcm_bytes), bytes_per_frame):
        chunk = pcm_bytes[offset : offset + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk += b"\x00" * (bytes_per_frame - len(chunk))
        try:
            encoded = encoder.encode(chunk, frame_size)
            frames.append(encoded)
        except Exception:
            break
    return frames


def _opus_decode_frame(decoder: Any, opus_data: bytes, frame_size: int = VOICE_OPUS_FRAME_SIZE) -> bytes:
    if decoder is None or not opus_data:
        return b""
    try:
        return decoder.decode(opus_data, frame_size)
    except Exception:
        return b""


def _render_reply_bmp(text: str, screen_w: int, screen_h: int, *, user_text: str = "") -> bytes:
    img = Image.new("1", (screen_w, screen_h), 1)
    draw = ImageDraw.Draw(img)

    title_font = load_font("noto_serif_regular", max(16, min(screen_w // 18, screen_h // 10)))
    body_font = load_font("noto_serif_regular", max(14, min(screen_w // 22, screen_h // 14)))
    label_font = load_font("noto_serif_light", max(10, min(screen_w // 30, screen_h // 22)))

    draw.rounded_rectangle((10, 10, screen_w - 10, screen_h - 10), radius=14, outline=0, width=2, fill=1)
    draw.text((20, 18), "AI MODE", font=title_font, fill=0)

    margin_x = 18
    bubble_w = screen_w - margin_x * 2
    body_top = 56

    if user_text:
        draw.text((margin_x, body_top), "YOU", font=label_font, fill=0)
        user_lines = wrap_text(user_text, body_font, bubble_w)[:3]
        y = body_top + 18
        for line in user_lines:
            draw.text((margin_x, y), line, font=body_font, fill=0)
            box = draw.textbbox((0, 0), line, font=body_font)
            y += (box[3] - box[1]) + 4
        body_top = y + 12

    draw.text((margin_x, body_top), "AI", font=label_font, fill=0)
    lines = wrap_text(text or "...", body_font, bubble_w)[:4] or [text or "..."]
    y = body_top + 18
    for line in lines:
        draw.text((margin_x, y), line, font=body_font, fill=0)
        box = draw.textbbox((0, 0), line, font=body_font)
        y += (box[3] - box[1]) + 4

    return image_to_bmp_bytes(img)


async def render_ai_chat_bmp(
    *,
    screen_w: int,
    screen_h: int,
    user_text: str = "",
    reply_text: str = "",
) -> bytes:
    return _render_reply_bmp(reply_text or "请和我对话", screen_w, screen_h, user_text=user_text)


def _dashscope_api_key(explicit_key: str | None = None) -> str:
    api_key = (explicit_key or VOICE_DASHSCOPE_API_KEY or _env_str("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("Missing DashScope API key")
    return api_key


def _dashscope_realtime_asr_url() -> str:
    normalized = VOICE_REALTIME_ASR_WS_URL.strip()
    if normalized.startswith("ws://") or normalized.startswith("wss://"):
        return normalized
    normalized = normalized.rstrip("/")
    if normalized.startswith("http://"):
        return "ws://" + normalized[len("http://") :]
    if normalized.startswith("https://"):
        return "wss://" + normalized[len("https://") :]
    return VOICE_REALTIME_ASR_WS_URL


def _dashscope_tts_ws_url() -> str:
    normalized = VOICE_STREAMING_TTS_WS_URL.strip()
    if not normalized:
        return VOICE_STREAMING_TTS_WS_URL
    if normalized.startswith("ws://") or normalized.startswith("wss://"):
        return normalized

    normalized = normalized.rstrip("/")
    if normalized.endswith("/api/v1") or normalized.endswith("/compatible-mode/v1"):
        normalized = normalized[: normalized.rfind("/")]

    if normalized.startswith("http://"):
        return f"ws://{normalized[len('http://'):]}/api-ws/v1/inference"
    if normalized.startswith("https://"):
        return f"wss://{normalized[len('https://'):]}/api-ws/v1/inference"
    return VOICE_STREAMING_TTS_WS_URL


async def _transcribe_pcm_bytes(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    settings: VoiceRuntimeSettings,
) -> str:
    started_at = time.perf_counter()
    async def _noop_partial(_: str) -> None:
        return

    bridge = RealtimeAsrTurnBridge(
        settings=settings,
        sample_rate=sample_rate,
        partial_callback=_noop_partial,
    )
    try:
        if pcm_bytes:
            await bridge.append_audio(pcm_bytes)
        transcript = await bridge.commit()
    finally:
        await bridge.close()
    logger.info("[VOICE_STT] transcript=%s elapsed_ms=%d", _preview_text(transcript), _ms_since(started_at))
    return transcript


def _build_voice_reply_prompt(transcript: str) -> str:
    switch_mode = _detect_mode_switch(transcript)
    if switch_mode:
        mode_name = next(
            (k for k, v in _MODE_SWITCH_KEYWORDS.items() if v == switch_mode),
            switch_mode,
        )
        return (
            "你是一个简洁、自然、口语化的中文语音助手。"
            + f"用户要求切换到'{mode_name}'模式，请简短确认，"
            + "例如'好的，帮你切换'，不超过一句话。"
            + f"用户输入：{transcript}"
        )
    return (
        "你是一个简洁、自然、口语化的中文语音助手。"
        "请直接回答用户问题，不要解释推理过程。"
        "优先控制在 2 到 4 句之内，避免长段落。"
        f"用户输入：{transcript}"
    )


def _normalize_voice_reply_text(reply_text: str, *, limit: int = 80) -> str:
    clean = " ".join((reply_text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if not clean:
        return ""
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip()


def _normalize_tts_stream_text(text: str) -> str:
    clean = " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if not clean:
        return ""
    # 百炼双向流式 TTS 对极短的纯标点/无效片段比较敏感，这里只丢弃没有实际内容的碎片。
    if not any(ch.isalnum() for ch in clean):
        return ""
    return clean


def _extract_stream_delta_text(delta_content: object) -> str:
    if isinstance(delta_content, str):
        return delta_content
    if isinstance(delta_content, list):
        parts: list[str] = []
        for item in delta_content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                parts.append(str(text))
        return "".join(parts)
    return ""


def _split_tts_segments(buffer: str, *, final: bool) -> tuple[list[str], str]:
    if not buffer:
        return [], ""

    segments: list[str] = []
    flush_chars = set("。！？!?；;\n")
    soft_break_chars = set("，,、")
    start = 0
    for idx, ch in enumerate(buffer):
        current_len = idx - start + 1
        should_flush = ch in flush_chars
        if not should_flush and ch in soft_break_chars and current_len >= VOICE_TTS_STREAM_MIN_CHARS:
            should_flush = True
        if not should_flush:
            continue
        segment = buffer[start : idx + 1].strip()
        if segment:
            segments.append(segment)
        start = idx + 1

    remainder = buffer[start:]
    if remainder.strip():
        if final or len(remainder.strip()) >= VOICE_TTS_STREAM_MAX_CHARS:
            segments.append(remainder.strip())
            remainder = ""
    return segments, remainder


async def _stream_llm_sentence_segments(
    *,
    settings: VoiceRuntimeSettings,
    prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> AsyncIterator[str]:
    if not VOICE_LLM_STREAMING:
        reply_text = await _call_llm(
            settings.llm_provider,
            settings.llm_model,
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        normalized = _normalize_voice_reply_text(reply_text, limit=160)
        if normalized:
            yield normalized
        return

    try:
        client, default_max_tokens = _get_client(
            settings.llm_provider,
            settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        request_kwargs = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or default_max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        extra_body = _chat_completion_extra_body(settings.llm_provider, settings.llm_model)
        if extra_body is not None:
            request_kwargs["extra_body"] = extra_body

        stream = await client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            if delta is None:
                continue
            text_piece = _extract_stream_delta_text(getattr(delta, "content", ""))
            if text_piece:
                yield text_piece
    except Exception:
        logger.exception("[VOICE_LLM_DELTA] streaming failed, falling back to non-streaming reply generation")
        reply_text = await _call_llm(
            settings.llm_provider,
            settings.llm_model,
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        normalized = _normalize_voice_reply_text(reply_text, limit=160)
        if normalized:
            yield normalized


async def _stream_llm_deltas(
    *,
    settings: VoiceRuntimeSettings,
    prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> AsyncIterator[str]:
    if not VOICE_LLM_STREAMING:
        reply_text = await _call_llm(
            settings.llm_provider,
            settings.llm_model,
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        normalized = _normalize_voice_reply_text(reply_text, limit=160)
        if normalized:
            yield normalized
        return

    try:
        client, default_max_tokens = _get_client(
            settings.llm_provider,
            settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        request_kwargs = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or default_max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        extra_body = _chat_completion_extra_body(settings.llm_provider, settings.llm_model)
        if extra_body is not None:
            request_kwargs["extra_body"] = extra_body

        stream = await client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            if delta is None:
                continue
            text_piece = _extract_stream_delta_text(getattr(delta, "content", ""))
            if text_piece:
                yield text_piece
    except Exception:
        logger.exception("[VOICE_LLM_DELTA] streaming failed, falling back to non-streaming reply generation")
        reply_text = await _call_llm(
            settings.llm_provider,
            settings.llm_model,
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        normalized = _normalize_voice_reply_text(reply_text, limit=160)
        if normalized:
            yield normalized


def _tts_text_len(text: str) -> int:
    return len(text.strip())


def _tts_extend_break(buffer: str, idx: int) -> int:
    trailing_closers = set("\"'”’）)]】》」』")
    while idx < len(buffer) and buffer[idx] in trailing_closers:
        idx += 1
    return idx


def _find_last_tts_break(buffer: str, *, weak_break_min_chars: int) -> tuple[int, str | None]:
    strong_punctuation = set("。！？!?；;\n")
    weak_punctuation = set("，,、：:")
    strong_break = -1
    weak_break = -1
    whitespace_break = -1
    clean_len = 0

    for idx, ch in enumerate(buffer):
        if not ch.isspace():
            clean_len += 1
        if clean_len < VOICE_TTS_DELTA_MIN_CHARS:
            continue
        if ch in strong_punctuation:
            strong_break = idx + 1
            continue
        if ch in weak_punctuation and clean_len >= weak_break_min_chars:
            weak_break = idx + 1
            continue
        if ch.isspace() and clean_len >= weak_break_min_chars:
            whitespace_break = idx + 1

    if strong_break > 0:
        return _tts_extend_break(buffer, strong_break), "strong"
    if weak_break > 0:
        return _tts_extend_break(buffer, weak_break), "weak"
    if whitespace_break > 0:
        return _tts_extend_break(buffer, whitespace_break), "space"
    return -1, None


def _force_tts_split_index(buffer: str, *, target_chars: int, max_overflow_chars: int) -> int:
    punctuation = set("。！？!?；;，,、：:")
    clean_len = 0
    fallback_idx = -1

    for idx, ch in enumerate(buffer):
        if not ch.isspace():
            clean_len += 1
        if clean_len >= target_chars and fallback_idx < 0:
            fallback_idx = idx + 1
        if clean_len >= target_chars and (ch in punctuation or ch.isspace()):
            return _tts_extend_break(buffer, idx + 1)
        if clean_len >= target_chars + max_overflow_chars:
            return fallback_idx if fallback_idx > 0 else idx + 1

    return len(buffer) if fallback_idx > 0 else -1


def _split_delta_tts_segments(buffer: str, *, final: bool, idle_break: bool) -> tuple[list[str], str]:
    if not buffer:
        return [], ""

    segments: list[str] = []
    remaining = buffer
    weak_break_min_chars = max(
        VOICE_TTS_DELTA_MIN_CHARS + 2,
        min(VOICE_TTS_DELTA_MAX_CHARS, (VOICE_TTS_DELTA_MIN_CHARS + VOICE_TTS_DELTA_MAX_CHARS) // 2),
    )
    hard_limit_chars = max(VOICE_TTS_DELTA_MAX_CHARS, weak_break_min_chars + 4)
    force_overflow_chars = max(4, VOICE_TTS_DELTA_MIN_CHARS // 2)

    while remaining:
        clean_len = _tts_text_len(remaining)
        preferred_break_idx, preferred_break_kind = _find_last_tts_break(
            remaining,
            weak_break_min_chars=weak_break_min_chars,
        )

        should_emit_preferred = False
        if preferred_break_idx > 0:
            preferred_text = remaining[:preferred_break_idx]
            preferred_len = _tts_text_len(preferred_text)
            if final:
                should_emit_preferred = True
            elif preferred_break_kind == "strong":
                # Strong punctuation usually marks a natural TTS phrase boundary.
                should_emit_preferred = preferred_len >= VOICE_TTS_DELTA_MIN_CHARS
            elif preferred_break_kind == "weak":
                should_emit_preferred = (
                    (idle_break and preferred_len >= weak_break_min_chars)
                    or preferred_len >= hard_limit_chars
                )
            elif preferred_break_kind == "space":
                should_emit_preferred = (
                    (idle_break and preferred_len >= hard_limit_chars)
                    or preferred_len >= hard_limit_chars + force_overflow_chars
                )
            if should_emit_preferred:
                segment = preferred_text.strip()
                if segment:
                    segments.append(segment)
                remaining = remaining[preferred_break_idx:]
                continue

        if clean_len >= hard_limit_chars + force_overflow_chars:
            forced_break_idx = _force_tts_split_index(
                remaining,
                target_chars=hard_limit_chars,
                max_overflow_chars=force_overflow_chars,
            )
            if forced_break_idx > 0:
                segment = remaining[:forced_break_idx].strip()
                if segment:
                    segments.append(segment)
                remaining = remaining[forced_break_idx:]
                continue

        break

    if remaining.strip():
        trailing_len = _tts_text_len(remaining)
        if final or (idle_break and trailing_len >= hard_limit_chars):
            segments.append(remaining.strip())
            remaining = ""

    return [segment for segment in segments if segment], remaining


async def _synthesize_reply_pcm(reply_text: str, *, settings: VoiceRuntimeSettings) -> bytes:
    started_at = time.perf_counter()
    bridge = _StreamingTtsBridge(settings=settings)
    bridge.start()
    bridge.feed_text(reply_text)
    bridge.finish()

    audio_parts: list[bytes] = []
    async for chunk in bridge.iter_audio():
        if chunk:
            audio_parts.append(chunk)
    pcm = b"".join(audio_parts)
    logger.info("[VOICE_TTS] text=%s pcm_bytes=%d elapsed_ms=%d", _preview_text(reply_text), len(pcm), _ms_since(started_at))
    return pcm


class _StreamingTtsBridge:
    """Bridge direct DashScope WebSocket TTS to async."""

    def __init__(self, *, settings: VoiceRuntimeSettings) -> None:
        self._settings = settings
        self._loop = asyncio.get_running_loop()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._text_queue: queue.Queue[str | None] = queue.Queue()
        self._error: Exception | None = None
        self._thread: threading.Thread | None = None
        self._started_at = time.perf_counter()
        self._first_audio_at = 0.0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def feed_text(self, text: str) -> None:
        self._text_queue.put(text)

    def finish(self) -> None:
        self._text_queue.put(None)

    async def iter_audio(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                if self._error is not None:
                    raise self._error
                break
            yield chunk

    @property
    def first_audio_delay_ms(self) -> int:
        if self._first_audio_at <= 0:
            return -1
        return int((self._first_audio_at - self._started_at) * 1000)

    def _run(self) -> None:
        try:
            asyncio.run(self._run_ws())
        except Exception as exc:
            logger.exception("[VOICE_TTS_STREAM] thread failed")
            self._error = exc
            self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, None)

    async def _run_ws(self) -> None:
        api_key = _dashscope_api_key(self._settings.tts_api_key)
        url = _dashscope_tts_ws_url()
        task_id = uuid.uuid4().hex
        started_event = asyncio.Event()
        finished_event = asyncio.Event()

        async with websockets.connect(
            url,
            extra_headers={"Authorization": f"bearer {api_key}"},
            max_size=VOICE_STREAMING_TTS_MAX_EVENT_BYTES,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            logger.info(
                "[VOICE_TTS_STREAM] ws_connected connect_ms=%d model=%s voice=%s url=%s",
                _ms_since(self._started_at),
                VOICE_STREAMING_TTS_MODEL,
                VOICE_STREAMING_TTS_VOICE,
                url,
            )
            await ws.send(
                json.dumps(
                    {
                        "header": {
                            "action": "run-task",
                            "task_id": task_id,
                            "streaming": "duplex",
                        },
                        "payload": {
                            "task_group": "audio",
                            "task": "tts",
                            "function": "SpeechSynthesizer",
                            "model": VOICE_STREAMING_TTS_MODEL,
                            "parameters": {
                                "text_type": "PlainText",
                                "voice": VOICE_STREAMING_TTS_VOICE,
                                "format": "pcm",
                                "sample_rate": VOICE_STREAMING_TTS_SAMPLE_RATE,
                                "volume": VOICE_STREAMING_TTS_VOLUME,
                                "rate": VOICE_STREAMING_TTS_SPEED,
                                "pitch": VOICE_STREAMING_TTS_PITCH,
                            },
                            "input": {},
                        },
                    },
                    ensure_ascii=False,
                )
            )

            async def _sender() -> None:
                send_started = False
                wait_started = asyncio.create_task(started_event.wait())
                wait_finished = asyncio.create_task(finished_event.wait())
                done, pending = await asyncio.wait(
                    {wait_started, wait_finished},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for pending_task in pending:
                    pending_task.cancel()
                if wait_finished in done and finished_event.is_set():
                    return
                while True:
                    text = await asyncio.to_thread(self._text_queue.get)
                    if text is None:
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {
                                        "action": "finish-task",
                                        "task_id": task_id,
                                        "streaming": "duplex",
                                    },
                                    "payload": {"input": {}},
                                },
                                ensure_ascii=False,
                            )
                        )
                        logger.info(
                            "[VOICE_TTS_STREAM] finish_task_sent elapsed_ms=%d send_started=%s",
                            _ms_since(self._started_at),
                            str(send_started).lower(),
                        )
                        return

                    text = text.strip()
                    if not text or not any(ch.isalnum() for ch in text):
                        continue

                    await ws.send(
                        json.dumps(
                            {
                                "header": {
                                    "action": "continue-task",
                                    "task_id": task_id,
                                    "streaming": "duplex",
                                },
                                "payload": {"input": {"text": text}},
                            },
                            ensure_ascii=False,
                        )
                    )
                    send_started = True

            async def _receiver() -> None:
                while True:
                    raw = await ws.recv()
                    if isinstance(raw, bytes):
                        if self._first_audio_at <= 0:
                            self._first_audio_at = time.perf_counter()
                            logger.info(
                                "[VOICE_TTS_STREAM] first audio chunk delay_ms=%d bytes=%d",
                                self.first_audio_delay_ms,
                                len(raw),
                            )
                        self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, raw)
                        continue

                    payload = json.loads(raw)
                    header = payload.get("header") or {}
                    event = str(header.get("event") or "").strip()
                    if event == "task-started":
                        started_event.set()
                        logger.info("[VOICE_TTS_STREAM] task_started elapsed_ms=%d", _ms_since(self._started_at))
                        continue
                    if event == "result-generated":
                        continue
                    if event == "task-finished":
                        finished_event.set()
                        logger.info("[VOICE_TTS_STREAM] complete total_ms=%d", _ms_since(self._started_at))
                        return
                    if event == "task-failed":
                        finished_event.set()
                        message = json.dumps(payload, ensure_ascii=False)
                        logger.warning("[VOICE_TTS_STREAM] task-failed (non-fatal): %s", message)
                        return

            sender_task = asyncio.create_task(_sender())
            receiver_task = asyncio.create_task(_receiver())
            try:
                done, pending = await asyncio.wait(
                    {sender_task, receiver_task},
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for done_task in done:
                    exc = done_task.exception()
                    if exc is not None:
                        raise exc
                if receiver_task in pending:
                    await receiver_task
            finally:
                finished_event.set()
                self._text_queue.put_nowait(None)
                for task in (sender_task, receiver_task):
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
                self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, None)


async def synthesize_prompt_pcm(text: str, settings: VoiceRuntimeSettings | None = None) -> bytes:
    effective_settings = settings or VoiceRuntimeSettings.from_llm(
        llm_provider="aliyun",
        llm_model="qwen3-coder-480b-a35b-instruct",
    )
    cache_key = "|".join(
        [
            VOICE_STREAMING_TTS_MODEL,
            VOICE_STREAMING_TTS_VOICE,
            text,
        ]
    )
    cached = _voice_prompt_cache.get(cache_key)
    if cached is not None:
        return cached
    audio_pcm = await _synthesize_reply_pcm(text, settings=effective_settings)
    _voice_prompt_cache[cache_key] = audio_pcm
    return audio_pcm


class RealtimeAsrTurnBridge:
    def __init__(
        self,
        *,
        settings: VoiceRuntimeSettings,
        sample_rate: int,
        partial_callback,
    ) -> None:
        self.settings = settings
        self.sample_rate = sample_rate
        self.partial_callback = partial_callback
        self.audio_queue: asyncio.Queue[tuple[str, bytes | None]] = asyncio.Queue()
        self._result_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run())
        self.started_at = time.perf_counter()
        self.first_audio_sent_at = 0.0
        self.commit_sent_at = 0.0
        self.first_partial_at = 0.0

    async def append_audio(self, pcm_bytes: bytes) -> None:
        if pcm_bytes:
            await self.audio_queue.put(("append", pcm_bytes))

    async def commit(self) -> str:
        await self.audio_queue.put(("commit", None))
        return await self._result_future

    async def close(self) -> None:
        if not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        api_key = _dashscope_api_key(self.settings.stt_api_key)
        url = f"{_dashscope_realtime_asr_url()}?model={VOICE_REALTIME_ASR_MODEL}"
        final_transcript = ""
        try:
            async with websockets.connect(
                url,
                extra_headers={"Authorization": f"bearer {api_key}"},
                max_size=VOICE_REALTIME_ASR_MAX_EVENT_BYTES,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                logger.info("[VOICE_PERF][BACKEND][ASR] ws_connected connect_ms=%d sample_rate=%d", _ms_since(self.started_at), self.sample_rate)
                await ws.send(
                    json.dumps(
                        {
                            "event_id": uuid.uuid4().hex,
                            "type": "session.update",
                            "session": {
                                "input_audio_format": "pcm",
                                "sample_rate": self.sample_rate,
                                "input_audio_transcription": {"language": VOICE_REALTIME_ASR_LANGUAGE},
                                "turn_detection": None,
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                logger.info("[VOICE_PERF][BACKEND][ASR] session_update_sent elapsed_ms=%d", _ms_since(self.started_at))

                async def _sender() -> None:
                    committed = False
                    while True:
                        kind, payload = await asyncio.wait_for(
                            self.audio_queue.get(),
                            timeout=VOICE_REALTIME_ASR_IDLE_TIMEOUT_SECONDS,
                        )
                        if kind == "append" and payload:
                            if self.first_audio_sent_at <= 0:
                                self.first_audio_sent_at = time.perf_counter()
                                logger.info(
                                    "[VOICE_PERF][BACKEND][ASR] first_audio_uploaded elapsed_ms=%d bytes=%d",
                                    _ms_since(self.started_at), len(payload),
                                )
                            await ws.send(
                                json.dumps({
                                    "event_id": uuid.uuid4().hex,
                                    "type": "input_audio_buffer.append",
                                    "audio": base64.b64encode(payload).decode("ascii"),
                                })
                            )
                            continue
                        if kind == "commit":
                            committed = True
                            self.commit_sent_at = time.perf_counter()
                            logger.info("[VOICE_PERF][BACKEND][ASR] commit_sent elapsed_ms=%d", _ms_since(self.started_at))
                            await ws.send(json.dumps({"event_id": uuid.uuid4().hex, "type": "input_audio_buffer.commit"}))
                            await ws.send(json.dumps({"event_id": uuid.uuid4().hex, "type": "session.finish"}))
                            break
                    if not committed:
                        await ws.send(json.dumps({"event_id": uuid.uuid4().hex, "type": "session.finish"}))

                async def _receiver() -> None:
                    nonlocal final_transcript
                    while True:
                        raw = await ws.recv()
                        event = json.loads(raw)
                        event_type = str(event.get("type", ""))
                        if event_type == "conversation.item.input_audio_transcription.text":
                            partial_text = f"{event.get('text', '')}{event.get('stash', '')}".strip()
                            if partial_text:
                                if self.first_partial_at <= 0:
                                    self.first_partial_at = time.perf_counter()
                                    logger.info(
                                        "[VOICE_PERF][BACKEND][ASR] first_partial elapsed_ms=%d since_commit_ms=%d text=%s",
                                        _ms_since(self.started_at),
                                        _elapsed_ms_between(self.commit_sent_at, self.first_partial_at),
                                        _preview_text(partial_text, limit=60),
                                    )
                                await self.partial_callback(partial_text)
                            continue
                        if event_type == "conversation.item.input_audio_transcription.completed":
                            final_transcript = str(event.get("transcript", "")).strip()
                            completed_at = time.perf_counter()
                            logger.info(
                                "[VOICE_PERF][BACKEND][ASR] final_transcript elapsed_ms=%d since_commit_ms=%d text=%s",
                                _ms_since(self.started_at),
                                _elapsed_ms_between(self.commit_sent_at, completed_at),
                                _preview_text(final_transcript, limit=80),
                            )
                            if not self._result_future.done():
                                self._result_future.set_result(final_transcript)
                            continue
                        if event_type == "conversation.item.input_audio_transcription.failed":
                            error = event.get("error") or {}
                            raise RuntimeError(str(error.get("message") or "Realtime ASR failed"))
                        if event_type == "error":
                            error = event.get("error") or {}
                            raise RuntimeError(str(error.get("message") or "Realtime ASR error"))
                        if event_type == "session.finished":
                            break

                await asyncio.gather(_sender(), _receiver())
                if not self._result_future.done():
                    self._result_future.set_result(final_transcript)
        except asyncio.CancelledError:
            if not self._result_future.done():
                self._result_future.set_result(final_transcript)
            raise
        except (TimeoutError, asyncio.TimeoutError):
            if not self._result_future.done():
                self._result_future.set_result("")
        except Exception as exc:
            if not self._result_future.done():
                self._result_future.set_exception(exc)


async def _queue_voice_ws_event(session: VoiceWsSessionState, event: str, **payload: Any) -> None:
    if session.closed:
        return
    await session.event_queue.put({"event": event, **payload})


def _schedule_server_auto_commit(session: VoiceWsSessionState) -> None:
    if session._auto_commit_task is not None and not session._auto_commit_task.done():
        session._auto_commit_task.cancel()

    async def _auto_commit_after_silence() -> None:
        await asyncio.sleep(VOICE_SERVER_VAD_SILENCE_MS / 1000.0)
        if session.closed or session.asr_bridge is None:
            return
        metrics = session.turn_metrics
        if metrics is not None and metrics.commit_requested_at > 0:
            return
        transcript = session.latest_partial_transcript.strip()
        if not transcript:
            return
        logger.info(
            "[VOICE_PERF][BACKEND] session=%s server_auto_commit silence_ms=%d transcript=%s",
            session.session_id, VOICE_SERVER_VAD_SILENCE_MS, _preview_text(transcript, limit=60),
        )
        await commit_voice_ws_audio(session)

    session._auto_commit_task = asyncio.create_task(_auto_commit_after_silence())


def _maybe_start_late_partial_warmup(session: VoiceWsSessionState) -> bool:
    metrics = session.turn_metrics
    if session.closed or metrics is None:
        return False
    if metrics.commit_requested_at <= 0 or metrics.asr_final_at > 0:
        return False
    if metrics.generation_started_at > 0:
        return False
    if session.generation_task is not None and not session.generation_task.done():
        return False

    speculative_transcript = session.latest_partial_transcript.strip()
    if len(_normalize_transcript_for_compare(speculative_transcript)) < VOICE_WS_PARTIAL_WARMUP_MIN_CHARS:
        return False

    turn_id = (metrics.turn_id or "").strip()
    if not turn_id:
        return False

    logger.info(
        "[VOICE_PERF][BACKEND] session=%s turn=%s late_partial_warmup_start since_commit_ms=%d transcript=%s",
        session.session_id,
        turn_id,
        _elapsed_ms_between(metrics.commit_requested_at, time.perf_counter()),
        _preview_text(speculative_transcript, limit=80),
    )
    _start_voice_ws_generation(session, transcript=speculative_transcript, turn_id=turn_id, warmup=True)
    return True


async def _handle_voice_ws_partial(session: VoiceWsSessionState, text: str) -> None:
    clean_text = (text or "").strip()
    if not clean_text:
        return
    session.latest_partial_transcript = clean_text
    session.latest_partial_at = time.perf_counter()
    metrics = session.turn_metrics
    if metrics is not None and metrics.first_audio_at > 0 and metrics.commit_requested_at <= 0:
        logger.info(
            "[VOICE_PERF][BACKEND] session=%s turn=%s first_partial_before_commit_ms=%d text=%s",
            session.session_id,
            metrics.turn_id or "-",
            _elapsed_ms_between(metrics.first_audio_at, session.latest_partial_at),
            _preview_text(clean_text, limit=60),
        )
    await _queue_voice_ws_event(session, "asr.partial", text=clean_text)
    if metrics is not None and metrics.commit_requested_at > 0 and metrics.asr_final_at <= 0:
        _maybe_start_late_partial_warmup(session)
        return
    if VOICE_SERVER_VAD_ENABLED and metrics is not None and metrics.commit_requested_at <= 0:
        _schedule_server_auto_commit(session)


async def _queue_voice_ws_audio_chunks(
    session: VoiceWsSessionState,
    *,
    generation_id: int,
    chunk_id_start: int,
    pcm_bytes: bytes,
    sample_rate: int = 16000,
) -> int:
    if session.binary_audio:
        return await _queue_voice_ws_binary_audio(
            session,
            generation_id=generation_id,
            chunk_id_start=chunk_id_start,
            pcm_bytes=pcm_bytes,
        )
    chunk_id = chunk_id_start
    for offset in range(0, len(pcm_bytes), VOICE_WS_AUDIO_CHUNK_BYTES):
        piece = pcm_bytes[offset : offset + VOICE_WS_AUDIO_CHUNK_BYTES]
        if not piece:
            continue
        await _queue_voice_ws_event(
            session,
            "tts.audio_chunk",
            generation_id=generation_id,
            chunk_id=chunk_id,
            sample_rate=sample_rate,
            audio=base64.b64encode(piece).decode("ascii"),
        )
        chunk_id += 1
    return chunk_id


async def _queue_voice_ws_binary_audio(
    session: VoiceWsSessionState,
    *,
    generation_id: int,
    chunk_id_start: int,
    pcm_bytes: bytes,
) -> int:
    if session.closed:
        return chunk_id_start
    chunk_id = chunk_id_start

    if session.audio_codec == "opus" and session.opus_encoder is not None:
        opus_frames = _opus_encode_pcm(session.opus_encoder, pcm_bytes)
        for frame in opus_frames:
            await session.event_queue.put({"__binary__": True, "data": frame})
            chunk_id += 1
        return chunk_id

    for offset in range(0, len(pcm_bytes), VOICE_WS_AUDIO_CHUNK_BYTES):
        piece = pcm_bytes[offset : offset + VOICE_WS_AUDIO_CHUNK_BYTES]
        if not piece:
            continue
        await session.event_queue.put({"__binary__": True, "data": piece})
        chunk_id += 1
    return chunk_id


async def _cancel_generation_task(session: VoiceWsSessionState, *, emit_interrupted: bool) -> None:
    task = session.generation_task
    session.generation_task = None
    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    if emit_interrupted:
        await _queue_voice_ws_event(session, "turn.interrupted", generation_id=session.generation_id)


async def _interrupt_voice_ws_session(session: VoiceWsSessionState, *, emit_event: bool) -> None:
    if session._auto_commit_task is not None and not session._auto_commit_task.done():
        if session._auto_commit_task is not asyncio.current_task():
            session._auto_commit_task.cancel()
        session._auto_commit_task = None
    if session.asr_bridge is not None:
        await session.asr_bridge.close()
        session.asr_bridge = None
    if session.pending_tts_bridge is not None:
        session.pending_tts_bridge.finish()
        session.pending_tts_bridge = None
    await _cancel_generation_task(session, emit_interrupted=emit_event)
    session.reply_parts.clear()
    session.audio_parts.clear()
    session.latest_partial_transcript = ""
    session.latest_partial_at = 0.0
    session.active_turn_id = None
    session.active_turn_transcript = ""
    session.turn_metrics = None


async def _finalize_voice_ws_turn(
    *,
    session: VoiceWsSessionState,
    turn_id: str,
    transcript: str,
    reply_text: str,
    audio_parts: list[bytes],
) -> bytes:
    image_bmp = await render_ai_chat_bmp(
        screen_w=session.screen_w,
        screen_h=session.screen_h,
        user_text=transcript,
        reply_text=reply_text,
    ) if session.include_image else b""
    _voice_turns[turn_id] = {
        "created_at": time.time(),
        "transcript": transcript,
        "reply_text": reply_text,
        "audio_pcm": b"".join(audio_parts),
        "image_bmp": image_bmp,
        "access_user_id": session.access_user_id,
        "access_mac": session.access_mac,
    }
    return image_bmp


def _start_voice_ws_generation(
    session: VoiceWsSessionState,
    *,
    transcript: str,
    turn_id: str | None = None,
    warmup: bool = False,
) -> tuple[str, int]:
    actual_turn_id = turn_id or uuid.uuid4().hex
    session.generation_id += 1
    generation_id = session.generation_id
    session.active_turn_id = actual_turn_id
    session.active_turn_transcript = transcript
    metrics = session.turn_metrics
    if metrics is None:
        metrics = VoiceWsTurnMetrics(turn_id=actual_turn_id, capture_started_at=time.perf_counter())
        session.turn_metrics = metrics
    metrics.turn_id = actual_turn_id
    metrics.generation_started_at = time.perf_counter()
    metrics.used_partial_warmup = warmup
    logger.info(
        "[VOICE_PERF][BACKEND] session=%s turn=%s generation_start warmup=%s transcript_len=%d since_commit_ms=%d transcript=%s",
        session.session_id,
        actual_turn_id,
        str(warmup).lower(),
        len(_normalize_transcript_for_compare(transcript)),
        _elapsed_ms_between(metrics.commit_requested_at, metrics.generation_started_at),
        _preview_text(transcript, limit=80),
    )
    gen_fn = _run_voice_ws_generation_streaming if VOICE_STREAMING_TTS_ENABLED else _run_voice_ws_generation
    session.generation_task = asyncio.create_task(
        gen_fn(session, transcript=transcript, turn_id=actual_turn_id, generation_id=generation_id)
    )
    return actual_turn_id, generation_id


async def _run_voice_ws_generation_streaming(
    session: VoiceWsSessionState,
    *,
    transcript: str,
    turn_id: str,
    generation_id: int,
) -> None:
    reply_parts: list[str] = []
    audio_parts: list[bytes] = []
    chunk_id = 0
    tts_buffer = ""
    last_delta_at = time.perf_counter()
    metrics = session.turn_metrics

    def _resolved_transcript() -> str:
        if session.active_turn_id == turn_id and session.active_turn_transcript:
            return session.active_turn_transcript
        return transcript

    async def _feed_tts_segment(segment: str) -> None:
        normalized_segment = _normalize_tts_stream_text(segment)
        if not normalized_segment:
            return
        await _queue_voice_ws_event(
            session,
            "tts.text_chunk",
            generation_id=generation_id,
            chunk_id=chunk_id,
            text=normalized_segment,
        )
        if metrics is not None and metrics.first_tts_text_at <= 0:
            metrics.first_tts_text_at = time.perf_counter()
            logger.info(
                "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_text since_llm_ms=%d since_commit_ms=%d text=%s",
                session.session_id,
                turn_id,
                _elapsed_ms_between(metrics.first_llm_delta_at, metrics.first_tts_text_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_text_at),
                _preview_text(normalized_segment, limit=60),
            )
        tts_bridge.feed_text(normalized_segment)

    try:
        if not transcript:
            pcm_chunk = await _synthesize_reply_pcm("没听清，请再说一次。", settings=session.settings)
            audio_parts.append(pcm_chunk)
            if metrics is not None and metrics.first_tts_audio_at <= 0:
                metrics.first_tts_audio_at = time.perf_counter()
            reply_text = "没听清，请再说一次。"
            image_bmp = await _finalize_voice_ws_turn(
                session=session, turn_id=turn_id, transcript=_resolved_transcript(),
                reply_text=reply_text, audio_parts=audio_parts,
            )
            chunk_id = await _queue_voice_ws_audio_chunks(
                session, generation_id=generation_id, chunk_id_start=chunk_id,
                pcm_bytes=pcm_chunk, sample_rate=16000,
            )
            await _queue_voice_ws_event(
                session, "turn.done", turn_id=turn_id, generation_id=generation_id,
                transcript=_resolved_transcript(), reply_text=reply_text,
                exit_conversation=False, switch_to_mode="",
            )
            if metrics is not None:
                metrics.done_at = time.perf_counter()
                session.turn_metrics = None
            return

        if session.pending_tts_bridge is not None:
            tts_bridge = session.pending_tts_bridge
            session.pending_tts_bridge = None
        else:
            tts_bridge = _StreamingTtsBridge(settings=session.settings)
            tts_bridge.start()
        llm_done = asyncio.Event()

        async def _feed_llm() -> None:
            nonlocal last_delta_at, tts_buffer
            try:
                prompt = _build_voice_reply_prompt(transcript)
                llm_request_started_at = time.perf_counter()
                logger.info(
                    "[VOICE_PERF][BACKEND] session=%s turn=%s llm_request_start warmup=%s provider=%s model=%s since_commit_ms=%d since_asr_final_ms=%d transcript=%s prompt_chars=%d",
                    session.session_id,
                    turn_id,
                    str(metrics.used_partial_warmup if metrics is not None else False).lower(),
                    session.settings.llm_provider,
                    session.settings.llm_model,
                    _elapsed_ms_between(metrics.commit_requested_at, llm_request_started_at) if metrics is not None else -1,
                    _elapsed_ms_between(metrics.asr_final_at, llm_request_started_at) if metrics is not None and metrics.asr_final_at > 0 else -1,
                    _preview_text(transcript, limit=80),
                    len(prompt),
                )
                async for delta in _stream_llm_deltas(
                    settings=session.settings, prompt=prompt, temperature=0.3, max_tokens=160,
                ):
                    if generation_id != session.generation_id:
                        return
                    if metrics is not None and metrics.first_llm_delta_at <= 0:
                        metrics.first_llm_delta_at = time.perf_counter()
                        logger.info(
                            "[VOICE_PERF][BACKEND] session=%s turn=%s first_llm_delta since_commit_ms=%d",
                            session.session_id, turn_id,
                            _elapsed_ms_between(metrics.commit_requested_at, metrics.first_llm_delta_at),
                        )
                    reply_parts.append(delta)
                    await _queue_voice_ws_event(session, "llm.delta", generation_id=generation_id, delta=delta)
                    idle_break = _ms_since(last_delta_at) >= VOICE_TTS_DELTA_IDLE_MS
                    next_tts_buffer = tts_buffer + delta
                    segments, remainder = _split_delta_tts_segments(next_tts_buffer, final=False, idle_break=idle_break)
                    for segment in segments:
                        await _feed_tts_segment(segment)
                    tts_buffer = remainder
                    last_delta_at = time.perf_counter()
            finally:
                trailing_segments, trailing_remainder = _split_delta_tts_segments(tts_buffer, final=True, idle_break=True)
                for segment in trailing_segments:
                    await _feed_tts_segment(segment)
                remainder_segment = _normalize_tts_stream_text(trailing_remainder)
                if remainder_segment:
                    await _feed_tts_segment(remainder_segment)
                tts_bridge.finish()
                llm_done.set()

        async def _send_audio() -> None:
            nonlocal chunk_id
            async for pcm_chunk in tts_bridge.iter_audio():
                if generation_id != session.generation_id:
                    return
                audio_parts.append(pcm_chunk)
                if metrics is not None and metrics.first_tts_audio_at <= 0:
                    metrics.first_tts_audio_at = time.perf_counter()
                    logger.info(
                        "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_audio streaming_delay_ms=%d since_commit_ms=%d bytes=%d",
                        session.session_id, turn_id,
                        tts_bridge.first_audio_delay_ms,
                        _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                        len(pcm_chunk),
                    )
                chunk_id = await _queue_voice_ws_audio_chunks(
                    session, generation_id=generation_id, chunk_id_start=chunk_id,
                    pcm_bytes=pcm_chunk, sample_rate=16000,
                )

        await asyncio.gather(_feed_llm(), _send_audio())

        reply_text = _normalize_voice_reply_text("".join(reply_parts), limit=160) or "我这边暂时答不上来。"
        if not audio_parts:
            pcm_chunk = await _synthesize_reply_pcm(reply_text, settings=session.settings)
            audio_parts.append(pcm_chunk)
            chunk_id = await _queue_voice_ws_audio_chunks(
                session, generation_id=generation_id, chunk_id_start=chunk_id,
                pcm_bytes=pcm_chunk, sample_rate=16000,
            )

        image_bmp = await _finalize_voice_ws_turn(
            session=session, turn_id=turn_id, transcript=_resolved_transcript(),
            reply_text=reply_text, audio_parts=audio_parts,
        )
        _exit_conv, _switch_mode = _resolve_turn_done_flags(_resolved_transcript())
        await _set_pending_mode_if_switch(session, _switch_mode)
        await _queue_voice_ws_event(
            session, "turn.done", turn_id=turn_id, generation_id=generation_id,
            transcript=_resolved_transcript(), reply_text=reply_text,
            exit_conversation=_exit_conv, switch_to_mode=_switch_mode or "",
        )
        if metrics is not None:
            metrics.done_at = time.perf_counter()
            logger.info(
                "[VOICE_PERF][BACKEND] session=%s turn=%s done_streaming total_ms=%d commit_to_first_tts_audio_ms=%d commit_to_done_ms=%d audio_chunks=%d",
                session.session_id, turn_id,
                _elapsed_ms_between(metrics.capture_started_at, metrics.done_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.done_at),
                metrics.audio_chunks,
            )
            session.turn_metrics = None
    except asyncio.CancelledError:
        logger.info("[VOICE_PERF][BACKEND] session=%s turn=%s streaming_generation_cancelled", session.session_id, turn_id)
        raise
    except Exception as exc:
        logger.exception("[VOICE_WS] streaming generation failed session_id=%s turn_id=%s", session.session_id, turn_id)
        await _queue_voice_ws_event(session, "error", message=str(exc))


async def _run_voice_ws_generation(
    session: VoiceWsSessionState,
    *,
    transcript: str,
    turn_id: str,
    generation_id: int,
) -> None:
    reply_parts: list[str] = []
    audio_parts: list[bytes] = []
    tts_buffer = ""
    chunk_id = 0
    last_delta_at = time.perf_counter()
    metrics = session.turn_metrics

    def _resolved_transcript() -> str:
        if session.active_turn_id == turn_id and session.active_turn_transcript:
            return session.active_turn_transcript
        return transcript

    try:
        if not transcript:
            reply_text = "没听清，请再说一次。"
            pcm_chunk = await _synthesize_reply_pcm(reply_text, settings=session.settings)
            audio_parts.append(pcm_chunk)
            if metrics is not None and metrics.first_tts_audio_at <= 0:
                metrics.first_tts_audio_at = time.perf_counter()
            image_bmp = await _finalize_voice_ws_turn(
                session=session,
                turn_id=turn_id,
                transcript=_resolved_transcript(),
                reply_text=reply_text,
                audio_parts=audio_parts,
            )
            await _queue_voice_ws_event(session, "tts.text_chunk", generation_id=generation_id, chunk_id=chunk_id, text=reply_text)
            if metrics is not None and metrics.first_tts_text_at <= 0:
                metrics.first_tts_text_at = time.perf_counter()
            chunk_id = await _queue_voice_ws_audio_chunks(
                session,
                generation_id=generation_id,
                chunk_id_start=chunk_id,
                pcm_bytes=pcm_chunk,
                sample_rate=16000,
            )
            await _queue_voice_ws_event(
                session,
                "turn.done",
                turn_id=turn_id,
                generation_id=generation_id,
                transcript=_resolved_transcript(),
                reply_text=reply_text,
                exit_conversation=False,
                switch_to_mode="",
            )
            if metrics is not None:
                metrics.done_at = time.perf_counter()
                logger.info(
                    "[VOICE_PERF][BACKEND] session=%s turn=%s empty_transcript_reply commit_to_first_tts_audio_ms=%d commit_to_done_ms=%d",
                    session.session_id,
                    turn_id,
                    _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                    _elapsed_ms_between(metrics.commit_requested_at, metrics.done_at),
                )
                session.turn_metrics = None
            return

        prompt = _build_voice_reply_prompt(transcript)
        async for delta in _stream_llm_deltas(
            settings=session.settings,
            prompt=prompt,
            temperature=0.3,
            max_tokens=160,
        ):
            if generation_id != session.generation_id:
                return
            if metrics is not None and metrics.first_llm_delta_at <= 0:
                metrics.first_llm_delta_at = time.perf_counter()
                logger.info(
                    "[VOICE_PERF][BACKEND] session=%s turn=%s first_llm_delta since_generation_ms=%d since_commit_ms=%d delta=%s",
                    session.session_id,
                    turn_id,
                    _elapsed_ms_between(metrics.generation_started_at, metrics.first_llm_delta_at),
                    _elapsed_ms_between(metrics.commit_requested_at, metrics.first_llm_delta_at),
                    _preview_text(delta, limit=60),
                )
            reply_parts.append(delta)
            await _queue_voice_ws_event(session, "llm.delta", generation_id=generation_id, delta=delta)
            idle_break = _ms_since(last_delta_at) >= VOICE_TTS_DELTA_IDLE_MS
            tts_buffer += delta
            segments, tts_buffer = _split_delta_tts_segments(tts_buffer, final=False, idle_break=idle_break)
            last_delta_at = time.perf_counter()
            for segment in segments:
                await _queue_voice_ws_event(
                    session,
                    "tts.text_chunk",
                    generation_id=generation_id,
                    chunk_id=chunk_id,
                    text=segment,
                )
                if metrics is not None and metrics.first_tts_text_at <= 0:
                    metrics.first_tts_text_at = time.perf_counter()
                    logger.info(
                        "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_text since_llm_ms=%d since_commit_ms=%d text=%s",
                        session.session_id,
                        turn_id,
                        _elapsed_ms_between(metrics.first_llm_delta_at, metrics.first_tts_text_at),
                        _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_text_at),
                        _preview_text(segment, limit=60),
                    )
                pcm_chunk = await _synthesize_reply_pcm(segment, settings=session.settings)
                audio_parts.append(pcm_chunk)
                if metrics is not None and metrics.first_tts_audio_at <= 0:
                    metrics.first_tts_audio_at = time.perf_counter()
                    logger.info(
                        "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_audio since_tts_text_ms=%d since_commit_ms=%d pcm_bytes=%d",
                        session.session_id,
                        turn_id,
                        _elapsed_ms_between(metrics.first_tts_text_at, metrics.first_tts_audio_at),
                        _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                        len(pcm_chunk),
                    )
                chunk_id = await _queue_voice_ws_audio_chunks(
                    session,
                    generation_id=generation_id,
                    chunk_id_start=chunk_id,
                    pcm_bytes=pcm_chunk,
                    sample_rate=16000,
                )

        trailing_segments, tts_buffer = _split_delta_tts_segments(tts_buffer, final=True, idle_break=True)
        for segment in trailing_segments:
            await _queue_voice_ws_event(
                session,
                "tts.text_chunk",
                generation_id=generation_id,
                chunk_id=chunk_id,
                text=segment,
            )
            if metrics is not None and metrics.first_tts_text_at <= 0:
                metrics.first_tts_text_at = time.perf_counter()
                logger.info(
                    "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_text since_llm_ms=%d since_commit_ms=%d text=%s",
                    session.session_id,
                    turn_id,
                    _elapsed_ms_between(metrics.first_llm_delta_at, metrics.first_tts_text_at),
                    _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_text_at),
                    _preview_text(segment, limit=60),
                )
            pcm_chunk = await _synthesize_reply_pcm(segment, settings=session.settings)
            audio_parts.append(pcm_chunk)
            if metrics is not None and metrics.first_tts_audio_at <= 0:
                metrics.first_tts_audio_at = time.perf_counter()
                logger.info(
                    "[VOICE_PERF][BACKEND] session=%s turn=%s first_tts_audio since_tts_text_ms=%d since_commit_ms=%d pcm_bytes=%d",
                    session.session_id,
                    turn_id,
                    _elapsed_ms_between(metrics.first_tts_text_at, metrics.first_tts_audio_at),
                    _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                    len(pcm_chunk),
                )
            chunk_id = await _queue_voice_ws_audio_chunks(
                session,
                generation_id=generation_id,
                chunk_id_start=chunk_id,
                pcm_bytes=pcm_chunk,
                sample_rate=16000,
            )

        reply_text = _normalize_voice_reply_text("".join(reply_parts), limit=160) or "我这边暂时答不上来。"
        if not audio_parts:
            pcm_chunk = await _synthesize_reply_pcm(reply_text, settings=session.settings)
            audio_parts.append(pcm_chunk)
            await _queue_voice_ws_event(
                session,
                "tts.text_chunk",
                generation_id=generation_id,
                chunk_id=chunk_id,
                text=reply_text,
            )
            chunk_id = await _queue_voice_ws_audio_chunks(
                session,
                generation_id=generation_id,
                chunk_id_start=chunk_id,
                pcm_bytes=pcm_chunk,
                sample_rate=16000,
            )

        image_bmp = await _finalize_voice_ws_turn(
            session=session,
            turn_id=turn_id,
            transcript=_resolved_transcript(),
            reply_text=reply_text,
            audio_parts=audio_parts,
        )
        _exit_conv, _switch_mode = _resolve_turn_done_flags(_resolved_transcript())
        await _set_pending_mode_if_switch(session, _switch_mode)
        await _queue_voice_ws_event(
            session,
            "turn.done",
            turn_id=turn_id,
            generation_id=generation_id,
            transcript=_resolved_transcript(),
            reply_text=reply_text,
            exit_conversation=_exit_conv,
            switch_to_mode=_switch_mode or "",
        )
        if metrics is not None:
            metrics.done_at = time.perf_counter()
            logger.info(
                "[VOICE_PERF][BACKEND] session=%s turn=%s done total_ms=%d capture_to_commit_ms=%d commit_to_final_asr_ms=%d commit_to_first_llm_ms=%d commit_to_first_tts_audio_ms=%d commit_to_done_ms=%d audio_chunks=%d audio_bytes=%d warmup=%s",
                session.session_id,
                turn_id,
                _elapsed_ms_between(metrics.capture_started_at, metrics.done_at),
                _elapsed_ms_between(metrics.capture_started_at, metrics.commit_requested_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.asr_final_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.first_llm_delta_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.first_tts_audio_at),
                _elapsed_ms_between(metrics.commit_requested_at, metrics.done_at),
                metrics.audio_chunks,
                metrics.audio_bytes,
                str(metrics.used_partial_warmup).lower(),
            )
            session.turn_metrics = None
    except asyncio.CancelledError:
        logger.info("[VOICE_PERF][BACKEND] session=%s turn=%s generation_cancelled", session.session_id, turn_id)
        raise
    except Exception as exc:
        logger.exception("[VOICE_WS] generation failed session_id=%s turn_id=%s", session.session_id, turn_id)
        await _queue_voice_ws_event(session, "error", message=str(exc))


def create_voice_ws_session(
    *,
    settings: VoiceRuntimeSettings,
    access_user_id: int | None,
    access_mac: str | None,
) -> VoiceWsSessionState:
    return VoiceWsSessionState(
        session_id=uuid.uuid4().hex,
        settings=settings,
        access_user_id=access_user_id,
        access_mac=access_mac,
    )


async def start_voice_ws_session(
    session: VoiceWsSessionState,
    *,
    sample_rate: int,
    screen_w: int,
    screen_h: int,
    include_image: bool,
    protocol_version: int = 1,
    audio_codec: str = "pcm",
) -> None:
    session.sample_rate = sample_rate
    session.screen_w = screen_w
    session.screen_h = screen_h
    session.include_image = include_image
    session.protocol_version = protocol_version
    session.binary_audio = protocol_version >= 2

    requested_codec = audio_codec.strip().lower()
    if requested_codec == "opus" and _HAS_OPUS and session.binary_audio:
        session.audio_codec = "opus"
        session.opus_encoder = _create_opus_encoder(sample_rate)
        session.opus_decoder = _create_opus_decoder(sample_rate)
        if session.opus_encoder is None or session.opus_decoder is None:
            session.audio_codec = "pcm"
            session.opus_encoder = None
            session.opus_decoder = None
    else:
        session.audio_codec = "pcm"

    session.started = True
    session.latest_partial_transcript = ""
    session.latest_partial_at = 0.0
    session.turn_metrics = None
    _ensure_asr_bridge(session)
    await _queue_voice_ws_event(
        session,
        "session.ready",
        session_id=session.session_id,
        conversation_id=session.conversation_id,
        sample_rate=session.sample_rate,
        binary_audio=session.binary_audio,
        audio_codec=session.audio_codec,
        server_vad=VOICE_SERVER_VAD_ENABLED,
    )


def _ensure_asr_bridge(session: VoiceWsSessionState) -> None:
    if session.asr_bridge is not None:
        if not session.asr_bridge._task.done():
            return
        session.asr_bridge = None
    if session.closed:
        return
    session.asr_bridge = RealtimeAsrTurnBridge(
        settings=session.settings,
        sample_rate=session.sample_rate,
        partial_callback=lambda text: _handle_voice_ws_partial(session, text),
    )
    logger.info("[VOICE_PERF][BACKEND] session=%s asr_bridge_preconnect sample_rate=%d", session.session_id, session.sample_rate)


async def append_voice_ws_audio(session: VoiceWsSessionState, audio_bytes: bytes) -> None:
    if not session.started:
        raise RuntimeError("voice websocket session not started")

    if session.audio_codec == "opus" and session.opus_decoder is not None:
        pcm_bytes = _opus_decode_frame(session.opus_decoder, audio_bytes)
        if not pcm_bytes:
            return
    else:
        pcm_bytes = audio_bytes

    _ensure_asr_bridge(session)
    if session.turn_metrics is None:
        session.latest_partial_transcript = ""
        session.latest_partial_at = 0.0
        session.turn_metrics = VoiceWsTurnMetrics(capture_started_at=time.perf_counter())
        logger.info("[VOICE_PERF][BACKEND] session=%s capture_start sample_rate=%d", session.session_id, session.sample_rate)
    metrics = session.turn_metrics
    if metrics is not None:
        now = time.perf_counter()
        if metrics.first_audio_at <= 0:
            metrics.first_audio_at = now
            logger.info("[VOICE_PERF][BACKEND] session=%s first_audio_append bytes=%d", session.session_id, len(pcm_bytes))
        metrics.last_audio_at = now
        metrics.audio_chunks += 1
        metrics.audio_bytes += len(pcm_bytes)
    await session.asr_bridge.append_audio(pcm_bytes)


async def commit_voice_ws_audio(session: VoiceWsSessionState) -> None:
    if not session.started:
        raise RuntimeError("voice websocket session not started")
    if session._auto_commit_task is not None and not session._auto_commit_task.done():
        if session._auto_commit_task is not asyncio.current_task():
            session._auto_commit_task.cancel()
        session._auto_commit_task = None
    if session.asr_bridge is None:
        await _queue_voice_ws_event(session, "asr.final", transcript="")
        session.turn_index += 1
        await _cancel_generation_task(session, emit_interrupted=False)
        _start_voice_ws_generation(session, transcript="")
        return
    session.turn_index += 1
    turn_id = uuid.uuid4().hex
    speculative_transcript = session.latest_partial_transcript.strip()
    metrics = session.turn_metrics
    if metrics is None:
        metrics = VoiceWsTurnMetrics(capture_started_at=time.perf_counter())
        session.turn_metrics = metrics
    metrics.turn_id = turn_id
    metrics.commit_requested_at = time.perf_counter()
    logger.info(
        "[VOICE_PERF][BACKEND] session=%s turn=%s commit_requested capture_ms=%d audio_chunks=%d audio_bytes=%d partial=%s",
        session.session_id,
        turn_id,
        _elapsed_ms_between(metrics.capture_started_at, metrics.commit_requested_at),
        metrics.audio_chunks,
        metrics.audio_bytes,
        _preview_text(speculative_transcript, limit=60),
    )
    await _cancel_generation_task(session, emit_interrupted=False)
    should_warmup = _should_warmup_voice_generation(session, speculative_transcript)
    logger.info(
        "[VOICE_PERF][BACKEND] session=%s turn=%s warmup_decision enabled=%s partial_len=%d latest_partial_age_ms=%d stable_threshold_ms=%d transcript=%s",
        session.session_id,
        turn_id,
        str(should_warmup).lower(),
        len(_normalize_transcript_for_compare(speculative_transcript)),
        _ms_since(session.latest_partial_at) if session.latest_partial_at > 0 else -1,
        VOICE_WS_PARTIAL_WARMUP_STABLE_MS,
        _preview_text(speculative_transcript, limit=80),
    )
    if should_warmup:
        _start_voice_ws_generation(session, transcript=speculative_transcript, turn_id=turn_id, warmup=True)
    if VOICE_STREAMING_TTS_ENABLED and session.pending_tts_bridge is None:
        session.pending_tts_bridge = _StreamingTtsBridge(settings=session.settings)
        session.pending_tts_bridge.start()
    transcript = await session.asr_bridge.commit()
    old_asr_bridge = session.asr_bridge
    session.asr_bridge = None
    session.latest_partial_transcript = ""
    session.latest_partial_at = 0.0

    async def _background_asr_close() -> None:
        with contextlib.suppress(Exception):
            await old_asr_bridge.close()

    asyncio.create_task(_background_asr_close())
    _ensure_asr_bridge(session)
    metrics.asr_final_at = time.perf_counter()
    await _queue_voice_ws_event(session, "asr.final", transcript=transcript)
    final_transcript = transcript.strip()
    logger.info(
        "[VOICE_PERF][BACKEND] session=%s turn=%s asr_final since_commit_ms=%d transcript=%s",
        session.session_id,
        turn_id,
        _elapsed_ms_between(metrics.commit_requested_at, metrics.asr_final_at),
        _preview_text(final_transcript, limit=80),
    )
    used_warmup_generation = metrics.used_partial_warmup
    if used_warmup_generation and _is_compatible_warmup_transcript(speculative_transcript, final_transcript):
        session.active_turn_transcript = final_transcript or speculative_transcript
        logger.info(
            "[VOICE_PERF][BACKEND] session=%s turn=%s warmup_reused transcript_delta=%d final_transcript=%s",
            session.session_id,
            turn_id,
            len(_normalize_transcript_for_compare(final_transcript)) - len(_normalize_transcript_for_compare(speculative_transcript)),
            _preview_text(final_transcript, limit=80),
        )
        return
    if used_warmup_generation:
        await _cancel_generation_task(session, emit_interrupted=True)
        logger.info(
            "[VOICE_PERF][BACKEND] session=%s turn=%s warmup_cancelled_restart=true speculative=%s final=%s",
            session.session_id,
            turn_id,
            _preview_text(speculative_transcript, limit=80),
            _preview_text(final_transcript, limit=80),
        )
    _start_voice_ws_generation(session, transcript=final_transcript, turn_id=turn_id, warmup=False)


async def interrupt_voice_ws_session(session: VoiceWsSessionState) -> None:
    await _interrupt_voice_ws_session(session, emit_event=True)


async def close_voice_ws_session(session: VoiceWsSessionState) -> None:
    if session.closed:
        return
    session.closed = True
    await _interrupt_voice_ws_session(session, emit_event=False)
    await session.event_queue.put(None)


async def iter_voice_ws_events(session: VoiceWsSessionState) -> AsyncIterator[dict]:
    while True:
        event = await session.event_queue.get()
        if event is None:
            break
        yield event


async def _finalize_pending_voice_turn(turn_id: str, pending: PendingVoiceTurn, fallback_reply: str = "") -> None:
    reply_text = _normalize_voice_reply_text("".join(pending.reply_parts), limit=80)
    if not reply_text:
        reply_text = _normalize_voice_reply_text(pending.reply_text or fallback_reply, limit=80)
    _voice_turns[turn_id] = {
        "created_at": pending.created_at,
        "transcript": pending.transcript,
        "reply_text": reply_text,
        "audio_pcm": b"".join(pending.audio_parts),
        "image_bmp": await render_ai_chat_bmp(
            screen_w=pending.screen_w,
            screen_h=pending.screen_h,
            user_text=pending.transcript,
            reply_text=reply_text,
        ) if pending.include_image else b"",
        "access_user_id": pending.access_user_id,
        "access_mac": pending.access_mac,
    }


async def _run_streaming_voice_turn(
    turn_id: str,
    pending: PendingVoiceTurn,
    *,
    settings: VoiceRuntimeSettings,
) -> None:
    fallback_reply = "我这边稍等一下。"
    try:
        await pending.event_queue.put({"event": "transcript", "transcript": pending.transcript})
        prompt = _build_voice_reply_prompt(pending.transcript)
        async for segment in _stream_llm_sentence_segments(
            settings=settings,
            prompt=prompt,
            temperature=0.3,
            max_tokens=160,
        ):
            pending.reply_parts.append(segment)
            await pending.event_queue.put({"event": "reply_segment", "text": segment})
            if not VOICE_TTS_STREAMING:
                continue
            pcm_chunk = await _synthesize_reply_pcm(segment, settings=settings)
            pending.audio_parts.append(pcm_chunk)
            await pending.audio_queue.put(pcm_chunk)

        final_reply = _normalize_voice_reply_text("".join(pending.reply_parts), limit=80)
        if not final_reply:
            final_reply = "我这边暂时答不上来。"
            pending.reply_parts = [final_reply]

        if not pending.audio_parts:
            pcm_chunk = await _synthesize_reply_pcm(final_reply, settings=settings)
            pending.audio_parts.append(pcm_chunk)
            await pending.audio_queue.put(pcm_chunk)

        pending.reply_text = final_reply
        await _finalize_pending_voice_turn(turn_id, pending, fallback_reply=fallback_reply)
        _exit_conv, _switch_mode = _resolve_turn_done_flags(pending.transcript)
        await pending.event_queue.put(
            {
                "event": "done",
                "turn_id": turn_id,
                "reply_text": final_reply,
                "exit_conversation": _exit_conv,
                "switch_to_mode": _switch_mode or "",
            }
        )
    except Exception as exc:
        logger.exception("[VOICE_STREAM_TURN] failed turn_id=%s", turn_id)
        pending.error = str(exc)
        try:
            error_reply = "我这边暂时出错了。"
            pcm_chunk = await _synthesize_reply_pcm(error_reply, settings=settings)
            pending.reply_parts = [error_reply]
            pending.audio_parts = [pcm_chunk]
            pending.reply_text = error_reply
            await pending.audio_queue.put(pcm_chunk)
            await _finalize_pending_voice_turn(turn_id, pending, fallback_reply=error_reply)
            await pending.event_queue.put({"event": "error", "message": str(exc)})
            await pending.event_queue.put(
                {
                    "event": "done",
                    "turn_id": turn_id,
                    "reply_text": error_reply,
                    "exit_conversation": False,
                }
            )
        except Exception:
            logger.exception("[VOICE_STREAM_TURN] fallback synth failed turn_id=%s", turn_id)
    finally:
        try:
            await pending.audio_queue.put(None)
            await pending.event_queue.put(None)
        finally:
            _pending_voice_turns.pop(turn_id, None)


def start_pending_voice_turn(
    *,
    transcript: str,
    screen_w: int,
    screen_h: int,
    include_image: bool,
    access_user_id: int | None,
    access_mac: str | None,
    settings: VoiceRuntimeSettings,
) -> str:
    _cleanup_pending_voice_turns()
    turn_id = uuid.uuid4().hex
    pending = PendingVoiceTurn(
        created_at=time.time(),
        transcript=transcript,
        screen_w=screen_w,
        screen_h=screen_h,
        include_image=include_image,
        access_user_id=access_user_id,
        access_mac=access_mac,
    )
    _pending_voice_turns[turn_id] = pending
    asyncio.create_task(_run_streaming_voice_turn(turn_id, pending, settings=settings))
    return turn_id


def get_pending_voice_turn(turn_id: str) -> PendingVoiceTurn | None:
    _cleanup_pending_voice_turns()
    return _pending_voice_turns.get(turn_id)


def get_pending_voice_turn_audio_stream(turn_id: str) -> AsyncIterator[bytes] | None:
    pending = get_pending_voice_turn(turn_id)
    if pending is None:
        return None

    async def _stream() -> AsyncIterator[bytes]:
        while True:
            chunk = await pending.audio_queue.get()
            if chunk is None:
                break
            if chunk:
                yield chunk

    return _stream()


def get_pending_voice_turn_event_stream(turn_id: str) -> AsyncIterator[dict] | None:
    pending = get_pending_voice_turn(turn_id)
    if pending is None:
        return None

    async def _stream() -> AsyncIterator[dict]:
        while True:
            event = await pending.event_queue.get()
            if event is None:
                break
            yield event

    return _stream()


async def create_voice_turn(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    screen_w: int,
    screen_h: int,
    include_image: bool = True,
    access_user_id: int | None = None,
    access_mac: str | None = None,
    settings: VoiceRuntimeSettings,
) -> dict[str, str | int | bool]:
    turn_started_at = time.perf_counter()
    _cleanup_voice_turns()
    _cleanup_pending_voice_turns()

    stt_elapsed_ms = 0
    llm_elapsed_ms = 0
    tts_elapsed_ms = 0
    image_elapsed_ms = 0

    stt_started_at = time.perf_counter()
    transcript = await _transcribe_pcm_bytes(
        pcm_bytes,
        sample_rate=sample_rate,
        settings=settings,
    )
    stt_elapsed_ms = _ms_since(stt_started_at)

    if not transcript:
        transcript = "未识别到清晰语音"
        reply_text = "没听清，请再说一次。"
        tts_started_at = time.perf_counter()
        audio_pcm = await _synthesize_reply_pcm(reply_text, settings=settings)
        tts_elapsed_ms = _ms_since(tts_started_at)
    elif VOICE_LLM_STREAMING or VOICE_TTS_STREAMING:
        exit_conversation, switch_to_mode = _resolve_turn_done_flags(transcript)
        turn_id = start_pending_voice_turn(
            transcript=transcript,
            screen_w=screen_w,
            screen_h=screen_h,
            include_image=include_image,
            access_user_id=access_user_id,
            access_mac=access_mac,
            settings=settings,
        )
        return {
            "turn_id": turn_id,
            "transcript": transcript,
            "reply_text": "",
            "streaming": True,
            "exit_conversation": exit_conversation,
            "switch_to_mode": switch_to_mode or "",
            "backend_stt_ms": stt_elapsed_ms,
            "backend_llm_ms": 0,
            "backend_tts_ms": 0,
            "backend_image_ms": 0,
            "backend_total_ms": _ms_since(turn_started_at),
        }
    else:
        llm_started_at = time.perf_counter()
        reply_text = await _call_llm(
            settings.llm_provider,
            settings.llm_model,
            _build_voice_reply_prompt(transcript),
            temperature=0.3,
            max_tokens=80,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        reply_text = _normalize_voice_reply_text(reply_text, limit=80) or "我暂时答不上来。"
        llm_elapsed_ms = _ms_since(llm_started_at)

        tts_started_at = time.perf_counter()
        audio_pcm = await _synthesize_reply_pcm(reply_text, settings=settings)
        tts_elapsed_ms = _ms_since(tts_started_at)

    exit_conversation, switch_to_mode = _resolve_turn_done_flags(transcript)
    image_bmp = b""
    if include_image:
        image_started_at = time.perf_counter()
        image_bmp = await render_ai_chat_bmp(
            screen_w=screen_w,
            screen_h=screen_h,
            user_text=transcript,
            reply_text=reply_text,
        )
        image_elapsed_ms = _ms_since(image_started_at)

    turn_id = uuid.uuid4().hex
    _voice_turns[turn_id] = {
        "created_at": time.time(),
        "transcript": transcript,
        "reply_text": reply_text,
        "audio_pcm": audio_pcm,
        "image_bmp": image_bmp,
        "access_user_id": access_user_id,
        "access_mac": access_mac,
    }
    return {
        "turn_id": turn_id,
        "transcript": transcript,
        "reply_text": reply_text,
        "streaming": False,
        "exit_conversation": exit_conversation,
        "switch_to_mode": switch_to_mode or "",
        "backend_stt_ms": stt_elapsed_ms,
        "backend_llm_ms": llm_elapsed_ms,
        "backend_tts_ms": tts_elapsed_ms,
        "backend_image_ms": image_elapsed_ms,
        "backend_total_ms": _ms_since(turn_started_at),
    }


def get_voice_turn(turn_id: str) -> VoiceTurn | None:
    _cleanup_voice_turns()
    _cleanup_pending_voice_turns()
    return _voice_turns.get(turn_id)
