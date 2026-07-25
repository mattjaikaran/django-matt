"""
Task dashboard for Unfold admin.
"""

from datetime import timedelta
from typing import Any

from django.db.models import Avg, Count, Q
from django.utils import timezone

from ..models import DeadLetterTask, TaskExecution, TaskSchedule
from ..types import TaskState


class TaskDashboard:
    """
    Dashboard metrics and widgets for task monitoring.

    Usage with Unfold:
        from django_matt.tasks_native.admin import get_task_dashboard_callback

        UNFOLD = {
            "DASHBOARD_CALLBACK": get_task_dashboard_callback(),
        }
    """

    @staticmethod
    def get_task_stats() -> dict[str, Any]:
        """Get task statistics for dashboard."""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        # Count by state
        state_counts = TaskExecution.objects.filter(created_at__gte=last_24h).aggregate(
            pending=Count("id", filter=Q(state=TaskState.PENDING.value)),
            running=Count("id", filter=Q(state=TaskState.RUNNING.value)),
            completed=Count("id", filter=Q(state=TaskState.COMPLETED.value)),
            failed=Count("id", filter=Q(state=TaskState.FAILED.value)),
        )

        # Performance metrics
        performance = TaskExecution.objects.filter(
            state=TaskState.COMPLETED.value, completed_at__gte=last_24h
        ).aggregate(
            avg_duration=Avg("completed_at") - Avg("started_at"),
            total_completed=Count("id"),
        )

        # Failure rate
        total_24h = state_counts["completed"] + state_counts["failed"]
        failure_rate = 0
        if total_24h > 0:
            failure_rate = (state_counts["failed"] / total_24h) * 100

        # Scheduled tasks
        scheduled_count = TaskSchedule.objects.filter(enabled=True).count()
        due_schedules = TaskSchedule.objects.filter(enabled=True, next_run_at__lte=now).count()

        # Dead letter queue
        dlq_count = DeadLetterTask.objects.filter(reprocessed=False).count()

        return {
            "state_counts": state_counts,
            "failure_rate": failure_rate,
            "scheduled_count": scheduled_count,
            "due_schedules": due_schedules,
            "dlq_count": dlq_count,
            "total_24h": total_24h,
        }

    @staticmethod
    def get_queue_metrics() -> list[dict[str, Any]]:
        """Get metrics per queue."""
        queues = (
            TaskExecution.objects.values("queue")
            .annotate(
                total=Count("id"),
                pending=Count("id", filter=Q(state=TaskState.PENDING.value)),
                running=Count("id", filter=Q(state=TaskState.RUNNING.value)),
                completed=Count("id", filter=Q(state=TaskState.COMPLETED.value)),
                failed=Count("id", filter=Q(state=TaskState.FAILED.value)),
            )
            .order_by("queue")
        )
        return list(queues)

    @staticmethod
    def get_recent_failures(limit: int = 10) -> list[TaskExecution]:
        """Get recent failed tasks."""
        return list(
            TaskExecution.objects.filter(state=TaskState.FAILED.value).order_by("-completed_at")[
                :limit
            ]
        )

    @staticmethod
    def get_upcoming_schedules(limit: int = 10) -> list[TaskSchedule]:
        """Get upcoming scheduled tasks."""
        return list(
            TaskSchedule.objects.filter(enabled=True, next_run_at__isnull=False).order_by(
                "next_run_at"
            )[:limit]
        )


def get_task_dashboard_callback():
    """
    Create dashboard callback for Unfold.

    Usage:
        # settings.py
        from django_matt.tasks_native.admin import get_task_dashboard_callback

        UNFOLD = {
            "DASHBOARD_CALLBACK": get_task_dashboard_callback(),
        }
    """

    def dashboard_callback(request, context):
        """Add task stats to dashboard context."""
        try:
            stats = TaskDashboard.get_task_stats()
            context["task_stats"] = stats
            context["recent_failures"] = TaskDashboard.get_recent_failures()
            context["upcoming_schedules"] = TaskDashboard.get_upcoming_schedules()
        except Exception:
            pass

        return context

    return dashboard_callback


def get_task_widgets() -> list[dict[str, Any]]:
    """
    Get task dashboard widgets for Unfold.

    These can be added to your dashboard template.
    """
    try:
        stats = TaskDashboard.get_task_stats()
    except Exception:
        return []

    return [
        {
            "type": "stat",
            "title": "Tasks (24h)",
            "value": stats["total_24h"],
            "description": "Total tasks in last 24 hours",
        },
        {
            "type": "stat",
            "title": "Running",
            "value": stats["state_counts"]["running"],
            "description": "Currently executing",
            "color": "indigo",
        },
        {
            "type": "stat",
            "title": "Failed",
            "value": stats["state_counts"]["failed"],
            "description": f"{stats['failure_rate']:.1f}% failure rate",
            "color": "red" if stats["state_counts"]["failed"] > 0 else "green",
        },
        {
            "type": "stat",
            "title": "Dead Letter",
            "value": stats["dlq_count"],
            "description": "Tasks requiring attention",
            "color": "purple" if stats["dlq_count"] > 0 else "green",
        },
        {
            "type": "stat",
            "title": "Schedules",
            "value": stats["scheduled_count"],
            "description": f"{stats['due_schedules']} due now",
        },
    ]
