"""
Pydantic schemas for the chat API and WebSocket messages.

Schemas are organized by domain:
- Auth schemas
- User schemas
- Workspace schemas
- Channel schemas
- Message schemas
- Direct message schemas
- WebSocket event schemas
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Auth Schemas
# =============================================================================


class LoginRequest(BaseModel):
    """Login request payload."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


# =============================================================================
# User Schemas
# =============================================================================


class UserBase(BaseModel):
    """Base user schema."""

    id: int
    username: str
    email: str


class UserProfile(BaseModel):
    """User profile with status."""

    user_id: int
    username: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    status: str = "offline"
    status_text: str = ""
    last_seen: datetime | None = None


class UserPresence(BaseModel):
    """User presence update."""

    user_id: int
    username: str
    status: str
    last_seen: datetime | None = None


class UserBrief(BaseModel):
    """Brief user info for lists."""

    id: int
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    status: str = "offline"


# =============================================================================
# Workspace Schemas
# =============================================================================


class WorkspaceCreate(BaseModel):
    """Create workspace request."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")
    description: str = ""


class WorkspaceUpdate(BaseModel):
    """Update workspace request."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    icon_url: str | None = None


class WorkspaceResponse(BaseModel):
    """Workspace response."""

    id: UUID
    name: str
    slug: str
    description: str
    icon_url: str | None
    owner_id: int
    member_count: int
    channel_count: int
    created_at: datetime


class WorkspaceInvite(BaseModel):
    """Invite user to workspace."""

    email: str
    role: str = "member"


# =============================================================================
# Channel Schemas
# =============================================================================


class ChannelCreate(BaseModel):
    """Create channel request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    is_private: bool = False


class ChannelUpdate(BaseModel):
    """Update channel request."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    topic: str | None = None
    is_archived: bool | None = None


class ChannelResponse(BaseModel):
    """Channel response."""

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str
    topic: str
    is_private: bool
    is_archived: bool
    member_count: int
    created_at: datetime
    created_by: UserBrief | None = None


class ChannelMember(BaseModel):
    """Channel member info."""

    user: UserBrief
    joined_at: datetime
    is_muted: bool = False


# =============================================================================
# Message Schemas
# =============================================================================


class MessageCreate(BaseModel):
    """Create message request."""

    content: str = Field(..., min_length=1, max_length=10000)
    thread_id: UUID | None = None  # Parent message ID for threading
    attachment_ids: list[UUID] = Field(default_factory=list)


class MessageUpdate(BaseModel):
    """Update message request."""

    content: str = Field(..., min_length=1, max_length=10000)


class ReactionSchema(BaseModel):
    """Reaction on a message."""

    emoji: str
    count: int
    users: list[UserBrief] = Field(default_factory=list)
    reacted_by_me: bool = False


class MessageResponse(BaseModel):
    """Message response."""

    id: UUID
    channel_id: UUID | None = None
    dm_thread_id: UUID | None = None
    author: UserBrief | None
    content: str
    content_html: str = ""
    parent_message_id: UUID | None = None
    reply_count: int = 0
    reply_users_count: int = 0
    reactions: list[ReactionSchema] = Field(default_factory=list)
    attachments: list["FileAttachmentResponse"] = Field(default_factory=list)
    mentioned_users: list[UserBrief] = Field(default_factory=list)
    is_edited: bool = False
    edited_at: datetime | None = None
    created_at: datetime


class ThreadResponse(BaseModel):
    """Thread (replies) response."""

    parent_message: MessageResponse
    replies: list[MessageResponse]
    reply_count: int


# =============================================================================
# Direct Message Schemas
# =============================================================================


class DMThreadCreate(BaseModel):
    """Create DM thread request."""

    user_ids: list[int] = Field(..., min_length=1)


class DMThreadResponse(BaseModel):
    """DM thread response."""

    id: UUID
    workspace_id: UUID
    participants: list[UserBrief]
    last_message: MessageResponse | None = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime


# =============================================================================
# File Attachment Schemas
# =============================================================================


class FileUploadResponse(BaseModel):
    """File upload response (before attaching to message)."""

    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    url: str
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None


class FileAttachmentResponse(BaseModel):
    """File attachment on a message."""

    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    url: str
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None


# =============================================================================
# Search Schemas
# =============================================================================


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(..., min_length=1, max_length=500)
    workspace_id: UUID | None = None
    channel_id: UUID | None = None
    from_user_id: int | None = None
    after: datetime | None = None
    before: datetime | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchResult(BaseModel):
    """Search result item."""

    message: MessageResponse
    channel: ChannelResponse | None = None
    highlight: str = ""


