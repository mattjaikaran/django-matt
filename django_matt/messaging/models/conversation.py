"""
Conversation models.

Models for managing conversations and their members.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from django_matt.messaging.enums import ConversationType, MemberRole


class ConversationManager(models.Manager):
    """Custom manager for Conversation model."""

    def get_for_user(self, user):
        """Get all conversations for a user."""
        return self.filter(members__user=user, members__is_active=True)

    def get_direct(self, user1, user2):
        """Get or create a direct conversation between two users."""
        # Find existing direct conversation
        conversations = self.filter(
            conversation_type=ConversationType.DIRECT,
            members__user=user1,
        ).filter(members__user=user2)

        if conversations.exists():
            return conversations.first(), False

        # Create new direct conversation
        conversation = self.create(
            conversation_type=ConversationType.DIRECT,
        )
        ConversationMember.objects.create(
            conversation=conversation,
            user=user1,
            role=MemberRole.MEMBER,
        )
        ConversationMember.objects.create(
            conversation=conversation,
            user=user2,
            role=MemberRole.MEMBER,
        )
        return conversation, True

    def create_group(self, name, creator, members=None, **kwargs):
        """Create a group conversation."""
        conversation = self.create(
            name=name,
            conversation_type=ConversationType.GROUP,
            created_by=creator,
            **kwargs,
        )

        # Add creator as owner
        ConversationMember.objects.create(
            conversation=conversation,
            user=creator,
            role=MemberRole.OWNER,
        )

        # Add other members
        if members:
            for member in members:
                if member != creator:
                    ConversationMember.objects.create(
                        conversation=conversation,
                        user=member,
                        role=MemberRole.MEMBER,
                    )

        return conversation


class Conversation(models.Model):
    """
    Base conversation model.

    Supports direct messages, group chats, channels, and support tickets.
    """

    id = models.BigAutoField(primary_key=True)

    # Conversation details
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    avatar = models.URLField(blank=True, default="")

    # Type
    conversation_type = models.CharField(
        max_length=20,
        choices=[(t.value, t.name) for t in ConversationType],
        default=ConversationType.DIRECT,
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Activity tracking
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=255, blank=True, default="")

    # Settings
    is_archived = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)  # Prevent new messages

    # Custom manager
    objects = ConversationManager()

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["conversation_type"]),
            models.Index(fields=["last_message_at"]),
            models.Index(fields=["created_by"]),
        ]

    def __str__(self):
        if self.name:
            return self.name
        if self.conversation_type == ConversationType.DIRECT:
            members = list(self.members.values_list("user__email", flat=True)[:2])
            return f"DM: {' & '.join(members)}"
        return f"Conversation #{self.id}"

    def update_last_message(self, message):
        """Update last message info for the conversation."""
        self.last_message_at = message.created_at
        preview = message.content[:100] if message.content else ""
        if message.attachments.exists():
            preview = preview or "[Attachment]"
        self.last_message_preview = preview
        self.save(update_fields=["last_message_at", "last_message_preview", "updated_at"])

    def add_member(self, user, role=MemberRole.MEMBER, added_by=None):
        """Add a member to the conversation."""
        member, created = ConversationMember.objects.get_or_create(
            conversation=self,
            user=user,
            defaults={"role": role, "added_by": added_by},
        )
        if not created and not member.is_active:
            member.is_active = True
            member.role = role
            member.save()
        return member, created

    def remove_member(self, user):
        """Remove a member from the conversation (soft delete)."""
        try:
            member = self.members.get(user=user)
            member.is_active = False
            member.left_at = timezone.now()
            member.save()
            return True
        except ConversationMember.DoesNotExist:
            return False

    def get_members(self, active_only=True):
        """Get conversation members."""
        qs = self.members.select_related("user")
        if active_only:
            qs = qs.filter(is_active=True)
        return qs

    def is_member(self, user):
        """Check if user is an active member."""
        return self.members.filter(user=user, is_active=True).exists()

    async def ais_member(self, user) -> bool:
        """Async wrapper for is_member using sync_to_async."""
        from asgiref.sync import sync_to_async

        return await sync_to_async(self.is_member)(user)

    def get_member_role(self, user):
        """Get user's role in the conversation."""
        try:
            member = self.members.get(user=user, is_active=True)
            return member.role
        except ConversationMember.DoesNotExist:
            return None


class ConversationMember(models.Model):
    """
    Membership model for conversations.

    Tracks who is in each conversation with their role and settings.
    """

    id = models.BigAutoField(primary_key=True)

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_memberships",
    )

    # Role
    role = models.CharField(
        max_length=20,
        choices=[(r.value, r.name) for r in MemberRole],
        default=MemberRole.MEMBER,
    )

    # Membership tracking
    joined_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_members",
    )
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Read tracking
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_message_id = models.BigIntegerField(null=True, blank=True)

    # Nickname (for display in this conversation)
    nickname = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        unique_together = ["conversation", "user"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["conversation", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.conversation}"

    def mark_as_read(self, message=None):
        """Mark conversation as read up to a specific message."""
        self.last_read_at = timezone.now()
        if message:
            self.last_read_message_id = message.id
        self.save(update_fields=["last_read_at", "last_read_message_id"])

    def can_send_messages(self):
        """Check if member can send messages."""
        if not self.is_active:
            return False
        if self.conversation.is_locked:
            return self.role in (MemberRole.OWNER, MemberRole.ADMIN)
        if self.role == MemberRole.GUEST:
            return False  # Guests are read-only
        return True

    def can_manage_members(self):
        """Check if member can add/remove members."""
        return self.role in (MemberRole.OWNER, MemberRole.ADMIN)

    def can_moderate(self):
        """Check if member can moderate (delete messages, etc.)."""
        return self.role in (MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MODERATOR)


class ConversationSettings(models.Model):
    """
    Per-user settings for a conversation.

    Stores user preferences like mute status, pinned state, etc.
    """

    id = models.BigAutoField(primary_key=True)

    member = models.OneToOneField(
        ConversationMember,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    # Notification settings
    is_muted = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)

    # Organization
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    # Display settings
    show_notifications = models.BooleanField(default=True)
    notification_sound = models.CharField(max_length=50, blank=True, default="default")

    # Custom
    custom_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Conversation settings"

    def __str__(self):
        return f"Settings for {self.member}"

    def is_currently_muted(self):
        """Check if conversation is currently muted."""
        if not self.is_muted:
            return False
        if self.muted_until and self.muted_until < timezone.now():
            # Mute expired
            self.is_muted = False
            self.muted_until = None
            self.save(update_fields=["is_muted", "muted_until"])
            return False
        return True
