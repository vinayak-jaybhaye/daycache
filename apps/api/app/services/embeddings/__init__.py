"""Embeddings service provider exports."""

from __future__ import annotations

from app.services.embeddings.provider import EmbeddingGenerator, get_embedding_generator

__all__ = ["EmbeddingGenerator", "get_embedding_generator"]
