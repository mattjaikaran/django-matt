"""
Retry policies for task execution.

Provides different strategies for retrying failed tasks.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence, Type


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
        pass

    @abstractmethod
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """
        Check if the task should be retried.

        Args:
            attempt: The retry attempt number (1-indexed)
            exception: The exception that was raised

        Returns:
            True if the task should be retried
        """
        pass


@dataclass
class ExponentialBackoff(RetryPolicy):
    """
    Exponential backoff retry policy.

    Delays increase exponentially with each retry attempt.
    Useful for rate-limited APIs or transient failures.

    Usage:
        @task(retry_policy=ExponentialBackoff(
            initial_delay=1,
            max_delay=300,
            multiplier=2,
            max_retries=5,
        ))
        def call_api():
            ...

    The delays would be: 1s, 2s, 4s, 8s, 16s (capped at max_delay)
    """

    initial_delay: float = 1.0
    max_delay: float = 300.0
    multiplier: float = 2.0
    max_retries: int = 3
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_on: Sequence[Type[Exception]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = self.initial_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add random jitter to prevent thundering herd
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry based on attempt count and exception type."""
        if attempt > self.max_retries:
            return False

        if self.retry_on:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class LinearBackoff(RetryPolicy):
    """
    Linear backoff retry policy.

    Delays increase linearly with each retry attempt.

    Usage:
        @task(retry_policy=LinearBackoff(
            initial_delay=5,
            increment=5,
            max_retries=3,
        ))
        def my_task():
            ...

    The delays would be: 5s, 10s, 15s
    """

    initial_delay: float = 5.0
    increment: float = 5.0
    max_delay: float = 300.0
    max_retries: int = 3
    retry_on: Sequence[Type[Exception]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with linear backoff."""
        delay = self.initial_delay + (self.increment * (attempt - 1))
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry."""
        if attempt > self.max_retries:
            return False

        if self.retry_on:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class FixedDelay(RetryPolicy):
    """
    Fixed delay retry policy.

    Uses a constant delay between all retry attempts.

    Usage:
        @task(retry_policy=FixedDelay(delay=60, max_retries=3))
        def my_task():
            ...

    The delays would be: 60s, 60s, 60s
    """

    delay: float = 60.0
    max_retries: int = 3
    retry_on: Sequence[Type[Exception]] = None

    def get_delay(self, attempt: int) -> float:
        """Return the fixed delay."""
        return self.delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry."""
        if attempt > self.max_retries:
            return False

        if self.retry_on:
            return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

        return True


@dataclass
class NoRetry(RetryPolicy):
    """
    No retry policy - tasks fail immediately.

    Usage:
        @task(retry_policy=NoRetry())
        def one_shot_task():
            ...
    """

    def get_delay(self, attempt: int) -> float:
        return 0

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        return False


@dataclass
class RetryOnException(RetryPolicy):
    """
    Retry only on specific exceptions.

    Usage:
        @task(retry_policy=RetryOnException(
            exceptions=[ConnectionError, TimeoutError],
            max_retries=3,
            delay=5,
        ))
        def network_task():
            ...
    """

    exceptions: Sequence[Type[Exception]]
    max_retries: int = 3
    delay: float = 5.0
    exponential: bool = False
    multiplier: float = 2.0

    def get_delay(self, attempt: int) -> float:
        if self.exponential:
            return self.delay * (self.multiplier ** (attempt - 1))
        return self.delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        if attempt > self.max_retries:
            return False

        return any(isinstance(exception, exc_type) for exc_type in self.exceptions)


@dataclass
class CompositeRetryPolicy(RetryPolicy):
    """
    Combine multiple retry policies.

    The first policy that allows a retry determines the behavior.

    Usage:
        @task(retry_policy=CompositeRetryPolicy([
            RetryOnException([ConnectionError], max_retries=5, delay=1),
            RetryOnException([ValueError], max_retries=2, delay=10),
        ]))
        def complex_task():
            ...
    """

    policies: Sequence[RetryPolicy]

    def get_delay(self, attempt: int) -> float:
        """Get delay from the first policy that would retry."""
        for policy in self.policies:
            return policy.get_delay(attempt)
        return 0

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if any policy allows retry."""
        return any(
            policy.should_retry(attempt, exception)
            for policy in self.policies
        )
