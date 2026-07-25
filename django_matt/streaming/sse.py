"""Server-Sent Events (SSE) formatting and response construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

from django.http import StreamingHttpResponse

import orjson


@dataclass(slots=True)
class SSEEvent:
    """Data class representing a single Server-Sent Event."""

    data: str | bytes | dict[str, Any] | list[Any] | None = None
    event: str | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None


def format_sse_event(event: SSEEvent) -> bytes:
    """Serialize an SSEEvent into the wire-format bytes per the SSE specification."""
    lines: list[bytes] = []

    if event.comment is not None:
        for line in event.comment.split("\n"):
            lines.append(b": " + line.encode())

    if event.retry is not None:
        lines.append(b"retry: " + str(event.retry).encode())

    if event.id is not None:
        lines.append(b"id: " + event.id.encode())

    if event.event is not None:
        lines.append(b"event: " + event.event.encode())

    if event.data is not None:
        if isinstance(event.data, (dict, list)):
            raw = orjson.dumps(event.data).decode()
        elif isinstance(event.data, bytes):
            raw = event.data.decode()
        else:
            raw = event.data

        for line in raw.split("\n"):
            lines.append(b"data: " + line.encode())

    lines.append(b"")
    return b"\n".join(lines) + b"\n"


async def _sse_stream(
    generator: AsyncIterator[SSEEvent],
) -> AsyncIterator[bytes]:
    async for event in generator:
        yield format_sse_event(event)


def sse_response(
    generator: AsyncIterator[SSEEvent],
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse:
    """Create a text/event-stream StreamingHttpResponse from an async SSEEvent generator."""
    response_headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if headers:
        response_headers.update(headers)

    response = StreamingHttpResponse(
        streaming_content=_sse_stream(generator),
        status=status,
        content_type="text/event-stream",
    )
    for key, value in response_headers.items():
        response[key] = value

    return response
