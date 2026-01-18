"""
Messaging event types and helpers.

Defines the events broadcast over WebSocket and polling connections.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class EventType(str, Enum):
    """Message event types."""

    # Message events
    MESSAGE_NEW = "message.new"
    MESSAGE_EDITED = "message.edited"
    MESSAGE_DELETED = "message.deleted"
    MESSAGE_PINNED = "message.pinned"
    MESSAGE_UNPINNED = "message.unpinned"

    # Reaction events
    REACTION_ADDED = "reaction.added"
    REACTION_REMOVED = "reaction.removed"

    # Presence events
    USER_TYPING = "user.typing"
    USER_ONLINE = "user.online"
    USER_OFFLINE = "user.offline"

    # Read receipt events
    MESSAGES_READ = "messages.read"

    # Conversation events
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_UPDATED = "conversation.updated"
    CONVERSATION_DELETED = "conversation.deleted"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    MEMBER_ROLE_CHANGED = "member.role_changed"


class BaseEvent(BaseModel):
    """Base event model."""

    type: EventType
    timestamp: datetime
    conversation_id: int | None = None


class MessageEvent(BaseEvent):
    """Event for message operations."""

    message_id: int
    sender_id: int | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None


class ReactionEvent(BaseEvent):
    """Event for reaction operations."""

    message_id: int
    user_id: int
    emoji: str


class TypingEvent(BaseEvent):
    """Event for typing indicator."""

    type: EventType = EventType.USER_TYPING
    user_id: int
    is_typing: bool = True


class PresenceEvent(BaseEvent):
    """Event for user presence."""

    user_id: int
    online: bool
    last_seen: datetime | None = None


class ReadReceiptEvent(BaseEvent):
    """Event for read receipts."""

    type: EventType = EventType.MESSAGES_READ
    user_id: int
    last_read_message_id: int | None = None


class MemberEvent(BaseEvent):
    """Event for member changes."""

    user_id: int
    role: str | None = None
    added_by_id: int | None = None


def create_message_event(
    event_type: EventType,
    conversation_id: int,
    message_id: int,
    sender_id: int | None = None,
    content: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Create a message event dictionary."""
    from django.utils import timezone

    return {
        "type": event_type.value,
        "timestamp": timezone.now().isoformat(),
        "conversation_id": conversation_id,
        "message_id": message_id,
        "sender_id": sender_id,
        "content": content,
        "metadata": metadata,
    }


def create_typing_event(
    conversation_id: int,
    user_id: int,
    is_typing: bool = True,
) -> dict:
    """Create a typing indicator event."""
    from django.utils import timezone

    return {
        "type": EventType.USER_TYPING.value,
        "timestamp": timezone.now().isoformat(),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "is_typing": is_typing,
    }


def create_presence_event(
    user_id: int,
    online: bool,
    last_seen: datetime | None = None,
) -> dict:
    """Create a presence event."""
    from django.utils import timezone

    return {
        "type": (EventType.USER_ONLINE if online else EventType.USER_OFFLINE).value,
        "timestamp": timezone.now().isoformat(),
        "user_id": user_id,
        "online": online,
        "last_seen": last_seen.isoformat() if last_seen else None,
    }


def create_read_receipt_event(
    conversation_id: int,
    user_id: int,
    last_read_message_id: int | None = None,
) -> dict:
    """Create a read receipt event."""
    from django.utils import timezone

    return {
        "type": EventType.MESSAGES_READ.value,
        "timestamp": timezone.now().isoformat(),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "last_read_message_id": last_read_message_id,
    }


def create_member_event(
    event_type: EventType,
    conversation_id: int,
    user_id: int,
    role: str | None = None,
    added_by_id: int | None = None,
) -> dict:
    """Create a member change event."""
    from django.utils import timezone

    return {
        "type": event_type.value,
        "timestamp": timezone.now().isoformat(),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "added_by_id": added_by_id,
    }
