"""Unified LLM provider interface supporting Gemini, OpenAI, Ollama, and Mock providers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from google import genai
from google.genai import types
from ollama import AsyncClient as AsyncOllamaClient
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Exception raised when LLM response fails validation against the Pydantic schema."""

    pass


def clean_and_parse_json(text: str) -> Any:
    """Clean markdown wrappers and parse JSON string robustly, allowing raw control chars."""
    text_clean = text.strip()

    # 1. Strip markdown code block markers
    if text_clean.startswith("```"):
        first_newline = text_clean.find("\n")
        if first_newline != -1:
            text_clean = text_clean[first_newline:].strip()
        else:
            text_clean = text_clean[3:].strip()

        if text_clean.endswith("```"):
            text_clean = text_clean[:-3].strip()

    # 2. Try to parse directly (with strict=False to support unescaped newlines/tabs inside JSON strings)
    try:
        return json.loads(text_clean, strict=False)
    except json.JSONDecodeError:
        pass

    # 3. Locate first '{' and last '}'
    first_brace = text_clean.find("{")
    last_brace = text_clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text_clean[first_brace : last_brace + 1]
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError as e:
            raise e

    raise json.JSONDecodeError("Could not locate JSON object boundaries", text, 0)


def _resolve_target_model(
    requested_model: str | None, own_model: str, foreign_prefixes: tuple[str, ...]
) -> str:
    """Resolve the model to actually use, ignoring cross-provider model names.

    If `requested_model` looks like it belongs to a different provider (e.g. a
    "gpt-" name passed to the Gemini provider), fall back to this provider's
    own configured model instead of sending a foreign model name upstream.
    """
    target_model = requested_model or own_model
    if requested_model and any(p in requested_model.lower() for p in foreign_prefixes):
        target_model = own_model
    return target_model


class LLMProvider(Protocol):
    """Protocol defining the interface for all LLM providers."""

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        """Send a prompt to the LLM and return a validated Pydantic model response."""
        ...

    def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        """Stream the model's response token by token."""
        ...


class MockLLMProvider:
    """Mock LLM provider for testing and local offline development."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        logger.info("Mock LLM called with prompt length: %d", len(prompt))

        # Check for ReflectEvaluation
        if response_model.__name__ == "ReflectEvaluation":
            from app.modules.reflect.tasks import ReflectEvaluation

            return cast(T, ReflectEvaluation(enough_content="YES"))

        # Check for ReflectEntryGeneration
        if response_model.__name__ == "ReflectEntryGeneration":
            from app.modules.reflect.tasks import ReflectEntryGeneration

            return cast(
                T,
                ReflectEntryGeneration(
                    title="Mock Reflect Title",
                    content="This is a mock Reflect journal entry generated automatically.",
                ),
            )

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

    async def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        logger.info("Mock LLM stream called with prompt length: %d", len(prompt))
        text = "Mock response: Based on your journal entries, you have been working on various tasks and reflecting on your mood."
        import asyncio

        for word in text.split(" "):
            yield word + " "
            await asyncio.sleep(0.01)


class GeminiLLMProvider:
    """Google Gemini LLM provider using the official Google GenAI SDK."""

    _FOREIGN_PREFIXES = ("claude-", "gpt-")

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model.removeprefix("models/") if model else ""
        self._client = genai.Client(api_key=api_key)

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)
        target_model = target_model.removeprefix("models/")

        try:
            response = await self._client.aio.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                ),
            )
        except Exception as e:
            raise LLMValidationError(f"Gemini generation request failed: {e}") from e

        text_response = response.text
        if not text_response:
            raise LLMValidationError("Empty response from Gemini API.")

        try:
            parsed_json = clean_and_parse_json(text_response)
            return response_model.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "Gemini output validation failed. Raw response: %s", text_response
            )
            raise LLMValidationError(
                f"Validation against schema {response_model.__name__} failed: {e}"
            ) from e

    async def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)
        target_model = target_model.removeprefix("models/")

        response_stream = await self._client.aio.models.generate_content_stream(
            model=target_model,
            contents=prompt,
        )

        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text


class OpenAILLMProvider:
    """OpenAI LLM provider using the official OpenAI SDK."""

    _FOREIGN_PREFIXES = ("claude-", "gemini-")

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        try:
            response = await self._client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMValidationError(f"OpenAI generation request failed: {e}") from e

        try:
            text_response = response.choices[0].message.content
            if not text_response:
                raise LLMValidationError("Empty response from OpenAI API.")
        except (IndexError, AttributeError) as e:
            raise LLMValidationError(
                f"Invalid OpenAI API response structure: {response}"
            ) from e

        try:
            parsed_json = clean_and_parse_json(text_response)
            return response_model.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "OpenAI output validation failed. Raw response: %s", text_response
            )
            raise LLMValidationError(
                f"Validation against schema {response_model.__name__} failed: {e}"
            ) from e

    async def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        stream = await self._client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=1000,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content


class GrokLLMProvider:
    """xAI Grok LLM provider, using the official OpenAI SDK against xAI's OpenAI-compatible endpoint."""

    _FOREIGN_PREFIXES = ("claude-", "gpt-", "gemini-")
    _BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=self._BASE_URL)

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        if not self.api_key:
            raise ValueError("Grok (xAI) API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        try:
            response = await self._client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMValidationError(f"Grok generation request failed: {e}") from e

        try:
            text_response = response.choices[0].message.content
            if not text_response:
                raise LLMValidationError("Empty response from Grok API.")
        except (IndexError, AttributeError) as e:
            raise LLMValidationError(
                f"Invalid Grok API response structure: {response}"
            ) from e

        try:
            parsed_json = clean_and_parse_json(text_response)
            return response_model.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "Grok output validation failed. Raw response: %s", text_response
            )
            raise LLMValidationError(
                f"Validation against schema {response_model.__name__} failed: {e}"
            ) from e

    async def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("Grok (xAI) API key is missing.")

        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        stream = await self._client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=1000,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content


class OllamaLLMProvider:
    """Ollama local LLM provider using the official Ollama SDK."""

    _FOREIGN_PREFIXES = ("claude-", "gpt-", "gemini-")

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model
        self._client = AsyncOllamaClient(host=base_url)

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        try:
            response = await self._client.generate(
                model=target_model,
                prompt=prompt,
                format="json",
                stream=False,
            )
        except Exception as e:
            raise LLMValidationError(f"Ollama generation request failed: {e}") from e

        text_response = response.response
        if not text_response:
            raise LLMValidationError("Empty response from Ollama API.")

        try:
            parsed_json = clean_and_parse_json(text_response)
            return response_model.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(
                "Ollama output validation failed. Raw response: %s", text_response
            )
            raise LLMValidationError(
                f"Validation against schema {response_model.__name__} failed: {e}"
            ) from e

    async def stream(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        target_model = _resolve_target_model(model, self.model, self._FOREIGN_PREFIXES)

        stream = await self._client.generate(
            model=target_model,
            prompt=prompt,
            stream=True,
            options={"num_predict": 1000},
        )

        async for part in stream:
            text_response = part.response
            if text_response:
                yield text_response
