from django.contrib import admin

from apps.webhooks.models import Webhook, WebhookDelivery


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "url", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["url", "description"]
    readonly_fields = ["id", "secret", "created_at", "updated_at"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["id", "webhook", "event_type", "success", "status_code", "attempted_at"]
    list_filter = ["success", "event_type", "attempted_at"]
    readonly_fields = ["id", "attempted_at", "created_at", "updated_at"]
