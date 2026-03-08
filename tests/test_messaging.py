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


# ===========================================================================
# Model Tests (database)
# ===========================================================================


@pytest.mark.django_db
class TestConversationModel:
    """Tests for the Conversation model and ConversationManager."""

    def _make_user(self, username):
        from django.contrib.auth.models import User

        return User.objects.create_user(username=username, password="testpass123")

    def test_create_conversation(self):
        from django_matt.messaging.models import Conversation

        conv = Conversation.objects.create(
            name="Test Chat",
            conversation_type=ConversationType.GROUP,
        )
        assert conv.pk is not None
        assert conv.name == "Test Chat"
        assert conv.conversation_type == ConversationType.GROUP
        assert conv.is_archived is False
        assert conv.is_locked is False

    def test_is_member_active(self):
        from django_matt.messaging.models import Conversation

        user = self._make_user("member1")
        conv = Conversation.objects.create(conversation_type=ConversationType.DIRECT)
        conv.add_member(user)
        assert conv.is_member(user) is True

    def test_is_member_non_member(self):
        from django_matt.messaging.models import Conversation

        user = self._make_user("outsider")
        conv = Conversation.objects.create(conversation_type=ConversationType.DIRECT)
        assert conv.is_member(user) is False

    def test_add_member(self):
        from django_matt.messaging.models import Conversation, ConversationMember

        user = self._make_user("addme")
        conv = Conversation.objects.create(conversation_type=ConversationType.GROUP)
        member, created = conv.add_member(user, role=MemberRole.ADMIN)
        assert created is True
        assert member.role == MemberRole.ADMIN
        assert ConversationMember.objects.filter(
            conversation=conv, user=user, is_active=True
        ).exists()

    def test_remove_member_soft_delete(self):
        from django_matt.messaging.models import Conversation, ConversationMember

        user = self._make_user("removeme")
        conv = Conversation.objects.create(conversation_type=ConversationType.GROUP)
        conv.add_member(user)
        result = conv.remove_member(user)
        assert result is True
        member = ConversationMember.objects.get(conversation=conv, user=user)
        assert member.is_active is False
        assert member.left_at is not None

    def test_create_group_conversation(self):
        from django_matt.messaging.models import Conversation, ConversationMember

        owner = self._make_user("owner")
        m1 = self._make_user("m1")
        m2 = self._make_user("m2")
        conv = Conversation.objects.create_group("Team", creator=owner, members=[m1, m2])
        assert conv.name == "Team"
        assert conv.conversation_type == ConversationType.GROUP
        assert conv.created_by == owner
        # Owner + 2 members = 3
        assert ConversationMember.objects.filter(conversation=conv, is_active=True).count() == 3
        # Owner has OWNER role
        owner_member = ConversationMember.objects.get(conversation=conv, user=owner)
        assert owner_member.role == MemberRole.OWNER

    @pytest.mark.django_db(transaction=True)
    async def test_ais_member_async(self):
        from asgiref.sync import sync_to_async

        from django_matt.messaging.models import Conversation

        make_user = sync_to_async(self._make_user)
        user = await make_user("async_member")
        non_member = await make_user("async_non_member")

        conv = await sync_to_async(Conversation.objects.create)(
            conversation_type=ConversationType.DIRECT,
        )
        await sync_to_async(conv.add_member)(user)

        assert await conv.ais_member(user) is True
        assert await conv.ais_member(non_member) is False


@pytest.mark.django_db
class TestMessageModel:
    """Tests for the Message model."""

    def _make_user(self, username):
        from django.contrib.auth.models import User

        return User.objects.create_user(username=username, password="testpass123")

    def test_create_message(self):
        from django_matt.messaging.models import Conversation, Message

        user = self._make_user("sender1")
        conv = Conversation.objects.create(conversation_type=ConversationType.DIRECT)
        conv.add_member(user)
        msg = Message.objects.create(
            conversation=conv,
            sender=user,
            content="Hello world",
            message_type=MessageType.TEXT,
        )
        assert msg.pk is not None
        assert msg.content == "Hello world"
        assert msg.sender == user
        assert msg.conversation == conv
        assert msg.message_type == MessageType.TEXT

    def test_attachment_model(self):
        from django_matt.messaging.models import Attachment, Conversation, Message

        user = self._make_user("uploader")
        conv = Conversation.objects.create(conversation_type=ConversationType.DIRECT)
        conv.add_member(user)
        msg = Message.objects.create(
            conversation=conv, sender=user, content="See attached"
        )
        attachment = Attachment.objects.create(
            message=msg,
            uploaded_by=user,
            filename="test.png",
            original_filename="test.png",
            content_type="image/png",
            file_size=1024,
            storage_path="/uploads/test.png",
        )
        assert attachment.pk is not None
        assert attachment.message == msg
        assert attachment.uploaded_by == user
        assert attachment.is_image is True


