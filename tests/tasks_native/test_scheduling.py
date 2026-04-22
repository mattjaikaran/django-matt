"""
Tests for the native task engine scheduling module.
"""

from datetime import UTC, datetime, timedelta

import pytest

from django_matt.tasks_native import (
    CrontabSchedule,
    IntervalSchedule,
    NativeTaskConfig,
    ScheduledTaskEntry,
    ScheduleRegistry,
    crontab,
    every,
    periodic_task,
    reset,
    schedule_registry,
    set_config,
    task,
    task_registry,
)


@pytest.fixture(autouse=True)
def reset_task_system():
    """Reset task system before each test."""
    reset()
    task_registry.clear()
    schedule_registry.clear()
    yield
    reset()
    task_registry.clear()
    schedule_registry.clear()


class TestCrontabSchedule:
    """Tests for CrontabSchedule."""

    def test_crontab_basic(self):
        """Test basic crontab creation."""
        schedule = crontab(hour=9, minute=0)

        assert schedule.hour == 9
        assert schedule.minute == 0
        assert schedule.day_of_week == "*"
        assert schedule.day_of_month == "*"
        assert schedule.month_of_year == "*"

    def test_crontab_every_15_minutes(self):
        """Test crontab every 15 minutes."""
        schedule = crontab(minute="*/15")

        assert schedule.minute == "*/15"

        # Check parsing
        minutes = schedule._parse_field("*/15", 0, 59)
        assert 0 in minutes
        assert 15 in minutes
        assert 30 in minutes
        assert 45 in minutes
        assert 10 not in minutes

    def test_crontab_weekdays_at_9am(self):
        """Test crontab for weekdays at 9am."""
        schedule = crontab(day_of_week="0-4", hour=9, minute=0)

        days = schedule._parse_field("0-4", 0, 6)
        assert days == {0, 1, 2, 3, 4}
        assert 5 not in days  # Saturday
        assert 6 not in days  # Sunday

    def test_crontab_next_run(self):
        """Test crontab next run calculation."""
        schedule = crontab(minute=30, hour=10)

        # Set a known time
        now = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
        next_run = schedule.get_next_run(now)

        # Should be 10:30 same day
        assert next_run.hour == 10
        assert next_run.minute == 30
        assert next_run.day == 15

    def test_crontab_next_run_past_time(self):
        """Test crontab next run when time has passed."""
        schedule = crontab(minute=30, hour=10)

        # Current time is past 10:30
        now = datetime(2024, 6, 15, 11, 0, 0, tzinfo=UTC)
        next_run = schedule.get_next_run(now)

        # Should be 10:30 next day
        assert next_run.hour == 10
        assert next_run.minute == 30
        assert next_run.day == 16

    def test_crontab_to_cron_string(self):
        """Test converting to cron string."""
        schedule = crontab(minute="*/15", hour=9, day_of_week="1-5")

        cron_str = schedule.to_cron_string()
        assert cron_str == "*/15 9 * * 1-5"

    def test_crontab_from_cron_string(self):
        """Test parsing cron string."""
        schedule = CrontabSchedule.from_cron_string("0 9 * * 1-5")

        assert schedule.minute == "0"
        assert schedule.hour == "9"
        assert schedule.day_of_week == "1-5"

    def test_crontab_comma_values(self):
        """Test crontab with comma-separated values."""
        schedule = crontab(hour="9,12,15")

        hours = schedule._parse_field("9,12,15", 0, 23)
        assert hours == {9, 12, 15}


class TestIntervalSchedule:
    """Tests for IntervalSchedule."""

    def test_interval_minutes(self):
        """Test interval with minutes."""
        schedule = every(minutes=5)

        assert schedule.minutes == 5
        assert schedule.total_seconds == 300

    def test_interval_hours(self):
        """Test interval with hours."""
        schedule = every(hours=2)

        assert schedule.hours == 2
        assert schedule.total_seconds == 7200

    def test_interval_complex(self):
        """Test interval with multiple components."""
        schedule = every(hours=1, minutes=30, seconds=15)

        assert schedule.total_seconds == 3600 + 1800 + 15

    def test_interval_next_run(self):
        """Test interval next run calculation."""
        schedule = every(minutes=30)

        now = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
        next_run = schedule.get_next_run(now)

        assert next_run == now + timedelta(minutes=30)

    def test_interval_repr(self):
        """Test interval string representation."""
        schedule = every(hours=1, minutes=30)

        repr_str = repr(schedule)
        assert "hours=1" in repr_str
        assert "minutes=30" in repr_str


