"""
Django Matt Streaming - SSE and streaming response helpers.

Provides:
- Server-Sent Events (SSE) formatting and responses
- Generic streaming responses (binary, NDJSON, text)
- Decorators for controller methods
- Heartbeat helpers to prevent proxy/LB timeouts

Usage:
    from django_matt.streaming import sse_response, SSEEvent, event

    async def my_sse_view(request):
        async def generate():
            yield event("hello", event_type="greeting")
            yield event({"count": 1}, event_type="update")

        return sse_response(generate())
"""

from django_matt.streaming.decorators import sse_endpoint, streaming
from django_matt.streaming.helpers import event, heartbeat, with_heartbeat
from django_matt.streaming.response import stream_json, stream_response, stream_text
from django_matt.streaming.sse import SSEEvent, format_sse_event, sse_response

__all__ = [
    # SSE
    "SSEEvent",
    "format_sse_event",
    "sse_response",
    # Streaming responses
    "stream_response",
    "stream_json",
    "stream_text",
    # Decorators
    "sse_endpoint",
    "streaming",
    # Helpers
    "event",
    "heartbeat",
    "with_heartbeat",
]
