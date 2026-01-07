"""Ollama LLM provider."""

import asyncio
from typing import AsyncIterator

import httpx
import ollama

from agentna.core.constants import DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL, EMBEDDING_MODEL
from agentna.core.exceptions import LLMConnectionError, LLMError
from agentna.llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        embed_model: str = EMBEDDING_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
    ) -> None:
        self.model = model
        self.embed_model = embed_model
        self.host = host
        self._client = ollama.AsyncClient(host=host)
        self._sync_client = ollama.Client(host=host)

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = self._sync_client.list()
            # Handle both old dict API and new Pydantic model API
            if hasattr(response, "models"):
                # New API: ListResponse with .models list of Model objects
                model_names = [m.model for m in response.models]
            else:
                # Old API: dict with "models" key
                model_names = [m.get("name", m.get("model", "")) for m in response.get("models", [])]

            # Check for model name with or without tag
            return any(
                self.model in name or name.startswith(self.model.split(":")[0])
                for name in model_names
            )
        except Exception:
            return False

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion using Ollama."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )
            return response["message"]["content"]
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}") from e

    async def stream(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream a completion using Ollama."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async for chunk in await self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            ):
                if chunk.get("message", {}).get("content"):
                    yield chunk["message"]["content"]
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}") from e

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using Ollama."""
        try:
            response = await self._client.embeddings(
                model=self.embed_model,
                prompt=text,
            )
            return response["embedding"]
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama embedding error: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}") from e

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        # Ollama doesn't support batch embeddings, so we do them sequentially
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings

    def complete_sync(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """Synchronous completion for non-async contexts."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._sync_client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )
            return response["message"]["content"]
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama error: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}") from e

    def embed_sync(self, text: str) -> list[float]:
        """Synchronous embedding for non-async contexts."""
        try:
            response = self._sync_client.embeddings(
                model=self.embed_model,
                prompt=text,
            )
            return response["embedding"]
        except ollama.ResponseError as e:
            raise LLMError(f"Ollama embedding error: {e}") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Cannot connect to Ollama at {self.host}") from e
