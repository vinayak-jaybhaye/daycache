"""Embedding providers implementation."""

from __future__ import annotations

import random
from typing import Any, ClassVar, Protocol

import numpy as np
from google import genai
from google.genai import types
from google.genai.errors import APIError as GeminiAPIError
from ollama import (
    AsyncClient as AsyncOllamaClient,
)
from ollama import (
    ResponseError as OllamaResponseError,
)
from openai import APIError as OpenAIAPIError
from openai import AsyncOpenAI

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    """Protocol defining the interface for embedding generation."""

    @property
    def dimension(self) -> int:
        """The dimension size of the generated vectors."""
        ...

    async def get_embedding(self, text: str) -> list[float]:
        """Generate a vector embedding for the given input text."""
        ...


class MockEmbeddingProvider:
    """Mock provider for local testing and CI runs."""

    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def get_embedding(self, text: str) -> list[float]:
        # Yield deterministic mock vectors based on text length to allow consistency in tests
        seed = len(text)
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self._dimension)]


class OpenAIEmbeddingProvider:
    """OpenAI embeddings provider using the official OpenAI SDK."""

    def __init__(self, api_key: str, model: str, dimension: int = 768) -> None:
        self.api_key = api_key
        self.model = model
        self._dimension = dimension
        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def dimension(self) -> int:
        # text-embedding-3-small/-large support truncation via the `dimensions` param;
        # text-embedding-ada-002 does NOT support truncation and is fixed at 1536.
        return self._dimension

    async def get_embedding(self, text: str) -> list[float]:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        kwargs: dict[str, Any] = {"model": self.model, "input": text}
        # ada-002 errors out if you pass `dimensions` at all, so only send it
        # for models that actually support truncation.
        if self.model != "text-embedding-ada-002":
            kwargs["dimensions"] = self._dimension

        try:
            response = await self._client.embeddings.create(**kwargs)
        except OpenAIAPIError as e:
            raise RuntimeError(f"OpenAI embedding request failed: {e}") from e

        return response.data[0].embedding


class GeminiEmbeddingProvider:
    """Gemini embeddings provider using the official Google GenAI SDK."""

    _NATIVE_768_MODELS: ClassVar[set[str]] = {"text-embedding-004"}

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model.removeprefix("models/") if model else ""
        self._client = genai.Client(api_key=api_key)

    @property
    def dimension(self) -> int:
        return 768  # enforced via output_dimensionality below

    async def get_embedding(self, text: str) -> list[float]:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        config = None
        if self.model not in self._NATIVE_768_MODELS:
            config = types.EmbedContentConfig(output_dimensionality=768)

        try:
            response = await self._client.aio.models.embed_content(
                model=self.model,
                contents=text,
                config=config,
            )
        except GeminiAPIError as e:
            raise RuntimeError(f"Gemini API error ({e.code}): {e.message}") from e
        except Exception as e:
            raise RuntimeError(f"Gemini embedding request failed: {e}") from e

        if not response.embeddings:
            raise RuntimeError("No embeddings returned from Gemini.")

        embedding = response.embeddings[0].values
        if embedding is None:
            raise RuntimeError("Gemini embedding values are missing.")

        # MRL-truncated outputs (anything != native model dim) need re-normalizing
        if self.model not in self._NATIVE_768_MODELS:
            vec = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embedding = vec.tolist()

        return embedding


class OllamaEmbeddingProvider:
    """Ollama local embeddings provider using the official Ollama SDK."""

    def __init__(self, base_url: str, model: str, dimension: int = 768) -> None:
        self.base_url = base_url
        self.model = model
        self._dimension = (
            dimension  # expected/enforced dimension, e.g. 768 for nomic-embed-text
        )
        self._client = AsyncOllamaClient(host=base_url)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def get_embedding(self, text: str) -> list[float]:
        try:
            response = await self._client.embed(model=self.model, input=text)
        except OllamaResponseError as e:
            raise RuntimeError(f"Ollama embedding request failed: {e}") from e

        embedding = response.embeddings[0]
        if len(embedding) != self._dimension:
            raise RuntimeError(
                f"Ollama model '{self.model}' returned a {len(embedding)}-dim vector, "
                f"but this provider is configured for {self._dimension} dims. "
                "Check AI_EMBEDDING_MODEL / your vector DB schema."
            )
        return list(embedding)


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to resolve the active embedding provider from settings."""
    settings = get_settings()
    provider_type = settings.AI_EMBEDDING_PROVIDER

    if provider_type == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            model=settings.AI_EMBEDDING_MODEL,
            dimension=768,
        )
    elif provider_type == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY.get_secret_value(),
            model=settings.AI_EMBEDDING_MODEL,
        )
    elif provider_type == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.AI_EMBEDDING_MODEL,
            dimension=768,
        )
    else:
        return MockEmbeddingProvider(dimension=768)


class EmbeddingGenerator:
    """Unified interface for generating text embeddings, hiding provider-specific configuration and naming."""

    def __init__(self) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        self.provider_name = settings.AI_EMBEDDING_PROVIDER
        self.model_name = settings.AI_EMBEDDING_MODEL
        self._provider = get_embedding_provider()

    async def generate(self, text: str) -> list[float]:
        """Generate an embedding for a single text chunk, enforcing the expected dimension."""
        embedding = await self._provider.get_embedding(text)
        if len(embedding) != self._provider.dimension:
            raise RuntimeError(
                f"Provider '{self.provider_name}' (model '{self.model_name}') returned a "
                f"{len(embedding)}-dim embedding, but {self._provider.dimension} dims were "
                "expected. This will not match your vector DB schema."
            )
        return embedding

    async def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings in parallel for a batch of text chunks."""
        import asyncio

        if not texts:
            return []
        return list(await asyncio.gather(*(self.generate(text) for text in texts)))


_generator: EmbeddingGenerator | None = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Return a cached singleton instance of the unified embedding generator."""
    global _generator
    if _generator is None:
        _generator = EmbeddingGenerator()
    return _generator
