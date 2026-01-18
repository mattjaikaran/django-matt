"""
Django admin configuration for messaging models.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from django_matt.messaging.models import (
    Attachment,
    Conversation,
    ConversationMember,
    ConversationSettings,
    Message,
    MessageEdit,
    MessageReaction,
    MessageStatus,
)


class ConversationMemberInline(admin.TabularInline):
    """Inline for conversation members."""

    model = ConversationMember
    extra = 0
    readonly_fields = ("joined_at",)
    raw_id_fields = ("user", "added_by")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin for Conversation model."""

    list_display = (
        "id",
        "name",
        "conversation_type",
        "member_count_display",
        "message_count_display",
        "last_message_at",
        "is_archived",
        "created_at",
    )
    list_filter = (
        "conversation_type",
        "is_archived",
        "is_locked",
        "created_at",
    )
    search_fields = (
        "name",
        "description",
        "members__user__email",
        "members__user__first_name",
        "members__user__last_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_message_at",
        "last_message_preview",
    )
    raw_id_fields = ("created_by",)
    inlines = [ConversationMemberInline]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        """Annotate with counts for display."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _member_count=Count("members", distinct=True),
            _message_count=Count("messages", distinct=True),
        )

    @admin.display(description="Members", ordering="_member_count")
    def member_count_display(self, obj):
        """Display member count."""
        return obj._member_count

    @admin.display(description="Messages", ordering="_message_count")
    def message_count_display(self, obj):
        """Display message count."""
        return obj._message_count


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    """Admin for ConversationMember model."""

    list_display = (
        "id",
        "user",
        "conversation",
        "role",
        "is_active",
        "joined_at",
    )
    list_filter = (
        "role",
        "is_active",
        "joined_at",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "conversation__name",
    )
    raw_id_fields = ("user", "conversation", "added_by")
    readonly_fields = ("joined_at", "last_read_at")


@admin.register(ConversationSettings)
class ConversationSettingsAdmin(admin.ModelAdmin):
    """Admin for ConversationSettings model."""

    list_display = (
        "id",
        "member",
        "is_muted",
        "is_pinned",
        "is_archived",
        "show_notifications",
    )
    list_filter = (
        "is_muted",
        "is_pinned",
        "is_archived",
        "show_notifications",
    )
    raw_id_fields = ("member",)


class MessageAttachmentInline(admin.TabularInline):
    """Inline for message attachments."""

    model = Attachment
    extra = 0
    readonly_fields = ("created_at", "file_size")


class MessageReactionInline(admin.TabularInline):
    """Inline for message reactions."""

    model = MessageReaction
    extra = 0
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)


class MessageEditInline(admin.TabularInline):
    """Inline for message edit history."""

    model = MessageEdit
    extra = 0
    readonly_fields = ("edited_at", "previous_content", "edited_by")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin for Message model."""

    list_display = (
        "id",
        "sender",
        "conversation",
        "message_type",
        "content_preview",
        "is_pinned",
        "is_edited",
        "is_deleted",
        "created_at",
    )
    list_filter = (
        "message_type",
        "is_pinned",
        "is_edited",
        "is_deleted",
        "created_at",
    )
    search_fields = (
        "content",
        "sender__email",
        "sender__first_name",
        "sender__last_name",
        "conversation__name",
    )
    raw_id_fields = (
        "conversation",
        "sender",
        "reply_to",
        "forwarded_from",
        "deleted_by",
        "pinned_by",
    )
    readonly_fields = (
        "created_at",
        "edited_at",
        "deleted_at",
        "pinned_at",
    )
    inlines = [MessageAttachmentInline, MessageReactionInline, MessageEditInline]
    date_hierarchy = "created_at"

    @admin.display(description="Content")
    def content_preview(self, obj):
        """Display truncated content."""
        if obj.is_deleted:
            return format_html('<span style="color: #999;">[Deleted]</span>')
        content = obj.content or ""
        if len(content) > 50:
            return content[:50] + "..."
        return content


@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    """Admin for MessageStatus model."""

    list_display = (
        "id",
        "message",
        "user",
        "status",
        "delivered_at",
        "read_at",
    )
    list_filter = (
        "status",
        "delivered_at",
        "read_at",
    )
    raw_id_fields = ("message", "user")
    readonly_fields = ("delivered_at", "read_at")


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    """Admin for MessageReaction model."""

    list_display = (
        "id",
        "message",
        "user",
        "emoji",
        "created_at",
    )
    list_filter = ("emoji", "created_at")
    search_fields = (
        "user__email",
        "emoji",
    )
    raw_id_fields = ("message", "user")
    readonly_fields = ("created_at",)


@admin.register(MessageEdit)
class MessageEditAdmin(admin.ModelAdmin):
    """Admin for MessageEdit model."""

    list_display = (
        "id",
        "message",
        "edited_by",
        "edited_at",
    )
    list_filter = ("edited_at",)
    raw_id_fields = ("message", "edited_by")
    readonly_fields = ("edited_at",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """Admin for Attachment model."""

    list_display = (
        "id",
        "original_filename",
        "attachment_type",
        "content_type",
        "file_size_display",
        "message",
        "created_at",
    )
    list_filter = (
        "attachment_type",
        "content_type",
        "created_at",
    )
    search_fields = (
        "original_filename",
        "filename",
        "message__content",
    )
    raw_id_fields = ("message", "uploaded_by")
    readonly_fields = ("created_at", "file_size", "width", "height", "duration")

    @admin.display(description="Size")
    def file_size_display(self, obj):
        """Display human-readable file size."""
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
