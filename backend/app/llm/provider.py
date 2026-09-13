"""LLM provider abstraction (spec §14).

The application depends only on this interface. Providers are selected via
LLM_PROVIDER config; swapping providers must not require app rewrites.
Providers do reasoning only — never arithmetic or live-data invention.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Provider misconfiguration or call failure (never crashes the app; callers degrade)."""


class LLMProvider(ABC):
    name: ClassVar[str] = "base"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client  # injectable for tests

    def client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=self.timeout)

    @abstractmethod
    async def generate(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.7
    ) -> str:
        """Free-form text completion."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        """Completion validated against a Pydantic schema (JSON mode where supported)."""

    def supports_tools(self) -> bool:
        return False

    async def call_tools(self, prompt: str, tools: list[dict], executor) -> dict:  # noqa: ARG002
        """Tool-calling loop (wired to the Travel MCP Gateway in Phase 5)."""
        raise NotImplementedError(f"{self.name} does not support tool calling yet")

    # -- shared structured-output parsing -------------------------------------
    @staticmethod
    def _extract_json(text: str) -> dict:
        """Parse JSON from a model reply, tolerating code fences and prose wrappers."""
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        candidate = fenced.group(1) if fenced else text
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", candidate, re.DOTALL)
            if match is None:
                raise LLMError("Model reply contained no JSON object") from None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise LLMError(f"Model reply was not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMError("Model JSON was not an object")
        return parsed

    def _validate_structured(self, text: str, schema: type[T]) -> T:
        try:
            return schema.model_validate(self._extract_json(text))
        except ValidationError as exc:
            raise LLMError(f"Structured output failed schema validation: {exc}") from exc
