"""
Admin for DeadLetterTask model.
"""

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from ..models import DeadLetterTask

try:
    from unfold.admin import ModelAdmin
    from unfold.decorators import action

    UNFOLD_AVAILABLE = True
except ImportError:
    from django.contrib.admin import ModelAdmin

    UNFOLD_AVAILABLE = False

    def action(description: str = "", **kwargs):
        def decorator(func):
            func.short_description = description
            return func

        return decorator


class DeadLetterTaskAdmin(ModelAdmin):
    """Admin for dead letter queue tasks."""

    list_display = [
        "task_name_display",
        "error_preview",
        "retry_count_display",
        "created_at",
        "reprocessed_badge",
    ]
    list_filter = ["reprocessed", "task_name", "created_at"]
    search_fields = ["task_name", "error"]
    readonly_fields = [
        "task_execution",
        "task_name",
        "args_json",
        "kwargs_json",
        "error",
        "traceback_display",
        "retry_count",
        "max_retries",
        "created_at",
        "reprocessed_at",
        "reprocessed",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        (
            "Task Information",
            {
                "fields": ("task_execution", "task_name"),
            },
        ),
        (
            "Arguments",
            {
                "fields": ("args_json", "kwargs_json"),
                "classes": ("collapse",),
            },
        ),
        (
            "Error Details",
            {
                "fields": ("error", "traceback_display"),
            },
        ),
        (
            "Retry Information",
            {
                "fields": ("retry_count", "max_retries"),
            },
        ),
        (
            "Status",
            {
                "fields": ("created_at", "reprocessed", "reprocessed_at"),
            },
        ),
    )

    actions = ["reprocess_tasks"]

    def task_name_display(self, obj: DeadLetterTask) -> str:
        """Display shortened task name."""
        parts = obj.task_name.split(".")
        if len(parts) > 2:
            return f"...{'.'.join(parts[-2:])}"
        return obj.task_name

    task_name_display.short_description = "Task"

    def error_preview(self, obj: DeadLetterTask) -> str:
        """Display error preview."""
        if len(obj.error) > 60:
            return obj.error[:60] + "..."
        return obj.error

    error_preview.short_description = "Error"

    def retry_count_display(self, obj: DeadLetterTask) -> str:
        """Display retry count."""
        return f"{obj.retry_count}/{obj.max_retries}"

    retry_count_display.short_description = "Retries"

    def reprocessed_badge(self, obj: DeadLetterTask) -> str:
        """Display reprocessed status as badge."""
        if obj.reprocessed:
            return format_html(
                '<span class="px-2 py-1 text-xs font-medium rounded-full '
                'bg-green-100 text-green-800">Reprocessed</span>'
            )
        return format_html(
            '<span class="px-2 py-1 text-xs font-medium rounded-full '
            'bg-yellow-100 text-yellow-800">Pending</span>'
        )

    reprocessed_badge.short_description = "Status"

    def traceback_display(self, obj: DeadLetterTask) -> str:
        """Display traceback in formatted block."""
        if not obj.traceback:
            return "-"
        return format_html(
            '<pre style="background: #1e1e1e; color: #d4d4d4; padding: 1rem; '
            'border-radius: 0.5rem; overflow-x: auto; font-size: 0.75rem;">{}</pre>',
            obj.traceback,
        )

    traceback_display.short_description = "Traceback"

    @action(description="Reprocess selected tasks")
    def reprocess_tasks(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Reprocess dead letter tasks."""
        reprocessed = 0
        for dlq_task in queryset.filter(reprocessed=False):
            try:
                dlq_task.reprocess()
                reprocessed += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to reprocess {dlq_task.task_name}: {e}",
                    messages.ERROR,
                )

        if reprocessed:
            self.message_user(request, f"Reprocessed {reprocessed} tasks.", messages.SUCCESS)
