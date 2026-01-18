"""
Django Matt Messaging System.

Full-featured real-time messaging with optional WebSocket support,
suitable for chat apps, support systems, and in-app communication.
"""

from django_matt.messaging.enums import (
    AttachmentType,
    ConversationType,
    DeliveryStatus,
    MemberRole,
    MessageType,
)
from django_matt.messaging.models import (
    Attachment,
    Conversation,
    ConversationMember,
    ConversationSettings,
    Message,
    MessageEdit,
    MessageReaction,
    MessageStatus,
)

# Real-time components (lazy import to avoid circular imports)


def get_messaging_consumer():
    """Get the MessagingConsumer class."""
    from django_matt.messaging.realtime import MessagingConsumer

    return MessagingConsumer


def get_polling_controller():
    """Get the PollingController class."""
    from django_matt.messaging.realtime import PollingController

    return PollingController


__all__ = [
    # Models
    "Conversation",
    "ConversationMember",
    "ConversationSettings",
    "Message",
    "MessageStatus",
    "MessageReaction",
    "MessageEdit",
    "Attachment",
    # Enums
    "ConversationType",
    "MemberRole",
    "MessageType",
    "DeliveryStatus",
    "AttachmentType",
    # Lazy accessors
    "get_messaging_consumer",
    "get_polling_controller",
]
