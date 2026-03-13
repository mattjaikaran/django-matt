from django.contrib import admin

from apps.stores.models import Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "is_active", "rating", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ["owner"]
    readonly_fields = ["id", "created_at", "updated_at"]
