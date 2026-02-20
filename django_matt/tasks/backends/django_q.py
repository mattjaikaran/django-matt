"""
Django-Q2 backend implementation.

Provides integration with Django-Q2 for task processing.
"""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .base import BaseBackend

if TYPE_CHECKING:
    from ..base import Task, TaskResult


class DjangoQBackend(BaseBackend):
    """
    Django-Q2 task queue backend.

    Django-Q2 is a Django-native task queue with:
    - Database-backed task storage
    - Multiprocessing cluster
    - Scheduled tasks
    - Admin interface integration
    - No external message broker required (uses Django ORM)

    Usage:
        # In settings.py
        DJANGO_MATT_TASKS = {
            "BACKEND": "django_q",
        }

        # Configure Django-Q
        Q_CLUSTER = {
            "name": "django-matt",
            "workers": 4,
            "recycle": 500,
            "timeout": 60,
            "django_redis": "default",  # or use ORM
        }

        # Define tasks
        @task
        def my_task(x, y):
            return x + y

        # Execute
        my_task.delay(1, 2)

    Requires:
        uv add django-q2
    """

    def __init__(self, **config):
        """
        Initialize Django-Q2 backend.

        Args:
            **config: Django-Q configuration options
        """
        self._config = config

    def _ensure_django_q(self):
        """Ensure Django-Q2 is installed and configured."""
        try:
            from django_q.models import Task as QTask
            from django_q.tasks import async_task, fetch, result

            return async_task, result, fetch, QTask
        except ImportError:
            raise ImportError(
                "Django-Q2 is required for DjangoQBackend. Install with: uv add django-q2"
            )

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
        """Send a task to Django-Q2."""

        async_task, _, _, _ = self._ensure_django_q()

        # Generate task ID
        task_id = task_id or str(uuid.uuid4())

        # Build options
        q_options = {
            "task_name": task_id,
            "hook": options.get("hook"),
            "group": options.get("group"),
        }

        if queue:
            q_options["cluster"] = queue

        # Handle scheduling
        if countdown:
            from django.utils import timezone

            q_options["schedule_type"] = "O"  # Once
            q_options["next_run"] = timezone.now() + timedelta(seconds=countdown)
        elif eta:
            q_options["schedule_type"] = "O"
            q_options["next_run"] = eta

        # Create the callable
        def execute():
            if task.bind:
                return task.func(task, *args, **(kwargs or {}))
            return task.func(*args, **(kwargs or {}))

        # Queue the task
        # Django-Q accepts a function path or a callable
        # We'll use the function directly
        result_id = async_task(
            task.func,
            *args,
            **(kwargs or {}),
            **{k: v for k, v in q_options.items() if v is not None},
        )

        return DjangoQTaskResult(task_id=result_id or task_id)

    def get_result(self, task_id: str) -> "TaskResult":
        """Get a task result from Django-Q2."""
        _, result_func, fetch, _ = self._ensure_django_q()

        return DjangoQTaskResult(
            task_id=task_id,
            result_func=result_func,
            fetch_func=fetch,
        )

    def revoke(self, task_id: str, terminate: bool = False) -> None:
        """
        Revoke a Django-Q2 task.

        Note: Django-Q2 doesn't support revoking running tasks.
        This deletes pending tasks.
        """
        _, _, _, QTask = self._ensure_django_q()

        try:
            task = QTask.objects.get(id=task_id)
            if not task.success:
                task.delete()
        except QTask.DoesNotExist:
            pass

    def configure(self, **config) -> None:
        """Update configuration."""
        self._config.update(config)

    def close(self) -> None:
        """Close Django-Q connections (no-op for Django-Q)."""


class DjangoQTaskResult:
    """Task result wrapper for Django-Q2."""

    def __init__(self, task_id: str, result_func=None, fetch_func=None):
        self.task_id = task_id
        self._result_func = result_func
        self._fetch_func = fetch_func
        self._cached_result = None
        self._cached_task = None

    def _fetch_task(self):
        """Fetch the task from Django-Q."""
        if self._cached_task is None and self._fetch_func:
            self._cached_task = self._fetch_func(self.task_id)
        return self._cached_task

    @property
    def status(self):
        from ..base import TaskStatus

        task = self._fetch_task()
        if task is None:
            return TaskStatus.PENDING

        if task.success:
            return TaskStatus.SUCCESS
        if task.stopped:
            return TaskStatus.FAILURE

        return TaskStatus.STARTED

    @property
    def result(self):
        if self._cached_result is not None:
            return self._cached_result

        if self._result_func:
            self._cached_result = self._result_func(self.task_id)
            return self._cached_result

        task = self._fetch_task()
        if task:
            return task.result

        return None

    @property
    def error(self):
        task = self._fetch_task()
        if task and not task.success:
            return task.result
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

        return self.status in (TaskStatus.SUCCESS, TaskStatus.FAILURE)

    def get(self, timeout: float = None, propagate: bool = True):
        """
        Wait for result.

        Note: Django-Q2 doesn't have built-in blocking wait.
        This polls the database.
        """
        import time

        start = time.time()
        while True:
            task = self._fetch_task()
            if task and (task.success or task.stopped):
                if not task.success and propagate:
                    raise Exception(task.result)
                return task.result

            if timeout and (time.time() - start) > timeout:
                raise TimeoutError(f"Task {self.task_id} did not complete in {timeout}s")

            # Reset cache and wait
            self._cached_task = None
            time.sleep(0.5)