class TestPeriodicTaskDecorator:
    """Tests for @periodic_task decorator."""

    def test_periodic_task_with_crontab(self):
        """Test periodic task with crontab schedule."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @periodic_task(crontab(hour=9, minute=0))
        def daily_task() -> str:
            return "daily"

        assert hasattr(daily_task, "schedule")
        assert isinstance(daily_task.schedule, CrontabSchedule)
        assert daily_task.name in schedule_registry

    def test_periodic_task_with_interval(self):
        """Test periodic task with interval schedule."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @periodic_task(every(minutes=5))
        def frequent_task() -> str:
            return "frequent"

        assert hasattr(frequent_task, "schedule")
        assert isinstance(frequent_task.schedule, IntervalSchedule)

    def test_periodic_task_with_custom_name(self):
        """Test periodic task with custom name."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @periodic_task(
            every(hours=1),
            name="custom_hourly_task",
            description="Runs every hour",
        )
        def hourly_task() -> str:
            return "hourly"

        assert "custom_hourly_task" in schedule_registry

        entry = schedule_registry.get("custom_hourly_task")
        assert entry is not None
        assert entry.description == "Runs every hour"

    def test_periodic_task_execution(self):
        """Test periodic task can be executed."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        counter = {"value": 0}

        @periodic_task(every(seconds=1))
        def increment_task() -> int:
            counter["value"] += 1
            return counter["value"]

        # Execute directly
        result = increment_task()
        assert result == 1
        assert counter["value"] == 1

        # Execute via delay
        task_result = increment_task.delay()
        assert task_result.is_completed
        assert task_result.result == 2


class TestScheduleRegistry:
    """Tests for ScheduleRegistry."""

    def test_registry_register(self):
        """Test registering a scheduled task."""
        registry = ScheduleRegistry()

        @task
        def test_task() -> None:
            pass

        entry = registry.register(test_task, every(minutes=5))

        assert entry.task is test_task
        assert isinstance(entry.schedule, IntervalSchedule)
        assert entry.enabled is True
        assert entry.next_run is not None

    def test_registry_get(self):
        """Test getting a scheduled task."""
        registry = ScheduleRegistry()

        @task(name="get_test_task")
        def get_task() -> None:
            pass

        registry.register(get_task, every(minutes=5), name="get_test_task")

        entry = registry.get("get_test_task")
        assert entry is not None
        assert entry.task is get_task

    def test_registry_unregister(self):
        """Test unregistering a scheduled task."""
        registry = ScheduleRegistry()

        @task(name="unreg_task")
        def unreg_task() -> None:
            pass

        registry.register(unreg_task, every(minutes=5), name="unreg_task")
        assert "unreg_task" in registry

        registry.unregister("unreg_task")
        assert "unreg_task" not in registry

    def test_registry_get_due_tasks(self):
        """Test getting due tasks."""
        registry = ScheduleRegistry()

        @task(name="due_task")
        def due_task() -> None:
            pass

        entry = registry.register(due_task, every(seconds=1), name="due_task")

        # Set next_run to past
        entry.next_run = datetime.now(UTC) - timedelta(seconds=10)

        due = registry.get_due_tasks()
        assert len(due) == 1
        assert due[0].task is due_task

    def test_registry_enable_disable(self):
        """Test enabling/disabling scheduled tasks."""
        registry = ScheduleRegistry()

        @task(name="toggle_task")
        def toggle_task() -> None:
            pass

        registry.register(toggle_task, every(minutes=5), name="toggle_task")

        assert registry.get("toggle_task").enabled is True

        registry.disable("toggle_task")
        assert registry.get("toggle_task").enabled is False

        registry.enable("toggle_task")
        assert registry.get("toggle_task").enabled is True

    def test_registry_all(self):
        """Test getting all scheduled tasks."""
        registry = ScheduleRegistry()

        @task(name="all_task_1")
        def task_1() -> None:
            pass

        @task(name="all_task_2")
        def task_2() -> None:
            pass

        registry.register(task_1, every(minutes=5), name="all_task_1")
        registry.register(task_2, crontab(hour=9), name="all_task_2")

        all_tasks = registry.all()
        assert len(all_tasks) == 2
        assert "all_task_1" in all_tasks
        assert "all_task_2" in all_tasks


class TestScheduledTaskEntry:
    """Tests for ScheduledTaskEntry."""

    def test_entry_next_run_calculated(self):
        """Test next run is calculated on creation."""

        @task
        def entry_task() -> None:
            pass

        entry = ScheduledTaskEntry(
            task=entry_task,
            schedule=every(minutes=10),
        )

        assert entry.next_run is not None
        # Should be ~10 minutes from now
        expected = datetime.now(UTC) + timedelta(minutes=10)
        assert abs((entry.next_run - expected).total_seconds()) < 5

    def test_entry_mark_run(self):
        """Test marking entry as run."""

        @task
        def mark_task() -> None:
            pass

        entry = ScheduledTaskEntry(
            task=mark_task,
            schedule=every(minutes=5),
        )

        old_next_run = entry.next_run
        entry.mark_run()

        assert entry.last_run is not None
        assert entry.run_count == 1
        assert entry.next_run > old_next_run

    def test_entry_timezone(self):
        """Test entry with custom timezone."""

        @task
        def tz_task() -> None:
            pass

        entry = ScheduledTaskEntry(
            task=tz_task,
            schedule=crontab(hour=9),
            timezone="America/New_York",
        )

        assert entry.timezone == "America/New_York"
