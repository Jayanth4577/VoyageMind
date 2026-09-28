"""Provider factory — the only place that knows which provider is active."""

from app.core.config import settings
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMError, LLMProvider

_REGISTRY = {
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
}


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or settings.llm_provider).lower().strip()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{name}'; expected one of {sorted(_REGISTRY)}")
    # Only pass overrides that are actually configured — an empty base_url must
    # NOT reach the adapter (it would override the adapter's default and break
    # the request URL), so adapters keep their sane defaults.
    kwargs: dict = {"api_key": getattr(settings, f"{name}_api_key", "")}
    base_url = getattr(settings, f"{name}_base_url", "") or ""
    if base_url:
        kwargs["base_url"] = base_url
    if settings.llm_model:
        kwargs["model"] = settings.llm_model
    return cls(**kwargs)
