# Add Real-Time Features

Add WebSocket consumers, Server-Sent Events (SSE), an async event bus,
push notifications, and presence indicators to a Django Matt application.

## Prerequisites

- Completed [Build a REST API](build-a-rest-api.md) tutorial
- Redis running locally (for WebSocket channel layers and event bus)
- For WebSockets: `uv add channels channels-redis`

## 1. WebSocket Setup

### Install and configure

```bash
uv add channels channels-redis
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_matt",
    "django_matt.websockets",
]

DJANGO_MATT_WEBSOCKETS = {
    "ENABLED": True,
    "AUTH_REQUIRED": False,
    "HEARTBEAT_INTERVAL": 30,
    "RATE_LIMIT": {
        "ENABLED": True,
        "MESSAGES_PER_SECOND": 10,
    },
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

### Create a consumer

Django Matt provides `BaseConsumer`, `JsonConsumer`, and `RoomConsumer`
base classes. `RoomConsumer` adds automatic group management:

```python
# chat/consumers.py
from django_matt.websockets import RoomConsumer


class ChatConsumer(RoomConsumer):
    """
    WebSocket consumer for a chat room.

    Connect: ws://localhost:8000/ws/chat/<room_name>/
    """

    async def handle_chat_message(self, data: dict):
        """Handle incoming chat messages and broadcast to room."""
        await self.broadcast_to_room({
            "type": "chat_message",
            "user": self.user.username if self.user.is_authenticated else "anonymous",
            "message": data.get("message", ""),
        })

    async def handle_typing(self, data: dict):
        """Broadcast typing indicators."""
        await self.broadcast_to_room({
            "type": "typing",
            "user": self.user.username,
            "is_typing": data.get("is_typing", False),
        })
```

### Configure routing

```python
# chat/routing.py
from django_matt.websockets import WebSocketRouter

router = WebSocketRouter()
router.route("ws/chat/<str:room_name>/", ChatConsumer)
```

### Wire into ASGI

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django_matt.websockets import create_asgi_application
from chat.routing import router

application = create_asgi_application(router)
```

### Connect from a client

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/chat/general/");

