"""
Tests for the Django Matt messaging module.

Tests cover:
- ConversationType, MemberRole, MessageType, DeliveryStatus, AttachmentType enums
- Schema classes (ConversationSchema, MessageSchema, etc.) - validation, defaults
- SendMessageSchema, EditMessageSchema, ReactionSchema - validation constraints
- SearchMessagesSchema, PaginatedMessagesSchema
- Presence schemas (TypingIndicatorSchema, PresenceSchema)
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from django_matt.messaging.enums import (
    AttachmentType,
    ConversationType,
    DeliveryStatus,
    MemberRole,
    MessageType,
)
from django_matt.messaging.schemas import (
    AddMembersSchema,
    AttachmentSchema,
    ConversationDetailSchema,
    ConversationListSchema,
    ConversationMemberSchema,
    ConversationSchema,
    ConversationSettingsSchema,
    CreateDirectConversationSchema,
    CreateGroupConversationSchema,
    EditMessageSchema,
    MessageDetailSchema,
    MessageEditSchema,
    MessageReactionSchema,
    MessageReactionSummarySchema,
    MessageSchema,
    MessageStatusSchema,
    PaginatedMessagesSchema,
    PresenceSchema,
    PresenceUpdateSchema,
    ReactionSchema,
    ReadReceiptSchema,
    SearchMessagesSchema,
    SearchResultSchema,
    SendMessageSchema,
    TypingIndicatorSchema,
    UpdateConversationSchema,
    UpdateMemberRoleSchema,
)


# ===========================================================================
# Enums
# ===========================================================================


class TestConversationType:
    def test_values(self):
        assert ConversationType.DIRECT.value == "direct"
        assert ConversationType.GROUP.value == "group"
        assert ConversationType.CHANNEL.value == "channel"
        assert ConversationType.SUPPORT.value == "support"

    def test_all_members(self):
        assert len(ConversationType) == 4

    def test_string_enum(self):
        assert ConversationType("direct") == ConversationType.DIRECT


class TestMemberRole:
    def test_values(self):
        assert MemberRole.OWNER.value == "owner"
        assert MemberRole.ADMIN.value == "admin"
        assert MemberRole.MODERATOR.value == "moderator"
        assert MemberRole.MEMBER.value == "member"
        assert MemberRole.GUEST.value == "guest"

    def test_all_members(self):
        assert len(MemberRole) == 5


class TestMessageType:
    def test_values(self):
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.FILE.value == "file"
        assert MessageType.VIDEO.value == "video"
        assert MessageType.AUDIO.value == "audio"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.REPLY.value == "reply"
        assert MessageType.FORWARD.value == "forward"
        assert MessageType.DELETED.value == "deleted"

    def test_all_members(self):
        assert len(MessageType) == 9


class TestDeliveryStatus:
    def test_values(self):
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SENT.value == "sent"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.READ.value == "read"
        assert DeliveryStatus.FAILED.value == "failed"


class TestAttachmentType:
    def test_values(self):
        assert AttachmentType.IMAGE.value == "image"
        assert AttachmentType.VIDEO.value == "video"
        assert AttachmentType.AUDIO.value == "audio"
        assert AttachmentType.DOCUMENT.value == "document"
        assert AttachmentType.ARCHIVE.value == "archive"
        assert AttachmentType.OTHER.value == "other"


# ===========================================================================
# Conversation Schemas
# ===========================================================================


class TestConversationSchemas:
    def test_conversation_schema(self):
        now = datetime.utcnow()
        schema = ConversationSchema(
            id=1,
            name="General",
            conversation_type="group",
            created_at=now,
            updated_at=now,
        )
        assert schema.id == 1
        assert schema.name == "General"
        assert schema.description == ""
        assert schema.is_archived is False
        assert schema.is_locked is False

    def test_conversation_list_schema(self):
        schema = ConversationListSchema(
            id=1,
            name="General",
            conversation_type="group",
        )
        assert schema.unread_count == 0
        assert schema.member_count == 0
        assert schema.last_message_at is None

    def test_conversation_detail_schema(self):
        now = datetime.utcnow()
        schema = ConversationDetailSchema(
            id=1,
            name="General",
            conversation_type="group",
            created_at=now,
            updated_at=now,
            members=[],
        )
        assert schema.members == []

    def test_create_direct_schema(self):
        schema = CreateDirectConversationSchema(user_id=42)
        assert schema.user_id == 42

    def test_create_group_schema(self):
        schema = CreateGroupConversationSchema(name="Team Chat")
        assert schema.name == "Team Chat"
        assert schema.member_ids == []

    def test_create_group_schema_validation(self):
        with pytest.raises(ValidationError):
            CreateGroupConversationSchema(name="")  # min_length=1

    def test_update_conversation_schema_all_none(self):
        schema = UpdateConversationSchema()
        assert schema.name is None
        assert schema.description is None
        assert schema.avatar is None

    def test_add_members_schema(self):
        schema = AddMembersSchema(user_ids=[1, 2, 3])
        assert len(schema.user_ids) == 3
        assert schema.role == "member"

    def test_add_members_empty_fails(self):
        with pytest.raises(ValidationError):
            AddMembersSchema(user_ids=[])

    def test_update_member_role(self):
        schema = UpdateMemberRoleSchema(role="admin")
        assert schema.role == "admin"

    def test_conversation_settings_defaults(self):
        schema = ConversationSettingsSchema()
        assert schema.is_muted is False
        assert schema.is_pinned is False
        assert schema.is_archived is False
        assert schema.show_notifications is True


# ===========================================================================
# Message Schemas
# ===========================================================================


class TestMessageSchemas:
    def test_send_message_schema(self):
        schema = SendMessageSchema(content="Hello!")
        assert schema.content == "Hello!"
        assert schema.message_type == "text"
        assert schema.reply_to_id is None

    def test_send_message_empty_fails(self):
        with pytest.raises(ValidationError):
            SendMessageSchema(content="")

    def test_edit_message_schema(self):
        schema = EditMessageSchema(content="Updated content")
        assert schema.content == "Updated content"

    def test_reaction_schema(self):
        schema = ReactionSchema(emoji="👍")
        assert schema.emoji == "👍"

    def test_reaction_empty_fails(self):
        with pytest.raises(ValidationError):
            ReactionSchema(emoji="")

    def test_message_schema(self):
        now = datetime.utcnow()
        schema = MessageSchema(
            id=1,
            conversation_id=10,
            sender_id=5,
            content="Hi",
            message_type="text",
            created_at=now,
        )
        assert schema.is_pinned is False
        assert schema.is_edited is False
        assert schema.attachments == []
        assert schema.reactions == []

    def test_message_detail_schema(self):
        now = datetime.utcnow()
        schema = MessageDetailSchema(
            id=1,
            conversation_id=10,
            sender_id=5,
            content="Hi",
            message_type="text",
            created_at=now,
        )
        assert schema.edit_history == []


# ===========================================================================
# Delivery / Presence / Search Schemas
# ===========================================================================


class TestDeliveryPresenceSearchSchemas:
    def test_read_receipt_schema(self):
        schema = ReadReceiptSchema()
        assert schema.up_to_message_id is None

    def test_typing_indicator(self):
        schema = TypingIndicatorSchema(
            conversation_id=1,
            user_id=5,
            is_typing=True,
        )
        assert schema.is_typing is True

    def test_presence_schema(self):
        schema = PresenceSchema(user_id=1, online=True)
        assert schema.typing is False
        assert schema.last_seen is None

    def test_search_messages_schema(self):
        schema = SearchMessagesSchema(query="hello")
        assert schema.limit == 50
        assert schema.conversation_id is None

    def test_search_messages_empty_query_fails(self):
        with pytest.raises(ValidationError):
            SearchMessagesSchema(query="")

    def test_search_result_schema(self):
        schema = SearchResultSchema(messages=[], total=0)
        assert schema.total == 0

    def test_paginated_messages_schema(self):
        schema = PaginatedMessagesSchema(messages=[], has_more=False)
        assert schema.next_cursor is None
