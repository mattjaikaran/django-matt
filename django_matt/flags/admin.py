"""
Django admin configuration for feature flags.

Provides admin interface for managing feature flags and overrides.

Usage:
    # In your admin.py or by importing from django_matt.flags.admin
    from django_matt.flags.admin import FeatureFlagAdmin, FlagOverrideAdmin

    # They are auto-registered when this module is imported
"""

from django.contrib import admin
from django.utils.html import format_html

# Check if Unfold is available
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.admin import TabularInline as UnfoldTabularInline

    HAS_UNFOLD = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin  # type: ignore
    UnfoldTabularInline = admin.TabularInline  # type: ignore
    HAS_UNFOLD = False


class FlagOverrideInline(UnfoldTabularInline):
    """Inline admin for flag overrides."""

    model = None  # Set dynamically
    extra = 0
    readonly_fields = ["created_at", "created_by"]
    fields = ["override_type", "target_id", "target_value", "enabled", "variant", "expires_at"]

    def __init__(self, *args, **kwargs):
        from django_matt.flags.models import FlagOverride

        self.model = FlagOverride
        super().__init__(*args, **kwargs)


class FeatureFlagAdmin(UnfoldModelAdmin):
    """Admin for feature flags."""

    list_display = [
        "key",
        "name",
        "flag_type_badge",
        "status_badge",
        "enabled_by_default",
        "rollout_display",
        "override_count",
        "updated_at",
    ]
    list_filter = ["status", "flag_type", "enabled_by_default", "created_at"]
    search_fields = ["key", "name", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "created_by"]
    ordering = ["key"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            None,
            {
                "fields": ("key", "name", "description"),
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "flag_type",
                    "status",
                    "enabled_by_default",
                    "rollout_percentage",
                ),
            },
        ),
        (
            "Variants & Targeting",
            {
                "fields": ("variants", "targeting_rules"),
                "classes": ("collapse",),
            },
        ),
        (
            "Scheduling",
            {
                "fields": ("scheduled_enable_at", "scheduled_disable_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("metadata", "id", "created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [FlagOverrideInline]

    actions = ["enable_flags", "disable_flags", "archive_flags"]

    def flag_type_badge(self, obj):
        """Display flag type as a badge."""
        colors = {
            "boolean": "#10b981",  # Green
            "percentage": "#3b82f6",  # Blue
            "variant": "#8b5cf6",  # Purple
        }
        color = colors.get(obj.flag_type, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color,
            obj.flag_type,
        )

    flag_type_badge.short_description = "Type"
    flag_type_badge.admin_order_field = "flag_type"

    def status_badge(self, obj):
        """Display status as a badge."""
        colors = {
            "active": "#10b981",  # Green
            "inactive": "#6b7280",  # Gray
            "archived": "#ef4444",  # Red
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color,
            obj.status,
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def rollout_display(self, obj):
        """Display rollout percentage with progress bar."""
        if obj.flag_type != "percentage":
            return "-"

        percentage = obj.rollout_percentage
        return format_html(
            '<div style="width: 100px; background-color: #e5e7eb; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: #3b82f6; height: 16px; display: flex; '
            'align-items: center; justify-content: center; color: white; font-size: 11px;">'
            "{}%</div></div>",
            percentage,
            percentage,
        )

    rollout_display.short_description = "Rollout"

    def override_count(self, obj):
        """Display number of overrides."""
        count = obj.overrides.count()
        if count == 0:
            return "-"
        return format_html(
            '<span style="background-color: #f3f4f6; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{} override{}</span>',
            count,
            "s" if count != 1 else "",
        )

    override_count.short_description = "Overrides"

    def enable_flags(self, request, queryset):
        """Enable selected flags."""
        from django_matt.flags.models import FlagAuditLog, FlagStatus

        count = 0
        for flag in queryset:
            if flag.status != FlagStatus.ACTIVE.value:
                old_status = flag.status
                flag.status = FlagStatus.ACTIVE.value
                flag.save(update_fields=["status", "updated_at"])
                count += 1

                FlagAuditLog.log(
                    flag=flag,
                    action="enable",
                    old_values={"status": old_status},
                    new_values={"status": flag.status},
                    user=request.user,
                )

        self.message_user(request, f"Enabled {count} flag(s).")

    enable_flags.short_description = "Enable selected flags"

    def disable_flags(self, request, queryset):
        """Disable selected flags."""
        from django_matt.flags.models import FlagAuditLog, FlagStatus

        count = 0
        for flag in queryset:
            if flag.status != FlagStatus.INACTIVE.value:
                old_status = flag.status
                flag.status = FlagStatus.INACTIVE.value
                flag.save(update_fields=["status", "updated_at"])
                count += 1

                FlagAuditLog.log(
                    flag=flag,
                    action="disable",
                    old_values={"status": old_status},
                    new_values={"status": flag.status},
                    user=request.user,
                )

        self.message_user(request, f"Disabled {count} flag(s).")

    disable_flags.short_description = "Disable selected flags"

    def archive_flags(self, request, queryset):
        """Archive selected flags."""
        from django_matt.flags.models import FlagAuditLog, FlagStatus

        count = 0
        for flag in queryset:
            if flag.status != FlagStatus.ARCHIVED.value:
                old_status = flag.status
                flag.status = FlagStatus.ARCHIVED.value
                flag.save(update_fields=["status", "updated_at"])
                count += 1

                FlagAuditLog.log(
                    flag=flag,
                    action="archive",
                    old_values={"status": old_status},
                    new_values={"status": flag.status},
                    user=request.user,
                )

        self.message_user(request, f"Archived {count} flag(s).")

    archive_flags.short_description = "Archive selected flags"

    def save_model(self, request, obj, form, change):
        """Set created_by on new flags."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class FlagOverrideAdmin(UnfoldModelAdmin):
    """Admin for flag overrides."""

    list_display = [
        "flag",
        "override_type_badge",
        "target_display",
        "enabled_badge",
        "variant",
        "status_display",
        "created_at",
    ]
    list_filter = ["override_type", "enabled", "flag__key"]
    search_fields = ["flag__key", "target_id", "target_value"]
    readonly_fields = ["id", "created_at", "created_by"]
    autocomplete_fields = ["flag"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            None,
            {
                "fields": ("flag", "override_type"),
            },
        ),
        (
            "Target",
            {
                "fields": ("target_id", "target_value"),
            },
        ),
        (
            "Override",
            {
                "fields": ("enabled", "variant", "expires_at"),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def override_type_badge(self, obj):
        """Display override type as a badge."""
        colors = {
            "user": "#3b82f6",  # Blue
            "organization": "#10b981",  # Green
            "email": "#f59e0b",  # Amber
            "attribute": "#8b5cf6",  # Purple
        }
        color = colors.get(obj.override_type, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color,
            obj.override_type,
        )

    override_type_badge.short_description = "Type"
    override_type_badge.admin_order_field = "override_type"

    def target_display(self, obj):
        """Display target (ID or value)."""
        target = obj.target_id or obj.target_value
        if len(target) > 30:
            return target[:30] + "..."
        return target

    target_display.short_description = "Target"

    def enabled_badge(self, obj):
        """Display enabled status as a badge."""
        if obj.enabled:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 11px;">ENABLED</span>'
            )
        return format_html(
            '<span style="background-color: #ef4444; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">DISABLED</span>'
        )

    enabled_badge.short_description = "State"

    def status_display(self, obj):
        """Display active/expired status."""
        if obj.is_expired:
            return format_html('<span style="color: #ef4444; font-size: 11px;">Expired</span>')
        if obj.expires_at:
            return format_html(
                '<span style="color: #10b981; font-size: 11px;">Active until {}</span>',
                obj.expires_at.strftime("%Y-%m-%d"),
            )
        return format_html('<span style="color: #10b981; font-size: 11px;">Active</span>')

    status_display.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """Set created_by on new overrides."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class FlagAuditLogAdmin(UnfoldModelAdmin):
    """Admin for flag audit logs."""

    list_display = [
        "flag_key",
        "action_badge",
        "user",
        "ip_address",
        "created_at",
    ]
    list_filter = ["action", "created_at"]
    search_fields = ["flag_key", "user__email", "ip_address"]
    readonly_fields = [
        "id",
        "flag",
        "flag_key",
        "action",
        "changes",
        "old_values",
        "new_values",
        "user",
        "ip_address",
        "user_agent",
        "created_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            None,
            {
                "fields": ("flag", "flag_key", "action"),
            },
        ),
        (
            "Changes",
            {
                "fields": ("changes", "old_values", "new_values"),
            },
        ),
        (
            "Context",
            {
                "fields": ("user", "ip_address", "user_agent"),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at"),
            },
        ),
    )

    def action_badge(self, obj):
        """Display action as a badge."""
        colors = {
            "create": "#10b981",  # Green
            "update": "#3b82f6",  # Blue
            "delete": "#ef4444",  # Red
            "enable": "#10b981",  # Green
            "disable": "#6b7280",  # Gray
            "archive": "#f59e0b",  # Amber
            "add_override": "#8b5cf6",  # Purple
            "remove_override": "#f97316",  # Orange
        }
        color = colors.get(obj.action, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color,
            obj.action,
        )

    action_badge.short_description = "Action"
    action_badge.admin_order_field = "action"

    def has_add_permission(self, request):
        """Audit logs cannot be added manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs cannot be changed."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete audit logs."""
        return request.user.is_superuser


# Register models
def register_flag_admin(site=None):
    """Register feature flag admin classes."""
    from django_matt.flags.models import FeatureFlag, FlagAuditLog, FlagOverride

    target_site = site or admin.site

    if not target_site.is_registered(FeatureFlag):
        target_site.register(FeatureFlag, FeatureFlagAdmin)
    if not target_site.is_registered(FlagOverride):
        target_site.register(FlagOverride, FlagOverrideAdmin)
    if not target_site.is_registered(FlagAuditLog):
        target_site.register(FlagAuditLog, FlagAuditLogAdmin)


# Auto-register on import
try:
    register_flag_admin()
except Exception:
    # Models may not be ready yet
    pass


__all__ = [
    "FeatureFlagAdmin",
    "FlagOverrideAdmin",
    "FlagAuditLogAdmin",
    "FlagOverrideInline",
    "register_flag_admin",
]
