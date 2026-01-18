"""
Task scheduling utilities.

Provides crontab and interval-based scheduling for periodic tasks.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Task


@dataclass
class ScheduleEntry:
    """Base class for schedule entries."""

    def get_next_run(self, now: datetime = None) -> datetime:
        """Get the next scheduled run time."""
        raise NotImplementedError


@dataclass
class CrontabSchedule(ScheduleEntry):
    """
    Crontab-style schedule.

    Supports standard crontab syntax for scheduling tasks.

    Usage:
        # Every day at midnight
        crontab(hour=0, minute=0)

        # Every Monday at 9am
        crontab(day_of_week=1, hour=9, minute=0)

        # Every 15 minutes
        crontab(minute="*/15")

        # First day of month at noon
        crontab(day_of_month=1, hour=12, minute=0)
    """

    minute: int | str = "*"
    hour: int | str = "*"
    day_of_week: int | str = "*"
    day_of_month: int | str = "*"
    month_of_year: int | str = "*"

    def _parse_field(self, value: int | str, min_val: int, max_val: int) -> set[int]:
        """Parse a crontab field into a set of valid values."""
        if isinstance(value, int):
            return {value}

        if value == "*":
            return set(range(min_val, max_val + 1))

        values = set()
        for part in value.split(","):
            if "/" in part:
                # Step values: */15, 0-30/5
                range_part, step = part.split("/")
                step = int(step)
                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-"))
                else:
                    start = end = int(range_part)
                values.update(range(start, end + 1, step))
            elif "-" in part:
                # Range: 1-5
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            else:
                # Single value
                values.add(int(part))

        return values

    def get_next_run(self, now: datetime = None) -> datetime:
        """Calculate the next run time."""
        if now is None:
            now = datetime.utcnow()

        # Parse all fields
        minutes = self._parse_field(self.minute, 0, 59)
        hours = self._parse_field(self.hour, 0, 23)
        days_of_week = self._parse_field(self.day_of_week, 0, 6)
        days_of_month = self._parse_field(self.day_of_month, 1, 31)
        months = self._parse_field(self.month_of_year, 1, 12)

        # Start from next minute
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Find next matching time (limit iterations to prevent infinite loop)
        for _ in range(525600):  # Max 1 year of minutes
            if (
                candidate.minute in minutes
                and candidate.hour in hours
                and candidate.weekday() in days_of_week
                and candidate.day in days_of_month
                and candidate.month in months
            ):
                return candidate

            candidate += timedelta(minutes=1)

        # Fallback (shouldn't happen with valid crontab)
        return now + timedelta(days=1)

    def __repr__(self):
        return (
            f"crontab(minute={self.minute!r}, hour={self.hour!r}, "
            f"day_of_week={self.day_of_week!r}, day_of_month={self.day_of_month!r}, "
            f"month_of_year={self.month_of_year!r})"
        )


@dataclass
class IntervalSchedule(ScheduleEntry):
    """
    Interval-based schedule.

    Runs tasks at regular intervals.

    Usage:
        # Every 5 minutes
        every(minutes=5)

        # Every hour
        every(hours=1)

        # Every 30 seconds
        every(seconds=30)

        # Complex interval
        every(hours=1, minutes=30)
    """

    seconds: int = 0
    minutes: int = 0
    hours: int = 0
    days: int = 0
    weeks: int = 0

    @property
    def total_seconds(self) -> int:
        """Get total interval in seconds."""
        return (
            self.seconds
            + self.minutes * 60
            + self.hours * 3600
            + self.days * 86400
            + self.weeks * 604800
        )

    def get_next_run(self, now: datetime = None) -> datetime:
        """Calculate the next run time."""
        if now is None:
            now = datetime.utcnow()
        return now + timedelta(seconds=self.total_seconds)

    def __repr__(self):
        parts = []
        if self.weeks:
            parts.append(f"weeks={self.weeks}")
        if self.days:
            parts.append(f"days={self.days}")
        if self.hours:
            parts.append(f"hours={self.hours}")
        if self.minutes:
            parts.append(f"minutes={self.minutes}")
        if self.seconds:
            parts.append(f"seconds={self.seconds}")
        return f"every({', '.join(parts)})"


# Convenience functions


def crontab(
    minute: int | str = "*",
    hour: int | str = "*",
    day_of_week: int | str = "*",
    day_of_month: int | str = "*",
    month_of_year: int | str = "*",
) -> CrontabSchedule:
    """
    Create a crontab schedule.

    Args:
        minute: Minute (0-59) or crontab expression
        hour: Hour (0-23) or crontab expression
        day_of_week: Day of week (0=Monday, 6=Sunday) or crontab expression
        day_of_month: Day of month (1-31) or crontab expression
        month_of_year: Month (1-12) or crontab expression

    Returns:
        CrontabSchedule instance

    Examples:
        crontab(minute=0, hour=0)  # Daily at midnight
        crontab(minute="*/15")     # Every 15 minutes
        crontab(day_of_week="0-4", hour=9)  # Weekdays at 9am
    """
    return CrontabSchedule(
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
    )


def every(
    seconds: int = 0,
    minutes: int = 0,
    hours: int = 0,
    days: int = 0,
    weeks: int = 0,
) -> IntervalSchedule:
    """
    Create an interval schedule.

    Args:
        seconds: Run every N seconds
        minutes: Run every N minutes
        hours: Run every N hours
        days: Run every N days
        weeks: Run every N weeks

    Returns:
        IntervalSchedule instance

    Examples:
        every(minutes=5)       # Every 5 minutes
        every(hours=1)         # Every hour
        every(days=1, hours=2) # Every 26 hours
    """
    return IntervalSchedule(
        seconds=seconds,
        minutes=minutes,
        hours=hours,
        days=days,
        weeks=weeks,
    )


@dataclass
class ScheduledTask:
    """A task with its schedule."""

    task: "Task"
    schedule: ScheduleEntry
    last_run: datetime | None = None
    next_run: datetime | None = None
    enabled: bool = True

    def update_next_run(self):
        """Update the next run time based on current time."""
        self.next_run = self.schedule.get_next_run(datetime.utcnow())


class Scheduler:
    """
    Task scheduler.

    Manages periodic task registration and scheduling.
    The actual execution is handled by the backend (Celery Beat, etc).
    """

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}

    def register(self, task: "Task", schedule: ScheduleEntry) -> None:
        """Register a task with a schedule."""
        scheduled = ScheduledTask(task=task, schedule=schedule)
        scheduled.update_next_run()
        self._tasks[task.name] = scheduled

    def unregister(self, task_name: str) -> None:
        """Unregister a scheduled task."""
        self._tasks.pop(task_name, None)

    def get(self, task_name: str) -> ScheduledTask | None:
        """Get a scheduled task by name."""
        return self._tasks.get(task_name)

    def all(self) -> dict[str, ScheduledTask]:
        """Get all scheduled tasks."""
        return self._tasks.copy()

    def get_due_tasks(self, now: datetime = None) -> list[ScheduledTask]:
        """Get all tasks that are due to run."""
        if now is None:
            now = datetime.utcnow()

        due = []
        for scheduled in self._tasks.values():
            if scheduled.enabled and scheduled.next_run and scheduled.next_run <= now:
                due.append(scheduled)

        return due

    def mark_run(self, task_name: str) -> None:
        """Mark a task as having run and update next run time."""
        scheduled = self._tasks.get(task_name)
        if scheduled:
            scheduled.last_run = datetime.utcnow()
            scheduled.update_next_run()

    def enable(self, task_name: str) -> None:
        """Enable a scheduled task."""
        if task_name in self._tasks:
            self._tasks[task_name].enabled = True

    def disable(self, task_name: str) -> None:
        """Disable a scheduled task."""
        if task_name in self._tasks:
            self._tasks[task_name].enabled = False


# Global scheduler instance
scheduler = Scheduler()
