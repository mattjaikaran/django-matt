"""
Core task implementation with Pydantic validation.

Provides type-safe task definitions that validate payloads at enqueue time.
"""

import asyncio
import inspect
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Generic, ParamSpec, TypeVar, get_type_hints, overload

from pydantic import BaseModel, ValidationError

from .config import get_backend
from .registry import task_registry
from .types import (
    TaskExecutionError,
    TaskMeta,
    TaskOptions,
    TaskResult,
    TaskState,
    TaskValidationError,
)

P = ParamSpec("P")
R = TypeVar("R")
PayloadT = TypeVar("PayloadT", bound=BaseModel)


class NativeTask(Generic[P, R]):
    """
    A type-safe background task with Pydantic validation.

    Tasks can be defined with typed payloads that are validated at enqueue time:

        class EmailPayload(BaseModel):
            user_id: int
            template: str

        @task
        async def send_email(payload: EmailPayload) -> bool:
            user = await User.objects.aget(id=payload.user_id)
            return await deliver_email(user, payload.template)

        # Enqueue - validates payload automatically
        send_email.delay(EmailPayload(user_id=1, template="welcome"))
    """

    def __init__(
        self,
        func: Callable[P, R] | Callable[P, Awaitable[R]],
        *,
        name: str | None = None,
        queue: str | None = None,
        priority: int = 0,
        timeout: int | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        rate_limit: str | None = None,
        expires: int | None = None,
        ignore_result: bool = False,
        bind: bool = False,
        validate_payload: bool = True,
    ):
        self.func = func
        self.name = name or f"{func.__module__}.{func.__qualname__}"
        self.bind = bind
        self.validate_payload = validate_payload
        self._is_async = asyncio.iscoroutinefunction(func)

        # Extract payload type from function signature
        self._payload_type = self._extract_payload_type(func)

        self.options = TaskOptions(
            queue=queue or "default",
            priority=priority,
            timeout=timeout,
            max_retries=max_retries if max_retries is not None else 3,
            retry_delay=retry_delay if retry_delay is not None else 60.0,
            rate_limit=rate_limit,
            expires=expires,
            ignore_result=ignore_result,
        )

        # Failure handlers
        self._on_failure_handlers: list[Callable[[NativeTask, Exception, Any], Any]] = []
        self._on_success_handlers: list[Callable[[NativeTask, Any, Any], Any]] = []

        # Register task
        task_registry.register(self)

    def _extract_payload_type(self, func: Callable) -> type[BaseModel] | None:
        """Extract Pydantic model type from function's first parameter."""
        try:
            hints = get_type_hints(func)
            sig = inspect.signature(func)
            params = list(sig.parameters.values())

            # Skip 'self' if bind=True
            start_idx = 1 if self.bind else 0

            if len(params) > start_idx:
                first_param = params[start_idx]
                param_type = hints.get(first_param.name)

                if param_type and isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    return param_type
        except Exception:
            pass
        return None

    def _validate_args(self, args: tuple, kwargs: dict) -> tuple[tuple, dict]:
        """Validate arguments, converting dicts to Pydantic models if needed."""
        if not self.validate_payload or not self._payload_type:
            return args, kwargs

        if args:
            first_arg = args[0]
            if isinstance(first_arg, dict):
                try:
                    validated = self._payload_type.model_validate(first_arg)
                    return (validated, *args[1:]), kwargs
                except ValidationError as e:
                    raise TaskValidationError(
                        f"Invalid payload for task '{self.name}'",
                        errors=e.errors(),
                    ) from e
            elif isinstance(first_arg, self._payload_type):
                return args, kwargs

        return args, kwargs

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Execute the task synchronously."""
        if self.bind:
            if self._is_async:
                return asyncio.get_event_loop().run_until_complete(
                    self.func(self, *args, **kwargs)
                )
            return self.func(self, *args, **kwargs)

        if self._is_async:
            return asyncio.get_event_loop().run_until_complete(
                self.func(*args, **kwargs)
            )
        return self.func(*args, **kwargs)

    def delay(self, *args: P.args, **kwargs: P.kwargs) -> TaskResult[R]:
        """
        Execute the task asynchronously with default options.

        Returns:
            TaskResult for tracking the task
        """
        return self.apply_async(args=args, kwargs=kwargs)

    def apply_async(
        self,
        args: tuple | None = None,
        kwargs: dict | None = None,
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
        queue: str | None = None,
        priority: int | None = None,
        task_id: str | None = None,
    ) -> TaskResult[R]:
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

        Returns:
            TaskResult for tracking the task
        """
        args = args or ()
        kwargs = kwargs or {}

        # Validate payload
        args, kwargs = self._validate_args(args, kwargs)

        task_id = task_id or str(uuid.uuid4())

        meta = TaskMeta(
            task_id=task_id,
            task_name=self.name,
            state=TaskState.PENDING,
            queue=queue or self.options.queue,
            priority=priority if priority is not None else self.options.priority,
            max_retries=self.options.max_retries,
        )

        backend = get_backend()
        return backend.enqueue(
            task=self,
            args=args,
            kwargs=kwargs,
            meta=meta,
            countdown=countdown,
            eta=eta,
            expires=expires or self.options.expires,
        )

    def apply(
        self,
        args: tuple | None = None,
        kwargs: dict | None = None,
        throw: bool = True,
    ) -> TaskResult[R]:
        """
        Execute the task synchronously.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments
            throw: Whether to raise exceptions

        Returns:
            TaskResult with the result
        """
        args = args or ()
        kwargs = kwargs or {}

        # Validate payload
        args, kwargs = self._validate_args(args, kwargs)

        task_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        meta = TaskMeta(
            task_id=task_id,
            task_name=self.name,
            state=TaskState.RUNNING,
            started_at=started_at,
        )

        try:
            if self.bind:
                if self._is_async:
                    result = asyncio.get_event_loop().run_until_complete(
                        self.func(self, *args, **kwargs)
                    )
                else:
                    result = self.func(self, *args, **kwargs)
            else:
                if self._is_async:
                    result = asyncio.get_event_loop().run_until_complete(
                        self.func(*args, **kwargs)
                    )
                else:
                    result = self.func(*args, **kwargs)

            meta.state = TaskState.COMPLETED
            meta.result = result
            meta.completed_at = datetime.now(UTC)

            # Call success handlers
            for handler in self._on_success_handlers:
                try:
                    handler(self, result, args)
                except Exception:
                    pass

            return TaskResult(task_id=task_id, meta=meta)

        except Exception as e:
            meta.state = TaskState.FAILED
            meta.error = str(e)
            meta.traceback = traceback.format_exc()
            meta.completed_at = datetime.now(UTC)

            # Call failure handlers
            for handler in self._on_failure_handlers:
                try:
                    handler(self, e, args)
                except Exception:
                    pass

            if throw:
                raise TaskExecutionError(str(e), meta.traceback) from e

            return TaskResult(task_id=task_id, meta=meta)

    def on_failure(
        self, handler: Callable[["NativeTask", Exception, Any], Any]
    ) -> Callable[["NativeTask", Exception, Any], Any]:
        """
        Register a failure handler.

        Usage:
            @send_email.on_failure
            async def handle_email_failure(task, exc, payload):
                await notify_ops(f"Email task failed: {exc}")
        """
        self._on_failure_handlers.append(handler)
        return handler

    def on_success(
        self, handler: Callable[["NativeTask", Any, Any], Any]
    ) -> Callable[["NativeTask", Any, Any], Any]:
        """
        Register a success handler.

        Usage:
            @send_email.on_success
            async def handle_email_success(task, result, payload):
                await log_success(f"Email sent: {result}")
        """
        self._on_success_handlers.append(handler)
        return handler

    @property
    def payload_type(self) -> type[BaseModel] | None:
        """Get the Pydantic model type for this task's payload."""
        return self._payload_type

    @property
    def is_async(self) -> bool:
        """Check if this task is async."""
        return self._is_async

    def __repr__(self) -> str:
        return f"NativeTask({self.name})"


