"""
Celery backend implementation.

Provides integration with Celery for distributed task processing.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseBackend

if TYPE_CHECKING:
    from ..base import Task, TaskResult
    from ..primitives import Group, GroupResult, Signature


class CeleryBackend(BaseBackend):
    """
    Celery task queue backend.

    Celery is a distributed task queue with support for:
    - Multiple message brokers (Redis, RabbitMQ, etc.)
    - Result backends (Redis, database, etc.)
    - Task priorities, routing, and rate limiting
    - Periodic tasks via Celery Beat
    - Task chains, groups, and chords

    Usage:
        # In settings.py
        DJANGO_MATT_TASKS = {
            "BACKEND": "celery",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
        }

        # Define tasks
        @task
        def my_task(x, y):
            return x + y

        # Execute
        my_task.delay(1, 2)

    Requires:
        pip install celery[redis]
    """

    def __init__(self, **config):
        """
        Initialize Celery backend.

        Args:
            **config: Celery configuration options
        """
        self._app = None
        self._config = config

    @property
    def app(self):
        """Get or create the Celery app."""
        if self._app is None:
            self._app = self._create_app()
        return self._app

    def _create_app(self):
        """Create and configure the Celery app."""
        try:
            from celery import Celery
        except ImportError:
            raise ImportError(
                "Celery is required for CeleryBackend. Install with: pip install celery[redis]"
            )

        app = Celery("django_matt_tasks")

        # Apply configuration
        config = {
            "broker_url": self._config.get(
                "CELERY_BROKER_URL",
                self._config.get("broker_url", "redis://localhost:6379/0"),
            ),
            "result_backend": self._config.get(
                "CELERY_RESULT_BACKEND",
                self._config.get("result_backend", "redis://localhost:6379/0"),
            ),
            "task_serializer": self._config.get("task_serializer", "json"),
            "result_serializer": self._config.get("result_serializer", "json"),
            "accept_content": self._config.get("accept_content", ["json"]),
            "timezone": self._config.get("timezone", "UTC"),
            "enable_utc": self._config.get("enable_utc", True),
            "task_track_started": self._config.get("task_track_started", True),
            "task_acks_late": self._config.get("task_acks_late", True),
        }

        app.config_from_object(config)

        # Register all tasks from registry
        from ..base import task_registry

        for task in task_registry:
            self._register_celery_task(task)

        return app

    def _register_celery_task(self, task: "Task"):
        """Register a django-matt task with Celery."""

        @self.app.task(
            name=task.name,
            bind=task.bind,
            max_retries=task.options.retry,
            default_retry_delay=task.options.retry_delay,
            rate_limit=task.options.rate_limit,
            ignore_result=task.options.ignore_result,
            track_started=task.options.track_started,
            acks_late=task.options.acks_late,
        )
        def celery_task(*args, **kwargs):
            if task.bind:
                return task.func(task, *args, **kwargs)
            return task.func(*args, **kwargs)

        task._celery_task = celery_task

    def send_task(
        self,
        task: "Task",
        args: tuple = (),
        kwargs: dict = None,
        task_id: str = None,
        countdown: int = None,
        eta: datetime = None,
        expires: int = None,
        queue: str = None,
        priority: int = None,
        **options,
    ) -> "TaskResult":
        """Send a task to Celery."""

        # Get the Celery task
        celery_task = getattr(task, "_celery_task", None)
        if celery_task is None:
            self._register_celery_task(task)
            celery_task = task._celery_task

        # Send to Celery
        async_result = celery_task.apply_async(
            args=args,
            kwargs=kwargs or {},
            task_id=task_id,
            countdown=countdown,
            eta=eta,
            expires=expires,
            queue=queue,
            priority=priority,
            **options,
        )

        return CeleryTaskResult(
            task_id=async_result.id,
            celery_result=async_result,
        )

    def get_result(self, task_id: str) -> "TaskResult":
        """Get a task result from Celery."""
        from celery.result import AsyncResult

        async_result = AsyncResult(task_id, app=self.app)
        return CeleryTaskResult(
            task_id=task_id,
            celery_result=async_result,
        )

    def revoke(self, task_id: str, terminate: bool = False) -> None:
        """Revoke a Celery task."""
        self.app.control.revoke(task_id, terminate=terminate)

    def send_group(
        self,
        tasks: Sequence["Signature"],
        **options,
    ) -> "GroupResult":
        """Send a group using Celery's native group support."""
        from celery import group as celery_group

        from ..primitives import GroupResult

        # Convert to Celery signatures
        celery_sigs = []
        for sig in tasks:
            celery_task = getattr(sig.task, "_celery_task", None)
            if celery_task is None:
                self._register_celery_task(sig.task)
                celery_task = sig.task._celery_task
            celery_sigs.append(celery_task.s(*sig.args, **sig.kwargs))

        # Execute group
        group_result = celery_group(celery_sigs).apply_async(**options)

        # Convert results
        results = [CeleryTaskResult(task_id=r.id, celery_result=r) for r in group_result.results]

        return GroupResult(results=results)

    def send_chain(
        self,
        tasks: Sequence["Signature"],
        **options,
    ) -> "TaskResult":
        """Send a chain using Celery's native chain support."""
        from celery import chain as celery_chain

        # Convert to Celery signatures
        celery_sigs = []
        for sig in tasks:
            celery_task = getattr(sig.task, "_celery_task", None)
            if celery_task is None:
                self._register_celery_task(sig.task)
                celery_task = sig.task._celery_task

            if sig.immutable:
                celery_sigs.append(celery_task.si(*sig.args, **sig.kwargs))
            else:
                celery_sigs.append(celery_task.s(*sig.args, **sig.kwargs))

        # Execute chain
        chain_result = celery_chain(*celery_sigs).apply_async(**options)

        return CeleryTaskResult(
            task_id=chain_result.id,
            celery_result=chain_result,
        )

    def send_chord(
        self,
        header: "Group",
        body: "Signature",
        **options,
    ) -> "TaskResult":
        """Send a chord using Celery's native chord support."""
        from celery import chord as celery_chord

        # Convert header to Celery signatures
        celery_header = []
        for sig in header.tasks:
            celery_task = getattr(sig.task, "_celery_task", None)
            if celery_task is None:
                self._register_celery_task(sig.task)
                celery_task = sig.task._celery_task
            celery_header.append(celery_task.s(*sig.args, **sig.kwargs))

        # Convert body
        body_celery = getattr(body.task, "_celery_task", None)
        if body_celery is None:
            self._register_celery_task(body.task)
            body_celery = body.task._celery_task

        # Execute chord
        chord_result = celery_chord(celery_header)(body_celery.s(*body.args, **body.kwargs))

        return CeleryTaskResult(
            task_id=chord_result.id,
            celery_result=chord_result,
        )

    def configure(self, **config) -> None:
        """Update configuration."""
        self._config.update(config)
        self._app = None  # Force recreation

    def close(self) -> None:
        """Close Celery connections."""
        if self._app:
            self._app.close()


