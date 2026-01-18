# WebSockets

Real-time communication with Django Channels.

## Configuration

```python
# settings.py
INSTALLED_APPS = [
    "channels",
    "django_matt",
    ...
]

ASGI_APPLICATION = "myproject.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("localhost", 6379)],
        },
    },
}
```

## Consumer Classes

### BaseConsumer

```python
from django_matt.websockets import BaseConsumer

class MyConsumer(BaseConsumer):
    async def connect(self):
        await self.accept()
        await self.send_json({"message": "Connected"})

    async def receive_json(self, content):
        # Handle message
        await self.send_json({"echo": content})

    async def disconnect(self, code):
        pass
```

### JsonConsumer

JSON message handling:

```python
from django_matt.websockets import JsonConsumer

class ChatConsumer(JsonConsumer):
    async def receive_json(self, content):
        message = content.get("message")
        await self.send_json({
            "type": "message",
            "message": message,
        })
```

### AuthenticatedConsumer

Requires authentication:

```python
from django_matt.websockets import AuthenticatedConsumer

class PrivateConsumer(AuthenticatedConsumer):
    async def connect(self):
        if self.user.is_authenticated:
            await self.accept()
        else:
            await self.close()

    async def receive_json(self, content):
        # self.user is available
        ...
```

### RoomConsumer

Room-based messaging:

```python
from django_matt.websockets import RoomConsumer

class ChatRoomConsumer(RoomConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        await self.join_room(self.room_name)
        await self.accept()

    async def receive_json(self, content):
        await self.room_send(self.room_name, {
            "type": "chat.message",
            "message": content["message"],
            "user": self.user.username,
        })

    async def chat_message(self, event):
        await self.send_json(event)
```

## Authentication Middleware

### JWT Authentication

```python
from django_matt.websockets import JWTAuthMiddleware, AuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        JWTAuthMiddleware(
            URLRouter([
                path("ws/chat/", ChatConsumer.as_asgi()),
            ])
        )
    ),
})
```

### Session Authentication

```python
from django_matt.websockets import SessionAuthMiddleware

application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        SessionAuthMiddleware(
            URLRouter([...])
        )
    ),
})
```

## Routing

```python
from django_matt.websockets import WebSocketRouter

router = WebSocketRouter()

router.route("chat/<room_name>/", ChatConsumer)
router.route("notifications/", NotificationConsumer)

# In asgi.py
application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        URLRouter(router.urls)
    ),
})
```

## Broadcasting

### To Groups

```python
from django_matt.websockets import broadcast

# Broadcast to a group
await broadcast("room_chat_general", {
    "type": "chat.message",
    "message": "Hello everyone!",
})
```

### To Users

```python
from django_matt.websockets import send_to_user

# Send to specific user
await send_to_user(user_id, {
    "type": "notification",
    "message": "You have a new message",
})
```

## Presence

Track online users:

```python
from django_matt.websockets import PresenceManager

presence = PresenceManager()

class ChatConsumer(RoomConsumer):
    async def connect(self):
        await self.accept()
        await presence.user_joined(self.room_name, self.user)

        # Notify others
        await self.room_send(self.room_name, {
            "type": "presence.join",
            "user": self.user.username,
        })

    async def disconnect(self, code):
        await presence.user_left(self.room_name, self.user)

        await self.room_send(self.room_name, {
            "type": "presence.leave",
            "user": self.user.username,
        })

    async def get_online_users(self):
        users = await presence.get_users(self.room_name)
        await self.send_json({"online_users": users})
```

## Message Schemas

```python
from django_matt.websockets import ChatMessage, NotificationMessage

# Structured messages
message = ChatMessage(
    user="john",
    content="Hello!",
    room="general",
)

notification = NotificationMessage(
    title="New message",
    body="You have a new message from John",
    action_url="/messages/123",
)
```

## ASGI Application

```python
# asgi.py
from django_matt.websockets import create_asgi_application

application = create_asgi_application(
    websocket_routes=[
        ("ws/chat/<room>/", ChatConsumer),
        ("ws/notifications/", NotificationConsumer),
    ],
    auth_middleware="jwt",  # or "session"
)
```

## Frontend Client

```javascript
const ws = new WebSocket("wss://myapp.com/ws/chat/general/");

ws.onopen = () => {
    ws.send(JSON.stringify({
        type: "message",
        content: "Hello!",
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received:", data);
};

// With JWT authentication
const ws = new WebSocket(
    `wss://myapp.com/ws/chat/general/?token=${accessToken}`
);
```
