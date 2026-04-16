"""
Chat models for the real-time chat application.

Models:
- UserProfile: Extended user information
- Workspace: Container for channels (like Slack workspace)
- WorkspaceMembership: User membership in workspace
- Channel: Public or private channel within workspace
- ChannelMembership: User membership in channel
- DirectMessageThread: Direct message conversation between users
- Message: Chat message (in channel or DM)
- Reaction: Emoji reaction on a message
- ReadReceipt: Tracks when users read messages
- FileAttachment: File uploaded with messages
"""

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    pass


class UserProfile(models.Model):
    """Extended user profile for chat features."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_profile",
    )
    display_name = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("online", "Online"),
            ("away", "Away"),
            ("dnd", "Do Not Disturb"),
            ("offline", "Offline"),
        ],
        default="offline",
    )
    status_text = models.CharField(max_length=100, blank=True)
    last_seen = models.DateTimeField(auto_now=True)
    timezone = models.CharField(max_length=50, default="UTC")

    def __str__(self):
        return self.display_name or self.user.username

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class Workspace(models.Model):
    """
    Workspace container (like a Slack workspace).

    Contains channels and members.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_workspaces",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="WorkspaceMembership",
        through_fields=("workspace", "user"),
        related_name="workspaces",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class WorkspaceMembership(models.Model):
    """User membership in a workspace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=[
            ("owner", "Owner"),
            ("admin", "Admin"),
            ("member", "Member"),
            ("guest", "Guest"),
        ],
        default="member",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workspace_invitations_sent",
    )

    def __str__(self):
        return f"{self.user.username} in {self.workspace.name}"

    class Meta:
        unique_together = ["workspace", "user"]
        ordering = ["joined_at"]


class Channel(models.Model):
    """
    Channel within a workspace.

    Can be public (anyone in workspace can join) or private (invite-only).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="channels"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    topic = models.CharField(max_length=255, blank=True)
    is_private = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_channels",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ChannelMembership",
        related_name="channels",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        prefix = "#" if not self.is_private else "lock "
        return f"{prefix}{self.name}"

    class Meta:
        unique_together = ["workspace", "slug"]
        ordering = ["name"]


class ChannelMembership(models.Model):
    """User membership in a channel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_memberships",
    )
    is_muted = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    last_read_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.channel.name}"

    class Meta:
        unique_together = ["channel", "user"]
        ordering = ["joined_at"]


class DirectMessageThread(models.Model):
    """
    Direct message conversation between users.

    Can be between 2 or more users (group DM).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="dm_threads"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="dm_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        usernames = ", ".join(u.username for u in self.participants.all()[:3])
        return f"DM: {usernames}"

    class Meta:
        ordering = ["-updated_at"]


class Message(models.Model):
    """
    Chat message.

    Can be in a channel or direct message thread.
    Supports threading via parent_message.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Either channel or dm_thread is set, not both
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
    )
    dm_thread = models.ForeignKey(
        DirectMessageThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
    )

    # Author
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="messages",
    )

    # Content
    content = models.TextField()
    content_html = models.TextField(blank=True)  # Rendered HTML with mentions, etc.

    # Threading
    parent_message = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    reply_count = models.PositiveIntegerField(default=0)
    reply_users_count = models.PositiveIntegerField(default=0)

    # Mentions
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="mentioned_in_messages",
    )
    mentions_everyone = models.BooleanField(default=False)

    # Status
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        author_name = self.author.username if self.author else "Unknown"
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{author_name}: {content_preview}"

    def soft_delete(self):
        """Soft delete the message."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["channel", "created_at"]),
            models.Index(fields=["dm_thread", "created_at"]),
            models.Index(fields=["parent_message"]),
            models.Index(fields=["author", "created_at"]),
        ]


class Reaction(models.Model):
    """Emoji reaction on a message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    emoji = models.CharField(max_length=50)  # Emoji shortcode or unicode
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message"

    class Meta:
        unique_together = ["message", "user", "emoji"]
        ordering = ["created_at"]


class ReadReceipt(models.Model):
    """Tracks when a user has read messages in a channel/DM."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="read_receipts",
    )

    # Either channel or dm_thread
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="read_receipts",
    )
    dm_thread = models.ForeignKey(
        DirectMessageThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="read_receipts",
    )

    last_read_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="read_by",
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ("user", "channel"),
            ("user", "dm_thread"),
        ]


class FileAttachment(models.Model):
    """File uploaded and attached to messages."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="files"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_files",
    )

    # File info
    file = models.FileField(upload_to="chat/attachments/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()  # In bytes

    # Image-specific
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    thumbnail_url = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename

    class Meta:
        ordering = ["-created_at"]
