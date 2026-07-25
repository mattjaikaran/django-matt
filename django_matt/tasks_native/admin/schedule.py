"""
Admin for TaskSchedule and ScheduleHistory models.
"""

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from ..models import ScheduleHistory, TaskSchedule

try:
    from unfold.admin import ModelAdmin, TabularInline
    from unfold.decorators import action

    UNFOLD_AVAILABLE = True
except ImportError:
    from django.contrib.admin import ModelAdmin, TabularInline

    UNFOLD_AVAILABLE = False

    def action(description: str = "", **kwargs):
        def decorator(func):
            func.short_description = description
            return func

        return decorator


class ScheduleHistoryInline(TabularInline):
    """Inline for schedule execution history."""

    model = ScheduleHistory
    extra = 0
    readonly_fields = ["scheduled_for", "executed_at", "success", "error"]
    can_delete = False
    max_num = 10
    ordering = ["-executed_at"]


class TaskScheduleAdmin(ModelAdmin):
    """Admin for task schedules."""

    list_display = [
        "name",
        "task_name_display",
        "schedule_display",
        "enabled_badge",
        "next_run_display",
        "last_run_display",
        "stats_display",
    ]
    list_filter = ["enabled", "schedule_type", "queue"]
    search_fields = ["name", "task_name", "description"]
    readonly_fields = [
        "last_run_at",
        "next_run_at",
        "run_count",
        "success_count",
        "failure_count",
        "created_at",
        "updated_at",
    ]
    ordering = ["name"]
    list_per_page = 50
    inlines = [ScheduleHistoryInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "task_name", "description", "enabled"),
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    "schedule_type",
                    "crontab_minute",
                    "crontab_hour",
                    "crontab_day_of_week",
                    "crontab_day_of_month",
                    "crontab_month_of_year",
                    "interval_seconds",
                    "interval_minutes",
                    "interval_hours",
                    "interval_days",
                    "timezone",
                ),
            },
        ),
        (
            "Task Configuration",
            {
                "fields": ("args_json", "kwargs_json", "queue", "priority"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "last_run_at",
                    "next_run_at",
                    "run_count",
                    "success_count",
                    "failure_count",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["enable_schedules", "disable_schedules", "run_now"]

    def task_name_display(self, obj: TaskSchedule) -> str:
        """Display shortened task name."""
        parts = obj.task_name.split(".")
        if len(parts) > 2:
            return f"...{'.'.join(parts[-2:])}"
        return obj.task_name

    task_name_display.short_description = "Task"

    def schedule_display(self, obj: TaskSchedule) -> str:
        """Display schedule in human-readable format."""
        return obj.get_schedule_display()

    schedule_display.short_description = "Schedule"

    def enabled_badge(self, obj: TaskSchedule) -> str:
        """Display enabled status as badge."""
        if obj.enabled:
            return format_html(
                '<span class="px-2 py-1 text-xs font-medium rounded-full '
                'bg-green-100 text-green-800">Enabled</span>'
            )
        return format_html(
            '<span class="px-2 py-1 text-xs font-medium rounded-full '
            'bg-gray-100 text-gray-800">Disabled</span>'
        )

    enabled_badge.short_description = "Status"

    def next_run_display(self, obj: TaskSchedule) -> str:
        """Display next run time."""
        if not obj.next_run_at:
            return "-"
        return obj.next_run_at.strftime("%Y-%m-%d %H:%M")

    next_run_display.short_description = "Next Run"

    def last_run_display(self, obj: TaskSchedule) -> str:
        """Display last run time."""
        if not obj.last_run_at:
            return "Never"
        return obj.last_run_at.strftime("%Y-%m-%d %H:%M")

    last_run_display.short_description = "Last Run"

    def stats_display(self, obj: TaskSchedule) -> str:
        """Display success/failure stats."""
        total = obj.success_count + obj.failure_count
        if total == 0:
            return "-"
        success_rate = (obj.success_count / total) * 100
        return f"{obj.success_count}/{total} ({success_rate:.0f}%)"

    stats_display.short_description = "Success"

    @action(description="Enable selected schedules")
    def enable_schedules(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Enable selected schedules."""
        updated = queryset.update(enabled=True)
        self.message_user(request, f"Enabled {updated} schedules.", messages.SUCCESS)

    @action(description="Disable selected schedules")
    def disable_schedules(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Disable selected schedules."""
        updated = queryset.update(enabled=False)
        self.message_user(request, f"Disabled {updated} schedules.", messages.SUCCESS)

    @action(description="Run selected schedules now")
    def run_now(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Trigger immediate execution of schedules."""
        from ..registry import task_registry

        run = 0
        for schedule in queryset.filter(enabled=True):
            task = task_registry.get(schedule.task_name)
            if task:
                try:
                    task.delay(*schedule.args_json, **schedule.kwargs_json)
                    run += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Failed to run {schedule.name}: {e}",
                        messages.ERROR,
                    )

        if run:
            self.message_user(request, f"Triggered {run} schedule(s).", messages.SUCCESS)


class ScheduleHistoryAdmin(ModelAdmin):
    """Admin for schedule execution history."""

    list_display = [
        "schedule",
        "scheduled_for",
        "executed_at",
        "success_badge",
        "error_preview",
    ]
    list_filter = ["success", "schedule", "executed_at"]
    search_fields = ["schedule__name", "error"]
    readonly_fields = [
        "schedule",
        "task_execution",
        "scheduled_for",
        "executed_at",
        "success",
        "error",
    ]
    ordering = ["-executed_at"]
    date_hierarchy = "executed_at"
    list_per_page = 100

    def success_badge(self, obj: ScheduleHistory) -> str:
        """Display success as badge."""
        if obj.success:
            return format_html(
                '<span class="px-2 py-1 text-xs font-medium rounded-full '
                'bg-green-100 text-green-800">OK</span>'
            )
        return format_html(
            '<span class="px-2 py-1 text-xs font-medium rounded-full '
            'bg-red-100 text-red-800">Failed</span>'
        )

    success_badge.short_description = "Status"

    def error_preview(self, obj: ScheduleHistory) -> str:
        """Display error preview."""
        if not obj.error:
            return "-"
        return obj.error[:50] + "..." if len(obj.error) > 50 else obj.error

    error_preview.short_description = "Error"
