"""
Django 6.0+ native task backend.

Uses Django's built-in task system when available.
"""

import asyncio
import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..types import TaskMeta, TaskResult, TaskState
from .base import BaseNativeBackend

if TYPE_CHECKING:
    from ..config import NativeTaskConfig
    from ..core import NativeTask


class DjangoNativeBackend(BaseNativeBackend):
    """
    Backend using Django 6.0+ native background tasks.

    This backend leverages Django's built-in task system
    introduced in Django 6.0 (DEP-0014).

    Note: Django 6.0 is not released yet. This backend
    provides a forward-compatible implementation that will
    integrate with Django's native tasks when available.
    """

    name = "django_native"

    def __init__(self, config: "NativeTaskConfig"):
        super().__init__(config)
        self._results: dict[str, TaskResult] = {}
        self._django_tasks_available = self._check_django_tasks()

    def _check_django_tasks(self) -> bool:
        """Check if Django native tasks are available."""
        try:
            import django

            version = tuple(int(x) for x in django.__version__.split(".")[:2])
            if version >= (6, 0):
                # Django 6.0+ - check for tasks module
                # This will be updated when Django 6.0 is released
                try:
                    from django import tasks  # noqa: F401

                    return True
                except ImportError:
                    pass
            return False
        except Exception:
            return False

    def enqueue(
        self,
        task: "NativeTask",
        args: tuple,
        kwargs: dict,
        meta: TaskMeta,
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
    ) -> TaskResult:
        """
        Enqueue task using Django native tasks.

        Falls back to sync execution if Django tasks unavailable.
        """
        if self._django_tasks_available:
            return self._enqueue_native(task, args, kwargs, meta, countdown, eta, expires)
        else:
            # Fallback to sync execution for Django < 6.0
            return self._execute_sync(task, args, kwargs, meta)

    def _enqueue_native(
        self,
        task: "NativeTask",
        args: tuple,
        kwargs: dict,
        meta: TaskMeta,
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
    ) -> TaskResult:
        """
        Enqueue using Django's native task system.

        This will be implemented when Django 6.0 is released.
        For now, it provides the API structure.
        """
        # TODO: Implement when Django 6.0 is released
        # Expected API:
        # from django.tasks import enqueue
        # django_task_id = enqueue(
        #     self._execute_task,
        #     args=(task.name, args, kwargs, meta.task_id),
        #     queue=meta.queue,
        #     priority=meta.priority,
        #     countdown=countdown,
        #     eta=eta,
        # )

        meta.state = TaskState.QUEUED
        meta.queued_at = datetime.now(UTC)

        # For now, execute synchronously as fallback
        return self._execute_sync(task, args, kwargs, meta)

    def _execute_sync(
        self,
        task: "NativeTask",
        args: tuple,
        kwargs: dict,
        meta: TaskMeta,
    ) -> TaskResult:
        """Execute task synchronously (fallback mode)."""
        meta.state = TaskState.RUNNING
        meta.started_at = datetime.now(UTC)

        try:
            if task.bind:
                if task.is_async:
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(task.func(task, *args, **kwargs))
                    finally:
                        loop.close()
                else:
                    result = task.func(task, *args, **kwargs)
            else:
                if task.is_async:
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(task.func(*args, **kwargs))
                    finally:
                        loop.close()
                else:
                    result = task.func(*args, **kwargs)

            meta.state = TaskState.COMPLETED
            meta.result = result
            meta.completed_at = datetime.now(UTC)

        except Exception as e:
            meta.state = TaskState.FAILED
            meta.error = str(e)
            meta.traceback = traceback.format_exc()
            meta.completed_at = datetime.now(UTC)

        task_result = TaskResult(task_id=meta.task_id, meta=meta)
        self._results[meta.task_id] = task_result
        return task_result

    def get_result(self, task_id: str) -> TaskResult | None:
        """Get task result."""
        if self._django_tasks_available:
            # TODO: Query Django's task result backend
            pass
        return self._results.get(task_id)

    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a task."""
        if self._django_tasks_available:
            # TODO: Use Django's task revocation API
            pass
        return False

    def get_queue_length(self, queue: str = "default") -> int:
        """Get queue length."""
        if self._django_tasks_available:
            # TODO: Query Django's task queue
            pass
        return 0

    def purge_queue(self, queue: str = "default") -> int:
        """Purge queue."""
        if self._django_tasks_available:
            # TODO: Use Django's queue purge API
            pass
        return 0

    def health_check(self) -> dict[str, Any]:
        """Check backend health."""
        return {
            "healthy": True,
            "backend": self.name,
            "django_native_available": self._django_tasks_available,
            "mode": "native" if self._django_tasks_available else "sync_fallback",
        }
