"""Ollama adapter for local/self-hosted models (dev-friendly, no API key)."""

import httpx

from app.llm.provider import LLMError, LLMProvider, T

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("base_url", DEFAULT_BASE_URL)
        kwargs.setdefault("model", DEFAULT_MODEL)
        super().__init__(**kwargs)

    async def _chat(self, messages: list[dict], *, temperature: float, json_mode: bool) -> str:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            body["format"] = "json"
        try:
            resp = await self.client().post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama call failed: {exc}") from exc
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Ollama response shape: {exc}") from exc

    async def generate(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.7
    ) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        return await self._chat(messages, temperature=temperature, json_mode=False)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        text = await self._chat(messages, temperature=temperature, json_mode=True)
        return self._validate_structured(text, schema)