class SearchResponse(BaseModel):
    """Search response."""

    results: list[SearchResult]
    total_count: int
    query: str


# =============================================================================
# WebSocket Event Schemas
# =============================================================================


class WSBaseMessage(BaseModel):
    """Base WebSocket message."""

    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSError(WSBaseMessage):
    """WebSocket error message."""

    type: str = "error"
    code: int
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class WSAck(WSBaseMessage):
    """WebSocket acknowledgment."""

    type: str = "ack"
    message_id: str


# Channel events
class WSChannelJoin(WSBaseMessage):
    """Join channel request."""

    type: str = "channel.join"
    channel_id: UUID


class WSChannelJoined(WSBaseMessage):
    """Channel joined confirmation."""

    type: str = "channel.joined"
    channel: ChannelResponse
    recent_messages: list[MessageResponse] = Field(default_factory=list)
    members_online: list[UserBrief] = Field(default_factory=list)


class WSChannelLeave(WSBaseMessage):
    """Leave channel request."""

    type: str = "channel.leave"


class WSChannelLeft(WSBaseMessage):
    """Channel left confirmation."""

    type: str = "channel.left"
    channel_id: UUID


class WSUserJoined(WSBaseMessage):
    """User joined channel notification."""

    type: str = "user.joined"
    channel_id: UUID
    user: UserBrief


class WSUserLeft(WSBaseMessage):
    """User left channel notification."""

    type: str = "user.left"
    channel_id: UUID
    user: UserBrief


# Message events
class WSMessageSend(WSBaseMessage):
    """Send message request."""

    type: str = "message.send"
    channel_id: UUID
    content: str
    thread_id: UUID | None = None
    attachment_ids: list[UUID] = Field(default_factory=list)


class WSMessageNew(WSBaseMessage):
    """New message notification."""

    type: str = "message.new"
    message: MessageResponse


class WSMessageUpdate(WSBaseMessage):
    """Update message request."""

    type: str = "message.update"
    message_id: UUID
    content: str


class WSMessageUpdated(WSBaseMessage):
    """Message updated notification."""

    type: str = "message.updated"
    message: MessageResponse


class WSMessageDelete(WSBaseMessage):
    """Delete message request."""

    type: str = "message.delete"
    message_id: UUID


class WSMessageDeleted(WSBaseMessage):
    """Message deleted notification."""

    type: str = "message.deleted"
    channel_id: UUID
    message_id: UUID


# Typing events
class WSTypingStart(WSBaseMessage):
    """Start typing indicator."""

    type: str = "typing.start"
    channel_id: UUID


class WSTypingStop(WSBaseMessage):
    """Stop typing indicator."""

    type: str = "typing.stop"
    channel_id: UUID


class WSTypingUpdate(WSBaseMessage):
    """Typing indicator update (server to client)."""

    type: str = "typing.update"
    channel_id: UUID
    users: list[UserBrief]


# Presence events
class WSPresenceUpdate(WSBaseMessage):
    """Update presence status."""

    type: str = "presence.update"
    status: str  # online, away, dnd, offline


class WSPresenceChanged(WSBaseMessage):
    """Presence changed notification."""

    type: str = "presence.changed"
    user_id: int
    status: str
    last_seen: datetime | None = None


# Reaction events
class WSReactionAdd(WSBaseMessage):
    """Add reaction request."""

    type: str = "reaction.add"
    message_id: UUID
    emoji: str


class WSReactionRemove(WSBaseMessage):
    """Remove reaction request."""

    type: str = "reaction.remove"
    message_id: UUID
    emoji: str


class WSReactionAdded(WSBaseMessage):
    """Reaction added notification."""

    type: str = "reaction.added"
    channel_id: UUID
    message_id: UUID
    emoji: str
    user: UserBrief


class WSReactionRemoved(WSBaseMessage):
    """Reaction removed notification."""

    type: str = "reaction.removed"
    channel_id: UUID
    message_id: UUID
    emoji: str
    user_id: int


# Read receipt events
class WSReadReceiptMark(WSBaseMessage):
    """Mark messages as read."""

    type: str = "read_receipt.mark"
    channel_id: UUID
    message_id: UUID  # Last read message


class WSReadReceiptUpdated(WSBaseMessage):
    """Read receipts updated notification."""

    type: str = "read_receipt.updated"
    channel_id: UUID
    receipts: list[dict[str, Any]]  # {user_id, last_read_message_id, last_read_at}


# =============================================================================
# Pagination Schemas
# =============================================================================


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list[Any]
    total: int
    limit: int
    offset: int
    has_more: bool


class CursorPaginatedResponse(BaseModel):
    """Cursor-based paginated response (better for real-time)."""

    items: list[Any]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
