"""
Type definitions for the native task engine.

Provides type-safe abstractions for background tasks with Pydantic validation.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")
P = TypeVar("P", bound=BaseModel)
R = TypeVar("R")


class TaskState(Enum):
    """State of a task execution."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


@dataclass
class TaskMeta:
    """
    Metadata for a task execution.

    Tracks the full lifecycle of a task from enqueue to completion.
    """

    task_id: str
    task_name: str
    state: TaskState = TaskState.PENDING
    queue: str = "default"
    priority: int = 0

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Execution
    worker_id: str | None = None
    retries: int = 0
    max_retries: int = 0

    # Result
    result: Any = None
    error: str | None = None
    traceback: str | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get task duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    @property
    def wait_time_ms(self) -> float | None:
        """Get time spent waiting in queue in milliseconds."""
        if self.queued_at and self.started_at:
            return (self.started_at - self.queued_at).total_seconds() * 1000
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.state in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.DEAD_LETTER,
        )


@dataclass
class TaskResult[R]:
    """
    Result of a task execution.

    Provides a unified interface for checking task status and results.
    """

    task_id: str
    meta: TaskMeta

    @property
    def state(self) -> TaskState:
        return self.meta.state

    @property
    def is_pending(self) -> bool:
        return self.meta.state == TaskState.PENDING

    @property
    def is_running(self) -> bool:
        return self.meta.state == TaskState.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.meta.state == TaskState.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.meta.state == TaskState.FAILED

    @property
    def is_terminal(self) -> bool:
        return self.meta.is_terminal

    @property
    def result(self) -> R | None:
        """Get the task result if completed."""
        if self.meta.state == TaskState.COMPLETED:
            return self.meta.result
        return None

    @property
    def error(self) -> str | None:
        """Get the error message if failed."""
        return self.meta.error

    def get(self, timeout: float | None = None, propagate: bool = True) -> R:
        """
        Wait for the task to complete and return result.

        Args:
            timeout: Maximum time to wait in seconds
            propagate: Whether to re-raise exceptions

        Returns:
            The task result

        Raises:
            TimeoutError: If timeout is exceeded
            Exception: If task failed and propagate=True
        """
        if self.is_failed and propagate:
            raise TaskExecutionError(self.meta.error or "Task failed", self.meta.traceback)
        return self.meta.result


class TaskExecutionError(Exception):
    """Raised when a task execution fails."""

    def __init__(self, message: str, traceback: str | None = None):
        self.message = message
        self.traceback = traceback
        super().__init__(message)


class TaskValidationError(Exception):
    """Raised when task payload validation fails."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


@dataclass
class TaskOptions:
    """Configuration options for task execution."""

    queue: str = "default"
    priority: int = 0
    timeout: int | None = None
    max_retries: int = 3
    retry_delay: float = 60.0
    rate_limit: str | None = None
    expires: int | None = None
    ignore_result: bool = False
    track_started: bool = True
    acks_late: bool = False


TaskFunc = Callable[..., Any] | Callable[..., Awaitable[Any]]
