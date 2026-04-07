# Streaming & SSE Recipes

Server-Sent Events and streaming responses for real-time data delivery.

## Basic SSE Endpoint

```python
from django_matt.streaming import SSEEvent, event, sse_response


async def notifications_stream(request):
    async def generate():
        yield event("connected", event_type="status")
        # In practice, poll a queue or database
        while True:
            notification = await get_next_notification(request.user)
            yield event(
                {"id": notification.id, "message": notification.text},
                event_type="notification",
                id=str(notification.id),
            )

    return sse_response(generate())
```

## Streaming LLM/AI Responses

```python
from django_matt.streaming import event, sse_response


async def chat_completion(request):
    import orjson

    body = orjson.loads(request.body)
    prompt = body["prompt"]

    async def generate():
        yield event({"status": "started"}, event_type="meta")

        # Stream tokens from your LLM provider
        async for token in llm_client.stream(prompt):
            yield event(
                {"token": token.text, "finish_reason": token.finish_reason},
                event_type="token",
            )

        yield event({"status": "complete"}, event_type="meta")

    return sse_response(generate())
```

## Progress Bar Updates via SSE

```python
import asyncio

from django_matt.streaming import event, sse_response


async def export_data(request):
    async def generate():
        total = await Record.objects.acount()
        processed = 0

        yield event(
            {"total": total, "processed": 0, "percent": 0},
            event_type="progress",
        )

        async for batch in Record.objects.all().aiterator(chunk_size=100):
            processed += 1
            if processed % 100 == 0:
                percent = int((processed / total) * 100)
                yield event(
                    {"total": total, "processed": processed, "percent": percent},
                    event_type="progress",
                )
            await asyncio.sleep(0)  # yield control

        yield event(
            {"total": total, "processed": total, "percent": 100},
            event_type="complete",
        )

    return sse_response(generate())
```

## NDJSON Streaming for Bulk Data Export

```python
from django_matt.streaming import stream_json


async def export_users(request):
    async def generate():
        async for user in User.objects.all().aiterator(chunk_size=500):
            yield {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            }

    # Each line is a JSON object followed by \n
    # Content-Type: application/x-ndjson
    return stream_json(generate())
```

## Heartbeat Keepalive for Long Connections

```python
from django_matt.streaming import event, sse_response, with_heartbeat


async def live_feed(request):
    async def generate():
        async for update in poll_for_updates():
            yield event(
                {"type": update.type, "data": update.payload},
                event_type="update",
            )

    # Wraps the generator to emit `: heartbeat\n\n` comments every 15s
    # Prevents proxies/load balancers from closing idle connections
    return sse_response(with_heartbeat(generate(), interval=15))
```

## Client Reconnection Handling

```python
from django_matt.streaming import SSEEvent, event, sse_response


async def event_stream(request):
    # Client sends Last-Event-ID header on reconnect
    last_id = request.headers.get("Last-Event-ID")

    async def generate():
        # Set retry interval (milliseconds) for automatic reconnection
        yield SSEEvent(retry=3000, comment="reconnect after 3s")

        # Resume from where the client left off
        if last_id:
            events = EventLog.objects.filter(id__gt=last_id).order_by("id")
        else:
            events = EventLog.objects.order_by("-id")[:50]

        async for evt in events.aiterator():
            yield event(
                {"action": evt.action, "payload": evt.payload},
                event_type=evt.event_type,
                id=str(evt.id),  # client stores this for reconnection
            )

    return sse_response(generate())
```

## Streaming with Authentication

```python
from django.http import JsonResponse

from django_matt.auth import jwt_required
from django_matt.streaming import event, sse_response, with_heartbeat


@jwt_required
async def protected_stream(request):
    """SSE endpoint that requires JWT authentication.

    Client connects with:
        const es = new EventSource("/api/stream/", {
            headers: { "Authorization": "Bearer <token>" }
        });

    Or pass token as query param if EventSource doesn't support headers:
        /api/stream/?token=<jwt>
    """
    user = request.user

    async def generate():
        yield event(
            {"user_id": user.pk, "status": "connected"},
            event_type="auth",
        )

        async for notification in user_notification_stream(user.pk):
            yield event(
                notification.to_dict(),
                event_type="notification",
                id=str(notification.id),
            )

    return sse_response(with_heartbeat(generate(), interval=20))
```

## Streaming Plain Text

```python
from django_matt.streaming import stream_text


async def log_tail(request):
    """Stream log file contents as plain text."""

    async def generate():
        import asyncio
        from pathlib import Path

        log_path = Path("/var/log/app/output.log")
        last_pos = 0

        while True:
            content = log_path.read_text()
            if len(content) > last_pos:
                yield content[last_pos:]
                last_pos = len(content)
            await asyncio.sleep(1)

    return stream_text(generate())
```

## Using the @sse_endpoint Decorator

```python
from django_matt.streaming import SSEEvent, event, sse_endpoint


class DashboardController:

    @sse_endpoint
    async def live_metrics(self, request):
        """Decorator auto-wraps the generator in sse_response()."""
        import asyncio

        while True:
            stats = await get_dashboard_stats()
            yield event(stats, event_type="metrics")
            await asyncio.sleep(5)
```
