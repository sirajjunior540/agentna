"""LLM router for provider selection and fallback."""

from typing import AsyncIterator

from agentna.core.config import LLMConfig
from agentna.core.exceptions import LLMConnectionError, LLMError
from agentna.llm.base import BaseLLMProvider
from agentna.llm.claude_provider import ClaudeProvider
from agentna.llm.ollama_provider import OllamaProvider


class LLMRouter:
    """Routes LLM requests to appropriate provider with fallback support."""

    def __init__(self, config: LLMConfig) -> None:
        """
        Initialize the router.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._ollama: OllamaProvider | None = None
        self._claude: ClaudeProvider | None = None

    @property
    def ollama(self) -> OllamaProvider:
        """Get Ollama provider."""
        if self._ollama is None:
            self._ollama = OllamaProvider(
                model=self.config.ollama_model,
                embed_model=self.config.ollama_embed_model,
                host=self.config.ollama_host,
            )
        return self._ollama

    @property
    def claude(self) -> ClaudeProvider:
        """Get Claude provider."""
        if self._claude is None:
            self._claude = ClaudeProvider(
                model=self.config.claude_model,
                api_key=self.config.anthropic_api_key,
            )
        return self._claude

    def get_preferred_provider(self) -> BaseLLMProvider:
        """Get the preferred provider based on config."""
        if self.config.preferred_provider == "claude":
            return self.claude
        return self.ollama

    def get_fallback_provider(self) -> BaseLLMProvider | None:
        """Get the fallback provider if enabled."""
        if not self.config.fallback_enabled:
            return None

        if self.config.preferred_provider == "ollama":
            return self.claude
        return self.ollama

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a completion with automatic fallback.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        primary = self.get_preferred_provider()
        fallback = self.get_fallback_provider()

        try:
            if primary.is_available():
                return await primary.complete(prompt, system, max_tokens, temperature)
            elif fallback and fallback.is_available():
                return await fallback.complete(prompt, system, max_tokens, temperature)
            else:
                raise LLMError("No LLM provider available")
        except LLMConnectionError:
            if fallback and fallback.is_available():
                return await fallback.complete(prompt, system, max_tokens, temperature)
            raise

    async def stream(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream a completion with automatic fallback.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Yields:
            Generated text chunks
        """
        primary = self.get_preferred_provider()
        fallback = self.get_fallback_provider()

        try:
            if primary.is_available():
                async for chunk in primary.stream(prompt, system, max_tokens, temperature):
                    yield chunk
            elif fallback and fallback.is_available():
                async for chunk in fallback.stream(prompt, system, max_tokens, temperature):
                    yield chunk
            else:
                raise LLMError("No LLM provider available")
        except LLMConnectionError:
            if fallback and fallback.is_available():
                async for chunk in fallback.stream(prompt, system, max_tokens, temperature):
                    yield chunk
            else:
                raise

    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings (uses Ollama).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Always use Ollama for embeddings since Claude doesn't support them
        if self.ollama.is_available():
            return await self.ollama.embed(text)
        raise LLMError("Ollama not available for embeddings")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if self.ollama.is_available():
            return await self.ollama.embed_batch(texts)
        raise LLMError("Ollama not available for embeddings")

    def complete_sync(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Synchronous completion with automatic fallback."""
        primary = self.get_preferred_provider()
        fallback = self.get_fallback_provider()

        try:
            if primary.is_available():
                if hasattr(primary, "complete_sync"):
                    return primary.complete_sync(prompt, system, max_tokens, temperature)
            if fallback and fallback.is_available():
                if hasattr(fallback, "complete_sync"):
                    return fallback.complete_sync(prompt, system, max_tokens, temperature)
            raise LLMError("No LLM provider available")
        except LLMConnectionError:
            if fallback and fallback.is_available() and hasattr(fallback, "complete_sync"):
                return fallback.complete_sync(prompt, system, max_tokens, temperature)
            raise

    def get_status(self) -> dict[str, bool]:
        """Get availability status of all providers."""
        return {
            "ollama": self.ollama.is_available(),
            "claude": self.claude.is_available(),
        }
