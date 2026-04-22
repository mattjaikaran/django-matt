"""
Synchronous backend for development.

Executes tasks immediately in the same process.
Perfect for development and testing.
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


class SyncNativeBackend(BaseNativeBackend):
    """
    Synchronous task backend for development.

    Executes tasks immediately in the calling thread.
    No external dependencies required.
    """

    name = "sync"

    def __init__(self, config: "NativeTaskConfig"):
        super().__init__(config)
        self._results: dict[str, TaskResult] = {}

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
        """Execute task synchronously."""
        meta.state = TaskState.RUNNING
        meta.started_at = datetime.now(UTC)

        try:
            # Execute the task
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

            # Call success handlers
            for handler in task._on_success_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(handler(task, result, args))
                        finally:
                            loop.close()
                    else:
                        handler(task, result, args)
                except Exception:
                    pass

        except Exception as e:
            meta.state = TaskState.FAILED
            meta.error = str(e)
            meta.traceback = traceback.format_exc()
            meta.completed_at = datetime.now(UTC)

            # Call failure handlers
            for handler in task._on_failure_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(handler(task, e, args))
                        finally:
                            loop.close()
                    else:
                        handler(task, e, args)
                except Exception:
                    pass

            # Propagate error if configured
            if self.config.eager_propagate_errors:
                from ..types import TaskExecutionError

                raise TaskExecutionError(str(e), meta.traceback) from e

        task_result = TaskResult(task_id=meta.task_id, meta=meta)
        self._results[meta.task_id] = task_result
        return task_result

    def get_result(self, task_id: str) -> TaskResult | None:
        """Get task result from in-memory store."""
        return self._results.get(task_id)

    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """Cannot revoke sync tasks (they complete immediately)."""
        return False

    def get_queue_length(self, queue: str = "default") -> int:
        """Sync backend has no queue."""
        return 0

    def purge_queue(self, queue: str = "default") -> int:
        """Sync backend has no queue to purge."""
        return 0

    def health_check(self) -> dict[str, Any]:
        """Sync backend is always healthy."""
        return {
            "healthy": True,
            "backend": self.name,
            "mode": "synchronous",
            "tasks_executed": len(self._results),
        }

    def clear_results(self) -> None:
        """Clear stored results (for testing)."""
        self._results.clear()
