from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.voice_service import (
    MINIMAX_TTS_ENDPOINTS,
    MINIMAX_TTS_MODELS,
    VoiceRuntimeSettings,
    _MiniMaxTtsBridge,
    _create_tts_bridge,
    _synthesize_minimax_pcm,
)


def test_minimax_provider_selects_tts_backend(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "env-minimax-key")

    settings = VoiceRuntimeSettings.from_llm(
        llm_provider="minimax",
        llm_model="MiniMax-M3",
    )

    assert settings.tts_provider == "minimax"
    assert settings.tts_api_key == "env-minimax-key"
    assert settings.tts_model == "speech-2.8-hd"
    assert set(MINIMAX_TTS_ENDPOINTS) == {"global_en", "cn_zh"}
    assert len(MINIMAX_TTS_MODELS) == 8


@pytest.mark.asyncio
async def test_minimax_tts_request_and_hex_response():
    response = MagicMock()
    response.json.return_value = {
        "data": {"audio": "000102ff"},
        "base_resp": {"status_code": 0},
    }
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post.return_value = response
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = client

    settings = VoiceRuntimeSettings(
        llm_provider="minimax",
        llm_model="MiniMax-M3",
        tts_api_key="test-key",
        tts_provider="minimax",
        tts_model="speech-2.8-turbo",
        tts_region="cn_zh",
        tts_voice="test-voice",
    )
    with patch("core.voice_service.httpx.AsyncClient", return_value=context_manager):
        audio = await _synthesize_minimax_pcm("Hello", settings=settings)

    assert audio == b"\x00\x01\x02\xff"
    response.raise_for_status.assert_called_once_with()
    call = client.post.call_args
    assert call.args[0] == "https://api.minimaxi.com/v1/t2a_v2"
    assert call.kwargs["headers"] == {"Authorization": "Bearer test-key"}
    assert call.kwargs["json"] == {
        "model": "speech-2.8-turbo",
        "text": "Hello",
        "stream": False,
        "output_format": "hex",
        "voice_setting": {"voice_id": "test-voice"},
        "audio_setting": {"format": "pcm", "sample_rate": 16000},
    }


@pytest.mark.asyncio
async def test_minimax_tts_reports_api_error():
    response = MagicMock()
    response.json.return_value = {
        "data": {"audio": ""},
        "base_resp": {"status_code": 1001, "status_msg": "invalid request"},
    }
    client = AsyncMock()
    client.post.return_value = response
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = client
    settings = VoiceRuntimeSettings(
        llm_provider="minimax",
        llm_model="MiniMax-M3",
        tts_api_key="test-key",
        tts_provider="minimax",
    )

    with (
        patch("core.voice_service.httpx.AsyncClient", return_value=context_manager),
        pytest.raises(RuntimeError, match="invalid request"),
    ):
        await _synthesize_minimax_pcm("Hello", settings=settings)


@pytest.mark.asyncio
async def test_minimax_bridge_collects_streamed_text():
    settings = VoiceRuntimeSettings(
        llm_provider="minimax",
        llm_model="MiniMax-M3",
        tts_api_key="test-key",
        tts_provider="minimax",
    )
    bridge = _create_tts_bridge(settings=settings)
    assert isinstance(bridge, _MiniMaxTtsBridge)
    bridge.start()
    bridge.feed_text("Hello")
    bridge.feed_text(" world")
    bridge.finish()

    with patch("core.voice_service._synthesize_minimax_pcm", new=AsyncMock(return_value=b"pcm")) as synthesize:
        chunks = [chunk async for chunk in bridge.iter_audio()]

    assert chunks == [b"pcm"]
    synthesize.assert_awaited_once_with("Hello world", settings=settings)
