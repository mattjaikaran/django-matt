"""
Message models.

Models for messages, reactions, edits, and delivery status.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from django_matt.messaging.enums import DeliveryStatus, MessageType


class MessageManager(models.Manager):
    """Custom manager for Message model."""

    def for_conversation(self, conversation, include_deleted=False):
        """Get messages for a conversation."""
        qs = self.filter(conversation=conversation)
        if not include_deleted:
            qs = qs.exclude(message_type=MessageType.DELETED)
        return qs.select_related("sender", "reply_to").prefetch_related("attachments")

    def unread_for_user(self, user, conversation=None):
        """Get unread messages for a user."""
        from django_matt.messaging.models.conversation import ConversationMember

        # Get user's memberships with last read info
        memberships = ConversationMember.objects.filter(
            user=user,
            is_active=True,
        )

        if conversation:
            memberships = memberships.filter(conversation=conversation)

        unread_messages = self.none()

        for membership in memberships:
            qs = self.filter(conversation=membership.conversation).exclude(sender=user)

            if membership.last_read_message_id:
                qs = qs.filter(id__gt=membership.last_read_message_id)
            elif membership.last_read_at:
                qs = qs.filter(created_at__gt=membership.last_read_at)

            unread_messages = unread_messages | qs

        return unread_messages.distinct()

    def search(self, query, conversation=None, user=None):
        """Search messages by content."""
        qs = self.filter(content__icontains=query)

        if conversation:
            qs = qs.filter(conversation=conversation)

        if user:
            # Only search in user's conversations
            qs = qs.filter(conversation__members__user=user, conversation__members__is_active=True)

        return qs.select_related("sender", "conversation")


class Message(models.Model):
    """
    Core message model.

    Supports various message types including text, attachments, replies, and forwards.
    """

    id = models.BigAutoField(primary_key=True)

    conversation = models.ForeignKey(
        "django_matt.Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_messages",
    )

    # Content
    content = models.TextField(blank=True, default="")
    message_type = models.CharField(
        max_length=20,
        choices=[(t.value, t.name) for t in MessageType],
        default=MessageType.TEXT,
    )

    # Reply/Forward
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    forwarded_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forwards",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Flags
    is_pinned = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Custom manager
    objects = MessageManager()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["message_type"]),
            models.Index(fields=["is_pinned"]),
        ]

    def __str__(self):
        preview = self.content[:50] if self.content else f"[{self.message_type}]"
        return f"{self.sender}: {preview}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            # Update conversation's last message
            self.conversation.update_last_message(self)

    def edit(self, new_content, edited_by=None):
        """Edit the message content."""
        if self.message_type == MessageType.DELETED:
            raise ValueError("Cannot edit deleted message")

        # Save edit history
        MessageEdit.objects.create(
            message=self,
            previous_content=self.content,
            edited_by=edited_by or self.sender,
        )

        self.content = new_content
        self.is_edited = True
        self.edited_at = timezone.now()
        self.save(update_fields=["content", "is_edited", "edited_at", "updated_at"])

    def soft_delete(self, deleted_by=None):
        """Soft delete the message."""
        self.message_type = MessageType.DELETED
        self.content = ""
        self.deleted_at = timezone.now()
        self.metadata["deleted_by"] = deleted_by.id if deleted_by else None
        self.save(update_fields=["message_type", "content", "deleted_at", "metadata", "updated_at"])

    def pin(self):
        """Pin the message."""
        self.is_pinned = True
        self.save(update_fields=["is_pinned", "updated_at"])

    def unpin(self):
        """Unpin the message."""
        self.is_pinned = False
        self.save(update_fields=["is_pinned", "updated_at"])

    def add_reaction(self, user, emoji):
        """Add a reaction to the message."""
        reaction, created = MessageReaction.objects.get_or_create(
            message=self,
            user=user,
            emoji=emoji,
        )
        return reaction, created

    def remove_reaction(self, user, emoji):
        """Remove a reaction from the message."""
        return (
            MessageReaction.objects.filter(
                message=self,
                user=user,
                emoji=emoji,
            ).delete()[0]
            > 0
        )

    def get_reactions_summary(self):
        """Get summary of reactions grouped by emoji."""
        from django.db.models import Count

        return self.reactions.values("emoji").annotate(count=Count("id")).order_by("-count")


class MessageStatus(models.Model):
    """
    Delivery status tracking for messages.

    Tracks sent/delivered/read status per recipient.
    """

    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="statuses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_statuses",
    )

    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name) for s in DeliveryStatus],
        default=DeliveryStatus.SENT,
    )

    # Timestamps for each status
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["message", "user"]
        verbose_name_plural = "Message statuses"
        indexes = [
            models.Index(fields=["message", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.message_id} -> {self.user}: {self.status}"

    def mark_delivered(self):
        """Mark message as delivered."""
        if self.status == DeliveryStatus.SENT:
            self.status = DeliveryStatus.DELIVERED
            self.delivered_at = timezone.now()
            self.save(update_fields=["status", "delivered_at"])

    def mark_read(self):
        """Mark message as read."""
        if self.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED):
            self.status = DeliveryStatus.READ
            self.read_at = timezone.now()
            if not self.delivered_at:
                self.delivered_at = self.read_at
            self.save(update_fields=["status", "delivered_at", "read_at"])


class MessageReaction(models.Model):
    """
    Emoji reactions on messages.
    """

    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions",
    )
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["message", "user", "emoji"]
        indexes = [
            models.Index(fields=["message", "emoji"]),
        ]

    def __str__(self):
        return f"{self.user} reacted {self.emoji} to {self.message_id}"


class MessageEdit(models.Model):
    """
    Edit history for messages.
    """

    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="edit_history",
    )
    previous_content = models.TextField()
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]

    def __str__(self):
        return f"Edit of {self.message_id} at {self.edited_at}"
