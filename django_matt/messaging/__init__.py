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
]
