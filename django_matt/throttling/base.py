"""
Base throttle class for django-matt.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest


class BaseThrottle(ABC):
    """
    Base class for all throttle implementations.

    Throttles control the rate of requests that clients can make to an API.
    Subclasses must implement `get_cache_key` and optionally override
    `allow_request` for custom throttling logic.
    """

    # Default rate format: "num_requests/period"
    # Period can be: s (second), m (minute), h (hour), d (day)
    rate: str | None = None

    # Backend for storing throttle data (set by middleware/decorator)
    backend: Any = None

    def __init__(self, rate: str | None = None) -> None:
        """
        Initialize the throttle.

        Args:
            rate: Rate string like "100/hour", "10/minute", "1000/day"
        """
        if rate is not None:
            self.rate = rate
        self.num_requests, self.duration = self.parse_rate(self.rate)
        self.history: list[float] = []

    def parse_rate(self, rate: str | None) -> tuple[int | None, int | None]:
        """
        Parse a rate string like "100/hour" into (num_requests, duration_seconds).

        Supported formats:
            - "100/s" or "100/second" - 100 requests per second
            - "100/m" or "100/minute" - 100 requests per minute
            - "100/h" or "100/hour" - 100 requests per hour
            - "100/d" or "100/day" - 100 requests per day

        Args:
            rate: Rate string

        Returns:
            Tuple of (num_requests, duration_in_seconds) or (None, None)
        """
        if rate is None:
            return (None, None)

        rate = rate.lower().strip()

        # Handle formats like "100/hour" or "100/h"
        if "/" in rate:
            num, period = rate.split("/", 1)
        else:
            raise ValueError(f"Invalid rate format: {rate}. Expected format: 'num/period'")

        try:
            num_requests = int(num)
        except ValueError:
            raise ValueError(f"Invalid number in rate: {num}")

        # Parse period
        period_map = {
            "s": 1,
            "sec": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
        }

        duration = period_map.get(period)
        if duration is None:
            raise ValueError(
                f"Invalid period in rate: {period}. Expected one of: {', '.join(period_map.keys())}"
            )

        return (num_requests, duration)

    @abstractmethod
    def get_cache_key(self, request: HttpRequest) -> str | None:
        """
        Return a unique cache key for the given request.

        Should return None to skip throttling for this request.

        Args:
            request: The Django HTTP request

        Returns:
            Cache key string or None to skip throttling
        """
        raise NotImplementedError("Subclasses must implement get_cache_key()")

    def get_ident(self, request: HttpRequest) -> str:
        """
        Get a unique identifier for the request, typically the IP address.

        Handles X-Forwarded-For header for requests behind proxies.

        Args:
            request: The Django HTTP request

        Returns:
            Client identifier string
        """
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            # X-Forwarded-For can contain multiple IPs, take the first (client IP)
            return xff.split(",")[0].strip()

        # Fall back to REMOTE_ADDR
        return request.META.get("REMOTE_ADDR", "unknown")

    def allow_request(self, request: HttpRequest) -> bool:
        """
        Check if the request should be allowed based on throttle rate.

        Uses a sliding window algorithm to track request history.

        Args:
            request: The Django HTTP request

        Returns:
            True if request is allowed, False if throttled
        """
        if self.rate is None:
            return True

        cache_key = self.get_cache_key(request)
        if cache_key is None:
            return True

        if self.num_requests is None or self.duration is None:
            return True

        # Get request history from backend
        now = time.time()
        self.history = self.get_history(cache_key)

        # Remove expired entries (outside the time window)
        cutoff = now - self.duration
        self.history = [timestamp for timestamp in self.history if timestamp > cutoff]

        # Check if under the limit
        if len(self.history) < self.num_requests:
            self.history.append(now)
            self.set_history(cache_key, self.history)
            return True

        return False

    def get_history(self, cache_key: str) -> list[float]:
        """
        Get request history from the backend.

        Args:
            cache_key: The cache key for this throttle

        Returns:
            List of timestamps
        """
        if self.backend is None:
            return []
        return self.backend.get(cache_key) or []

    def set_history(self, cache_key: str, history: list[float]) -> None:
        """
        Store request history in the backend.

        Args:
            cache_key: The cache key for this throttle
            history: List of timestamps to store
        """
        if self.backend is not None:
            # Set TTL slightly longer than duration to handle edge cases
            ttl = self.duration + 10 if self.duration else 3600
            self.backend.set(cache_key, history, ttl=ttl)

    def wait(self) -> float | None:
        """
        Return the number of seconds to wait before the next request is allowed.

        Returns:
            Seconds to wait, or None if no rate limit
        """
        if not self.history or self.duration is None:
            return None

        remaining = self.duration - (time.time() - self.history[0])
        return max(0, remaining)

    def get_throttle_headers(self) -> dict[str, str]:
        """
        Get rate limit headers to include in the response.

        Returns:
            Dict of header names to values
        """
        headers = {}

        if self.num_requests is not None:
            headers["X-RateLimit-Limit"] = str(self.num_requests)

        if self.history is not None:
            remaining = max(0, (self.num_requests or 0) - len(self.history))
            headers["X-RateLimit-Remaining"] = str(remaining)

        if self.duration is not None and self.history:
            reset_time = int(self.history[0] + self.duration)
            headers["X-RateLimit-Reset"] = str(reset_time)

        wait = self.wait()
        if wait is not None and wait > 0:
            headers["Retry-After"] = str(int(wait) + 1)

        return headers
