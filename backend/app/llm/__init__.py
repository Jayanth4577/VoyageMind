"""Provider factory — the only place that knows which provider is active."""

from app.core.config import settings
from app.llm.gemini_provider import GeminiProvider
from app.llm.nova_provider import NovaProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.provider import LLMError, LLMProvider

_REGISTRY = {
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "nova": NovaProvider,
}


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or settings.llm_provider).lower().strip()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{name}'; expected one of {sorted(_REGISTRY)}")
    return cls(
        api_key=getattr(settings, f"{name}_api_key", ""),
        base_url=getattr(settings, f"{name}_base_url", "") or "",
        model=settings.llm_model,
    )
