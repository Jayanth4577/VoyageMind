"""LLM abstraction tests: factory selection + adapters via httpx.MockTransport."""

import asyncio

import httpx
import pytest
from pydantic import BaseModel

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


def test_gemini_requires_api_key():
    with pytest.raises(LLMError):
        get_llm_provider("gemini")  # no key configured in test env


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
