"""
Real-time messaging transport.

Provides WebSocket and polling support for real-time messaging features.
"""

from django_matt.messaging.realtime.consumer import (
    MessagingConsumer,
    broadcast_to_conversation,
    get_conversation_group_name,
    send_to_user,
)
from django_matt.messaging.realtime.events import (
    BaseEvent,
    EventType,
    MemberEvent,
    MessageEvent,
    PresenceEvent,
    ReactionEvent,
    ReadReceiptEvent,
    TypingEvent,
    create_member_event,
    create_message_event,
    create_presence_event,
    create_read_receipt_event,
    create_typing_event,
)
from django_matt.messaging.realtime.polling import PollingController

__all__ = [
    # Consumer
    "MessagingConsumer",
    "broadcast_to_conversation",
    "send_to_user",
    "get_conversation_group_name",
    # Polling
    "PollingController",
    # Events
    "EventType",
    "BaseEvent",
    "MessageEvent",
    "ReactionEvent",
    "TypingEvent",
    "PresenceEvent",
    "ReadReceiptEvent",
    "MemberEvent",
    # Event helpers
    "create_message_event",
    "create_typing_event",
    "create_presence_event",
    "create_read_receipt_event",
    "create_member_event",
]
