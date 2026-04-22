"""
Database models for the native task engine.

Stores task executions, schedules, and results in the database
for persistence, admin UI, and historical tracking.
"""

from datetime import UTC, datetime

from django.db import models
from django.utils import timezone

from .types import TaskState


class TaskExecution(models.Model):
    """
    Record of a task execution.

    Stores execution history for monitoring, debugging, and analytics.
    """

    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=512, db_index=True)
    queue = models.CharField(max_length=128, default="default", db_index=True)
    priority = models.IntegerField(default=0)

    state = models.CharField(
        max_length=32,
        choices=[(s.value, s.name) for s in TaskState],
        default=TaskState.PENDING.value,
        db_index=True,
    )

    args_json = models.JSONField(default=list, blank=True)
    kwargs_json = models.JSONField(default=dict, blank=True)

    result_json = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)

    worker_id = models.CharField(max_length=255, null=True, blank=True)
    retries = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "tasks_native"
        db_table = "tasks_native_execution"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_name", "state"]),
            models.Index(fields=["queue", "state"]),
            models.Index(fields=["created_at", "state"]),
        ]

    def __str__(self) -> str:
        return f"{self.task_name} ({self.task_id[:8]})"

    @property
    def duration_ms(self) -> float | None:
        """Get task duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    @property
    def wait_time_ms(self) -> float | None:
        """Get time spent waiting in queue."""
        if self.queued_at and self.started_at:
            return (self.started_at - self.queued_at).total_seconds() * 1000
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.state in (
            TaskState.COMPLETED.value,
            TaskState.FAILED.value,
            TaskState.CANCELLED.value,
            TaskState.DEAD_LETTER.value,
        )

    def mark_queued(self) -> None:
        """Mark task as queued."""
        self.state = TaskState.QUEUED.value
        self.queued_at = timezone.now()
        self.save(update_fields=["state", "queued_at"])

    def mark_running(self, worker_id: str | None = None) -> None:
        """Mark task as running."""
        self.state = TaskState.RUNNING.value
        self.started_at = timezone.now()
        self.worker_id = worker_id
        self.save(update_fields=["state", "started_at", "worker_id"])

    def mark_completed(self, result: dict | list | str | None = None) -> None:
        """Mark task as completed."""
        self.state = TaskState.COMPLETED.value
        self.completed_at = timezone.now()
        self.result_json = result
        self.save(update_fields=["state", "completed_at", "result_json"])

    def mark_failed(self, error: str, traceback: str | None = None) -> None:
        """Mark task as failed."""
        self.state = TaskState.FAILED.value
        self.completed_at = timezone.now()
        self.error = error
        self.traceback = traceback
        self.save(update_fields=["state", "completed_at", "error", "traceback"])

    def mark_retrying(self) -> None:
        """Mark task as retrying."""
        self.state = TaskState.RETRYING.value
        self.retries += 1
        self.save(update_fields=["state", "retries"])


class TaskSchedule(models.Model):
    """
    Database-stored task schedule.

    Allows creating/editing schedules via admin without code changes.
    """

    SCHEDULE_TYPE_CRONTAB = "crontab"
    SCHEDULE_TYPE_INTERVAL = "interval"
    SCHEDULE_TYPE_CHOICES = [
        (SCHEDULE_TYPE_CRONTAB, "Crontab"),
        (SCHEDULE_TYPE_INTERVAL, "Interval"),
    ]

    name = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=512, db_index=True)
    description = models.TextField(blank=True)

    schedule_type = models.CharField(
        max_length=32,
        choices=SCHEDULE_TYPE_CHOICES,
        default=SCHEDULE_TYPE_CRONTAB,
    )

    crontab_minute = models.CharField(max_length=64, default="*")
    crontab_hour = models.CharField(max_length=64, default="*")
    crontab_day_of_week = models.CharField(max_length=64, default="*")
    crontab_day_of_month = models.CharField(max_length=64, default="*")
    crontab_month_of_year = models.CharField(max_length=64, default="*")

    interval_seconds = models.IntegerField(default=0)
    interval_minutes = models.IntegerField(default=0)
    interval_hours = models.IntegerField(default=0)
    interval_days = models.IntegerField(default=0)

    args_json = models.JSONField(default=list, blank=True)
    kwargs_json = models.JSONField(default=dict, blank=True)

    queue = models.CharField(max_length=128, default="default")
    priority = models.IntegerField(default=0)

    timezone = models.CharField(max_length=64, default="UTC")
    enabled = models.BooleanField(default=True, db_index=True)

    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    run_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tasks_native"
        db_table = "tasks_native_schedule"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_schedule_display()})"

    def get_schedule_display(self) -> str:
        """Get human-readable schedule string."""
        if self.schedule_type == self.SCHEDULE_TYPE_CRONTAB:
            return (
                f"{self.crontab_minute} {self.crontab_hour} "
                f"{self.crontab_day_of_month} {self.crontab_month_of_year} "
                f"{self.crontab_day_of_week}"
            )
        else:
            parts = []
            if self.interval_days:
                parts.append(f"{self.interval_days}d")
            if self.interval_hours:
                parts.append(f"{self.interval_hours}h")
            if self.interval_minutes:
                parts.append(f"{self.interval_minutes}m")
            if self.interval_seconds:
                parts.append(f"{self.interval_seconds}s")
            return "every " + " ".join(parts) if parts else "every 0s"

    def get_schedule_object(self):
        """Get the schedule primitive."""
        from .scheduling import CrontabSchedule, IntervalSchedule

        if self.schedule_type == self.SCHEDULE_TYPE_CRONTAB:
            return CrontabSchedule(
                minute=self.crontab_minute,
                hour=self.crontab_hour,
                day_of_week=self.crontab_day_of_week,
                day_of_month=self.crontab_day_of_month,
                month_of_year=self.crontab_month_of_year,
            )
        else:
            return IntervalSchedule(
                seconds=self.interval_seconds,
                minutes=self.interval_minutes,
                hours=self.interval_hours,
                days=self.interval_days,
            )

    def update_next_run(self) -> None:
        """Calculate and set the next run time."""
        schedule = self.get_schedule_object()
        self.next_run_at = schedule.get_next_run(timezone.now())
        self.save(update_fields=["next_run_at"])

    def mark_run(self, success: bool = True) -> None:
        """Mark schedule as having run."""
        self.last_run_at = timezone.now()
        self.run_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.update_next_run()
        self.save(update_fields=[
            "last_run_at", "run_count", "success_count", "failure_count", "next_run_at"
        ])

    @classmethod
    def get_due_schedules(cls, now: datetime | None = None):
        """Get all schedules that are due to run."""
        if now is None:
            now = timezone.now()

        return cls.objects.filter(
            enabled=True,
            next_run_at__lte=now,
        ).select_related()


class ScheduleHistory(models.Model):
    """
    History of schedule executions.

    Tracks when schedules ran and their outcomes.
    """

    schedule = models.ForeignKey(
        TaskSchedule,
        on_delete=models.CASCADE,
        related_name="history",
    )
    task_execution = models.ForeignKey(
        TaskExecution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_history",
    )

    scheduled_for = models.DateTimeField()
    executed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "tasks_native"
        db_table = "tasks_native_schedule_history"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["schedule", "-executed_at"]),
        ]

    def __str__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return f"{self.schedule.name} @ {self.executed_at} [{status}]"


class DeadLetterTask(models.Model):
    """
    Tasks that failed after max retries.

    Stored for manual review and potential reprocessing.
    """

    task_execution = models.OneToOneField(
        TaskExecution,
        on_delete=models.CASCADE,
        related_name="dead_letter",
    )
    task_name = models.CharField(max_length=512, db_index=True)

    args_json = models.JSONField(default=list)
    kwargs_json = models.JSONField(default=dict)

    error = models.TextField()
    traceback = models.TextField(null=True, blank=True)

    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reprocessed_at = models.DateTimeField(null=True, blank=True)
    reprocessed = models.BooleanField(default=False)

    class Meta:
        app_label = "tasks_native"
        db_table = "tasks_native_dead_letter"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "reprocessed" if self.reprocessed else "pending"
        return f"{self.task_name} [{status}]"

    def reprocess(self) -> "TaskExecution":
        """
        Reprocess this dead letter task.

        Returns:
            New TaskExecution for the reprocessed task
        """
        from .registry import task_registry

        task = task_registry.get(self.task_name)
        if task is None:
            raise ValueError(f"Task '{self.task_name}' not found in registry")

        result = task.delay(*self.args_json, **self.kwargs_json)

        self.reprocessed = True
        self.reprocessed_at = timezone.now()
        self.save(update_fields=["reprocessed", "reprocessed_at"])

        return result
