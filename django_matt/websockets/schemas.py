"""
Pydantic schemas for WebSocket messages.

Provides base schemas for common WebSocket message patterns.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    """Base WebSocket message schema."""

    type: str = Field(..., description="Message type identifier")


class ErrorMessage(BaseMessage):
    """Error message schema."""

    type: str = "error"
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: dict[str, Any] = Field(default_factory=dict, description="Additional error data")


class AckMessage(BaseMessage):
    """Acknowledgment message schema."""

    type: str = "ack"
    message_id: str = Field(..., description="ID of acknowledged message")
    success: bool = True


class PingMessage(BaseMessage):
    """Ping message for heartbeat."""

    type: str = "ping"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PongMessage(BaseMessage):
    """Pong response to ping."""

    type: str = "pong"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Chat Messages
# -----------------------------------------------------------------------------


class ChatMessage(BaseMessage):
    """Chat message schema."""

    type: str = "chat_message"
    message: str = Field(..., description="Message content")
    user: str | None = Field(None, description="Username of sender")
    user_id: str | None = Field(None, description="User ID of sender")
    room: str | None = Field(None, description="Room/channel name")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatJoinMessage(BaseMessage):
    """User joined chat message."""

    type: str = "user_joined"
    user: str = Field(..., description="Username who joined")
    user_id: str | None = None
    room: str = Field(..., description="Room joined")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatLeaveMessage(BaseMessage):
    """User left chat message."""

    type: str = "user_left"
    user: str = Field(..., description="Username who left")
    user_id: str | None = None
    room: str = Field(..., description="Room left")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TypingMessage(BaseMessage):
    """User typing indicator."""

    type: str = "typing"
    user: str = Field(..., description="Username who is typing")
    room: str = Field(..., description="Room")
    is_typing: bool = True


# -----------------------------------------------------------------------------
# Room Messages
# -----------------------------------------------------------------------------


class JoinRoomRequest(BaseMessage):
    """Request to join a room."""

    type: str = "join"
    room: str = Field(..., description="Room to join")


class LeaveRoomRequest(BaseMessage):
    """Request to leave a room."""

    type: str = "leave"
    room: str | None = Field(None, description="Room to leave (current if None)")


class RoomJoinedMessage(BaseMessage):
    """Confirmation of room join."""

    type: str = "room_joined"
    room: str = Field(..., description="Room joined")
    user_count: int | None = Field(None, description="Number of users in room")


class RoomLeftMessage(BaseMessage):
    """Confirmation of room leave."""

    type: str = "room_left"
    room: str = Field(..., description="Room left")


class RoomUsersMessage(BaseMessage):
    """List of users in a room."""

    type: str = "room_users"
    room: str = Field(..., description="Room name")
    users: list[dict[str, Any]] = Field(..., description="List of users")
    count: int = Field(..., description="Total user count")


# -----------------------------------------------------------------------------
# Notification Messages
# -----------------------------------------------------------------------------


class NotificationMessage(BaseMessage):
    """Notification message schema."""

    type: str = "notification"
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    level: str = Field("info", description="Notification level (info, warning, error)")
    action_url: str | None = Field(None, description="URL for action button")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Presence Messages
# -----------------------------------------------------------------------------


class PresenceMessage(BaseMessage):
    """User presence update."""

    type: str = "presence"
    user: str = Field(..., description="Username")
    user_id: str | None = None
    status: str = Field(..., description="Status (online, away, offline)")
    last_seen: datetime | None = None


class PresenceListMessage(BaseMessage):
    """List of online users."""

    type: str = "presence_list"
    users: list[dict[str, Any]] = Field(..., description="List of online users")


# -----------------------------------------------------------------------------
# Generic Data Messages
# -----------------------------------------------------------------------------


class DataMessage[DataT](BaseMessage):
    """Generic data message with typed payload."""

    type: str = "data"
    data: DataT


class EventMessage(BaseMessage):
    """Generic event message."""

    type: str = "event"
    event: str = Field(..., description="Event name")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Connection Messages
# -----------------------------------------------------------------------------


class ConnectedMessage(BaseMessage):
    """Connection established message."""

    type: str = "connected"
    message: str = "Connection established"
    connection_id: str | None = None
    user_id: str | None = None


class AuthenticatedMessage(BaseMessage):
    """Authentication successful message."""

    type: str = "authenticated"
    user_id: str | None = None
    username: str | None = None


class DisconnectedMessage(BaseMessage):
    """Disconnection message."""

    type: str = "disconnected"
    reason: str = ""
    code: int = 1000


# -----------------------------------------------------------------------------
# Request/Response Patterns
# -----------------------------------------------------------------------------


class RequestMessage(BaseMessage):
    """Request message with ID for correlation."""

    type: str = "request"
    request_id: str = Field(..., description="Unique request ID")
    action: str = Field(..., description="Action to perform")
    params: dict[str, Any] = Field(default_factory=dict, description="Action parameters")


class ResponseMessage(BaseMessage):
    """Response message correlated to request."""

    type: str = "response"
    request_id: str = Field(..., description="ID of original request")
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# -----------------------------------------------------------------------------
# Subscription Messages
# -----------------------------------------------------------------------------


class SubscribeMessage(BaseMessage):
    """Subscribe to a channel/topic."""

    type: str = "subscribe"
    channel: str = Field(..., description="Channel to subscribe to")


class UnsubscribeMessage(BaseMessage):
    """Unsubscribe from a channel/topic."""

    type: str = "unsubscribe"
    channel: str = Field(..., description="Channel to unsubscribe from")


class SubscribedMessage(BaseMessage):
    """Subscription confirmation."""

    type: str = "subscribed"
    channel: str = Field(..., description="Channel subscribed to")


class UnsubscribedMessage(BaseMessage):
    """Unsubscription confirmation."""

    type: str = "unsubscribed"
    channel: str = Field(..., description="Channel unsubscribed from")


class PublishMessage(BaseMessage):
    """Publish message to subscribers."""

    type: str = "publish"
    channel: str = Field(..., description="Channel published to")
    data: dict[str, Any] = Field(..., description="Published data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
