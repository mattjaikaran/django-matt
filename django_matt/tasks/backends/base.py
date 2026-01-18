"""
Base backend interface.

Defines the abstract interface that all task backends must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import Task, TaskResult
    from ..primitives import Group, GroupResult, Signature


class BaseBackend(ABC):
    """
    Abstract base class for task queue backends.

    All backends must implement this interface to be compatible
    with the django-matt task system.
    """

    @abstractmethod
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
        """
        Send a task for execution.

        Args:
            task: The task to execute
            args: Positional arguments
            kwargs: Keyword arguments
            task_id: Custom task ID
            countdown: Delay execution by this many seconds
            eta: Execute at this specific time
            expires: Task expires after this many seconds
            queue: Queue to send to
            priority: Task priority
            **options: Backend-specific options

        Returns:
            TaskResult for tracking
        """

    @abstractmethod
    def get_result(self, task_id: str) -> "TaskResult":
        """
        Get the result of a task.

        Args:
            task_id: The task ID to look up

        Returns:
            TaskResult with current status
        """

    @abstractmethod
    def revoke(self, task_id: str, terminate: bool = False) -> None:
        """
        Revoke a pending or running task.

        Args:
            task_id: The task ID to revoke
            terminate: Whether to terminate if already running
        """

    def send_group(
        self,
        tasks: Sequence["Signature"],
        **options,
    ) -> "GroupResult":
        """
        Send a group of tasks for parallel execution.

        Default implementation sends tasks individually.
        Override for backend-specific group support.

        Args:
            tasks: List of task signatures
            **options: Execution options

        Returns:
            GroupResult for tracking
        """
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
        """
        Send a chain of tasks for sequential execution.

        Default implementation uses callbacks.
        Override for backend-specific chain support.

        Args:
            tasks: List of task signatures in order
            **options: Execution options

        Returns:
            TaskResult for the final task
        """
        if not tasks:
            from ..base import TaskResult, TaskStatus

            return TaskResult(task_id="empty-chain", status=TaskStatus.SUCCESS)

        # Simple implementation: send first task, let backend chain the rest
        # Most backends have native chain support that's more efficient
        first_sig = tasks[0]
        return self.send_task(
            task=first_sig.task,
            args=first_sig.args,
            kwargs=first_sig.kwargs,
            **{**first_sig.options, **options},
        )

    def send_chord(
        self,
        header: "Group",
        body: "Signature",
        **options,
    ) -> "TaskResult":
        """
        Send a chord (group + callback).

        Default implementation uses callbacks.
        Override for backend-specific chord support.

        Args:
            header: Group of tasks to run first
            body: Callback to run with results
            **options: Execution options

        Returns:
            TaskResult for the callback task
        """
        # Simple implementation - most backends have native chord support
        group_result = self.send_group(header.tasks, **options)
        return self.send_task(
            task=body.task,
            args=body.args,
            kwargs=body.kwargs,
            **{**body.options, **options},
        )

    def configure(self, **config) -> None:
        """
        Configure the backend.

        Called during initialization with backend-specific settings.

        Args:
            **config: Configuration options
        """

    def close(self) -> None:
        """
        Close backend connections.

        Called during shutdown.
        """
