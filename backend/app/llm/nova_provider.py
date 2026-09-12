"""Amazon Nova adapter placeholder (spec §14).

Nova is delivered via Amazon Bedrock. The adapter slot exists so plugging it in
later requires zero application rewrites — implement `generate` /
`generate_structured` against the Bedrock Converse API.
"""

from app.llm.provider import LLMError, LLMProvider, T


class NovaProvider(LLMProvider):
    name = "nova"

    def _unavailable(self) -> LLMError:
        return LLMError(
            "Amazon Nova adapter is not implemented yet; "
            "configure LLM_PROVIDER=gemini|ollama|openai"
        )

    async def generate(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.7
    ) -> str:
        raise self._unavailable()

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        raise self._unavailable()
