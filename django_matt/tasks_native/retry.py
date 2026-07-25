# file-length-max: 500
"""
Retry policies for the native task engine.

Provides flexible retry strategies for failed tasks.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


class RetryPolicy(ABC):
    """
    Base class for retry policies.

    Retry policies determine when and how to retry failed tasks.
    """

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """
        Get the delay before the next retry.

        Args:
            attempt: The retry attempt number (1-indexed)

        Returns:
            Delay in seconds
        """

    @abstractmethod
    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """
        Check if the task should be retried.

        Args:
            attempt: The retry attempt number (1-indexed)
            exception: The exception that was raised (if any)

        Returns:
            True if the task should be retried
        """


@dataclass
class ExponentialBackoff(RetryPolicy):
    """
    Exponential backoff retry policy.

    Delays increase exponentially with each retry attempt.
    Useful for rate-limited APIs or transient failures.

    Usage:
        from django_matt.tasks_native import task, retry

        @task(retry=retry.exponential(max_retries=5, base_delay=1.0))
        async def call_api(url: str):
            ...

    The delays would be: 1s, 2s, 4s, 8s, 16s (capped at max_delay)
    """

    base_delay: float = 1.0
    max_delay: float = 300.0
    multiplier: float = 2.0
    max_retries: int = 3
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_on: Sequence[type[Exception]] | None = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = self.base_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return delay

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """Check if we should retry based on attempt count and exception type."""
        if attempt > self.max_retries:
            return False

        if self.retry_on and exception:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class LinearBackoff(RetryPolicy):
    """
    Linear backoff retry policy.

    Delays increase linearly with each retry attempt.

    Usage:
        @task(retry=retry.linear(max_retries=3, delay=10))
        async def send_webhook(payload: dict):
            ...

    The delays would be: 10s, 20s, 30s
    """

    delay: float = 10.0
    increment: float = 10.0
    max_delay: float = 300.0
    max_retries: int = 3
    retry_on: Sequence[type[Exception]] | None = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with linear backoff."""
        calculated = self.delay + (self.increment * (attempt - 1))
        return min(calculated, self.max_delay)

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """Check if we should retry."""
        if attempt > self.max_retries:
            return False

        if self.retry_on and exception:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class FixedDelay(RetryPolicy):
    """
    Fixed delay retry policy.

    Uses a constant delay between all retry attempts.

    Usage:
        @task(retry=retry.fixed(delay=60, max_retries=3))
        async def reliable_task():
            ...

    The delays would be: 60s, 60s, 60s
    """

    delay: float = 60.0
    max_retries: int = 3
    retry_on: Sequence[type[Exception]] | None = None

    def get_delay(self, attempt: int) -> float:
        """Return the fixed delay."""
        return self.delay

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """Check if we should retry."""
        if attempt > self.max_retries:
            return False

        if self.retry_on and exception:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class NoRetry(RetryPolicy):
    """
    No retry policy - tasks fail immediately on first error.

    Usage:
        @task(retry=retry.none())
        async def one_shot_task():
            ...
    """

    def get_delay(self, attempt: int) -> float:
        return 0

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        return False


@dataclass
class RetryOnException(RetryPolicy):
    """
    Retry only on specific exception types.

    Usage:
        @task(retry=retry.on_exception(
            [ConnectionError, TimeoutError],
            max_retries=5,
            delay=5,
        ))
        async def network_task():
            ...
    """

    exceptions: Sequence[type[Exception]]
    max_retries: int = 3
    delay: float = 5.0
    exponential: bool = False
    multiplier: float = 2.0

    def get_delay(self, attempt: int) -> float:
        if self.exponential:
            return self.delay * (self.multiplier ** (attempt - 1))
        return self.delay

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        if attempt > self.max_retries:
            return False

        if exception is None:
            return False

        return any(isinstance(exception, exc_type) for exc_type in self.exceptions)


@dataclass
class CompositePolicy(RetryPolicy):
    """
    Combine multiple retry policies.

    Checks each policy in order. First policy that allows retry determines behavior.

    Usage:
        @task(retry=retry.composite([
            retry.on_exception([ConnectionError], max_retries=5, delay=1),
            retry.on_exception([ValueError], max_retries=2, delay=10),
        ]))
        async def complex_task():
            ...
    """

    policies: Sequence[RetryPolicy] = field(default_factory=list)

    def get_delay(self, attempt: int) -> float:
        """Get delay from the first policy that would retry."""
        for policy in self.policies:
            return policy.get_delay(attempt)
        return 0

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """Check if any policy allows retry."""
        return any(policy.should_retry(attempt, exception) for policy in self.policies)


