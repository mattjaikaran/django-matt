"""
Streaming utilities for LLM responses.

Provides helpers for streaming LLM responses with:
- Server-sent events formatting
- Token counting during stream
- Chunked response handling
- Django/ASGI integration
"""

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import orjson

from django_matt.ai.base import (
    LLMProvider,
    Message,
    StreamChunk,
)


@dataclass
class StreamStats:
    """Statistics for a streaming response."""

    start_time: float = 0.0
    end_time: float = 0.0
    first_token_time: float = 0.0
    chunk_count: int = 0
    total_chars: int = 0
    estimated_tokens: int = 0

    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        return self.end_time - self.start_time if self.end_time else 0.0

    @property
    def time_to_first_token(self) -> float:
        """Time to first token in seconds."""
        return self.first_token_time - self.start_time if self.first_token_time else 0.0

    @property
    def tokens_per_second(self) -> float:
        """Estimated tokens per second."""
        if self.duration == 0:
            return 0.0
        return self.estimated_tokens / self.duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_seconds": self.duration,
            "time_to_first_token_seconds": self.time_to_first_token,
            "chunk_count": self.chunk_count,
            "total_chars": self.total_chars,
            "estimated_tokens": self.estimated_tokens,
            "tokens_per_second": self.tokens_per_second,
        }


@dataclass
class StreamingConfig:
    """Configuration for streaming behavior."""

    # SSE formatting
    event_name: str = "message"
    include_stats: bool = False

    # Token estimation (rough approximation: 1 token ~= 4 chars)
    chars_per_token: float = 4.0

    # Callbacks
    on_start: Callable[[], None] | None = None
    on_chunk: Callable[[str], None] | None = None
    on_complete: Callable[[str, StreamStats], None] | None = None
    on_error: Callable[[Exception], None] | None = None


