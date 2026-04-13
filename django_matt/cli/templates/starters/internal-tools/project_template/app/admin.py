"""Admin configuration for {{ project_name }}."""

from django.contrib import admin

from .models import AuditEntry, FeatureFlag


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ["action", "resource_type", "user", "created_at"]
    list_filter = ["action", "resource_type", "created_at"]
    search_fields = ["resource_type", "resource_id"]
    readonly_fields = [
        "user",
        "action",
        "resource_type",
        "resource_id",
        "details",
        "ip_address",
        "created_at",
    ]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "rollout_percent", "updated_at"]
    list_filter = ["enabled"]
    search_fields = ["name", "description"]
    list_editable = ["enabled", "rollout_percent"]
