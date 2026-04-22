"""
Tests for the native task engine CLI commands.

Note: These tests verify command functionality without capturing
Rich console output (which goes to a separate console).
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from django_matt.tasks_native import reset, task, task_registry
from django_matt.tasks_native.scheduling import schedule_registry


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


class TestMattTasksListCommand:
    """Tests for matt_tasks list subcommand."""

    def test_list_runs_without_error(self):
        """Test list command runs without error."""
        # Command runs without raising
        call_command("matt_tasks", "list")

    def test_list_json_format(self):
        """Test JSON output format writes to stdout."""

        @task(name="json_list_task")
        def json_task() -> str:
            return "done"

        out = StringIO()
        call_command("matt_tasks", "list", "--format", "json", stdout=out)
        output = out.getvalue()
        assert "json_list_task" in output


class TestMattTasksRunCommand:
    """Tests for matt_tasks run subcommand."""

    def test_run_task_sync_executes(self):
        """Test running a task synchronously actually executes it."""
        result_holder = {"called": False}

        @task(name="sync_run_task")
        def sync_task() -> str:
            result_holder["called"] = True
            return "completed"

        call_command("matt_tasks", "run", "sync_run_task", "--sync")
        assert result_holder["called"] is True

    def test_run_task_with_payload(self):
        """Test running a task with JSON payload."""
        received_payload = {}

        @task(name="payload_task")
        def payload_task(key: str = "", value: int = 0) -> dict:
            received_payload["key"] = key
            received_payload["value"] = value
            return received_payload

        call_command(
            "matt_tasks",
            "run",
            "payload_task",
            "--sync",
            "--payload",
            '{"key": "test", "value": 42}',
        )
        assert received_payload.get("key") == "test"
        assert received_payload.get("value") == 42


class TestMattTasksStatusCommand:
    """Tests for matt_tasks status subcommand."""

    def test_status_runs_without_error(self):
        """Test status command runs without error."""
        call_command("matt_tasks", "status")

    def test_status_json_format(self):
        """Test JSON status output."""
        out = StringIO()
        call_command("matt_tasks", "status", "--format", "json", stdout=out)
        output = out.getvalue()
        assert "{" in output


class TestMattTasksSchedulesCommand:
    """Tests for matt_tasks schedules subcommand."""

    def test_schedules_runs_without_error(self):
        """Test schedules command runs without error."""
        call_command("matt_tasks", "schedules")

    def test_schedules_json_format(self):
        """Test JSON output format."""
        from django_matt.tasks_native import every, periodic_task

        @periodic_task(every(minutes=5), name="json_cli_schedule")
        def scheduled_task() -> str:
            return "done"

        out = StringIO()
        call_command("matt_tasks", "schedules", "--format", "json", stdout=out)
        output = out.getvalue()
        assert "json_cli_schedule" in output


class TestAgeParser:
    """Tests for age string parsing."""

    def test_parse_days(self):
        """Test parsing days."""
        from django_matt.management.commands.matt_tasks import Command

        cmd = Command()
        cutoff = cmd._parse_age("7d")
        expected = timezone.now() - timedelta(days=7)
        assert abs((cutoff - expected).total_seconds()) < 5

    def test_parse_hours(self):
        """Test parsing hours."""
        from django_matt.management.commands.matt_tasks import Command

        cmd = Command()
        cutoff = cmd._parse_age("24h")
        expected = timezone.now() - timedelta(hours=24)
        assert abs((cutoff - expected).total_seconds()) < 5

    def test_parse_minutes(self):
        """Test parsing minutes."""
        from django_matt.management.commands.matt_tasks import Command

        cmd = Command()
        cutoff = cmd._parse_age("30m")
        expected = timezone.now() - timedelta(minutes=30)
        assert abs((cutoff - expected).total_seconds()) < 5

    def test_parse_invalid(self):
        """Test parsing invalid format."""
        from django_matt.management.commands.matt_tasks import Command

        cmd = Command()
        cutoff = cmd._parse_age("invalid")
        assert cutoff is None
