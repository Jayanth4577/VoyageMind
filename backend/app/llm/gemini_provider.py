"""Google Gemini adapter (REST, no extra SDK dependency).

Model resilience: Google retires model names over time (gemini-2.0-flash was
removed and produced 404s in production). The default is the `*-latest` alias,
and on a 404 the adapter auto-discovers an available generateContent-capable
model via the ListModels API, switches to it, and retries the request once.

Transient resilience: the free tier intermittently serves 503s per request,
so 429/5xx responses are retried with a short backoff.
"""

import asyncio

import httpx

from app.core.logging import get_logger
from app.llm.provider import LLMError, LLMProvider, T

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-flash-latest"

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
TRANSIENT_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5
MAX_RETRY_AFTER_SECONDS = 30.0


def _backoff_seconds(response: httpx.Response, attempt: int) -> float:
    """Honor Google's Retry-After on quota errors; exponential backoff otherwise."""
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass
    return RETRY_BACKOFF_SECONDS * (attempt + 1)

# Preference order for auto-discovery. ListModels can list retired models, so
# every candidate is probe-verified before use — this order is just preference.
FALLBACK_MODEL_PREFERENCES = (
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, **kwargs) -> None:
        if not kwargs.get("base_url"):
            kwargs["base_url"] = DEFAULT_BASE_URL
        kwargs.setdefault("model", DEFAULT_MODEL)
        super().__init__(**kwargs)
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not configured")
        self._model_resolved = False
        self._hopped_models = False

    async def _list_usable_models(self) -> list[str]:
        """Model ids that support generateContent for this API key."""
        try:
            resp = await self.client().get(
                f"{self.base_url}/models",
                headers={"x-goog-api-key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Gemini model discovery failed: {exc}") from exc

        usable = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                usable.append(m.get("name", "").removeprefix("models/"))
        return usable

    async def _model_accepts(self, model: str) -> bool:
        """Probe a candidate with a trivial request — ListModels can list
        retired models, so advertised availability must be verified."""
        try:
            resp = await self.client().post(
                f"{self.base_url}/models/{model}:generateContent",
                json={"contents": [{"parts": [{"text": "ping"}]}]},
                headers={"x-goog-api-key": self.api_key},
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def _pick_verified_model(self, exclude: set[str]) -> str | None:
        """First working model from the preference list + usable list, probed."""
        usable = await self._list_usable_models()
        ordered: list[str] = []
        for preferred in FALLBACK_MODEL_PREFERENCES:
            if preferred in usable and preferred not in exclude:
                ordered.append(preferred)
        for name in usable:
            if name not in exclude and name not in ordered:
                ordered.append(name)
        for candidate in ordered:
            if "tts" in candidate or "image" in candidate or "embed" in candidate:
                continue
            if await self._model_accepts(candidate):
                return candidate
        return None

    async def _resolve_model_on_404(self) -> str:
        """Pick a verified available model after a 404 (retired model)."""
        resolved = await self._pick_verified_model(exclude={self.model})
        if resolved is None:
            raise LLMError(
                "Gemini returned 404 for the configured model and no working "
                "alternative models are available for this API key"
            )
        return resolved

    async def _alternate_model(self, exhausted: str) -> str | None:
        """A different verified-working model (quota is per model)."""
        return await self._pick_verified_model(exclude={exhausted})

    async def _post(self, body: dict) -> dict:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        # Google's free tier intermittently returns 503 per request; agent runs
        # make several LLM calls, so transient failures must be retried.
        last_error: httpx.HTTPError | None = None
        for attempt in range(TRANSIENT_RETRIES):
            try:
                resp = await self.client().post(
                    url, json=body, headers={"x-goog-api-key": self.api_key}
                )
                if resp.status_code == 404 and not self._model_resolved:
                    # Model likely retired — discover an available one and retry once.
                    resolved = await self._resolve_model_on_404()
                    logger.warning(
                        "Gemini model '%s' returned 404; falling back to '%s'",
                        self.model,
                        resolved,
                    )
                    self.model = resolved
                    self._model_resolved = True
                    url = f"{self.base_url}/models/{self.model}:generateContent"
                    resp = await self.client().post(
                        url, json=body, headers={"x-goog-api-key": self.api_key}
                    )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in TRANSIENT_STATUS_CODES:
                    last_error = exc
                    logger.warning(
                        "Gemini transient %s (attempt %d/%d) for %s",
                        exc.response.status_code,
                        attempt + 1,
                        TRANSIENT_RETRIES,
                        self.model,
                    )
                    await asyncio.sleep(
                        _backoff_seconds(exc.response, attempt)
                    )
                    continue
                raise LLMError(f"Gemini call failed: {exc}") from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"Gemini call failed: {exc}") from exc

        # When retries are spent, try a different verified model once: quota is
        # enforced PER MODEL (429), and persistent 503s are often model-specific
        # overload — a probe-verified alternate model cures both.
        if last_error is not None and not self._hopped_models:
            alternative = await self._alternate_model(self.model)
            if alternative is not None:
                logger.warning(
                    "Gemini persistent failure on '%s'; hopping to '%s'",
                    self.model,
                    alternative,
                )
                self._hopped_models = True
                self.model = alternative
                url = f"{self.base_url}/models/{self.model}:generateContent"
                for attempt in range(TRANSIENT_RETRIES):
                    try:
                        resp = await self.client().post(
                            url, json=body, headers={"x-goog-api-key": self.api_key}
                        )
                        resp.raise_for_status()
                        return resp.json()
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in TRANSIENT_STATUS_CODES:
                            last_error = exc
                            await asyncio.sleep(_backoff_seconds(exc.response, attempt))
                            continue
                        raise LLMError(f"Gemini call failed: {exc}") from exc
                    except httpx.HTTPError as exc:
                        raise LLMError(f"Gemini call failed: {exc}") from exc

        raise LLMError(
            f"Gemini call failed after {TRANSIENT_RETRIES} attempts "
            f"(service temporarily unavailable): {last_error}"
        ) from last_error

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
