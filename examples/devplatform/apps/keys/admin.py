from django.contrib import admin

from apps.keys.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "key_prefix", "project", "is_active", "created_by", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "key_prefix"]
    raw_id_fields = ["project", "created_by"]
    readonly_fields = ["id", "key_prefix", "key_hash", "created_at", "updated_at"]
    exclude = ["key_hash"]
