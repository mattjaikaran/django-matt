# file-length-max: 600
"""
WebSocket consumer base classes.

Provides base classes for building WebSocket consumers with:
- JSON message handling
- Authentication support
- Group/room management
- Error handling
- Rate limiting

Requires: uv add channels
"""

import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth.models import AnonymousUser

import orjson

from django_matt.websockets.config import get_websocket_config

logger = logging.getLogger(__name__)


# Type aliases
MessageHandler = Callable[["BaseConsumer", dict], Coroutine[Any, Any, None]]


@dataclass
class ConnectionState:
    """Tracks connection state."""

    connected_at: float = 0
    last_message_at: float = 0
    message_count: int = 0
    groups: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSocketError(Exception):
    """Base WebSocket error."""

    def __init__(self, code: int, message: str, data: dict | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)


class AuthenticationError(WebSocketError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(4001, message)


class RateLimitError(WebSocketError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(4002, message)


class ValidationError(WebSocketError):
    """Message validation failed."""

    def __init__(self, message: str, data: dict | None = None):
        super().__init__(4003, message, data)


class BaseConsumer:
    """
    Base WebSocket consumer with core functionality.

    Subclass this for custom WebSocket handling.

    Usage:
        class MyConsumer(BaseConsumer):
            async def on_connect(self):
                await self.accept()

            async def on_message(self, data: dict):
                await self.send_json({"echo": data})

            async def on_disconnect(self, code: int):
                pass
    """

    # Class-level configuration
    auth_required: bool = False
    allowed_groups: list[str] | None = None  # None = allow all

    def __init__(self, scope: dict, receive: Callable, send: Callable):
        self.scope = scope
        self._receive = receive
        self._send = send
        self.config = get_websocket_config()
        self.state = ConnectionState()
        self._closed = False
        self._handlers: dict[str, MessageHandler] = {}
        self._rate_limit_tokens: float = self.config.rate_limit.burst_size
        self._rate_limit_last_update: float = time.time()

        # Register message handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message type handlers from methods."""
        for name in dir(self):
            if name.startswith("handle_"):
                handler = getattr(self, name)
                if callable(handler):
                    message_type = name[7:]  # Remove "handle_" prefix
                    self._handlers[message_type] = handler

    @property
    def user(self):
        """Get the authenticated user."""
        return self.scope.get("user", AnonymousUser())

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        user = self.user
        return user and hasattr(user, "is_authenticated") and user.is_authenticated

    @property
    def channel_name(self) -> str:
        """Get the channel name for this connection."""
        return self.scope.get("channel_name", "")

    @property
    def channel_layer(self):
        """Get the channel layer."""
        return self.scope.get("channel_layer")

    async def __call__(self, receive: Callable, send: Callable) -> None:
        """ASGI interface."""
        self._receive = receive
        self._send = send

        try:
            while True:
                message = await self._receive()
                message_type = message.get("type", "")

                if message_type == "websocket.connect":
                    await self._handle_connect()
                elif message_type == "websocket.receive":
                    await self._handle_receive(message)
                elif message_type == "websocket.disconnect":
                    await self._handle_disconnect(message.get("code", 1000))
                    break
                else:
                    # Handle channel layer messages
                    handler = getattr(self, message_type.replace(".", "_"), None)
                    if handler:
                        await handler(message)

        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
            await self.close(code=1011)

    async def _handle_connect(self) -> None:
        """Handle WebSocket connection."""
        self.state.connected_at = time.time()

        # Check authentication if required
        if self.auth_required and not self.is_authenticated:
            await self.close(code=4001)
            return

        try:
            await self.on_connect()
        except WebSocketError as e:
            await self.send_error(e.code, e.message, e.data)
            await self.close(code=e.code)
        except Exception as e:
            logger.exception(f"Error in on_connect: {e}")
            await self.close(code=1011)

    async def _handle_receive(self, message: dict) -> None:
        """Handle incoming WebSocket message."""
        if self._closed:
            return

        # Check rate limit
        if not self._check_rate_limit():
            await self.send_error(4002, "Rate limit exceeded")
            return

        self.state.last_message_at = time.time()
        self.state.message_count += 1

        # Get message data
        text_data = message.get("text")
        bytes_data = message.get("bytes")

        try:
            if text_data:
                await self.on_receive(text_data=text_data)
            elif bytes_data:
                await self.on_receive(bytes_data=bytes_data)
        except WebSocketError as e:
            await self.send_error(e.code, e.message, e.data)
        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            await self.send_error(1011, "Internal error")

    async def _handle_disconnect(self, code: int) -> None:
        """Handle WebSocket disconnection."""
        self._closed = True

        # Leave all groups
        for group in list(self.state.groups):
            await self.leave_group(group)

        try:
            await self.on_disconnect(code)
        except Exception as e:
            logger.exception(f"Error in on_disconnect: {e}")

    def _check_rate_limit(self) -> bool:
        """Check and update rate limit."""
        if not self.config.rate_limit.enabled:
            return True

        now = time.time()
        elapsed = now - self._rate_limit_last_update
        self._rate_limit_last_update = now

        # Replenish tokens
        self._rate_limit_tokens = min(
            self.config.rate_limit.burst_size,
            self._rate_limit_tokens + elapsed * self.config.rate_limit.messages_per_second,
        )

        # Check if we have tokens
        if self._rate_limit_tokens >= 1:
            self._rate_limit_tokens -= 1
            return True

        return False

    # -------------------------------------------------------------------------
    # Connection lifecycle (override these)
    # -------------------------------------------------------------------------

    async def on_connect(self) -> None:
        """
        Called when WebSocket connection is established.

        Override to customize connection handling.
        Call await self.accept() to accept the connection.
        """
        await self.accept()

    async def on_receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        """
        Called when a message is received.

        Override for custom message handling.
        Default implementation parses JSON and routes to handlers.
        """
        if text_data:
            try:
                data = orjson.loads(text_data)
                await self.on_message(data)
            except orjson.JSONDecodeError:
                await self.send_error(4003, "Invalid JSON")
        elif bytes_data:
            await self.on_binary_message(bytes_data)

    async def on_message(self, data: dict) -> None:
        """
        Called when a JSON message is received.

        Override for custom message handling.
        Default routes to handle_<type> methods.
        """
        message_type = data.get("type", "message")
        handler = self._handlers.get(message_type)

        if handler:
            await handler(data)
        else:
            await self.on_unhandled_message(message_type, data)

    async def on_binary_message(self, data: bytes) -> None:
        """Called when binary message is received. Override for custom handling."""

    async def on_unhandled_message(self, message_type: str, data: dict) -> None:
        """Called when no handler exists for message type."""
        logger.warning(f"Unhandled message type: {message_type}")

    async def on_disconnect(self, code: int) -> None:
        """
        Called when WebSocket disconnects.

        Override for cleanup logic.
        """

    # -------------------------------------------------------------------------
    # Sending messages
    # -------------------------------------------------------------------------

    async def accept(self, subprotocol: str | None = None) -> None:
        """Accept the WebSocket connection."""
        await self._send(
            {
                "type": "websocket.accept",
                "subprotocol": subprotocol,
            }
        )

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the WebSocket connection."""
        self._closed = True
        await self._send(
            {
                "type": "websocket.close",
                "code": code,
                "reason": reason,
            }
        )

    async def send(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        """Send a message."""
        if self._closed:
            return

        message: dict[str, Any] = {"type": "websocket.send"}
        if text_data:
            message["text"] = text_data
        elif bytes_data:
            message["bytes"] = bytes_data

        await self._send(message)

    async def send_json(self, data: dict, **kwargs) -> None:
        """Send a JSON message."""
        await self.send(text_data=orjson.dumps(data).decode())

    async def send_error(
        self,
        code: int,
        message: str,
        data: dict | None = None,
    ) -> None:
        """Send an error message."""
        await self.send_json(
            {
                "type": "error",
                "code": code,
                "message": message,
                "data": data or {},
            }
        )

    # -------------------------------------------------------------------------
    # Group/Room management
    # -------------------------------------------------------------------------

    async def join_group(self, group_name: str) -> bool:
        """
        Join a channel group.

        Returns True if successful, False if limit reached or not allowed.
        """
        if not self.channel_layer:
            logger.warning("No channel layer configured")
            return False

        # Check if group is allowed
        if self.allowed_groups is not None and group_name not in self.allowed_groups:
            return False

        # Check group limit
        if len(self.state.groups) >= self.config.max_groups_per_user:
            return False

        prefixed_name = f"{self.config.group_prefix}{group_name}"
        await self.channel_layer.group_add(prefixed_name, self.channel_name)
        self.state.groups.add(group_name)
        return True

    async def leave_group(self, group_name: str) -> None:
        """Leave a channel group."""
        if not self.channel_layer:
            return

        prefixed_name = f"{self.config.group_prefix}{group_name}"
        await self.channel_layer.group_discard(prefixed_name, self.channel_name)
        self.state.groups.discard(group_name)

    async def broadcast_to_group(
        self,
        group_name: str,
        data: dict,
        exclude_self: bool = False,
    ) -> None:
        """Broadcast a message to a group."""
        if not self.channel_layer:
            return

        prefixed_name = f"{self.config.group_prefix}{group_name}"
        message = {
            "type": "group_message",
            "data": data,
            "sender_channel": self.channel_name if exclude_self else None,
        }
        await self.channel_layer.group_send(prefixed_name, message)

    async def group_message(self, event: dict) -> None:
        """Handle incoming group message."""
        # Skip if we're the sender and exclude_self was True
        sender = event.get("sender_channel")
        if sender and sender == self.channel_name:
            return

        await self.send_json(event.get("data", {}))


class JsonConsumer(BaseConsumer):
    """
    JSON-focused WebSocket consumer.

    Provides structured message handling with type routing.

    Usage:
        class ChatConsumer(JsonConsumer):
            async def handle_chat_message(self, data: dict):
                message = data.get("message", "")
                await self.broadcast_to_group("chat", {
                    "type": "chat_message",
                    "user": self.user.username,
                    "message": message,
                })

            async def handle_join_room(self, data: dict):
                room = data.get("room")
                await self.join_group(room)
                await self.send_json({"type": "joined", "room": room})
    """

    async def on_connect(self) -> None:
        """Accept connection and send welcome message."""
        await self.accept()
        await self.send_json(
            {
                "type": "connected",
                "message": "Connection established",
            }
        )


class AuthenticatedConsumer(BaseConsumer):
    """
    Consumer that requires authentication.

    Automatically rejects unauthenticated connections.
    """

    auth_required = True

    async def on_connect(self) -> None:
        """Accept only authenticated connections."""
        if not self.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()
        await self.send_json(
            {
                "type": "authenticated",
                "user_id": str(self.user.id) if hasattr(self.user, "id") else None,
            }
        )


class RoomConsumer(JsonConsumer):
    """
    Consumer for room-based communication.

    Provides room join/leave functionality out of the box.

    Usage:
        class GameConsumer(RoomConsumer):
            async def handle_game_action(self, data: dict):
                action = data.get("action")
                await self.broadcast_to_room({
                    "type": "game_action",
                    "user": self.user.username,
                    "action": action,
                })
    """

    room_param: str = "room_name"  # URL parameter for room name

    def __init__(self, scope: dict, receive: Callable, send: Callable):
        super().__init__(scope, receive, send)
        self._current_room: str | None = None

    @property
    def room_name(self) -> str | None:
        """Get current room name."""
        return self._current_room

    async def on_connect(self) -> None:
        """Connect and optionally join room from URL."""
        await self.accept()

        # Auto-join room from URL parameter
        room_name = self.scope.get("url_route", {}).get("kwargs", {}).get(self.room_param)
        if room_name:
            await self.join_room(room_name)

    async def join_room(self, room_name: str) -> bool:
        """Join a room."""
        # Leave current room first
        if self._current_room:
            await self.leave_room()

        success = await self.join_group(room_name)
        if success:
            self._current_room = room_name
            await self.on_room_join(room_name)
            await self.send_json(
                {
                    "type": "room_joined",
                    "room": room_name,
                }
            )
        return success

    async def leave_room(self) -> None:
        """Leave current room."""
        if self._current_room:
            room_name = self._current_room
            await self.leave_group(room_name)
            self._current_room = None
            await self.on_room_leave(room_name)
            await self.send_json(
                {
                    "type": "room_left",
                    "room": room_name,
                }
            )

    async def broadcast_to_room(
        self,
        data: dict,
        exclude_self: bool = False,
    ) -> None:
        """Broadcast to current room."""
        if self._current_room:
            await self.broadcast_to_group(self._current_room, data, exclude_self)

    async def on_room_join(self, room_name: str) -> None:
        """Called when joining a room. Override for custom logic."""

    async def on_room_leave(self, room_name: str) -> None:
        """Called when leaving a room. Override for custom logic."""

    async def handle_join(self, data: dict) -> None:
        """Handle join room request."""
        room = data.get("room")
        if room:
            await self.join_room(room)

    async def handle_leave(self, data: dict) -> None:
        """Handle leave room request."""
        await self.leave_room()

    async def on_disconnect(self, code: int) -> None:
        """Leave room on disconnect."""
        if self._current_room:
            await self.leave_room()