class StreamingLLM:
    """
    Wrapper for streaming LLM responses with utilities.

    Provides:
    - Server-sent events (SSE) formatting
    - Token counting during stream
    - Statistics collection
    - Django StreamingHttpResponse integration

    Usage:
        from django_matt.ai import StreamingLLM, get_provider

        provider = get_provider("openai")
        streaming = StreamingLLM(provider)

        # Basic streaming
        async for chunk in streaming.stream([Message.user("Hello!")]):
            print(chunk.content, end="", flush=True)

        # Get SSE formatted response for Django
        from django.http import StreamingHttpResponse

        async def chat_stream(request):
            messages = [Message.user(request.GET["prompt"])]
            return StreamingHttpResponse(
                streaming.stream_sse(messages),
                content_type="text/event-stream",
            )

        # With statistics
        streaming = StreamingLLM(provider, config=StreamingConfig(include_stats=True))
        full_response, stats = await streaming.stream_with_stats(messages)
        print(f"Tokens per second: {stats.tokens_per_second}")
    """

    def __init__(
        self,
        provider: LLMProvider,
        config: StreamingConfig | None = None,
    ):
        """
        Initialize streaming LLM.

        Args:
            provider: Base LLM provider
            config: Streaming configuration
        """
        self.provider = provider
        self.config = config or StreamingConfig()

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return int(len(text) / self.config.chars_per_token)

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion with optional callbacks.

        Yields StreamChunk objects as they arrive.
        """
        if self.config.on_start:
            self.config.on_start()

        try:
            async for chunk in self.provider.stream(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                if self.config.on_chunk and chunk.content:
                    self.config.on_chunk(chunk.content)
                yield chunk

        except Exception as e:
            if self.config.on_error:
                self.config.on_error(e)
            raise

    async def stream_text(
        self,
        messages: list[Message],
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream just the text content.

        Convenience method that yields only the text strings.
        """
        async for chunk in self.stream(messages, **kwargs):
            if chunk.content:
                yield chunk.content

    async def stream_sse(
        self,
        messages: list[Message],
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream as Server-Sent Events.

        Formats each chunk as an SSE event for use with EventSource.

        Usage:
            from django.http import StreamingHttpResponse

            async def stream_view(request):
                return StreamingHttpResponse(
                    streaming.stream_sse(messages),
                    content_type="text/event-stream",
                )
        """
        stats = StreamStats(start_time=time.time())

        try:
            async for chunk in self.stream(messages, **kwargs):
                if chunk.content:
                    if stats.first_token_time == 0:
                        stats.first_token_time = time.time()

                    stats.chunk_count += 1
                    stats.total_chars += len(chunk.content)

                    # Format as SSE
                    data = {"content": chunk.content, "done": False}
                    yield f"event: {self.config.event_name}\n"
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

                if chunk.finish_reason:
                    stats.end_time = time.time()
                    stats.estimated_tokens = self._estimate_tokens(
                        "".join([str(stats.total_chars)])
                    )

                    # Send completion event
                    data = {"content": "", "done": True}
                    if self.config.include_stats:
                        data["stats"] = stats.to_dict()
                    yield f"event: {self.config.event_name}\n"
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

        except Exception as e:
            # Send error event
            data = {"error": str(e), "done": True}
            yield "event: error\n"
            yield f"data: {orjson.dumps(data).decode()}\n\n"
            raise

    async def stream_json(
        self,
        messages: list[Message],
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream as newline-delimited JSON.

        Each chunk is a JSON object on its own line.
        """
        async for chunk in self.stream(messages, **kwargs):
            data = {
                "content": chunk.content,
                "finish_reason": chunk.finish_reason,
            }
            yield orjson.dumps(data).decode() + "\n"

    async def stream_with_stats(
        self,
        messages: list[Message],
        **kwargs,
    ) -> tuple[str, StreamStats]:
        """
        Stream and collect the full response with statistics.

        Returns:
            Tuple of (full_response_text, statistics)
        """
        stats = StreamStats(start_time=time.time())
        chunks = []

        async for chunk in self.stream(messages, **kwargs):
            if chunk.content:
                if stats.first_token_time == 0:
                    stats.first_token_time = time.time()

                stats.chunk_count += 1
                stats.total_chars += len(chunk.content)
                chunks.append(chunk.content)

            if chunk.finish_reason:
                stats.end_time = time.time()

        full_response = "".join(chunks)
        stats.estimated_tokens = self._estimate_tokens(full_response)

        if self.config.on_complete:
            self.config.on_complete(full_response, stats)

        return full_response, stats

    async def collect(
        self,
        messages: list[Message],
        **kwargs,
    ) -> str:
        """
        Stream and collect the full response.

        Convenience method that returns just the full text.
        """
        text, _ = await self.stream_with_stats(messages, **kwargs)
        return text

    @property
    def model(self) -> str:
        return self.provider.model

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name


class TokenCounter:
    """
    Token counter for streaming responses.

    Provides accurate token counting using tiktoken (if available)
    or estimation.

    Usage:
        counter = TokenCounter()

        async for chunk in provider.stream(messages):
            counter.add(chunk.content)
            print(f"Tokens so far: {counter.count}")

        print(f"Total tokens: {counter.count}")
    """

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize token counter.

        Args:
            model: Model name for accurate counting (uses tiktoken)
        """
        self.model = model
        self._count = 0
        self._text = ""
        self._encoder = None

        # Try to load tiktoken for accurate counting
        try:
            import tiktoken

            try:
                self._encoder = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            pass

    def add(self, text: str) -> int:
        """
        Add text and return updated token count.

        Args:
            text: Text to add

        Returns:
            Current total token count
        """
        if not text:
            return self._count

        self._text += text

        if self._encoder:
            self._count = len(self._encoder.encode(self._text))
        else:
            # Rough estimation: ~4 chars per token
            self._count = len(self._text) // 4

        return self._count

    @property
    def count(self) -> int:
        """Current token count."""
        return self._count

    @property
    def text(self) -> str:
        """Accumulated text."""
        return self._text

    def reset(self) -> None:
        """Reset counter."""
        self._count = 0
        self._text = ""


def create_sse_response(
    provider: LLMProvider,
    messages: list[Message],
    **kwargs,
) -> "StreamingHttpResponse":  # noqa: F821
    """
    Create a Django StreamingHttpResponse for SSE.

    Usage:
        from django_matt.ai.streaming import create_sse_response
        from django_matt.ai import get_provider

        async def chat_stream(request):
            provider = get_provider("openai")
            messages = [Message.user(request.GET["prompt"])]
            return create_sse_response(provider, messages)
    """
    try:
        from django.http import StreamingHttpResponse
    except ImportError:
        raise ImportError("Django is required for create_sse_response")

    streaming = StreamingLLM(provider)

    response = StreamingHttpResponse(
        streaming.stream_sse(messages, **kwargs),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"

    return response


__all__ = [
    "StreamStats",
    "StreamingConfig",
    "StreamingLLM",
    "TokenCounter",
    "create_sse_response",
]