ws.onopen = () => {
    ws.send(JSON.stringify({
        type: "chat_message",
        message: "Hello everyone!"
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`${data.user}: ${data.message}`);
};
```

## 2. Server-Sent Events (SSE)

SSE is simpler than WebSockets for server-to-client streaming. Django
Matt provides `sse_response()`, the `event()` helper, and the
`@sse_endpoint` decorator.

### Basic SSE endpoint

```python
# notifications/controllers.py
from django_matt import APIController
from django_matt.streaming import sse_response, event, SSEEvent
from .api import api


@api.controller("/stream", tags=["Streaming"])
class StreamController(APIController):

    @api.get("/notifications")
    async def notification_stream(self, request):
        """SSE stream of user notifications."""

        async def generate():
            # Send initial connection event
            yield event(
                {"status": "connected"},
                event_type="connection",
            )

            # Poll for new notifications (in production, use event bus)
            import asyncio
            while True:
                notifications = await self._get_pending(request.user)
                for n in notifications:
                    yield event(
                        {"id": n.id, "message": n.message, "type": n.notification_type},
                        event_type="notification",
                        id=str(n.id),
                    )
                await asyncio.sleep(2)

        return sse_response(generate())

    async def _get_pending(self, user):
        # Fetch unread notifications
        from django_matt.notifications import Notification
        return [
            n async for n in Notification.objects.filter(
                recipient=user, read_at__isnull=True
            ).order_by("-created_at")[:10]
        ]
```

### Using the decorator

The `@sse_endpoint` decorator wraps the return value in `sse_response()`
automatically:

```python
from django_matt.streaming import sse_endpoint, event

@api.get("/events")
@sse_endpoint
async def event_stream(request):
    import asyncio
    for i in range(100):
        yield event({"count": i}, event_type="tick")
        await asyncio.sleep(1)
```

### SSEEvent dataclass

```python
from django_matt.streaming import SSEEvent

# Full control over SSE fields
SSEEvent(
    data={"key": "value"},   # auto-serialized with orjson if dict/list
    event="update",          # SSE event type
    id="msg-42",             # Last-Event-ID for reconnection
    retry=5000,              # Client retry interval (ms)
    comment="keepalive",     # SSE comment line
)
```

### Heartbeat to prevent timeouts

```python
from django_matt.streaming import sse_response, event, with_heartbeat

@api.get("/live")
async def live_feed(self, request):
    async def generate():
        import asyncio
        while True:
            data = await get_latest_data()
            yield event(data, event_type="update")
            await asyncio.sleep(5)

    # with_heartbeat sends a comment every 15s to keep the connection alive
    return sse_response(with_heartbeat(generate(), interval=15))
```

### Connect from a client

```javascript
const source = new EventSource("/api/stream/notifications");

source.addEventListener("notification", (e) => {
    const data = JSON.parse(e.data);
    showToast(data.message);
});

source.addEventListener("connection", (e) => {
    console.log("Connected to notification stream");
});

source.onerror = () => {
    console.log("SSE connection lost, reconnecting...");
};
```

## 3. Event Bus

The async event bus decouples producers from consumers. Handlers run
concurrently via `asyncio.gather`.

### Setup

```python
from django_matt.events import EventBus, Event, get_event_bus, on
```

### Define events

Events are Pydantic models:

```python
# core/events.py
from django_matt.events import Event


class PostPublished(Event):
    __event_type__ = "post.published"
    post_id: str
    author_id: int
    title: str


class UserSignedUp(Event):
    __event_type__ = "user.signed_up"
    user_id: int
    email: str
```

### Subscribe with the `@on` decorator

```python
# core/handlers.py
from django_matt.events import on
from .events import PostPublished, UserSignedUp


@on("post.published")
async def send_post_notification(event: PostPublished):
    """Notify followers when a post is published."""
    from django_matt.notifications import NotificationService

    service = NotificationService()
    await service.send(
        recipient_id=event.author_id,
        message=f"Your post '{event.title}' is now live!",
        notification_type="post_published",
    )


@on("user.signed_up")
async def send_welcome_email(event: UserSignedUp):
    """Send welcome email to new users."""
    from django_matt.email import send_email
    await send_email(
        to=event.email,
        template="welcome",
        context={"user_id": event.user_id},
    )


@on("user.*")
async def log_user_events(event):
    """Wildcard handler -- log all user events."""
    import logging
    logging.getLogger("audit").info(
        f"User event: {event.event_type}",
        extra=event.metadata,
    )
```

### Emit events

```python
from django_matt.events import get_event_bus
from core.events import PostPublished

bus = get_event_bus()
await bus.emit(PostPublished(
    post_id=str(post.id),
    author_id=post.author_id,
    title=post.title,
))
```

### Redis backend for distributed events

```python
from django_matt.events import get_event_bus, RedisBackend

bus = get_event_bus()
bus.backend = RedisBackend(redis_url="redis://localhost:6379/0")
```

### Auto-discover handlers

Load `events.py` from all installed apps at startup:

```python
# config/apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from django_matt.events import autodiscover
        autodiscover()
```

## 4. Notifications

Django Matt ships a full notification system with multiple delivery
channels.

### Models

- `Notification` -- the notification record
- `NotificationDelivery` -- tracks delivery per channel
- `NotificationPreferences` -- per-user channel preferences
- `NotificationRule` -- routing rules

### Channels

```python
from django_matt.notifications import NotificationChannel

# Available channels:
#   NotificationChannel.IN_APP
#   NotificationChannel.EMAIL
#   NotificationChannel.PUSH     (FCM/APNs)
#   NotificationChannel.SMS
```

### Send a notification

```python
from django_matt.notifications import NotificationService, NotificationChannel

service = NotificationService()

await service.send(
    recipient=user,
    title="New comment on your post",
    message="Alice commented on 'Hello World'",
    notification_type="comment",
    channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
    data={"post_id": str(post.id), "comment_id": str(comment.id)},
)
```

### In-app notification controller

```python
# notifications/controllers.py
from django_matt import APIController
from django_matt.auth import jwt_required
from django_matt.notifications import Notification
from .api import api


@api.controller("/notifications", tags=["Notifications"])
class NotificationController(APIController):

    @api.get("/")
    @jwt_required
    async def list_notifications(self, request):
        notifications = []
        async for n in Notification.objects.filter(
            recipient=request.user
        ).order_by("-created_at")[:50]:
            notifications.append({
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "read": n.read_at is not None,
                "created_at": n.created_at.isoformat(),
            })
        return {"items": notifications}

    @api.post("/{notification_id}/read")
    @jwt_required
    async def mark_read(self, request, notification_id: str):
        from django.utils import timezone
        n = await Notification.objects.aget(
            id=notification_id, recipient=request.user
        )
        n.read_at = timezone.now()
        await n.asave(update_fields=["read_at"])
        return {"success": True}
```

## 5. Presence and Typing Indicators

Build on `RoomConsumer` to track who is online:

```python
# chat/consumers.py
from django_matt.websockets import RoomConsumer


class PresenceConsumer(RoomConsumer):
    """Tracks online users in a room."""

    # In-memory store (use Redis in production)
    _online_users: dict[str, set[str]] = {}

    async def websocket_connect(self, message):
        await super().websocket_connect(message)

        room = self.room_name
        user = self.user.username
        self._online_users.setdefault(room, set()).add(user)

        await self.broadcast_to_room({
            "type": "presence_update",
            "online": list(self._online_users[room]),
            "event": "join",
            "user": user,
        })

    async def websocket_disconnect(self, message):
        room = self.room_name
        user = self.user.username
        self._online_users.get(room, set()).discard(user)

        await self.broadcast_to_room({
            "type": "presence_update",
            "online": list(self._online_users.get(room, set())),
            "event": "leave",
            "user": user,
        })
        await super().websocket_disconnect(message)

    async def handle_typing(self, data: dict):
        await self.broadcast_to_room({
            "type": "typing_indicator",
            "user": self.user.username,
            "is_typing": data.get("is_typing", False),
        })
```

### Client-side typing detection

```javascript
let typingTimeout;

input.addEventListener("input", () => {
    ws.send(JSON.stringify({ type: "typing", is_typing: true }));

    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        ws.send(JSON.stringify({ type: "typing", is_typing: false }));
    }, 2000);
});

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "typing_indicator") {
        updateTypingUI(data.user, data.is_typing);
    }
    if (data.type === "presence_update") {
        updateOnlineList(data.online);
    }
};
```

## 6. Complete Architecture

```
Client (Browser/Mobile)
  |
  |--- HTTP ---------> DjangoMattAPI (Controllers/ViewSets)
  |                         |
  |                         |--> EventBus.emit(PostPublished(...))
  |                         |        |
  |                         |        |--> @on handler -> NotificationService
  |                         |        |--> @on handler -> Analytics
  |                         |        |--> @on handler -> WebSocket broadcast
  |                         |
  |--- SSE ----------> StreamController (sse_response)
  |
  |--- WebSocket ----> ChatConsumer (RoomConsumer)
                            |
                            |--> Channel Layer (Redis)
                            |--> Presence tracking
