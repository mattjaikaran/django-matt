"""
Django Matt WebSockets - Real-time communication with Django Channels.

Provides:
- Base consumer classes for WebSocket handling
- JWT and session authentication for WebSockets
- Room/group management with presence tracking
- Routing utilities
- Pydantic schemas for messages

Requires: uv add channels channels-redis

Configuration in settings.py:

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

Example usage:

    # consumers.py
    from django_matt.websockets import JsonConsumer, RoomConsumer

    class ChatConsumer(RoomConsumer):
        async def handle_chat_message(self, data: dict):
            await self.broadcast_to_room({
                "type": "chat_message",
                "user": self.user.username,
                "message": data.get("message"),
            })

    # routing.py
    from django_matt.websockets import WebSocketRouter

    router = WebSocketRouter()
    router.route("ws/chat/<str:room_name>/", ChatConsumer)

    # asgi.py
    from django_matt.websockets import create_asgi_application
    application = create_asgi_application(router)
"""

# Configuration
# Authentication
from django_matt.websockets.auth import (
    AuthMiddlewareBase,
    AuthMiddlewareStack,
    CombinedAuthMiddleware,
    JWTAuthMiddleware,
    JWTAuthMiddlewareStack,
    SessionAuthMiddleware,
    SessionAuthMiddlewareStack,
    TokenAuthMiddleware,
)
from django_matt.websockets.config import (
    RateLimitConfig,
    WebSocketConfig,
    get_websocket_config,
    websocket_config,
)

# Consumers
from django_matt.websockets.consumers import (
    AuthenticatedConsumer,
    AuthenticationError,
    BaseConsumer,
    ConnectionState,
    JsonConsumer,
    RateLimitError,
    RoomConsumer,
    ValidationError,
    WebSocketError,
)

# Groups/Presence
from django_matt.websockets.groups import (
    PresenceInfo,
    PresenceManager,
    broadcast,
    get_channel_layer,
    get_group_count,
    get_group_users,
    get_presence_manager,
    send_to_channel,
    send_to_user,
)

# Routing
from django_matt.websockets.routing import (
    WebSocketRoute,
    WebSocketRouter,
    collect_routes,
    create_asgi_application,
    websocket_route,
)

# Schemas
from django_matt.websockets.schemas import (
    AckMessage,
    AuthenticatedMessage,
    BaseMessage,
    ChatJoinMessage,
    ChatLeaveMessage,
    ChatMessage,
    ConnectedMessage,
    DataMessage,
    DisconnectedMessage,
    ErrorMessage,
    EventMessage,
    JoinRoomRequest,
    LeaveRoomRequest,
    NotificationMessage,
    PingMessage,
    PongMessage,
    PresenceListMessage,
    PresenceMessage,
    PublishMessage,
    RequestMessage,
    ResponseMessage,
    RoomJoinedMessage,
    RoomLeftMessage,
    RoomUsersMessage,
    SubscribedMessage,
    SubscribeMessage,
    TypingMessage,
    UnsubscribedMessage,
    UnsubscribeMessage,
)

__all__ = [
    # Configuration
    "WebSocketConfig",
    "RateLimitConfig",
    "get_websocket_config",
    "websocket_config",
    # Consumers
    "BaseConsumer",
    "JsonConsumer",
    "AuthenticatedConsumer",
    "RoomConsumer",
    "ConnectionState",
    "WebSocketError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    # Authentication
    "AuthMiddlewareBase",
    "JWTAuthMiddleware",
    "SessionAuthMiddleware",
    "TokenAuthMiddleware",
    "CombinedAuthMiddleware",
    "AuthMiddlewareStack",
    "JWTAuthMiddlewareStack",
    "SessionAuthMiddlewareStack",
    # Groups/Presence
    "PresenceManager",
    "PresenceInfo",
    "get_presence_manager",
    "get_channel_layer",
    "broadcast",
    "send_to_user",
    "send_to_channel",
    "get_group_users",
    "get_group_count",
    # Routing
    "WebSocketRouter",
    "WebSocketRoute",
    "websocket_route",
    "collect_routes",
    "create_asgi_application",
    # Schemas
    "BaseMessage",
    "ErrorMessage",
    "AckMessage",
    "PingMessage",
    "PongMessage",
    "ChatMessage",
    "ChatJoinMessage",
    "ChatLeaveMessage",
    "TypingMessage",
    "JoinRoomRequest",
    "LeaveRoomRequest",
    "RoomJoinedMessage",
    "RoomLeftMessage",
    "RoomUsersMessage",
    "NotificationMessage",
    "PresenceMessage",
    "PresenceListMessage",
    "DataMessage",
    "EventMessage",
    "ConnectedMessage",
    "AuthenticatedMessage",
    "DisconnectedMessage",
    "RequestMessage",
    "ResponseMessage",
    "SubscribeMessage",
    "UnsubscribeMessage",
    "SubscribedMessage",
    "UnsubscribedMessage",
    "PublishMessage",
]
