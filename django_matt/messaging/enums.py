"""
Messaging system enums.

Defines types and statuses used throughout the messaging system.
"""

from enum import Enum


class ConversationType(str, Enum):
    """Types of conversations."""

    DIRECT = "direct"  # 1-on-1 conversation
    GROUP = "group"  # Multi-user group chat
    CHANNEL = "channel"  # Broadcast channel (one-to-many)
    SUPPORT = "support"  # Support ticket conversation


class MemberRole(str, Enum):
    """Roles for conversation members."""

    OWNER = "owner"  # Creator/owner with full permissions
    ADMIN = "admin"  # Can manage members and settings
    MODERATOR = "moderator"  # Can moderate messages
    MEMBER = "member"  # Regular participant
    GUEST = "guest"  # Limited access (read-only in some cases)


class MessageType(str, Enum):
    """Types of messages."""

    TEXT = "text"  # Plain text message
    IMAGE = "image"  # Image attachment
    FILE = "file"  # File attachment
    VIDEO = "video"  # Video attachment
    AUDIO = "audio"  # Audio/voice message
    SYSTEM = "system"  # System-generated message
    REPLY = "reply"  # Reply to another message
    FORWARD = "forward"  # Forwarded message
    DELETED = "deleted"  # Placeholder for deleted message


class DeliveryStatus(str, Enum):
    """Message delivery status."""

    PENDING = "pending"  # Not yet sent to server
    SENT = "sent"  # Sent to server
    DELIVERED = "delivered"  # Delivered to recipient(s)
    READ = "read"  # Read by recipient(s)
    FAILED = "failed"  # Failed to send


class AttachmentType(str, Enum):
    """Types of attachments."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    OTHER = "other"