@pytest.mark.django_db
class TestMessageService:
    """Tests for the MessageService."""

    def _make_user(self, username):
        from django.contrib.auth.models import User

        return User.objects.create_user(username=username, password="testpass123")

    def _make_conversation_with_members(self, *usernames):
        from django_matt.messaging.models import Conversation

        users = [self._make_user(u) for u in usernames]
        conv = Conversation.objects.create_group(
            name="test-group", creator=users[0], members=users[1:]
        )
        return conv, users

    def test_send_message_success(self):
        from django_matt.messaging.models import MessageStatus
        from django_matt.messaging.services.message import MessageService

        conv, users = self._make_conversation_with_members("sender", "receiver")
        msg = MessageService.send_message(conv, users[0], "Hello!")
        assert msg.content == "Hello!"
        assert msg.sender == users[0]
        # Delivery status created for receiver (not sender)
        statuses = MessageStatus.objects.filter(message=msg)
        assert statuses.count() == 1
        assert statuses.first().user == users[1]
        assert statuses.first().status == DeliveryStatus.SENT

    def test_send_message_non_member_raises(self):
        from django_matt.messaging.models import Conversation
        from django_matt.messaging.services.message import MessageService

        conv = Conversation.objects.create(conversation_type=ConversationType.GROUP)
        outsider = self._make_user("outsider")
        with pytest.raises(PermissionError, match="not a member"):
            MessageService.send_message(conv, outsider, "Should fail")

    def test_mark_as_read(self):
        from django_matt.messaging.models import MessageStatus
        from django_matt.messaging.services.message import MessageService

        conv, users = self._make_conversation_with_members("s1", "r1")
        msg = MessageService.send_message(conv, users[0], "Read me")
        MessageService.mark_as_read(conv, users[1], up_to_message=msg)
        status = MessageStatus.objects.get(message=msg, user=users[1])
        assert status.status == DeliveryStatus.READ
        assert status.read_at is not None

    @pytest.mark.django_db(transaction=True)
    async def test_asend_message_async(self):
        from asgiref.sync import sync_to_async

        from django_matt.messaging.services.message import MessageService

        conv, users = await sync_to_async(self._make_conversation_with_members)(
            "async_s", "async_r"
        )
        msg = await MessageService.asend_message(conv, users[0], "Async hello")
        assert msg.content == "Async hello"
        assert msg.sender == users[0]

    @pytest.mark.django_db(transaction=True)
    async def test_amark_as_read_async(self):
        from asgiref.sync import sync_to_async

        from django_matt.messaging.services.message import MessageService

        conv, users = await sync_to_async(self._make_conversation_with_members)(
            "as_s2", "as_r2"
        )
        msg = await MessageService.asend_message(conv, users[0], "Read async")
        await MessageService.amark_as_read(conv, users[1], up_to_message=msg)

        from django_matt.messaging.models import MessageStatus

        status = await sync_to_async(MessageStatus.objects.get)(
            message=msg, user=users[1]
        )
        assert status.status == DeliveryStatus.READ


class TestPresenceManagerReverseIndex:
    """Tests for the PresenceManager reverse index."""

    @pytest.fixture
    def presence(self):
        from django_matt.websockets.groups import PresenceManager

        return PresenceManager()

    @pytest.mark.asyncio
    async def test_user_joined_updates_reverse_index(self, presence):
        await presence.user_joined("room_a", "user1", "ch1")
        groups = await presence.get_user_groups("user1")
        assert "room_a" in groups

    @pytest.mark.asyncio
    async def test_user_left_removes_from_reverse_index(self, presence):
        await presence.user_joined("room_b", "user2", "ch2")
        groups = await presence.get_user_groups("user2")
        assert "room_b" in groups
        await presence.user_left("room_b", "user2")
        groups = await presence.get_user_groups("user2")
        assert groups == []

    @pytest.mark.asyncio
    async def test_multiple_groups(self, presence):
        await presence.user_joined("grp1", "user3", "ch3")
        await presence.user_joined("grp2", "user3", "ch3")
        await presence.user_joined("grp3", "user3", "ch3")
        groups = await presence.get_user_groups("user3")
        assert set(groups) == {"grp1", "grp2", "grp3"}
