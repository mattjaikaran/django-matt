"""
Django Matt native task engine CLI.

Manage background tasks, schedules, and queues from the command line.

Usage:
    python manage.py matt_tasks list                              # List all registered tasks
    python manage.py matt_tasks run send_email --payload '{}'     # Run task manually
    python manage.py matt_tasks status                            # Show queue status
    python manage.py matt_tasks purge --older-than 30d            # Clean up old tasks
    python manage.py matt_tasks retry --failed --last 24h         # Bulk retry failures
    python manage.py matt_tasks schedules                         # List all schedules
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta

from django.utils import timezone

from django_matt.cli import MattCommand


class Command(MattCommand):
    """Native task engine management commands."""

    help = "Manage native tasks: list, run, status, purge, retry, schedules"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

        # list
        list_parser = subparsers.add_parser("list", help="List all registered tasks")
        list_parser.add_argument(
            "--format",
            "-f",
            choices=["table", "json"],
            default="table",
            help="Output format",
        )

        # run
        run_parser = subparsers.add_parser("run", help="Run a task manually")
        run_parser.add_argument("task_name", help="Task name to run")
        run_parser.add_argument(
            "--payload",
            "-p",
            default="{}",
            help="JSON payload for the task",
        )
        run_parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously instead of enqueueing",
        )

        # status
        status_parser = subparsers.add_parser("status", help="Show queue status")
        status_parser.add_argument(
            "--queue",
            "-q",
            default=None,
            help="Filter by queue name",
        )
        status_parser.add_argument(
            "--format",
            "-f",
            choices=["table", "json"],
            default="table",
            help="Output format",
        )

        # purge
        purge_parser = subparsers.add_parser("purge", help="Purge old completed tasks")
        purge_parser.add_argument(
            "--older-than",
            default="30d",
            help="Age threshold (e.g., 30d, 7d, 24h)",
        )
        purge_parser.add_argument(
            "--state",
            choices=["completed", "failed", "cancelled", "all"],
            default="completed",
            help="Task state to purge",
        )
        purge_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be purged without deleting",
        )

        # retry
        retry_parser = subparsers.add_parser("retry", help="Retry failed tasks")
        retry_parser.add_argument(
            "--failed",
            action="store_true",
            help="Retry failed tasks",
        )
        retry_parser.add_argument(
            "--last",
            default="24h",
            help="Time window (e.g., 24h, 7d)",
        )
        retry_parser.add_argument(
            "--task",
            "-t",
            default=None,
            help="Filter by task name",
        )
        retry_parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum tasks to retry",
        )
        retry_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be retried without executing",
        )

        # schedules
        schedules_parser = subparsers.add_parser(
            "schedules", help="List all schedules"
        )
        schedules_parser.add_argument(
            "--enabled-only",
            action="store_true",
            help="Show only enabled schedules",
        )
        schedules_parser.add_argument(
            "--format",
            "-f",
            choices=["table", "json"],
            default="table",
            help="Output format",
        )

    def handle(self, *args, **options) -> None:
        subcommand = options.get("subcommand")

        if not subcommand:
            self.console.error("Please specify a subcommand: list, run, status, purge, retry, schedules")
            self.print_help("manage.py", "matt_tasks")
            return

        handler = getattr(self, f"handle_{subcommand}", None)
        if handler:
            handler(options)
        else:
            self.console.error(f"Unknown subcommand: {subcommand}")

    def handle_list(self, options: dict) -> None:
        """List all registered tasks."""
        from django_matt.tasks_native.registry import task_registry

        tasks = list(task_registry.all().values())

        if not tasks:
            self.console.warning("No tasks registered.")
            return

        if options["format"] == "json":
            self._output_json([
                {
                    "name": t.name,
                    "is_async": t.is_async,
                    "queue": t.options.queue,
                    "max_retries": t.options.max_retries,
                    "has_payload_type": t.payload_type is not None,
                }
                for t in tasks
            ])
        else:
            self._output_task_table(tasks)

    def _output_task_table(self, tasks: list) -> None:
        """Output tasks as a table."""
        from rich.table import Table
        from rich.text import Text

        from django_matt.cli.console import console

        table = Table(show_edge=False, pad_edge=False)
        table.add_column("Task Name", style="cyan")
        table.add_column("Type", justify="center")
        table.add_column("Queue", justify="center")
        table.add_column("Retries", justify="right")
        table.add_column("Payload", justify="center")

        for t in sorted(tasks, key=lambda x: x.name):
            task_type = Text("async", style="green") if t.is_async else Text("sync", style="yellow")
            payload = "✓" if t.payload_type else "-"

            table.add_row(
                t.name,
                task_type,
                t.options.queue,
                str(t.options.max_retries),
                payload,
            )

        console._console.print(f"\n{len(tasks)} registered tasks:\n")
        console._console.print(table)

    def handle_run(self, options: dict) -> None:
        """Run a task manually."""
        from django_matt.tasks_native.registry import task_registry

        task_name = options["task_name"]
        task = task_registry.get(task_name)

        if task is None:
            self.console.error(f"Task not found: {task_name}")
            self.console.info("Available tasks:")
            for name in sorted(task_registry.names()):
                self.console.info(f"  - {name}")
            return

        try:
            payload = json.loads(options["payload"])
        except json.JSONDecodeError as e:
            self.console.error(f"Invalid JSON payload: {e}")
            return

        self.console.info(f"Running task: {task_name}")

        if options["sync"]:
            # Synchronous execution
            try:
                if isinstance(payload, dict):
                    result = task(**payload)
                elif isinstance(payload, list):
                    result = task(*payload)
                else:
                    result = task(payload)

                self.console.success(f"Task completed successfully")
                self.console.info(f"Result: {result}")
            except Exception as e:
                self.console.error(f"Task failed: {e}")
        else:
            # Async execution
            try:
                if isinstance(payload, dict):
                    task_result = task.delay(**payload)
                elif isinstance(payload, list):
                    task_result = task.delay(*payload)
                else:
                    task_result = task.delay(payload)

                self.console.success(f"Task enqueued: {task_result.task_id}")
            except Exception as e:
                self.console.error(f"Failed to enqueue task: {e}")

    def handle_status(self, options: dict) -> None:
        """Show queue status."""
        from django_matt.tasks_native.config import get_backend
        from django_matt.tasks_native.registry import task_registry

        backend = get_backend()

        # Backend health
        health = backend.health_check()

        if options["format"] == "json":
            self._output_json({
                "backend": health,
                "registered_tasks": len(task_registry),
                "queue_length": backend.get_queue_length(options.get("queue") or "default"),
            })
        else:
            self._output_status_table(health, backend, options)

    def _output_status_table(self, health: dict, backend, options: dict) -> None:
        """Output status as formatted text."""
        from rich.panel import Panel
        from rich.table import Table

        from django_matt.cli.console import console

        # Health panel
        status = "✓ Healthy" if health.get("healthy") else "✗ Unhealthy"
        status_style = "green" if health.get("healthy") else "red"

        console._console.print(f"\n[bold]Task Engine Status[/bold]\n")
        console._console.print(f"  Backend: [cyan]{health.get('backend', 'unknown')}[/cyan]")
        console._console.print(f"  Status: [{status_style}]{status}[/{status_style}]")

        if "mode" in health:
            console._console.print(f"  Mode: {health['mode']}")
        if "workers" in health:
            console._console.print(f"  Workers: {len(health['workers'])}")

        # Queue info
        queue_name = options.get("queue") or "default"
        queue_length = backend.get_queue_length(queue_name)
        console._console.print(f"\n  Queue '{queue_name}': {queue_length} pending tasks")

    def handle_purge(self, options: dict) -> None:
        """Purge old tasks."""
        from django_matt.tasks_native.loading import is_tasks_native_installed
        from django_matt.tasks_native.types import TaskState

        if not is_tasks_native_installed():
            self.console.warning("tasks_native not in INSTALLED_APPS, no database models available")
            return

        from django_matt.tasks_native.models import TaskExecution

        # Parse age
        age_str = options["older_than"]
        cutoff = self._parse_age(age_str)

        if cutoff is None:
            self.console.error(f"Invalid age format: {age_str}")
            return

        # Build query
        queryset = TaskExecution.objects.filter(created_at__lt=cutoff)

        state = options["state"]
        if state == "completed":
            queryset = queryset.filter(state=TaskState.COMPLETED.value)
        elif state == "failed":
            queryset = queryset.filter(state=TaskState.FAILED.value)
        elif state == "cancelled":
            queryset = queryset.filter(state=TaskState.CANCELLED.value)
        # "all" doesn't filter by state

        count = queryset.count()

        if options["dry_run"]:
            self.console.info(f"Would purge {count} tasks older than {age_str}")
        else:
            deleted, _ = queryset.delete()
            self.console.success(f"Purged {deleted} tasks older than {age_str}")

    def handle_retry(self, options: dict) -> None:
        """Retry failed tasks."""
        from django_matt.tasks_native.loading import is_tasks_native_installed
        from django_matt.tasks_native.registry import task_registry
        from django_matt.tasks_native.types import TaskState

        if not is_tasks_native_installed():
            self.console.warning("tasks_native not in INSTALLED_APPS, no database models available")
            return

        from django_matt.tasks_native.models import TaskExecution

        # Parse time window
        window_str = options["last"]
        cutoff = self._parse_age(window_str)

        if cutoff is None:
            self.console.error(f"Invalid time format: {window_str}")
            return

        # Build query
        queryset = TaskExecution.objects.filter(
            state=TaskState.FAILED.value,
            created_at__gte=cutoff,
        )

        if options.get("task"):
            queryset = queryset.filter(task_name=options["task"])

        queryset = queryset.order_by("-created_at")[: options["limit"]]
        tasks_to_retry = list(queryset)

        if not tasks_to_retry:
            self.console.info("No failed tasks found matching criteria")
            return

        if options["dry_run"]:
            self.console.info(f"Would retry {len(tasks_to_retry)} tasks:")
            for t in tasks_to_retry[:10]:
                self.console.info(f"  - {t.task_name} ({t.task_id[:8]})")
            if len(tasks_to_retry) > 10:
                self.console.info(f"  ... and {len(tasks_to_retry) - 10} more")
        else:
            retried = 0
            for execution in tasks_to_retry:
                task = task_registry.get(execution.task_name)
                if task:
                    try:
                        task.delay(*execution.args_json, **execution.kwargs_json)
                        retried += 1
                    except Exception as e:
                        self.console.warning(f"Failed to retry {execution.task_id[:8]}: {e}")
            self.console.success(f"Retried {retried} tasks")

    def handle_schedules(self, options: dict) -> None:
        """List all schedules."""
        from django_matt.tasks_native.scheduling import schedule_registry

        schedules = list(schedule_registry.all().values())

        if options.get("enabled_only"):
            schedules = [s for s in schedules if s.enabled]

        if not schedules:
            self.console.warning("No schedules registered.")
            return

        if options["format"] == "json":
            self._output_json([
                {
                    "name": s.name or s.task.name,
                    "task": s.task.name,
                    "schedule": repr(s.schedule),
                    "enabled": s.enabled,
                    "next_run": s.next_run.isoformat() if s.next_run else None,
                    "run_count": s.run_count,
                }
                for s in schedules
            ])
        else:
            self._output_schedule_table(schedules)

    def _output_schedule_table(self, schedules: list) -> None:
        """Output schedules as a table."""
        from rich.table import Table
        from rich.text import Text

        from django_matt.cli.console import console

        table = Table(show_edge=False, pad_edge=False)
        table.add_column("Name", style="cyan")
        table.add_column("Schedule")
        table.add_column("Enabled", justify="center")
        table.add_column("Next Run")
        table.add_column("Runs", justify="right")

        for s in sorted(schedules, key=lambda x: x.name or x.task.name):
            name = s.name or s.task.name
            enabled = Text("✓", style="green") if s.enabled else Text("✗", style="red")
            next_run = s.next_run.strftime("%Y-%m-%d %H:%M") if s.next_run else "-"

            table.add_row(
                name,
                repr(s.schedule),
                enabled,
                next_run,
                str(s.run_count),
            )

        console._console.print(f"\n{len(schedules)} registered schedules:\n")
        console._console.print(table)

    def _parse_age(self, age_str: str):
        """Parse age string like '30d', '24h' to cutoff datetime."""
        try:
            if age_str.endswith("d"):
                days = int(age_str[:-1])
                return timezone.now() - timedelta(days=days)
            elif age_str.endswith("h"):
                hours = int(age_str[:-1])
                return timezone.now() - timedelta(hours=hours)
            elif age_str.endswith("m"):
                minutes = int(age_str[:-1])
                return timezone.now() - timedelta(minutes=minutes)
            else:
                # Assume days
                return timezone.now() - timedelta(days=int(age_str))
        except ValueError:
            return None

    def _output_json(self, data) -> None:
        """Output data as JSON."""
        import orjson

        self.stdout.write(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode())
