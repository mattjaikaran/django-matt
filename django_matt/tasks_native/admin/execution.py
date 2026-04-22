"""
Admin for TaskExecution model.
"""

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..models import TaskExecution
from ..types import TaskState
from .filters import QueueFilter, StateFilter, TaskNameFilter

try:
    from unfold.admin import ModelAdmin
    from unfold.decorators import action

    UNFOLD_AVAILABLE = True
except ImportError:
    from django.contrib.admin import ModelAdmin

    UNFOLD_AVAILABLE = False

    def action(description: str = "", **kwargs):
        """Fallback decorator when Unfold not available."""

        def decorator(func):
            func.short_description = description
            return func

        return decorator


class TaskExecutionAdmin(ModelAdmin):
    """Admin for task executions with Unfold integration."""

    list_display = [
        "task_id_short",
        "task_name_display",
        "state_badge",
        "queue",
        "duration_display",
        "retries_display",
        "created_at",
    ]
    list_filter = [StateFilter, QueueFilter, TaskNameFilter, "created_at"]
    search_fields = ["task_id", "task_name", "error"]
    readonly_fields = [
        "task_id",
        "task_name",
        "state",
        "queue",
        "priority",
        "args_json",
        "kwargs_json",
        "result_json",
        "error",
        "traceback_display",
        "worker_id",
        "retries",
        "max_retries",
        "created_at",
        "queued_at",
        "started_at",
        "completed_at",
        "expires_at",
        "duration_display",
        "wait_time_display",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        (
            "Task Information",
            {
                "fields": (
                    "task_id",
                    "task_name",
                    "state",
                    "queue",
                    "priority",
                )
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
            "Result",
            {
                "fields": ("result_json",),
                "classes": ("collapse",),
            },
        ),
        (
            "Error Details",
            {
                "fields": ("error", "traceback_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Execution",
            {
                "fields": (
                    "worker_id",
                    "retries",
                    "max_retries",
                ),
            },
        ),
        (
            "Timing",
            {
                "fields": (
                    "created_at",
                    "queued_at",
                    "started_at",
                    "completed_at",
                    "expires_at",
                    "duration_display",
                    "wait_time_display",
                ),
            },
        ),
    )

    actions = ["retry_tasks", "cancel_tasks", "purge_completed"]

    def task_id_short(self, obj: TaskExecution) -> str:
        """Display shortened task ID."""
        return obj.task_id[:8] + "..."

    task_id_short.short_description = "Task ID"

    def task_name_display(self, obj: TaskExecution) -> str:
        """Display task name with module path."""
        parts = obj.task_name.split(".")
        if len(parts) > 2:
            return f"...{'.'.join(parts[-2:])}"
        return obj.task_name

    task_name_display.short_description = "Task"

    def state_badge(self, obj: TaskExecution) -> str:
        """Display state as colored badge."""
        colors = {
            TaskState.PENDING.value: "bg-yellow-100 text-yellow-800",
            TaskState.QUEUED.value: "bg-blue-100 text-blue-800",
            TaskState.RUNNING.value: "bg-indigo-100 text-indigo-800",
            TaskState.COMPLETED.value: "bg-green-100 text-green-800",
            TaskState.FAILED.value: "bg-red-100 text-red-800",
            TaskState.RETRYING.value: "bg-orange-100 text-orange-800",
            TaskState.CANCELLED.value: "bg-gray-100 text-gray-800",
            TaskState.DEAD_LETTER.value: "bg-purple-100 text-purple-800",
        }
        color = colors.get(obj.state, "bg-gray-100 text-gray-800")
        return format_html(
            '<span class="px-2 py-1 text-xs font-medium rounded-full {}">{}</span>',
            color,
            obj.state.upper(),
        )

    state_badge.short_description = "State"

    def duration_display(self, obj: TaskExecution) -> str:
        """Display task duration."""
        duration = obj.duration_ms
        if duration is None:
            return "-"
        if duration < 1000:
            return f"{duration:.0f}ms"
        return f"{duration / 1000:.2f}s"

    duration_display.short_description = "Duration"

    def wait_time_display(self, obj: TaskExecution) -> str:
        """Display queue wait time."""
        wait_time = obj.wait_time_ms
        if wait_time is None:
            return "-"
        if wait_time < 1000:
            return f"{wait_time:.0f}ms"
        return f"{wait_time / 1000:.2f}s"

    wait_time_display.short_description = "Wait Time"

    def retries_display(self, obj: TaskExecution) -> str:
        """Display retries as x/max."""
        return f"{obj.retries}/{obj.max_retries}"

    retries_display.short_description = "Retries"

    def traceback_display(self, obj: TaskExecution) -> str:
        """Display traceback in formatted block."""
        if not obj.traceback:
            return "-"
        return format_html(
            '<pre style="background: #1e1e1e; color: #d4d4d4; padding: 1rem; '
            'border-radius: 0.5rem; overflow-x: auto; font-size: 0.75rem;">{}</pre>',
            obj.traceback,
        )

    traceback_display.short_description = "Traceback"

    @action(description="Retry selected tasks")
    def retry_tasks(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Retry failed tasks."""
        from ..registry import task_registry

        retried = 0
        for execution in queryset.filter(state=TaskState.FAILED.value):
            task = task_registry.get(execution.task_name)
            if task:
                try:
                    task.delay(*execution.args_json, **execution.kwargs_json)
                    retried += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Failed to retry {execution.task_id}: {e}",
                        messages.ERROR,
                    )

        if retried:
            self.message_user(request, f"Retried {retried} tasks.", messages.SUCCESS)

    @action(description="Cancel selected tasks")
    def cancel_tasks(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Cancel pending/running tasks."""
        cancelled = queryset.filter(
            state__in=[TaskState.PENDING.value, TaskState.QUEUED.value]
        ).update(state=TaskState.CANCELLED.value)

        if cancelled:
            self.message_user(
                request, f"Cancelled {cancelled} tasks.", messages.SUCCESS
            )

    @action(description="Purge completed tasks older than 7 days")
    def purge_completed(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Purge old completed tasks."""
        from datetime import timedelta

        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=7)
        deleted, _ = queryset.filter(
            state=TaskState.COMPLETED.value, completed_at__lt=cutoff
        ).delete()

        if deleted:
            self.message_user(
                request, f"Purged {deleted} old completed tasks.", messages.SUCCESS
            )
