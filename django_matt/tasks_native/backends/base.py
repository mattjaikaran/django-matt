"""
Base backend interface for the native task engine.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import NativeTaskConfig
    from ..core import NativeTask
    from ..types import TaskMeta, TaskResult


class BaseNativeBackend(ABC):
    """
    Abstract base class for task backends.

    All backends must implement these methods to provide
    consistent task execution across different systems.
    """

    name: str = "base"

    def __init__(self, config: "NativeTaskConfig"):
        self.config = config

    @abstractmethod
    def enqueue(
        self,
        task: "NativeTask",
        args: tuple,
        kwargs: dict,
        meta: "TaskMeta",
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
    ) -> "TaskResult":
        """
        Enqueue a task for execution.

        Args:
            task: The task to execute
            args: Positional arguments
            kwargs: Keyword arguments
            meta: Task metadata
            countdown: Delay in seconds
            eta: Execute at specific time
            expires: Task expiry in seconds

        Returns:
            TaskResult for tracking the task
        """

    @abstractmethod
    def get_result(self, task_id: str) -> "TaskResult | None":
        """
        Get the result of a task.

        Args:
            task_id: The task ID

        Returns:
            TaskResult if found, None otherwise
        """

    @abstractmethod
    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: The task ID
            terminate: Whether to terminate running tasks

        Returns:
            True if task was revoked
        """

    @abstractmethod
    def get_queue_length(self, queue: str = "default") -> int:
        """
        Get the number of tasks in a queue.

        Args:
            queue: Queue name

        Returns:
            Number of pending tasks
        """

    @abstractmethod
    def purge_queue(self, queue: str = "default") -> int:
        """
        Remove all pending tasks from a queue.

        Args:
            queue: Queue name

        Returns:
            Number of tasks purged
        """

    def health_check(self) -> dict[str, Any]:
        """
        Check backend health.

        Returns:
            Health status dict with 'healthy' bool and optional details
        """
        return {"healthy": True, "backend": self.name}

    def close(self) -> None:
        """Close backend connections."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
