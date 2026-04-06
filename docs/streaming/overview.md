# Streaming

Django Matt provides first-class support for Server-Sent Events (SSE), NDJSON streaming, and plain text streaming. All streaming helpers return Django's `StreamingHttpResponse` with correct headers for proxy/load balancer compatibility.

## Quick Start

```python
from django_matt.streaming import sse_response, event

@api.get("/stream/updates")
async def stream_updates(request):
    async def generate():
        yield event("connected", event_type="status")
        async for update in watch_updates():
            yield event(update, event_type="update")

    return sse_response(generate())
```

## Server-Sent Events (SSE)

### SSEEvent

The `SSEEvent` dataclass represents a single SSE message, compliant with the [W3C SSE specification](https://html.spec.whatwg.org/multipage/server-sent-events.html).

```python
from django_matt.streaming import SSEEvent

SSEEvent(
    data="hello",           # str, bytes, dict, list, or None
    event="greeting",       # event type (maps to EventSource event name)
    id="msg-1",             # last-event-id for reconnection
    retry=3000,             # reconnection interval in ms
    comment="keep-alive",   # SSE comment (prefixed with :)
)
```

**Formatting rules:**
- `data` with dict/list values are JSON-serialized via orjson
- Multi-line data is split into separate `data:` lines per the spec
- Comments are prefixed with `: ` on each line
- Each event ends with a blank line (`\n\n`)

### event() Helper

Convenience factory for creating `SSEEvent` instances.

```python
from django_matt.streaming import event

event("hello")                                    # data-only
event({"count": 42}, event_type="counter")        # typed JSON event
event("reconnect", id="r-1", retry=5000)          # with reconnection hints
event(comment="ping")                             # comment-only (keepalive)
```

### sse_response()

Wraps an async generator of `SSEEvent` objects into a `StreamingHttpResponse` with correct SSE headers.

```python
from django_matt.streaming import sse_response

def sse_response(
    generator: AsyncIterator[SSEEvent],
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse
```

**Response headers set automatically:**
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`
- `X-Accel-Buffering: no` (disables nginx buffering)

### format_sse_event()

Low-level formatter that converts an `SSEEvent` to raw bytes. Useful when building custom streaming logic.

```python
from django_matt.streaming import format_sse_event, SSEEvent

raw = format_sse_event(SSEEvent(data="hello", event="greeting"))
# b'event: greeting\ndata: hello\n\n'
```

## NDJSON Streaming

`stream_json()` streams newline-delimited JSON objects. Each item from the async generator is serialized with orjson and terminated with `\n`.

```python
from django_matt.streaming import stream_json

@api.get("/stream/logs")
async def stream_logs(request):
    async def generate():
        async for log in tail_logs():
            yield {"ts": log.timestamp, "msg": log.message, "level": log.level}

    return stream_json(generate())
```

Response content type: `application/x-ndjson`.

## Plain Text Streaming

`stream_text()` streams string or bytes chunks as `text/plain; charset=utf-8`.

```python
from django_matt.streaming import stream_text

@api.get("/stream/ai")
async def stream_ai(request):
    async def generate():
        async for token in llm.stream("Explain Django signals"):
            yield token

    return stream_text(generate())
```

## Generic Binary Streaming

`stream_response()` is the base streaming primitive. `stream_json` and `stream_text` are built on top of it.

```python
from django_matt.streaming import stream_response

stream_response(
    generator: AsyncIterator[bytes],
    *,
    content_type: str = "application/octet-stream",
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingHttpResponse
```

All streaming responses include `Cache-Control: no-cache` and `X-Accel-Buffering: no`.

## Decorators

### @sse_endpoint

Wraps a function that returns an async generator of `SSEEvent` objects. The decorator handles calling `sse_response()`.

```python
from django_matt.streaming import sse_endpoint

@api.get("/notifications")
@sse_endpoint
async def notifications(request):
    async for notification in user_notifications(request.user):
        yield event(notification.to_dict(), event_type="notification", id=str(notification.id))
```

The decorated function gets `_is_sse_endpoint = True` for introspection.

### @streaming(content_type)

Wraps a function that returns an async generator of bytes. Calls `stream_response()` with the given content type.

```python
from django_matt.streaming import streaming

@api.get("/export/csv")
@streaming(content_type="text/csv")
async def export_csv(request):
    yield b"id,name,email\n"
    async for user in User.objects.all().aiterator():
        yield f"{user.id},{user.name},{user.email}\n".encode()
```

The decorated function gets `_is_streaming_endpoint = True` for introspection.

## Heartbeat Helpers

Proxies and load balancers often close idle connections. Heartbeat helpers prevent this by sending periodic SSE comments that are invisible to `EventSource` clients.

### heartbeat()

Standalone async generator that yields SSE comment events at a fixed interval. Useful for merging into your own stream logic.

```python
from django_matt.streaming import heartbeat

# Yields SSEEvent(comment="heartbeat") every 15 seconds
async for hb in heartbeat(interval=15):
    ...
```

### with_heartbeat()

Wraps an existing SSE generator, interleaving heartbeat comments between real events. Uses `asyncio.Queue` internally to multiplex the data generator and heartbeat timer.

```python
from django_matt.streaming import sse_response, event, with_heartbeat

@api.get("/stream/live")
async def live_feed(request):
    async def generate():
        async for item in watch_feed():
            yield event(item, event_type="item")

    return sse_response(with_heartbeat(generate(), interval=10))
```

The heartbeat task is properly cancelled when the generator completes or the client disconnects.

## Usage with AI/LLM Streaming

SSE is the standard transport for streaming LLM responses. Here is a typical pattern:

```python
from django_matt.streaming import sse_response, event, with_heartbeat

@api.post("/ai/chat")
@jwt_required
async def chat(request, data: ChatRequest):
    async def generate():
        yield event({"status": "thinking"}, event_type="status")

        async for chunk in llm.stream_chat(data.messages):
            yield event({"content": chunk.text}, event_type="token")

        yield event({"status": "done"}, event_type="status")

    # 30s heartbeat keeps connection alive during slow generation
    return sse_response(with_heartbeat(generate(), interval=30))
```

**Frontend consumption:**

```typescript
const source = new EventSource("/api/ai/chat");

source.addEventListener("token", (e) => {
  const { content } = JSON.parse(e.data);
  appendToChat(content);
});

source.addEventListener("status", (e) => {
  const { status } = JSON.parse(e.data);
  if (status === "done") source.close();
});
```

## Best Practices

1. **Always use `with_heartbeat()`** for long-lived SSE connections to prevent proxy timeouts
2. **Set `X-Accel-Buffering: no`** -- already done automatically, but verify your reverse proxy respects it
3. **Use event types** (`event_type` parameter) so clients can listen selectively via `addEventListener`
4. **Include `id` fields** on events that support reconnection so `EventSource` can resume with `Last-Event-ID`
5. **Prefer `stream_json()`** over manual NDJSON formatting -- it handles orjson serialization and correct content type
6. **Clean up resources** -- async generators are finalized when the client disconnects; use `try/finally` for cleanup
