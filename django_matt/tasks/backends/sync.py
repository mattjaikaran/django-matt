"""
Synchronous backend implementation.

Executes tasks immediately in the same process.
Useful for development and testing.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseBackend

if TYPE_CHECKING:
    from ..base import Task, TaskResult
    from ..primitives import Group, GroupResult, Signature


class SyncBackend(BaseBackend):
    """
    Synchronous task backend.

    Executes tasks immediately in the same process.
    Useful for:
    - Development without running workers
    - Testing
    - Simple deployments

    Usage:
        # In settings.py
        DJANGO_MATT_TASKS = {
            "BACKEND": "sync",
        }

        # Tasks run immediately when called
        @task
        def my_task(x, y):
            return x + y

        result = my_task.delay(1, 2)
        print(result.result)  # 3 - available immediately
    """

    def __init__(self, **config):
        """
        Initialize sync backend.

        Args:
            **config: Configuration options (mostly ignored)
        """
        self._config = config
        self._results = {}

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
        """Execute a task synchronously."""
        from ..base import TaskResult, TaskStatus

        task_id = task_id or str(uuid.uuid4())
        started_at = datetime.utcnow()

        try:
            # Execute immediately
            if task.bind:
                result = task.func(task, *args, **(kwargs or {}))
            else:
                result = task.func(*args, **(kwargs or {}))

            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                result=result,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        except Exception as e:
            import traceback

            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                error=str(e),
                traceback=traceback.format_exc(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        # Store result
        self._results[task_id] = task_result
        return task_result

    def get_result(self, task_id: str) -> "TaskResult":
        """Get a stored task result."""
        from ..base import TaskResult, TaskStatus

        if task_id in self._results:
            return self._results[task_id]

        return TaskResult(task_id=task_id, status=TaskStatus.PENDING)

    def revoke(self, task_id: str, terminate: bool = False) -> None:
        """
        Revoke a task (no-op for sync backend).

        Since tasks execute immediately, there's nothing to revoke.
        """

    def send_group(
        self,
        tasks: Sequence["Signature"],
        **options,
    ) -> "GroupResult":
        """Execute a group of tasks synchronously."""
        from ..primitives import GroupResult

        results = []
        for sig in tasks:
            result = self.send_task(
                task=sig.task,
                args=sig.args,
                kwargs=sig.kwargs,
                **{**sig.options, **options},
            )
            results.append(result)

        return GroupResult(results=results)

    def send_chain(
        self,
        tasks: Sequence["Signature"],
        **options,
    ) -> "TaskResult":
        """Execute a chain of tasks synchronously."""
        from ..base import TaskResult, TaskStatus

        if not tasks:
            return TaskResult(task_id="empty-chain", status=TaskStatus.SUCCESS)

        result = None
        last_result = None

        for sig in tasks:
            # Pass previous result as first argument (unless immutable)
            if result is not None and not sig.immutable:
                args = (result,) + sig.args
            else:
                args = sig.args

            last_result = self.send_task(
                task=sig.task,
                args=args,
                kwargs=sig.kwargs,
                **{**sig.options, **options},
            )

            if last_result.is_failure:
                return last_result

            result = last_result.result

        return last_result

    def send_chord(
        self,
        header: "Group",
        body: "Signature",
        **options,
    ) -> "TaskResult":
        """Execute a chord synchronously."""
        # Run header
        group_result = self.send_group(header.tasks, **options)

        # Collect results
        results = [r.result for r in group_result.results]

        # Run body with results
        return self.send_task(
            task=body.task,
            args=(results,) + body.args,
            kwargs=body.kwargs,
            **{**body.options, **options},
        )

    def configure(self, **config) -> None:
        """Update configuration."""
        self._config.update(config)

    def close(self) -> None:
        """Clear stored results."""
        self._results.clear()
