"""
Test utilities for AI-powered code.

Provides FakeProvider and FakeEmbeddingProvider for deterministic testing
of agent and LLM-powered features without real API calls.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    EmbeddingProvider,
    EmbeddingResponse,
    LLMProvider,
    Message,
    StreamChunk,
    StructuredOutputProvider,
    ToolDefinition,
    Usage,
)


class FakeProvider(LLMProvider, StructuredOutputProvider):
    """
    Deterministic LLM provider for testing.

    Usage:
        provider = FakeProvider(responses=["Hello!", "How can I help?"])
        response = await provider.complete([Message.user("Hi")])
        assert response.content == "Hello!"

        # With tool calls
        provider = FakeProvider(responses=[
            CompletionResponse(content="", tool_calls=[ToolCall(...)]),
            "Final answer",
        ])

        # Assertions
        provider.assert_called()
        provider.assert_call_count(2)
        provider.assert_called_with_message("Hi")
    """

    def __init__(
        self,
        responses: list[str | CompletionResponse] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._responses = responses or ["OK"]
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []

    @property
    def default_model(self) -> str:
        return "fake-model"

    @property
    def provider_name(self) -> str:
        return "fake"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
                "kwargs": kwargs,
            }
        )

        response_item = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1

        if isinstance(response_item, CompletionResponse):
            return response_item

        # Estimate tokens from content length
        total_chars = sum(len(m.content) for m in messages) + len(response_item)
        est_tokens = max(total_chars // 4, 1)

        return CompletionResponse(
            content=response_item,
            model=model or self.default_model,
            finish_reason="stop",
            usage=Usage(
                prompt_tokens=est_tokens // 2,
                completion_tokens=est_tokens // 2,
                total_tokens=est_tokens,
            ),
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        response = await self.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        # Yield content word by word
        words = response.content.split(" ") if response.content else [""]
        for i, word in enumerate(words):
            suffix = " " if i < len(words) - 1 else ""
            yield StreamChunk(content=word + suffix)
        yield StreamChunk(finish_reason="stop")

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> BaseModel:
        response = await self.complete(
            messages,
            model=model,
            temperature=temperature,
            **kwargs,
        )
        return response_model.model_validate_json(response.content)

    # ---- Assertion helpers ----

    def assert_called(self) -> None:
        """Assert the provider was called at least once."""
        assert len(self.calls) > 0, "FakeProvider was never called"

    def assert_not_called(self) -> None:
        """Assert the provider was never called."""
        assert len(self.calls) == 0, f"FakeProvider was called {len(self.calls)} time(s)"

    def assert_call_count(self, expected: int) -> None:
        """Assert the provider was called exactly N times."""
        actual = len(self.calls)
        assert actual == expected, f"Expected {expected} calls, got {actual}"

    def assert_called_with_message(self, content: str) -> None:
        """Assert any call included a message with the given content."""
        for call in self.calls:
            for msg in call["messages"]:
                if msg.content == content:
                    return
        raise AssertionError(f"No call contained message with content: {content!r}")

    def reset(self) -> None:
        """Reset call history and response index."""
        self.calls.clear()
        self._call_index = 0


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic embedding provider for testing.

    Generates consistent, hash-based embeddings so the same input
    always produces the same vector. Different inputs produce different vectors.
    """

    def __init__(self, dimensions: int = 384, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._dimensions = dimensions

    @property
    def default_model(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        embeddings = [self._hash_to_vector(text) for text in texts]
        return EmbeddingResponse(
            embeddings=embeddings,
            model=model or self.default_model,
            usage=Usage(
                prompt_tokens=sum(len(t) // 4 for t in texts),
                completion_tokens=0,
                total_tokens=sum(len(t) // 4 for t in texts),
            ),
        )

    def _hash_to_vector(self, text: str) -> list[float]:
        """Generate a deterministic vector from text using SHA-256."""
        h = hashlib.sha256(text.encode()).digest()
        extended = h * ((self._dimensions * 4 // len(h)) + 1)
        floats = []
        for i in range(self._dimensions):
            raw = struct.unpack("f", extended[i * 4 : (i + 1) * 4])[0]
            floats.append(max(-1.0, min(1.0, raw % 2 - 1)))
        return floats


__all__ = [
    "FakeEmbeddingProvider",
    "FakeProvider",
]
