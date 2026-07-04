"""Unified LLM provider interface supporting Gemini, OpenAI, Ollama, and Mock providers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

import httpx
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
    """Google Gemini LLM provider using direct REST API calls."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        if not self.api_key:
            raise ValueError("Gemini API key is missing.")

        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gpt-"]):
            target_model = self.model

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"
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

        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gpt-"]):
            target_model = self.model

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:streamGenerateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 1000},
        }

        async with (
            httpx.AsyncClient(timeout=30.0) as client,
            client.stream("POST", url, json=payload) as response,
        ):
            response.raise_for_status()
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while True:
                    start_idx = buffer.find("{")
                    if start_idx == -1:
                        break
                    depth = 0
                    end_idx = -1
                    for i in range(start_idx, len(buffer)):
                        if buffer[i] == "{":
                            depth += 1
                        elif buffer[i] == "}":
                            depth -= 1
                            if depth == 0:
                                end_idx = i
                                break
                    if end_idx == -1:
                        break

                    obj_str = buffer[start_idx : end_idx + 1]
                    buffer = buffer[end_idx + 1 :]
                    try:
                        data = json.loads(obj_str)
                        text_part = data["candidates"][0]["content"]["parts"][0]["text"]
                        if text_part:
                            yield text_part
                    except (KeyError, IndexError, json.JSONDecodeError):
                        continue


class OpenAILLMProvider:
    """OpenAI LLM provider using direct REST API calls."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing.")

        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gemini-"]):
            target_model = self.model

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": target_model,
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

        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gemini-"]):
            target_model = self.model

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": 1000,
        }

        async with (
            httpx.AsyncClient(timeout=30.0) as client,
            client.stream("POST", url, headers=headers, json=payload) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[len("data: ") :].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data_json = json.loads(data_str)
                        choice = data_json.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except Exception:
                        continue


class OllamaLLMProvider:
    """Ollama local LLM provider using direct REST API calls."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    async def generate(
        self, prompt: str, response_model: type[T], model: str | None = None
    ) -> T:
        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gpt-", "gemini-"]):
            target_model = self.model

        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": target_model,
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
        target_model = model or self.model
        if model and any(p in model.lower() for p in ["claude-", "gpt-", "gemini-"]):
            target_model = self.model

        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
            "options": {"num_predict": 1000},
        }

        async with (
            httpx.AsyncClient(timeout=60.0) as client,
            client.stream("POST", url, json=payload) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    text_response = data.get("response", "")
                    if text_response:
                        yield text_response
                except json.JSONDecodeError:
                    continue