@overload
def task(func: Callable[P, R]) -> NativeTask[P, R]: ...


@overload
def task(
    *,
    name: str | None = None,
    queue: str | None = None,
    priority: int = 0,
    timeout: int | None = None,
    max_retries: int | None = None,
    retry_delay: float | None = None,
    rate_limit: str | None = None,
    expires: int | None = None,
    ignore_result: bool = False,
    bind: bool = False,
    validate_payload: bool = True,
) -> Callable[[Callable[P, R]], NativeTask[P, R]]: ...


def task(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    queue: str | None = None,
    priority: int = 0,
    timeout: int | None = None,
    max_retries: int | None = None,
    retry_delay: float | None = None,
    rate_limit: str | None = None,
    expires: int | None = None,
    ignore_result: bool = False,
    bind: bool = False,
    validate_payload: bool = True,
) -> NativeTask[P, R] | Callable[[Callable[P, R]], NativeTask[P, R]]:
    """
    Decorator to define a type-safe background task.

    Usage:
        @task
        def simple_task(x: int, y: int) -> int:
            return x + y

        @task(max_retries=5, retry_delay=30)
        async def reliable_task() -> None:
            await do_something()

        # With Pydantic validation
        class EmailPayload(BaseModel):
            user_id: int
            template: str

        @task
        async def send_email(payload: EmailPayload) -> bool:
            user = await User.objects.aget(id=payload.user_id)
            return await deliver_email(user, payload.template)

        # Validates at enqueue time
        send_email.delay(EmailPayload(user_id=1, template="welcome"))

        # Dict is auto-converted and validated
        send_email.delay({"user_id": 1, "template": "welcome"})
    """

    def decorator(fn: Callable[P, R]) -> NativeTask[P, R]:
        return NativeTask(
            fn,
            name=name,
            queue=queue,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            rate_limit=rate_limit,
            expires=expires,
            ignore_result=ignore_result,
            bind=bind,
            validate_payload=validate_payload,
        )

    if func is not None:
        return decorator(func)
    return decorator
