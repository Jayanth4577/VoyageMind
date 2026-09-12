"""OpenAI-compatible adapter (works with OpenAI and compatible gateways)."""

import httpx

from app.llm.provider import LLMError, LLMProvider, T

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("base_url", DEFAULT_BASE_URL)
        kwargs.setdefault("model", DEFAULT_MODEL)
        super().__init__(**kwargs)
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not configured")

    async def _chat(self, messages: list[dict], *, temperature: float, json_mode: bool) -> str:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = await self.client().post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenAI call failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenAI response shape: {exc}") from exc

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
