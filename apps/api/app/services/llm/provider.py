"""Unified LLM provider interface supporting Gemini, OpenAI, Ollama, and Mock providers."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Protocol, TypeVar, cast

import httpx
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Exception raised when LLM response fails validation against the Pydantic schema."""

    pass


class LLMProvider(Protocol):
    """Protocol defining the interface for all LLM providers."""

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        """Send a prompt to the LLM and return a validated Pydantic model response."""
        ...


class MockLLMProvider:
    """Mock LLM provider for testing and local offline development."""

    def __init__(self, model: str = "mock-llm") -> None:
        self.model = model

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        logger.info("Mock LLM called with prompt length: %d", len(prompt))

        # Check for SummaryOutput model (specific feature summary schema)
        if response_model.__name__ == "SummaryOutput":
            from app.modules.ai.schemas import SummaryOutput

            return cast(
                T,
                SummaryOutput(
                    content="Mock summary: This is a generated summary of your journal entries, indicating high focus and stable mood.",
                    highlights=[
                        "Worked on core features",
                        "Completed task roadmap",
                        "Had a good sleep",
                    ],
                    challenges=[
                        "Slightly tired in the evening",
                        "Felt minor block on auth configurations",
                    ],
                    themes=["productivity", "health", "focus"],
                    mood_analysis={
                        "average_intensity": 7.5,
                        "trend": "stable",
                        "breakdown": [
                            {"mood": "motivated", "count": 2},
                            {"mood": "tired", "count": 1},
                        ],
                    },
                ),
            )

        # General fallback if another model is used
        try:
            # Return an empty model instance if valid, or raise validation error
            return response_model.model_validate({})
        except ValidationError as e:
            raise LLMValidationError(
                f"Mock validation failed for model {response_model.__name__}: {e}"
            ) from e


class GeminiLLMProvider:
    """Google Gemini LLM provider using direct REST API calls."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            try:
                text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise LLMValidationError(
                    f"Invalid Gemini API response structure: {data}"
                ) from e

            try:
                parsed_json = json.loads(text_response)
                return response_model.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(
                    "Gemini output validation failed. Raw response: %s", text_response
                )
                raise LLMValidationError(
                    f"Validation against schema {response_model.__name__} failed: {e}"
                ) from e


class OpenAILLMProvider:
    """OpenAI LLM provider using direct REST API calls."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            try:
                text_response = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise LLMValidationError(
                    f"Invalid OpenAI API response structure: {data}"
                ) from e

            try:
                parsed_json = json.loads(text_response)
                return response_model.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(
                    "OpenAI output validation failed. Raw response: %s", text_response
                )
                raise LLMValidationError(
                    f"Validation against schema {response_model.__name__} failed: {e}"
                ) from e


class OllamaLLMProvider:
    """Ollama local LLM provider using direct REST API calls."""

    def __init__(self, base_url: str, model: str = "llama3.2") -> None:
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            try:
                text_response = data["response"]
            except KeyError as e:
                raise LLMValidationError(
                    f"Invalid Ollama response structure: {data}"
                ) from e

            try:
                parsed_json = json.loads(text_response)
                return response_model.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(
                    "Ollama output validation failed. Raw response: %s", text_response
                )
                raise LLMValidationError(
                    f"Validation against schema {response_model.__name__} failed: {e}"
                ) from e
