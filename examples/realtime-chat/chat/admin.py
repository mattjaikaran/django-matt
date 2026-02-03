"""Django admin configuration for chat models."""

from django.contrib import admin

from .models import (
    Channel,
    ChannelMembership,
    DirectMessageThread,
    FileAttachment,
    Message,
    Reaction,
    ReadReceipt,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "display_name", "status", "last_seen"]
    list_filter = ["status"]
    search_fields = ["user__username", "user__email", "display_name"]


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    raw_id_fields = ["user", "invited_by"]


class ChannelInline(admin.TabularInline):
    model = Channel
    extra = 0
    fields = ["name", "slug", "is_private", "is_archived"]
    readonly_fields = ["slug"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "slug"]
    raw_id_fields = ["owner"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [WorkspaceMembershipInline, ChannelInline]


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "workspace", "role", "joined_at"]
    list_filter = ["role", "joined_at"]
    search_fields = ["user__username", "workspace__name"]
    raw_id_fields = ["workspace", "user", "invited_by"]


class ChannelMembershipInline(admin.TabularInline):
    model = ChannelMembership
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "is_private", "is_archived", "created_at"]
    list_filter = ["is_private", "is_archived", "created_at"]
    search_fields = ["name", "workspace__name"]
    raw_id_fields = ["workspace", "created_by"]
    inlines = [ChannelMembershipInline]


@admin.register(ChannelMembership)
class ChannelMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "channel", "is_muted", "joined_at"]
    list_filter = ["is_muted", "joined_at"]
    search_fields = ["user__username", "channel__name"]
    raw_id_fields = ["channel", "user"]


@admin.register(DirectMessageThread)
class DirectMessageThreadAdmin(admin.ModelAdmin):
    list_display = ["id", "workspace", "created_at", "updated_at"]
    list_filter = ["created_at"]
    search_fields = ["workspace__name"]
    raw_id_fields = ["workspace"]
    filter_horizontal = ["participants"]


class ReactionInline(admin.TabularInline):
    model = Reaction
    extra = 0
    raw_id_fields = ["user"]


class FileAttachmentInline(admin.TabularInline):
    model = FileAttachment
    extra = 0
    raw_id_fields = ["uploaded_by"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "short_content",
        "author",
        "channel",
        "is_edited",
        "is_deleted",
        "created_at",
    ]
    list_filter = ["is_edited", "is_deleted", "created_at"]
    search_fields = ["content", "author__username"]
    raw_id_fields = ["channel", "dm_thread", "author", "parent_message"]
    filter_horizontal = ["mentioned_users"]
    inlines = [ReactionInline, FileAttachmentInline]

    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    short_content.short_description = "Content"


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ["message", "user", "emoji", "created_at"]
    list_filter = ["emoji", "created_at"]
    search_fields = ["user__username", "emoji"]
    raw_id_fields = ["message", "user"]


@admin.register(ReadReceipt)
class ReadReceiptAdmin(admin.ModelAdmin):
    list_display = ["user", "channel", "dm_thread", "last_read_at"]
    list_filter = ["last_read_at"]
    search_fields = ["user__username"]
    raw_id_fields = ["user", "channel", "dm_thread", "last_read_message"]


@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "mime_type", "file_size", "uploaded_by", "created_at"]
    list_filter = ["mime_type", "created_at"]
    search_fields = ["original_filename", "uploaded_by__username"]
    raw_id_fields = ["message", "workspace", "uploaded_by"]
