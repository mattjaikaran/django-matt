"""
Base task classes and registry.

Provides the core abstractions for background tasks.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .backends import BaseBackend
    from .retry import RetryPolicy


class TaskStatus(Enum):
    """Status of a task execution."""

    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


@dataclass
class TaskResult:
    """
    Result of a task execution.

    Provides a unified interface for checking task status and results
    across different backends.
    """

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    traceback: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retries: int = 0

    @property
    def is_pending(self) -> bool:
        return self.status == TaskStatus.PENDING

    @property
    def is_started(self) -> bool:
        return self.status == TaskStatus.STARTED

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self.status == TaskStatus.FAILURE

    @property
    def is_complete(self) -> bool:
        return self.status in (TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED)

    def get(self, timeout: float = None, propagate: bool = True) -> Any:
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
        # This is overridden by backend-specific implementations
        if self.is_failure and propagate:
            raise Exception(self.error)
        return self.result


@dataclass
class TaskOptions:
    """Options for task execution."""

    queue: str | None = None
    priority: int = 0
    timeout: int | None = None
    retry: int = 0
    retry_delay: int = 0
    retry_policy: Optional["RetryPolicy"] = None
    rate_limit: str | None = None
    ignore_result: bool = False
    store_errors_even_if_ignored: bool = False
    track_started: bool = False
    acks_late: bool = False
    expires: int | None = None


class Task:
    """
    Represents a background task.

    This is the main interface for defining and calling background tasks.
    Tasks can be executed synchronously, asynchronously, or scheduled.

    Usage:
        @task
        def my_task(x, y):
            return x + y

        # Call synchronously
        result = my_task(1, 2)

        # Call asynchronously
        async_result = my_task.delay(1, 2)

        # Call with options
        async_result = my_task.apply_async(
            args=(1, 2),
            countdown=60,
            queue="high-priority",
        )
    """

    def __init__(
        self,
        func: Callable,
        name: str = None,
        queue: str = None,
        priority: int = 0,
        timeout: int = None,
        retry: int = 0,
        retry_delay: int = 0,
        retry_policy: "RetryPolicy" = None,
        rate_limit: str = None,
        ignore_result: bool = False,
        bind: bool = False,
        **kwargs,
    ):
        """
        Initialize a task.

        Args:
            func: The function to execute
            name: Task name (defaults to function's qualified name)
            queue: Default queue for this task
            priority: Task priority (higher = more important)
            timeout: Execution timeout in seconds
            retry: Number of retries on failure
            retry_delay: Delay between retries in seconds
            retry_policy: Custom retry policy
            rate_limit: Rate limit (e.g., "10/m" for 10 per minute)
            ignore_result: Whether to discard the result
            bind: Whether to pass the task instance as first argument
        """
        self.func = func
        self.name = name or f"{func.__module__}.{func.__qualname__}"
        self.bind = bind

        self.options = TaskOptions(
            queue=queue,
            priority=priority,
            timeout=timeout,
            retry=retry,
            retry_delay=retry_delay,
            retry_policy=retry_policy,
            rate_limit=rate_limit,
            ignore_result=ignore_result,
        )

        # Register the task
        task_registry.register(self)

        # Backend will be set later
        self._backend: BaseBackend | None = None

    @property
    def backend(self) -> "BaseBackend":
        """Get the task backend."""
        if self._backend is None:
            from .config import get_backend

            self._backend = get_backend()
        return self._backend

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the task synchronously."""
        if self.bind:
            return self.func(self, *args, **kwargs)
        return self.func(*args, **kwargs)

    def delay(self, *args, **kwargs) -> TaskResult:
        """
        Execute the task asynchronously with default options.

        This is a shortcut for apply_async(args=args, kwargs=kwargs).

        Returns:
            TaskResult for tracking the task
        """
        return self.apply_async(args=args, kwargs=kwargs)

    def apply_async(
        self,
        args: tuple = None,
        kwargs: dict = None,
        countdown: int = None,
        eta: datetime = None,
        expires: int = None,
        queue: str = None,
        priority: int = None,
        task_id: str = None,
        **options,
    ) -> TaskResult:
        """
        Execute the task asynchronously with options.

        Args:
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            countdown: Delay execution by this many seconds
            eta: Execute at this specific time
            expires: Task expires after this many seconds
            queue: Override the default queue
            priority: Override the default priority
            task_id: Custom task ID
            **options: Additional backend-specific options

        Returns:
            TaskResult for tracking the task
        """
        task_id = task_id or str(uuid.uuid4())

        return self.backend.send_task(
            task=self,
            args=args or (),
            kwargs=kwargs or {},
            task_id=task_id,
            countdown=countdown,
            eta=eta,
            expires=expires or self.options.expires,
            queue=queue or self.options.queue,
            priority=priority if priority is not None else self.options.priority,
            **options,
        )

    def apply(
        self,
        args: tuple = None,
        kwargs: dict = None,
        throw: bool = True,
    ) -> TaskResult:
        """
        Execute the task synchronously.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments
            throw: Whether to raise exceptions

        Returns:
            TaskResult with the result
        """
        task_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        try:
            if self.bind:
                result = self.func(self, *(args or ()), **(kwargs or {}))
            else:
                result = self.func(*(args or ()), **(kwargs or {}))

            return TaskResult(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                result=result,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        except Exception as e:
            if throw:
                raise
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILURE,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def s(self, *args, **kwargs) -> "Signature":
        """
        Create a signature (lazy task call).

        This is used for building task workflows.

        Returns:
            Signature that can be used in chains/groups
        """
        from .primitives import Signature

        return Signature(self, args=args, kwargs=kwargs)

    def si(self, *args, **kwargs) -> "Signature":
        """
        Create an immutable signature.

        Immutable signatures don't receive results from previous tasks.

        Returns:
            Immutable Signature
        """
        from .primitives import Signature

        return Signature(self, args=args, kwargs=kwargs, immutable=True)

    def retry(
        self,
        exc: Exception = None,
        countdown: int = None,
        max_retries: int = None,
    ) -> None:
        """
        Retry the current task.

        Call this from within a task to trigger a retry.

        Args:
            exc: The exception that caused the retry
            countdown: Delay before retrying
            max_retries: Override max retries

        Raises:
            Retry: Signal to retry the task
        """
        raise Retry(exc=exc, countdown=countdown, max_retries=max_retries)

    def __repr__(self):
        return f"Task({self.name})"


class Retry(Exception):
    """
    Exception raised to signal a task should be retried.

    This is caught by the backend and triggers a retry.
    """

    def __init__(
        self,
        exc: Exception = None,
        countdown: int = None,
        max_retries: int = None,
    ):
        self.exc = exc
        self.countdown = countdown
        self.max_retries = max_retries
        super().__init__(str(exc) if exc else "Task retry requested")


class TaskRegistry:
    """
    Registry for all defined tasks.

    Tasks are automatically registered when decorated with @task.
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def register(self, task: Task) -> None:
        """Register a task."""
        self._tasks[task.name] = task

    def get(self, name: str) -> Task | None:
        """Get a task by name."""
        return self._tasks.get(name)

    def unregister(self, name: str) -> None:
        """Unregister a task."""
        self._tasks.pop(name, None)

    def all(self) -> dict[str, Task]:
        """Get all registered tasks."""
        return self._tasks.copy()

    def __contains__(self, name: str) -> bool:
        return name in self._tasks

    def __iter__(self):
        return iter(self._tasks.values())

    def __len__(self):
        return len(self._tasks)


# Global task registry
task_registry = TaskRegistry()
