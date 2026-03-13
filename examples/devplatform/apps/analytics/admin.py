from django.contrib import admin

from apps.analytics.models import DailyMetric, UsageRecord


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["metric_name", "value", "project", "recorded_at"]
    list_filter = ["metric_name", "project"]
    search_fields = ["metric_name"]
    readonly_fields = ["id", "recorded_at"]
    ordering = ["-recorded_at"]


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = [
        "project",
        "date",
        "total_requests",
        "failed_requests",
        "avg_response_time_ms",
        "unique_ips",
    ]
    list_filter = ["project", "date"]
    readonly_fields = ["id"]
    ordering = ["-date"]
