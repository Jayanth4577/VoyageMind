import json as _json

"""LLM abstraction tests: factory selection + adapters via httpx.MockTransport."""

import asyncio

import httpx
import pytest
from pydantic import BaseModel

from app.core.config import settings
from app.llm import get_llm_provider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMError


class Answer(BaseModel):
    answer: str
    score: int


def ollama_client(handler) -> OllamaProvider:
    return OllamaProvider(
        base_url="http://fake",
        model="test",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_factory_unknown_provider():
    with pytest.raises(LLMError):
        get_llm_provider("doesnotexist")


def test_gemini_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(LLMError):
        get_llm_provider("gemini")


def test_ollama_generate_call():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "hi there"}})

    assert asyncio.run(ollama_client(handler).generate("say hi")) == "hi there"


def test_ollama_structured_parses_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": '{"answer": "Goa", "score": 5}'}})

    out = asyncio.run(ollama_client(handler).generate_structured("pick a place", Answer))
    assert out == Answer(answer="Goa", score=5)


def test_structured_tolerates_code_fences():
    fenced = '```json\n{"answer": "Manali", "score": 4}\n```'

    def handler(request):
        return httpx.Response(200, json={"message": {"content": fenced}})

    out = asyncio.run(ollama_client(handler).generate_structured("pick", Answer))
    assert out.answer == "Manali"


def test_structured_schema_violation_raises_llm_error():
    bad = '{"wrong": "shape"}'

    def handler(request):
        return httpx.Response(200, json={"message": {"content": bad}})

    with pytest.raises(LLMError):
        asyncio.run(ollama_client(handler).generate_structured("pick", Answer))


def test_http_error_wrapped_as_llm_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(LLMError):
        asyncio.run(ollama_client(handler).generate("hi"))


def test_openai_requires_api_key():
    with pytest.raises(LLMError):
        OpenAIProvider(base_url="http://fake", client=httpx.AsyncClient())


def test_gemini_factory_defaults_base_url(monkeypatch):
    """Regression: empty base_url must fall back to the adapter default,
    not produce a protocol-less request URL (Render deployment bug)."""
    from app.core.config import settings
    from app.llm.gemini_provider import DEFAULT_BASE_URL

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    provider = get_llm_provider("gemini")
    assert provider.base_url == DEFAULT_BASE_URL
    assert provider.base_url.startswith("https://")


def test_openai_factory_defaults_base_url(monkeypatch):
    from app.core.config import settings
    from app.llm.openai_provider import DEFAULT_BASE_URL

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    provider = get_llm_provider("openai")
    assert provider.base_url == DEFAULT_BASE_URL


def test_gemini_404_falls_back_to_available_model(monkeypatch):
    """Regression: retired model names (gemini-2.0-flash -> 404) must
    auto-discover an available model and retry instead of failing."""
    import asyncio

    import httpx

    from app.llm.gemini_provider import GeminiProvider

    calls = {"generate": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-3.8-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/gemini-2.5-pro",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                    ]
                },
            )
        if ":generateContent" in url:
            body = _json.loads(request.read())
            is_probe = body["contents"][0]["parts"][0]["text"] == "ping"
            if "gemini-flash-latest" in url and not is_probe:
                calls["generate"] += 1
                return httpx.Response(404, text="model not found")
            if is_probe:
                return httpx.Response(
                    200, json={"candidates": [{"content": {"parts": [{"text": "pong"}]}}]}
                )
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "hi!"}]}}]},
            )
        return httpx.Response(404, text="unexpected")

    provider = GeminiProvider(
        api_key="test",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    answer = asyncio.run(provider.generate("say hi"))
    assert answer == "hi!"
    assert calls["generate"] == 1  # dead model called once, retried on the new model
    assert provider.model != "gemini-flash-latest"  # switched away from the 404 model
    assert "tts" not in provider.model and "image" not in provider.model


def test_gemini_transient_503_retried_then_success(monkeypatch):
    import asyncio

    import httpx

    from app.llm.gemini_provider import GeminiProvider

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(503, text="overloaded")
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )

    provider = GeminiProvider(
        api_key="test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    # shrink backoff for the test
    import app.llm.gemini_provider as gp

    monkeypatch.setattr(gp, "RETRY_BACKOFF_SECONDS", 0)
    answer = asyncio.run(provider.generate("hi"))
    assert answer == "ok"
    assert calls["n"] == 3


def test_gemini_persistent_503_raises_after_retries(monkeypatch):
    import asyncio

    import httpx
    import pytest

    from app.llm.gemini_provider import GeminiProvider
    from app.llm.provider import LLMError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="overloaded")

    provider = GeminiProvider(
        api_key="test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    import app.llm.gemini_provider as gp

    monkeypatch.setattr(gp, "RETRY_BACKOFF_SECONDS", 0)
    with pytest.raises(LLMError, match="after 3 attempts"):
        asyncio.run(provider.generate("hi"))


def test_gemini_quota_hops_to_alternate_model(monkeypatch):
    """Free-tier quota is per model: persistent 429 must hop to another model's pool."""
    import asyncio

    import httpx

    from app.llm.gemini_provider import GeminiProvider

    state = {"gen": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-flash-latest",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/gemini-flash-lite-latest",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                    ]
                },
            )
        if ":generateContent" in url:
            body = _json.loads(request.read())
            if body["contents"][0]["parts"][0]["text"] == "ping":
                return httpx.Response(
                    200, json={"candidates": [{"content": {"parts": [{"text": "pong"}]}}]}
                )
            state["gen"] += 1
            if "flash-latest:" in url:
                return httpx.Response(429, text="quota")
            return httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": "hopped!"}]}}]}
            )
        return httpx.Response(404)

    provider = GeminiProvider(
        api_key="test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    import app.llm.gemini_provider as gp

    monkeypatch.setattr(gp, "RETRY_BACKOFF_SECONDS", 0)
    answer = asyncio.run(provider.generate("hi"))
    assert answer == "hopped!"
    assert provider.model == "gemini-flash-lite-latest"
    assert provider._hopped_models is True
