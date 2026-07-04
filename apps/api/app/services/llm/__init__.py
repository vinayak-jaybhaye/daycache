"""Llm service package."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.provider import (
    GeminiLLMProvider,
    GrokLLMProvider,
    LLMProvider,
    MockLLMProvider,
    OllamaLLMProvider,
    OpenAILLMProvider,
)


def get_llm_provider() -> LLMProvider:
    """Factory to resolve the active LLM provider from settings."""
    settings = get_settings()
    provider_type = settings.AI_LLM_PROVIDER

    if provider_type == "openai":
        return OpenAILLMProvider(
            api_key=settings.AI_LLM_API_KEY.get_secret_value(),
            model=settings.AI_LLM_MODEL,
        )
    elif provider_type == "gemini":
        return GeminiLLMProvider(
            api_key=settings.AI_LLM_API_KEY.get_secret_value(),
            model=settings.AI_LLM_MODEL,
        )
    elif provider_type == "ollama":
        return OllamaLLMProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.AI_LLM_MODEL,
        )
    elif provider_type in ("grok", "xai"):
        return GrokLLMProvider(
            api_key=settings.AI_LLM_API_KEY.get_secret_value(),
            model=settings.AI_LLM_MODEL,
        )
    else:
        return MockLLMProvider(model=settings.AI_LLM_MODEL)
