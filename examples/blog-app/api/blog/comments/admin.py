"""Admin configuration for comments app."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from blog.comments.models import Comment


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ["display_name", "post", "is_approved", "parent", "created_at"]
    list_filter = ["is_approved", "created_at"]
    search_fields = ["content", "author__email", "author_name", "author_email"]
    raw_id_fields = ["post", "author", "parent"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["approve_comments", "unapprove_comments"]

    @admin.action(description="Approve selected comments")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Unapprove selected comments")
    def unapprove_comments(self, request, queryset):
        queryset.update(is_approved=False)
