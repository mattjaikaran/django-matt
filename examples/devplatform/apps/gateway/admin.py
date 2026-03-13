from django.contrib import admin

from apps.gateway.models import RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ["method", "path", "status_code", "response_time_ms", "created_at"]
    list_filter = ["method", "status_code", "project"]
    search_fields = ["path", "error_message"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