# Convenience factory functions
class retry:
    """
    Factory for creating retry policies.

    Usage:
        from django_matt.tasks_native import task, retry

        @task(retry=retry.exponential(max_retries=5, base_delay=1.0))
        async def flaky_api_call(url: str):
            ...

        @task(retry=retry.linear(max_retries=3, delay=10))
        async def send_webhook(payload: dict):
            ...
    """

    @staticmethod
    def exponential(
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        retry_on: Sequence[type[Exception]] | None = None,
    ) -> ExponentialBackoff:
        """Create exponential backoff retry policy."""
        return ExponentialBackoff(
            base_delay=base_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            max_retries=max_retries,
            jitter=jitter,
            retry_on=retry_on,
        )

    @staticmethod
    def linear(
        max_retries: int = 3,
        delay: float = 10.0,
        increment: float | None = None,
        max_delay: float = 300.0,
        retry_on: Sequence[type[Exception]] | None = None,
    ) -> LinearBackoff:
        """Create linear backoff retry policy."""
        return LinearBackoff(
            delay=delay,
            increment=increment if increment is not None else delay,
            max_delay=max_delay,
            max_retries=max_retries,
            retry_on=retry_on,
        )

    @staticmethod
    def fixed(
        delay: float = 60.0,
        max_retries: int = 3,
        retry_on: Sequence[type[Exception]] | None = None,
    ) -> FixedDelay:
        """Create fixed delay retry policy."""
        return FixedDelay(
            delay=delay,
            max_retries=max_retries,
            retry_on=retry_on,
        )

    @staticmethod
    def none() -> NoRetry:
        """Create no-retry policy."""
        return NoRetry()

    @staticmethod
    def on_exception(
        exceptions: Sequence[type[Exception]],
        max_retries: int = 3,
        delay: float = 5.0,
        exponential: bool = False,
        multiplier: float = 2.0,
    ) -> RetryOnException:
        """Create exception-specific retry policy."""
        return RetryOnException(
            exceptions=exceptions,
            max_retries=max_retries,
            delay=delay,
            exponential=exponential,
            multiplier=multiplier,
        )

    @staticmethod
    def composite(policies: Sequence[RetryPolicy]) -> CompositePolicy:
        """Combine multiple retry policies."""
        return CompositePolicy(policies=policies)


class RetryState:
    """
    Tracks retry state for a task execution.

    Used by backends to manage retries.
    """

    def __init__(
        self,
        policy: RetryPolicy,
        max_retries: int | None = None,
    ):
        self.policy = policy
        self.max_retries = max_retries or getattr(policy, "max_retries", 3)
        self.attempt = 0
        self.last_exception: Exception | None = None
        self.delays: list[float] = []

    def record_attempt(self, exception: Exception | None = None) -> None:
        """Record a retry attempt."""
        self.attempt += 1
        self.last_exception = exception
        if self.attempt > 1:
            self.delays.append(self.policy.get_delay(self.attempt - 1))

    def should_retry(self) -> bool:
        """Check if task should be retried."""
        return self.policy.should_retry(self.attempt, self.last_exception)

    def get_next_delay(self) -> float:
        """Get the delay before the next retry."""
        return self.policy.get_delay(self.attempt)

    @property
    def total_delay(self) -> float:
        """Get total delay so far."""
        return sum(self.delays)

    @property
    def is_exhausted(self) -> bool:
        """Check if retries are exhausted."""
        return self.attempt >= self.max_retries


class TaskFailureHandler:
    """
    Handles task failures with configurable strategies.

    Supports:
    - Retry logic
    - Dead letter queue
    - Custom failure callbacks
    - Error notification
    """

    def __init__(self):
        self._global_handlers: list[Any] = []

    def register_handler(self, handler: Any) -> None:
        """Register a global failure handler."""
        self._global_handlers.append(handler)

    def unregister_handler(self, handler: Any) -> None:
        """Unregister a global failure handler."""
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)

    async def handle_failure(
        self,
        task: Any,
        exception: Exception,
        args: tuple,
        kwargs: dict,
        retry_state: RetryState | None = None,
    ) -> dict[str, Any]:
        """
        Handle a task failure.

        Returns:
            Dict with 'retry' bool and optional 'delay' float
        """
        result = {"retry": False, "delay": 0.0, "dead_letter": False}

        # Check retry policy
        if retry_state and retry_state.should_retry():
            result["retry"] = True
            result["delay"] = retry_state.get_next_delay()
        elif retry_state and retry_state.is_exhausted:
            result["dead_letter"] = True

        # Call task-level failure handlers
        for handler in getattr(task, "_on_failure_handlers", []):
            try:
                import asyncio

                if asyncio.iscoroutinefunction(handler):
                    await handler(task, exception, args)
                else:
                    handler(task, exception, args)
            except Exception:
                pass

        # Call global handlers
        for handler in self._global_handlers:
            try:
                import asyncio

                if asyncio.iscoroutinefunction(handler):
                    await handler(task, exception, args, kwargs)
                else:
                    handler(task, exception, args, kwargs)
            except Exception:
                pass

        return result


# Global failure handler
failure_handler = TaskFailureHandler()
