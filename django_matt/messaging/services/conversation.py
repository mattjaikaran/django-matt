"""
Conversation service.

Business logic for conversation operations.
"""

from django.db import transaction
from django.db.models import Count, Q

from django_matt.messaging.enums import ConversationType, MemberRole
from django_matt.messaging.models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
)


class ConversationService:
    """Service for managing conversations."""

    @staticmethod
    def get_user_conversations(user, include_archived=False):
        """
        Get all conversations for a user.

        Returns conversations with unread counts and last message info.
        """
        qs = Conversation.objects.filter(
            members__user=user,
            members__is_active=True,
        ).select_related("created_by")

        if not include_archived:
            qs = qs.exclude(Q(is_archived=True) | Q(members__settings__is_archived=True))

        # Annotate with unread count
        qs = qs.annotate(
            member_count=Count("members", filter=Q(members__is_active=True)),
        )

        return qs.order_by("-last_message_at", "-created_at")

    @staticmethod
    def get_conversation_with_unread_count(conversation, user):
        """Get a conversation with unread count for a specific user."""
        try:
            membership = ConversationMember.objects.get(
                conversation=conversation,
                user=user,
                is_active=True,
            )
        except ConversationMember.DoesNotExist:
            return None, 0

        # Count unread messages
        unread_filter = Q()
        if membership.last_read_message_id:
            unread_filter = Q(id__gt=membership.last_read_message_id)
        elif membership.last_read_at:
            unread_filter = Q(created_at__gt=membership.last_read_at)

        unread_count = conversation.messages.exclude(sender=user).filter(unread_filter).count()

        return conversation, unread_count

    @staticmethod
    @transaction.atomic
    def create_direct_conversation(user1, user2):
        """Create or get a direct conversation between two users."""
        return Conversation.objects.get_direct(user1, user2)

    @staticmethod
    @transaction.atomic
    def create_group_conversation(
        name,
        creator,
        members=None,
        description="",
        avatar="",
    ):
        """Create a group conversation."""
        conversation = Conversation.objects.create_group(
            name=name,
            creator=creator,
            members=members,
            description=description,
            avatar=avatar,
        )
        return conversation

    @staticmethod
    @transaction.atomic
    def create_channel(name, creator, description="", avatar=""):
        """Create a broadcast channel."""
        conversation = Conversation.objects.create(
            name=name,
            conversation_type=ConversationType.CHANNEL,
            created_by=creator,
            description=description,
            avatar=avatar,
        )

        ConversationMember.objects.create(
            conversation=conversation,
            user=creator,
            role=MemberRole.OWNER,
        )

        return conversation

    @staticmethod
    @transaction.atomic
    def add_members(conversation, users, added_by=None, role=MemberRole.MEMBER):
        """Add multiple members to a conversation."""
        added = []
        for user in users:
            member, created = conversation.add_member(
                user=user,
                role=role,
                added_by=added_by,
            )
            if created:
                added.append(member)
        return added

    @staticmethod
    @transaction.atomic
    def remove_member(conversation, user, removed_by=None):
        """Remove a member from a conversation."""
        return conversation.remove_member(user)

    @staticmethod
    @transaction.atomic
    def update_member_role(conversation, user, new_role, updated_by=None):
        """Update a member's role."""
        try:
            member = ConversationMember.objects.get(
                conversation=conversation,
                user=user,
                is_active=True,
            )
            member.role = new_role
            member.save(update_fields=["role"])
            return member
        except ConversationMember.DoesNotExist:
            return None

    @staticmethod
    def update_settings(member, **settings):
        """Update conversation settings for a member."""
        obj, _ = ConversationSettings.objects.get_or_create(member=member)

        for key, value in settings.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        obj.save()
        return obj

    @staticmethod
    def mute_conversation(member, until=None):
        """Mute a conversation for a member."""
        return ConversationService.update_settings(
            member,
            is_muted=True,
            muted_until=until,
        )

    @staticmethod
    def unmute_conversation(member):
        """Unmute a conversation for a member."""
        return ConversationService.update_settings(
            member,
            is_muted=False,
            muted_until=None,
        )

    @staticmethod
    def pin_conversation(member):
        """Pin a conversation for a member."""
        return ConversationService.update_settings(member, is_pinned=True)

    @staticmethod
    def unpin_conversation(member):
        """Unpin a conversation for a member."""
        return ConversationService.update_settings(member, is_pinned=False)

    @staticmethod
    def archive_conversation(member):
        """Archive a conversation for a member."""
        return ConversationService.update_settings(member, is_archived=True)

    @staticmethod
    def unarchive_conversation(member):
        """Unarchive a conversation for a member."""
        return ConversationService.update_settings(member, is_archived=False)

    @staticmethod
    @transaction.atomic
    def leave_conversation(conversation, user):
        """Leave a conversation."""
        return conversation.remove_member(user)

    @staticmethod
    @transaction.atomic
    def delete_conversation(conversation, deleted_by=None):
        """
        Delete a conversation.

        Only owners can delete. Soft deletes by archiving for all members.
        """
        conversation.is_archived = True
        conversation.save(update_fields=["is_archived", "updated_at"])
        return True

    @staticmethod
    def search_conversations(user, query):
        """Search conversations by name or member."""
        return Conversation.objects.filter(
            Q(name__icontains=query)
            | Q(members__user__email__icontains=query)
            | Q(members__user__first_name__icontains=query)
            | Q(members__user__last_name__icontains=query),
            members__user=user,
            members__is_active=True,
        ).distinct()
