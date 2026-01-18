"""
Messaging API schemas.

Pydantic schemas for request/response serialization.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Conversation Schemas
# =============================================================================


class ConversationMemberSchema(BaseModel):
    """Schema for conversation member."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    role: str
    joined_at: datetime
    nickname: str = ""


class ConversationSchema(BaseModel):
    """Schema for conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str = ""
    avatar: str = ""
    conversation_type: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    last_message_preview: str = ""
    is_archived: bool = False
    is_locked: bool = False


class ConversationListSchema(BaseModel):
    """Schema for conversation in list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    avatar: str = ""
    conversation_type: str
    last_message_at: datetime | None = None
    last_message_preview: str = ""
    unread_count: int = 0
    member_count: int = 0


class ConversationDetailSchema(ConversationSchema):
    """Schema for conversation with details."""

    members: list[ConversationMemberSchema] = []


class CreateDirectConversationSchema(BaseModel):
    """Schema for creating a direct conversation."""

    user_id: int = Field(..., description="ID of the user to start conversation with")


class CreateGroupConversationSchema(BaseModel):
    """Schema for creating a group conversation."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    avatar: str = ""
    member_ids: list[int] = Field(default_factory=list)


class UpdateConversationSchema(BaseModel):
    """Schema for updating a conversation."""

    name: str | None = None
    description: str | None = None
    avatar: str | None = None


class AddMembersSchema(BaseModel):
    """Schema for adding members to a conversation."""

    user_ids: list[int] = Field(..., min_length=1)
    role: str = "member"


class UpdateMemberRoleSchema(BaseModel):
    """Schema for updating a member's role."""

    role: str = Field(..., description="New role: owner, admin, moderator, member, guest")


class ConversationSettingsSchema(BaseModel):
    """Schema for conversation settings."""

    is_muted: bool = False
    is_pinned: bool = False
    is_archived: bool = False
    show_notifications: bool = True


# =============================================================================
# Message Schemas
# =============================================================================


class MessageReactionSchema(BaseModel):
    """Schema for message reaction."""

    model_config = ConfigDict(from_attributes=True)

    emoji: str
    user_id: int
    created_at: datetime


class MessageReactionSummarySchema(BaseModel):
    """Schema for reaction summary."""

    emoji: str
    count: int


class MessageEditSchema(BaseModel):
    """Schema for message edit history."""

    model_config = ConfigDict(from_attributes=True)

    previous_content: str
    edited_by_id: int | None
    edited_at: datetime


class AttachmentSchema(BaseModel):
    """Schema for attachment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    content_type: str
    attachment_type: str
    file_size: int
    url: str = ""
    thumbnail_url: str = ""
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class MessageSchema(BaseModel):
    """Schema for message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int | None
    content: str
    message_type: str
    reply_to_id: int | None = None
    forwarded_from_id: int | None = None
    created_at: datetime
    edited_at: datetime | None = None
    is_pinned: bool = False
    is_edited: bool = False
    attachments: list[AttachmentSchema] = []
    reactions: list[MessageReactionSummarySchema] = []


class MessageDetailSchema(MessageSchema):
    """Schema for message with full details."""

    edit_history: list[MessageEditSchema] = []


class SendMessageSchema(BaseModel):
    """Schema for sending a message."""

    content: str = Field(..., min_length=1, max_length=10000)
    message_type: str = "text"
    reply_to_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EditMessageSchema(BaseModel):
    """Schema for editing a message."""

    content: str = Field(..., min_length=1, max_length=10000)


class ReactionSchema(BaseModel):
    """Schema for adding/removing a reaction."""

    emoji: str = Field(..., min_length=1, max_length=10)


# =============================================================================
# Delivery Status Schemas
# =============================================================================


class MessageStatusSchema(BaseModel):
    """Schema for message delivery status."""

    model_config = ConfigDict(from_attributes=True)

    message_id: int
    user_id: int
    status: str
    sent_at: datetime
    delivered_at: datetime | None = None
    read_at: datetime | None = None


class ReadReceiptSchema(BaseModel):
    """Schema for marking messages as read."""

    up_to_message_id: int | None = None


# =============================================================================
# Presence Schemas
# =============================================================================


class TypingIndicatorSchema(BaseModel):
    """Schema for typing indicator."""

    conversation_id: int
    user_id: int
    is_typing: bool


class PresenceSchema(BaseModel):
    """Schema for user presence."""

    user_id: int
    online: bool
    last_seen: datetime | None = None
    typing: bool = False


class PresenceUpdateSchema(BaseModel):
    """Schema for presence update from client."""

    conversation_id: int | None = None


# =============================================================================
# Search Schemas
# =============================================================================


class SearchMessagesSchema(BaseModel):
    """Schema for message search."""

    query: str = Field(..., min_length=1)
    conversation_id: int | None = None
    limit: int = Field(default=50, ge=1, le=100)


class SearchResultSchema(BaseModel):
    """Schema for search result."""

    messages: list[MessageSchema]
    total: int


# =============================================================================
# Pagination Schemas
# =============================================================================


class PaginatedMessagesSchema(BaseModel):
    """Schema for paginated messages."""

    messages: list[MessageSchema]
    has_more: bool
    next_cursor: int | None = None
