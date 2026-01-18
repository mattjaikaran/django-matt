"""
Message service.

Business logic for message operations.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from django_matt.messaging.enums import DeliveryStatus, MessageType
from django_matt.messaging.models import (
    ConversationMember,
    Message,
    MessageStatus,
)


class MessageService:
    """Service for managing messages."""

    @staticmethod
    @transaction.atomic
    def send_message(
        conversation,
        sender,
        content,
        message_type=MessageType.TEXT,
        reply_to=None,
        attachments=None,
        metadata=None,
    ):
        """
        Send a message to a conversation.

        Args:
            conversation: Target conversation
            sender: User sending the message
            content: Message content
            message_type: Type of message
            reply_to: Message being replied to
            attachments: List of attachment data
            metadata: Additional metadata

        Returns:
            Created message
        """
        # Verify sender is a member
        if not conversation.is_member(sender):
            raise PermissionError("User is not a member of this conversation")

        # Check if sender can send messages
        membership = ConversationMember.objects.get(
            conversation=conversation,
            user=sender,
            is_active=True,
        )
        if not membership.can_send_messages():
            raise PermissionError("User cannot send messages to this conversation")

        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            message_type=message_type,
            reply_to=reply_to,
            metadata=metadata or {},
        )

        # Create delivery statuses for all other members
        other_members = conversation.get_members().exclude(user=sender)
        statuses = [
            MessageStatus(
                message=message,
                user=member.user,
                status=DeliveryStatus.SENT,
            )
            for member in other_members
        ]
        MessageStatus.objects.bulk_create(statuses)

        return message

    @staticmethod
    def get_messages(
        conversation,
        user,
        cursor=None,
        limit=50,
        include_deleted=False,
    ):
        """
        Get messages for a conversation with pagination.

        Args:
            conversation: Target conversation
            user: User requesting messages
            cursor: Message ID to paginate from
            limit: Maximum messages to return
            include_deleted: Include deleted messages

        Returns:
            Queryset of messages
        """
        # Verify user is a member
        if not conversation.is_member(user):
            raise PermissionError("User is not a member of this conversation")

        qs = Message.objects.for_conversation(
            conversation,
            include_deleted=include_deleted,
        )

        if cursor:
            qs = qs.filter(id__lt=cursor)

        return qs.order_by("-created_at")[:limit]

    @staticmethod
    def get_pinned_messages(conversation, user):
        """Get pinned messages in a conversation."""
        if not conversation.is_member(user):
            raise PermissionError("User is not a member of this conversation")

        return Message.objects.filter(
            conversation=conversation,
            is_pinned=True,
        ).select_related("sender")

    @staticmethod
    @transaction.atomic
    def edit_message(message, new_content, edited_by):
        """
        Edit a message.

        Args:
            message: Message to edit
            new_content: New content
            edited_by: User editing the message

        Returns:
            Updated message
        """
        # Only sender can edit their own messages
        if message.sender != edited_by:
            raise PermissionError("Only the sender can edit this message")

        message.edit(new_content, edited_by)
        return message

    @staticmethod
    @transaction.atomic
    def delete_message(message, deleted_by):
        """
        Delete a message.

        Args:
            message: Message to delete
            deleted_by: User deleting the message

        Returns:
            Updated message
        """
        # Check permissions
        membership = ConversationMember.objects.filter(
            conversation=message.conversation,
            user=deleted_by,
            is_active=True,
        ).first()

        if not membership:
            raise PermissionError("User is not a member of this conversation")

        # Sender can delete their own messages
        # Moderators+ can delete any message
        if message.sender != deleted_by and not membership.can_moderate():
            raise PermissionError("User cannot delete this message")

        message.soft_delete(deleted_by)
        return message

    @staticmethod
    @transaction.atomic
    def forward_message(original_message, to_conversation, sender):
        """
        Forward a message to another conversation.

        Args:
            original_message: Message to forward
            to_conversation: Target conversation
            sender: User forwarding the message

        Returns:
            New forwarded message
        """
        # Verify sender is a member of target conversation
        if not to_conversation.is_member(sender):
            raise PermissionError("User is not a member of the target conversation")

        # Create forwarded message
        message = Message.objects.create(
            conversation=to_conversation,
            sender=sender,
            content=original_message.content,
            message_type=MessageType.FORWARD,
            forwarded_from=original_message,
            metadata={
                "original_sender": original_message.sender.id if original_message.sender else None,
                "original_conversation": original_message.conversation.id,
                "original_timestamp": original_message.created_at.isoformat(),
            },
        )

        return message

    @staticmethod
    def pin_message(message, user):
        """Pin a message."""
        membership = ConversationMember.objects.filter(
            conversation=message.conversation,
            user=user,
            is_active=True,
        ).first()

        if not membership or not membership.can_moderate():
            raise PermissionError("User cannot pin messages")

        message.pin()
        return message

    @staticmethod
    def unpin_message(message, user):
        """Unpin a message."""
        membership = ConversationMember.objects.filter(
            conversation=message.conversation,
            user=user,
            is_active=True,
        ).first()

        if not membership or not membership.can_moderate():
            raise PermissionError("User cannot unpin messages")

        message.unpin()
        return message

    @staticmethod
    @transaction.atomic
    def mark_as_read(conversation, user, up_to_message=None):
        """
        Mark messages as read.

        Args:
            conversation: Conversation to mark as read
            user: User marking as read
            up_to_message: Mark all messages up to this one as read
        """
        membership = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            is_active=True,
        ).first()

        if not membership:
            return

        # Update membership last read
        membership.mark_as_read(up_to_message)

        # Update message statuses
        statuses = MessageStatus.objects.filter(
            message__conversation=conversation,
            user=user,
            status__in=[DeliveryStatus.SENT, DeliveryStatus.DELIVERED],
        )

        if up_to_message:
            statuses = statuses.filter(message__id__lte=up_to_message.id)

        for status in statuses:
            status.mark_read()

    @staticmethod
    @transaction.atomic
    def mark_as_delivered(conversation, user):
        """Mark all messages as delivered for a user."""
        MessageStatus.objects.filter(
            message__conversation=conversation,
            user=user,
            status=DeliveryStatus.SENT,
        ).update(
            status=DeliveryStatus.DELIVERED,
            delivered_at=timezone.now(),
        )

    @staticmethod
    def add_reaction(message, user, emoji):
        """Add a reaction to a message."""
        if not message.conversation.is_member(user):
            raise PermissionError("User is not a member of this conversation")

        return message.add_reaction(user, emoji)

    @staticmethod
    def remove_reaction(message, user, emoji):
        """Remove a reaction from a message."""
        return message.remove_reaction(user, emoji)

    @staticmethod
    def search_messages(user, query, conversation=None, limit=50):
        """
        Search messages.

        Args:
            user: User searching
            query: Search query
            conversation: Specific conversation to search in
            limit: Maximum results

        Returns:
            Queryset of matching messages
        """
        return Message.objects.search(query, conversation, user)[:limit]

    @staticmethod
    def get_unread_counts(user):
        """
        Get unread message counts per conversation.

        Returns:
            Dict mapping conversation_id to unread count
        """
        memberships = ConversationMember.objects.filter(
            user=user,
            is_active=True,
        ).select_related("conversation")

        counts = {}
        for membership in memberships:
            unread_filter = Q()
            if membership.last_read_message_id:
                unread_filter = Q(id__gt=membership.last_read_message_id)
            elif membership.last_read_at:
                unread_filter = Q(created_at__gt=membership.last_read_at)

            count = (
                Message.objects.filter(
                    conversation=membership.conversation,
                )
                .exclude(sender=user)
                .filter(unread_filter)
                .count()
            )

            if count > 0:
                counts[membership.conversation.id] = count

        return counts
