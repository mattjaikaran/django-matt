"""
Celery compatibility backend.

Allows using Celery as the task backend while maintaining
the native task API.
"""

import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..types import TaskMeta, TaskResult, TaskState
from .base import BaseNativeBackend

if TYPE_CHECKING:
    from ..config import NativeTaskConfig
    from ..core import NativeTask


class CeleryNativeBackend(BaseNativeBackend):
    """
    Celery-based task backend.

    Wraps Celery to provide the native task API while
    leveraging Celery's production-grade infrastructure.
    """

    name = "celery"

    def __init__(self, config: "NativeTaskConfig"):
        super().__init__(config)
        self._celery_app = None
        self._results: dict[str, TaskResult] = {}
        self._initialize_celery()

    def _initialize_celery(self) -> None:
        """Initialize Celery app."""
        try:
            from celery import Celery

            broker_url = self.config.url or self.config.redis_url
            result_backend = broker_url

            self._celery_app = Celery(
                "django_matt_tasks",
                broker=broker_url,
                backend=result_backend,
            )

            # Configure Celery
            self._celery_app.conf.update(
                task_serializer="json",
                accept_content=["json"],
                result_serializer="json",
                timezone="UTC",
                enable_utc=True,
                task_track_started=True,
                task_default_queue=self.config.default_queue,
                worker_prefetch_multiplier=self.config.worker_prefetch,
                worker_concurrency=self.config.worker_concurrency,
            )

        except ImportError:
            raise ImportError(
                "Celery is not installed. Install it with: uv add celery"
            )

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
        """Enqueue task using Celery."""
        if self._celery_app is None:
            raise RuntimeError("Celery not initialized")

        # Create Celery task dynamically
        @self._celery_app.task(
            name=task.name,
            bind=True,
            max_retries=task.options.max_retries,
            default_retry_delay=task.options.retry_delay,
            time_limit=task.options.timeout,
            queue=meta.queue,
            priority=meta.priority,
        )
        def celery_task(self_celery, *task_args, **task_kwargs):
            import asyncio

            if task.bind:
                if task.is_async:
                    loop = asyncio.new_event_loop()
                    try:
                        return loop.run_until_complete(task.func(task, *task_args, **task_kwargs))
                    finally:
                        loop.close()
                return task.func(task, *task_args, **task_kwargs)
            else:
                if task.is_async:
                    loop = asyncio.new_event_loop()
                    try:
                        return loop.run_until_complete(task.func(*task_args, **task_kwargs))
                    finally:
                        loop.close()
                return task.func(*task_args, **task_kwargs)

        # Enqueue the task
        celery_result = celery_task.apply_async(
            args=args,
            kwargs=kwargs,
            task_id=meta.task_id,
            countdown=countdown,
            eta=eta,
            expires=expires,
            queue=meta.queue,
            priority=meta.priority,
        )

        meta.state = TaskState.QUEUED
        meta.queued_at = datetime.now(UTC)

        task_result = TaskResult(task_id=meta.task_id, meta=meta)
        task_result._celery_result = celery_result
        self._results[meta.task_id] = task_result

        return task_result

    def get_result(self, task_id: str) -> TaskResult | None:
        """Get task result from Celery."""
        task_result = self._results.get(task_id)
        if task_result and hasattr(task_result, "_celery_result"):
            celery_result = task_result._celery_result

            # Update state from Celery
            if celery_result.ready():
                if celery_result.successful():
                    task_result.meta.state = TaskState.COMPLETED
                    task_result.meta.result = celery_result.result
                else:
                    task_result.meta.state = TaskState.FAILED
                    task_result.meta.error = str(celery_result.result)
                task_result.meta.completed_at = datetime.now(UTC)
            elif celery_result.state == "STARTED":
                task_result.meta.state = TaskState.RUNNING
                task_result.meta.started_at = datetime.now(UTC)

        return task_result

    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a Celery task."""
        if self._celery_app is None:
            return False

        try:
            self._celery_app.control.revoke(task_id, terminate=terminate)
            if task_id in self._results:
                self._results[task_id].meta.state = TaskState.CANCELLED
            return True
        except Exception:
            return False

    def get_queue_length(self, queue: str = "default") -> int:
        """Get Celery queue length."""
        if self._celery_app is None:
            return 0

        try:
            inspect = self._celery_app.control.inspect()
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}

            count = 0
            for worker_tasks in active.values():
                count += len([t for t in worker_tasks if t.get("queue") == queue])
            for worker_tasks in reserved.values():
                count += len([t for t in worker_tasks if t.get("queue") == queue])

            return count
        except Exception:
            return 0

    def purge_queue(self, queue: str = "default") -> int:
        """Purge Celery queue."""
        if self._celery_app is None:
            return 0

        try:
            return self._celery_app.control.purge()
        except Exception:
            return 0

    def health_check(self) -> dict[str, Any]:
        """Check Celery backend health."""
        if self._celery_app is None:
            return {"healthy": False, "backend": self.name, "error": "Not initialized"}

        try:
            inspect = self._celery_app.control.inspect()
            ping = inspect.ping() or {}
            workers = list(ping.keys())

            return {
                "healthy": len(workers) > 0,
                "backend": self.name,
                "workers": workers,
                "worker_count": len(workers),
            }
        except Exception as e:
            return {"healthy": False, "backend": self.name, "error": str(e)}
