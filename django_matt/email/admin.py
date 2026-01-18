"""
Django admin configuration for email models.
"""

from django.contrib import admin
from django.utils.html import format_html

from django_matt.email.models import (
    EmailEvent,
    EmailMessage,
    EmailTemplate,
    SuppressedEmail,
)


class EmailEventInline(admin.TabularInline):
    """Inline for email events."""

    model = EmailEvent
    extra = 0
    readonly_fields = (
        "event_type",
        "occurred_at",
        "ip_address",
        "user_agent",
        "url",
    )
    can_delete = False


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    """Admin for EmailMessage model."""

    list_display = (
        "id",
        "recipients_display",
        "subject_preview",
        "status_badge",
        "provider",
        "sent_at",
        "created_at",
    )
    list_filter = (
        "status",
        "email_type",
        "provider",
        "category",
        "created_at",
        "sent_at",
    )
    search_fields = (
        "subject",
        "to_emails",
        "from_email",
        "tracking_id",
        "provider_message_id",
    )
    readonly_fields = (
        "tracking_id",
        "provider_message_id",
        "created_at",
        "sent_at",
        "delivered_at",
    )
    raw_id_fields = ("user",)
    inlines = [EmailEventInline]
    date_hierarchy = "created_at"

    @admin.display(description="To")
    def recipients_display(self, obj):
        """Display recipients."""
        recipients = obj.to_emails
        if len(recipients) == 1:
            return recipients[0]
        return f"{recipients[0]} (+{len(recipients) - 1})"

    @admin.display(description="Subject")
    def subject_preview(self, obj):
        """Display truncated subject."""
        subject = obj.subject
        if len(subject) > 50:
            return subject[:50] + "..."
        return subject

    @admin.display(description="Status")
    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            "pending": "#6c757d",
            "queued": "#17a2b8",
            "sent": "#007bff",
            "delivered": "#28a745",
            "opened": "#20c997",
            "clicked": "#198754",
            "bounced": "#dc3545",
            "complained": "#dc3545",
            "failed": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    actions = ["resend_emails", "mark_as_sent"]

    @admin.action(description="Resend selected emails")
    def resend_emails(self, request, queryset):

        count = 0
        for email in queryset:
            if email.status in ["failed", "bounced"]:
                email.status = "pending"
                email.retry_count = 0
                email.error_message = ""
                email.save()
                count += 1

        self.message_user(request, f"Queued {count} emails for resend")


@admin.register(EmailEvent)
class EmailEventAdmin(admin.ModelAdmin):
    """Admin for EmailEvent model."""

    list_display = (
        "id",
        "email",
        "event_type",
        "occurred_at",
        "ip_address",
    )
    list_filter = (
        "event_type",
        "occurred_at",
    )
    raw_id_fields = ("email",)
    readonly_fields = ("created_at",)
    date_hierarchy = "occurred_at"


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin for EmailTemplate model."""

    list_display = (
        "name",
        "subject_preview",
        "email_type",
        "category",
        "is_active",
        "version",
        "updated_at",
    )
    list_filter = (
        "email_type",
        "is_active",
        "category",
    )
    search_fields = (
        "name",
        "subject",
        "description",
    )
    readonly_fields = ("created_at", "updated_at", "version")
    raw_id_fields = ("created_by",)

    @admin.display(description="Subject")
    def subject_preview(self, obj):
        """Display truncated subject."""
        subject = obj.subject
        if len(subject) > 40:
            return subject[:40] + "..."
        return subject

    fieldsets = (
        (None, {
            "fields": ("name", "description", "is_active"),
        }),
        ("Content", {
            "fields": ("subject", "html_body", "text_body"),
        }),
        ("Settings", {
            "fields": ("email_type", "category", "variables", "default_context"),
        }),
        ("Metadata", {
            "fields": ("version", "created_at", "updated_at", "created_by"),
            "classes": ("collapse",),
        }),
    )


@admin.register(SuppressedEmail)
class SuppressedEmailAdmin(admin.ModelAdmin):
    """Admin for SuppressedEmail model."""

    list_display = (
        "email",
        "reason",
        "bounce_type",
        "created_at",
        "expires_at",
    )
    list_filter = (
        "reason",
        "bounce_type",
        "created_at",
    )
    search_fields = ("email",)
    raw_id_fields = ("source_email",)
    readonly_fields = ("created_at",)

    actions = ["remove_suppression"]

    @admin.action(description="Remove selected suppressions")
    def remove_suppression(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Removed {count} suppressions")
