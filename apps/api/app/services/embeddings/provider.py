"""Embedding providers implementation."""

from __future__ import annotations

import random
from typing import Protocol

import httpx

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
    """OpenAI embeddings provider using direct API calls."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model = model

    @property
    def dimension(self) -> int:
        # text-embedding-3-small and text-embedding-ada-002 are 1536-dimensional
        return 1536

    async def get_embedding(self, text: str) -> list[float]:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "input": text,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]


class GeminiEmbeddingProvider:
    """Gemini embeddings provider using direct API calls."""

    def __init__(self, api_key: str, model: str = "models/text-embedding-004") -> None:
        self.api_key = api_key
        self.model = model

    @property
    def dimension(self) -> int:
        # text-embedding-004 has 768 dimensions
        return 768

    async def get_embedding(self, text: str) -> list[float]:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent?key={self.api_key}"
        payload = {"content": {"parts": [{"text": text}]}}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["embedding"]["values"]


class OllamaEmbeddingProvider:
    """Ollama local embeddings provider using direct API calls."""

    def __init__(self, base_url: str, model: str = "nomic-embed-text") -> None:
        self.base_url = base_url
        self.model = model
        self._dimension = 768  # default to 768 for nomic-embed-text

    @property
    def dimension(self) -> int:
        return self._dimension

    async def get_embedding(self, text: str) -> list[float]:
        url = f"{self.base_url.rstrip('/')}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["embedding"]
            self._dimension = len(embedding)
            return embedding


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to resolve the active embedding provider from settings."""
    settings = get_settings()
    provider_type = settings.AI_EMBEDDING_PROVIDER

    if provider_type == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY.get_secret_value(),
            model=settings.AI_EMBEDDING_MODEL,
        )
    elif provider_type == "gemini":
        model = settings.AI_EMBEDDING_MODEL
        if "/" not in model:
            # Prefix with models/ if not present
            model = f"models/{model}"
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY.get_secret_value(),
            model=model,
        )
    elif provider_type == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.AI_EMBEDDING_MODEL,
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
        """Generate an embedding for a single text chunk."""
        return await self._provider.get_embedding(text)

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
