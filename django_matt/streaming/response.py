"""Streaming HTTP response factories for binary, NDJSON, and text content."""

from __future__ import annotations

from typing import Any, AsyncIterator

from django.http import StreamingHttpResponse

import orjson


async def _encode_ndjson(generator: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    async for item in generator:
        yield orjson.dumps(item) + b"\n"


async def _encode_text(generator: AsyncIterator[str | bytes]) -> AsyncIterator[bytes]:
    async for chunk in generator:
        if isinstance(chunk, str):
            yield chunk.encode()
        else:
            yield chunk


def stream_response(
    generator: AsyncIterator[bytes],
    *,
    content_type: str = "application/octet-stream",
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse:
    """Create a StreamingHttpResponse from an async byte generator."""
    response = StreamingHttpResponse(
        streaming_content=generator,
        status=status,
        content_type=content_type,
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def stream_json(
    generator: AsyncIterator[Any],
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse:
    """Create an NDJSON streaming response from an async generator of serializable objects."""
    return stream_response(
        _encode_ndjson(generator),
        content_type="application/x-ndjson",
        status=status,
        headers=headers,
    )


def stream_text(
    generator: AsyncIterator[str | bytes],
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse:
    """Create a text/plain streaming response from an async string generator."""
    return stream_response(
        _encode_text(generator),
        content_type="text/plain; charset=utf-8",
        status=status,
        headers=headers,
    )
