"""Claude API LLM provider."""

import os
from typing import AsyncIterator

import anthropic

from agentna.core.exceptions import LLMConnectionError, LLMError
from agentna.llm.base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: anthropic.AsyncAnthropic | None = None
        self._sync_client: anthropic.Anthropic | None = None

    @property
    def name(self) -> str:
        return "claude"

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Get or create async client."""
        if self._client is None:
            if not self.api_key:
                raise LLMError("ANTHROPIC_API_KEY not set")
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _get_sync_client(self) -> anthropic.Anthropic:
        """Get or create sync client."""
        if self._sync_client is None:
            if not self.api_key:
                raise LLMError("ANTHROPIC_API_KEY not set")
            self._sync_client = anthropic.Anthropic(api_key=self.api_key)
        return self._sync_client

    def is_available(self) -> bool:
        """Check if Claude API is available."""
        return bool(self.api_key)

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion using Claude."""
        client = self._get_client()

        try:
            message = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "You are a helpful coding assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError(f"Cannot connect to Claude API: {e}") from e
        except anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}") from e

    async def stream(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream a completion using Claude."""
        client = self._get_client()

        try:
            async with client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "You are a helpful coding assistant.",
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError(f"Cannot connect to Claude API: {e}") from e
        except anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}") from e

    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings.

        Note: Claude doesn't have a native embedding API, so this falls back
        to a simple implementation or raises an error.
        """
        raise LLMError("Claude does not support embeddings. Use Ollama for embeddings.")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        raise LLMError("Claude does not support embeddings. Use Ollama for embeddings.")

    def complete_sync(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Synchronous completion for non-async contexts."""
        client = self._get_sync_client()

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "You are a helpful coding assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.APIConnectionError as e:
            raise LLMConnectionError(f"Cannot connect to Claude API: {e}") from e
        except anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}") from e
