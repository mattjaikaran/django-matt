# file-length-max: 450
"""
Database-driven task scheduling for the native task engine.

Provides schedule primitives (crontab, every) and the @periodic_task decorator.
No external beat process required - schedules are stored in the database.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .core import NativeTask


@dataclass(frozen=True)
class CrontabSchedule:
    """
    Crontab-style schedule.

    Supports standard crontab syntax for scheduling tasks.

    Usage:
        crontab(hour=9, minute=0)          # Daily at 9 AM
        crontab(day_of_week=1, hour=9)     # Mondays at 9 AM
        crontab(minute="*/15")             # Every 15 minutes
        crontab(day_of_month=1, hour=12)   # First of month at noon
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

        values: set[int] = set()
        for part in str(value).split(","):
            if "/" in part:
                range_part, step = part.split("/")
                step_int = int(step)
                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-"))
                else:
                    start = end = int(range_part)
                values.update(range(start, end + 1, step_int))
            elif "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            else:
                values.add(int(part))

        return values

    def get_next_run(self, now: datetime | None = None) -> datetime:
        """Calculate the next run time from the given datetime."""
        if now is None:
            now = datetime.now(UTC)

        minutes = self._parse_field(self.minute, 0, 59)
        hours = self._parse_field(self.hour, 0, 23)
        days_of_week = self._parse_field(self.day_of_week, 0, 6)
        days_of_month = self._parse_field(self.day_of_month, 1, 31)
        months = self._parse_field(self.month_of_year, 1, 12)

        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(525600):
            if (
                candidate.minute in minutes
                and candidate.hour in hours
                and candidate.weekday() in days_of_week
                and candidate.day in days_of_month
                and candidate.month in months
            ):
                return candidate
            candidate += timedelta(minutes=1)

        return now + timedelta(days=1)

    def to_cron_string(self) -> str:
        """Convert to standard cron string format."""
        return (
            f"{self.minute} {self.hour} {self.day_of_month} {self.month_of_year} {self.day_of_week}"
        )

    @classmethod
    def from_cron_string(cls, cron_str: str) -> "CrontabSchedule":
        """Parse a standard cron string."""
        parts = cron_str.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron string: {cron_str}")

        return cls(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month_of_year=parts[3],
            day_of_week=parts[4],
        )

    def __repr__(self) -> str:
        return f"crontab({self.to_cron_string()!r})"


@dataclass(frozen=True)
class IntervalSchedule:
    """
    Interval-based schedule.

    Runs tasks at regular intervals.

    Usage:
        every(minutes=5)            # Every 5 minutes
        every(hours=1)              # Every hour
        every(seconds=30)           # Every 30 seconds
        every(hours=1, minutes=30)  # Every 1.5 hours
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

    def get_next_run(self, now: datetime | None = None) -> datetime:
        """Calculate the next run time."""
        if now is None:
            now = datetime.now(UTC)
        return now + timedelta(seconds=self.total_seconds)

    def __repr__(self) -> str:
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


ScheduleType = CrontabSchedule | IntervalSchedule


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
        crontab(minute=0, hour=0)           # Daily at midnight
        crontab(minute="*/15")              # Every 15 minutes
        crontab(day_of_week="0-4", hour=9)  # Weekdays at 9am
        crontab(hour=9, minute=0)           # Daily at 9 AM
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
class ScheduledTaskEntry:
    """Metadata for a scheduled task."""

    task: "NativeTask"
    schedule: ScheduleType
    name: str | None = None
    description: str | None = None
    enabled: bool = True
    timezone: str = "UTC"
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0

    def __post_init__(self):
        if self.next_run is None:
            self.update_next_run()

    def update_next_run(self) -> None:
        """Update the next run time based on current time."""
        self.next_run = self.schedule.get_next_run(datetime.now(UTC))

    def mark_run(self) -> None:
        """Mark the task as having run."""
        self.last_run = datetime.now(UTC)
        self.run_count += 1
        self.update_next_run()


class ScheduleRegistry:
    """
    In-memory registry for scheduled tasks.

    Works alongside database-stored schedules for decorator-defined schedules.
    """

    def __init__(self):
        self._schedules: dict[str, ScheduledTaskEntry] = {}

    def register(
        self,
        task: "NativeTask",
        schedule: ScheduleType,
        name: str | None = None,
        description: str | None = None,
        enabled: bool = True,
        timezone: str = "UTC",
    ) -> ScheduledTaskEntry:
        """Register a task with a schedule."""
        entry = ScheduledTaskEntry(
            task=task,
            schedule=schedule,
            name=name or task.name,
            description=description,
            enabled=enabled,
            timezone=timezone,
        )
        self._schedules[entry.name] = entry
        return entry

    def unregister(self, name: str) -> None:
        """Unregister a scheduled task."""
        self._schedules.pop(name, None)

    def get(self, name: str) -> ScheduledTaskEntry | None:
        """Get a scheduled task entry by name."""
        return self._schedules.get(name)

    def all(self) -> dict[str, ScheduledTaskEntry]:
        """Get all scheduled tasks."""
        return self._schedules.copy()

    def get_due_tasks(self, now: datetime | None = None) -> list[ScheduledTaskEntry]:
        """Get all tasks that are due to run."""
        if now is None:
            now = datetime.now(UTC)

        due = []
        for entry in self._schedules.values():
            if entry.enabled and entry.next_run and entry.next_run <= now:
                due.append(entry)

        return due

    def enable(self, name: str) -> bool:
        """Enable a scheduled task."""
        entry = self._schedules.get(name)
        if entry:
            entry.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a scheduled task."""
        entry = self._schedules.get(name)
        if entry:
            entry.enabled = False
            return True
        return False

    def clear(self) -> None:
        """Clear all scheduled tasks."""
        self._schedules.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._schedules

    def __len__(self) -> int:
        return len(self._schedules)


# Global schedule registry
schedule_registry = ScheduleRegistry()


def periodic_task(
    schedule: ScheduleType,
    *,
    name: str | None = None,
    description: str | None = None,
    queue: str | None = None,
    timezone: str = "UTC",
    enabled: bool = True,
    **task_kwargs: Any,
) -> Callable[[Callable], "NativeTask"]:
    """
    Decorator to define a periodic (scheduled) task.

    Usage:
        from django_matt.tasks_native import periodic_task, crontab, every

        @periodic_task(crontab(hour=9, minute=0))
        async def daily_report():
            # Runs daily at 9 AM
            await generate_report()

        @periodic_task(every(minutes=5))
        async def health_check():
            # Runs every 5 minutes
            await check_system_health()

        @periodic_task(
            crontab(hour=0, minute=0),
            name="nightly_cleanup",
            description="Clean old data nightly",
            timezone="America/New_York",
        )
        async def cleanup():
            await clean_old_data()

    Args:
        schedule: When to run the task (crontab or interval)
        name: Task name (for display in admin)
        description: Human-readable description
        queue: Queue to run on
        timezone: Timezone for schedule (default: UTC)
        enabled: Whether schedule is enabled (default: True)
        **task_kwargs: Additional task options

    Returns:
        Task instance with schedule attached
    """
    from .core import NativeTask

    def decorator(func: Callable) -> NativeTask:
        task_instance = NativeTask(
            func,
            name=name,
            queue=queue,
            **task_kwargs,
        )

        task_instance.schedule = schedule

        schedule_registry.register(
            task=task_instance,
            schedule=schedule,
            name=name or task_instance.name,
            description=description,
            enabled=enabled,
            timezone=timezone,
        )

        return task_instance

    return decorator
