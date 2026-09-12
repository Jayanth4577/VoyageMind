"""Google Gemini adapter (REST, no extra SDK dependency)."""
import httpx

from app.llm.provider import LLMError, LLMProvider, T

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("base_url", DEFAULT_BASE_URL)
        kwargs.setdefault("model", DEFAULT_MODEL)
        super().__init__(**kwargs)
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not configured")

    async def _post(self, body: dict) -> dict:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        try:
            resp = await self.client().post(
                url, json=body, headers={"x-goog-api-key": self.api_key}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini call failed: {exc}") from exc

    @staticmethod
    def _text(payload: dict) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected Gemini response shape: {exc}") from exc

    async def generate(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.7
    ) -> str:
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return self._text(await self._post(body))

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return self._validate_structured(self._text(await self._post(body)), schema)