```

## 7. Complete Code Listing

```python
# settings.py (additions)
INSTALLED_APPS = [
    # ...
    "django_matt",
    "django_matt.websockets",
]

DJANGO_MATT_WEBSOCKETS = {
    "ENABLED": True,
    "AUTH_REQUIRED": False,
    "HEARTBEAT_INTERVAL": 30,
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}
```

```python
# core/events.py
from django_matt.events import Event


class PostPublished(Event):
    __event_type__ = "post.published"
    post_id: str
    author_id: int
    title: str
```

```python
# core/handlers.py
from django_matt.events import on


@on("post.published")
async def notify_post_published(event):
    from django_matt.notifications import NotificationService
    service = NotificationService()
    await service.send(
        recipient_id=event.author_id,
        message=f"Your post '{event.title}' is live!",
        notification_type="post_published",
    )
```

```python
# chat/consumers.py
from django_matt.websockets import RoomConsumer


class ChatConsumer(RoomConsumer):
    async def handle_chat_message(self, data: dict):
        await self.broadcast_to_room({
            "type": "chat_message",
            "user": self.user.username,
            "message": data.get("message", ""),
        })
```

```python
# chat/routing.py
from django_matt.websockets import WebSocketRouter
from chat.consumers import ChatConsumer

router = WebSocketRouter()
router.route("ws/chat/<str:room_name>/", ChatConsumer)
```

```python
# stream/controllers.py
from django_matt import APIController
from django_matt.streaming import sse_response, event, with_heartbeat
from .api import api


@api.controller("/stream", tags=["Streaming"])
class StreamController(APIController):

    @api.get("/events")
    async def event_stream(self, request):
        async def generate():
            import asyncio
            yield event({"status": "connected"}, event_type="connection")
            while True:
                data = await self._poll()
                if data:
                    yield event(data, event_type="update")
                await asyncio.sleep(2)

        return sse_response(with_heartbeat(generate(), interval=15))

    async def _poll(self):
        return None  # replace with real data source
```

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django_matt.websockets import create_asgi_application
from chat.routing import router

application = create_asgi_application(router)
```

## Next Steps

- [Build an AI/LLM Streaming API](ai-streaming-api.md) -- SSE for LLM token streaming
- [Build a Multi-Tenant SaaS API](build-a-saas-app.md) -- add organizations and billing
- [Testing Your Django Matt App](testing-guide.md) -- test WebSocket consumers and SSE
