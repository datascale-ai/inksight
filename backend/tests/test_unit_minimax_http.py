"""Exercise MiniMax requests through the real SDK and an offline HTTP transport."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from core import content
from core.config import get_default_llm_model_for_provider


@pytest.fixture
async def captured_requests(monkeypatch):
    requests = []
    clients = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "test-completion",
            "object": "chat.completion",
            "created": 0,
            "model": json.loads(request.content)["model"],
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "  Test response  "},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        })

    def create_client(**kwargs):
        client = AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(content, "AsyncOpenAI", create_client)
    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    yield requests
    for client in clients:
        await client.close()


@pytest.mark.parametrize("entrypoint", ["public", "internal", "client"])
@pytest.mark.parametrize("provider,model,base_url,expected_budget", [
    ("minimax", None, None, 1024),
    ("minimax", "MiniMax-M3", None, 1024),
    ("minimax", "MiniMax-M2.7", None, 1024),
    ("minimax", "saved-custom-model", None, 120),
    ("openai_compat", "MiniMax-M3.1-Flash", "https://api.minimax.io/v1", 120),
    ("openai_compat", "MiniMax-M3.1-Flash", "https://api.minimaxi.com/v1", 120),
    ("openai_compat", "MiniMax-M3", "https://api.minimaxi.com/v1", 120),
    ("openai_compat", "MiniMax-M2.7", "https://api.minimaxi.com/v1", 120),
    ("openai_compat", "custom-model", "https://custom.example/v1", 120),
])
async def test_serialized_text_request(
    captured_requests, entrypoint, provider, model, base_url, expected_budget,
):
    selected_model = model or get_default_llm_model_for_provider(provider)
    api_key = "test-user-key" if provider == "openai_compat" else None
    if entrypoint == "public":
        result = await content.call_llm(
            "Test prompt", system_prompt="Test system", llm_provider=provider,
            llm_model=selected_model, api_key=api_key, llm_base_url=base_url,
        )
    elif entrypoint == "internal":
        result = await content._call_llm(
            provider, selected_model, "Test prompt", api_key=api_key, base_url=base_url,
        )
    else:
        client = content.LLMClient(provider, selected_model, api_key=api_key, base_url=base_url)
        result = await client.call("Test prompt")

    assert result == "Test response"
    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"{base_url or 'https://api.minimax.io/v1'}/chat/completions"
    messages = [{"role": "user", "content": "Test prompt"}]
    if entrypoint == "public":
        messages.insert(0, {"role": "system", "content": "Test system"})
    assert json.loads(request.content) == {
        "model": selected_model,
        "messages": messages,
        "max_tokens": expected_budget,
        "temperature": 0.8,
    }
    # Exact payload equality also guards against unsupported thinking/effort fields.
    if model is None:
        assert selected_model == "MiniMax-M3.1-Flash"


def test_current_catalog_is_flash_first():
    assert list(content.LLM_CONFIGS["minimax"]["models"]) == [
        "MiniMax-M3.1-Flash", "MiniMax-M3",
    ]


async def test_explicit_budget_and_multimodal_messages_are_preserved(captured_requests):
    from core.mode_generator import _call_llm_with_messages

    messages = [{"role": "user", "content": [
        {"type": "text", "text": "Describe the reference"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,dGVzdA=="}},
    ]}]
    result = await _call_llm_with_messages(
        "openai_compat", "custom-vision-model", messages, max_tokens=2048,
        api_key="test-user-key", base_url="https://custom.example/v1",
    )
    assert result == "Test response"
    assert len(captured_requests) == 1
    assert json.loads(captured_requests[0].content) == {
        "model": "custom-vision-model", "messages": messages,
        "max_tokens": 2048, "temperature": 0.3,
    }