class CeleryTaskResult:
    """Task result wrapper for Celery."""

    def __init__(self, task_id: str, celery_result=None):
        self.task_id = task_id
        self._celery_result = celery_result

    @property
    def status(self):
        from ..base import TaskStatus

        if self._celery_result is None:
            return TaskStatus.PENDING

        state = self._celery_result.state
        mapping = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.STARTED,
            "SUCCESS": TaskStatus.SUCCESS,
            "FAILURE": TaskStatus.FAILURE,
            "RETRY": TaskStatus.RETRY,
            "REVOKED": TaskStatus.REVOKED,
        }
        return mapping.get(state, TaskStatus.PENDING)

    @property
    def result(self):
        if self._celery_result:
            return self._celery_result.result
        return None

    @property
    def error(self):
        if self._celery_result and self._celery_result.failed():
            return str(self._celery_result.result)
        return None

    @property
    def is_pending(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.PENDING

    @property
    def is_success(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.SUCCESS

    @property
    def is_failure(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.FAILURE

    @property
    def is_complete(self):
        from ..base import TaskStatus

        return self.status in (TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED)

    def get(self, timeout: float = None, propagate: bool = True):
        """Wait for result."""
        if self._celery_result:
            return self._celery_result.get(timeout=timeout, propagate=propagate)
        return None
