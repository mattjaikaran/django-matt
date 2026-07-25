"""Token bucket rate limiter with optional Rust acceleration.

Uses the Rust ``RateLimiter`` when compiled, otherwise falls back to a
pure-Python implementation with identical semantics.

Usage::

    from django_matt.throttling.token_bucket import TokenBucketThrottle

    # As a throttle class on a controller
    class MyController(APIController):
        throttle_classes = [TokenBucketThrottle(capacity=100, refill_per_second=10)]

    # Direct usage
    bucket = TokenBucketThrottle(capacity=50, refill_per_second=5.0)
    allowed, remaining, reset_ms = bucket.check(request)
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Generator
from typing import TYPE_CHECKING

from django_matt._accel import HAS_RUST, RateLimiterRust

if TYPE_CHECKING:
    from django.http import HttpRequest

# Global bypass flag — when True, all throttle checks return allowed
_bypass_throttle = threading.local()


class _PythonTokenBucket:
    """Pure-Python token bucket — fallback when Rust is unavailable."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._refill_rate = refill_per_second
        self._buckets: dict[bytes, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._lock = threading.Lock()

    def check(self, key: bytes) -> tuple[bool, int, int]:
        with self._lock:
            now = time.monotonic()

            if key in self._buckets:
                tokens, last_refill = self._buckets[key]
                elapsed = now - last_refill
                tokens = min(self._capacity, tokens + elapsed * self._refill_rate)
            else:
                tokens = float(self._capacity)
                last_refill = now

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = (tokens, now)
                remaining = int(tokens)
                reset_ms = int((self._capacity - tokens) / self._refill_rate * 1000) if remaining < self._capacity else 0
                return (True, remaining, reset_ms)
            self._buckets[key] = (tokens, now)
            reset_ms = int((1.0 - tokens) / self._refill_rate * 1000)
            return (False, 0, reset_ms)

    def check_many(self, keys: list[bytes]) -> list[tuple[bool, int, int]]:
        return [self.check(k) for k in keys]

    def cleanup(self, max_idle_seconds: float) -> int:
        with self._lock:
            now = time.monotonic()
            before = len(self._buckets)
            self._buckets = {
                k: (tokens, last)
                for k, (tokens, last) in self._buckets.items()
                if (now - last) < max_idle_seconds
                or min(self._capacity, tokens + (now - last) * self._refill_rate) < self._capacity
            }
            return before - len(self._buckets)

    @property
    def size(self) -> int:
        return len(self._buckets)


def is_throttle_bypassed() -> bool:
    """Check if throttle bypass is active (e.g. during tests)."""
    return getattr(_bypass_throttle, "active", False)


@contextlib.contextmanager
def bypass_throttle() -> Generator[None, None, None]:
    """Context manager to bypass all token bucket throttle checks.

    Usage in tests::

        from django_matt.throttling.token_bucket import bypass_throttle

        with bypass_throttle():
            # All throttle checks return (True, capacity, 0)
            response = client.get("/api/endpoint")

    Also works as a pytest fixture::

        @pytest.fixture(autouse=True)
        def no_throttle():
            with bypass_throttle():
                yield
    """
    _bypass_throttle.active = True
    try:
        yield
    finally:
        _bypass_throttle.active = False


def disable_throttle() -> None:
    """Globally disable throttle checks (call in test setup)."""
    _bypass_throttle.active = True


def enable_throttle() -> None:
    """Re-enable throttle checks after ``disable_throttle()``."""
    _bypass_throttle.active = False


class TokenBucketThrottle:
    """Token bucket rate limiter with Rust acceleration.

    Automatically uses the Rust ``RateLimiter`` when the native extension
    is compiled, falling back to a pure-Python implementation otherwise.

    Test bypass: set ``disabled=True``, use ``bypass_throttle()`` context
    manager, or call ``disable_throttle()`` globally. The throttle also
    auto-disables when Django's ``settings.TESTING`` is ``True``.

    Args:
        capacity: Maximum number of tokens (burst size).
        refill_per_second: Rate at which tokens refill.
        key_func: Callable that extracts the throttle key from a request.
                  Defaults to client IP address.
        disabled: Explicitly disable this throttle instance.
    """

    def __init__(
        self,
        capacity: int = 100,
        refill_per_second: float = 10.0,
        key_func: callable | None = None,
        disabled: bool = False,
    ) -> None:
        self._disabled = disabled
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.key_func = key_func or self._default_key

        if HAS_RUST and RateLimiterRust is not None:
            self._backend = RateLimiterRust(capacity, refill_per_second)
            self._is_rust = True
        else:
            self._backend = _PythonTokenBucket(capacity, refill_per_second)
            self._is_rust = False

    @property
    def is_rust_accelerated(self) -> bool:
        return self._is_rust

    @property
    def _is_bypassed(self) -> bool:
        if self._disabled:
            return True
        if is_throttle_bypassed():
            return True
        try:
            from django.conf import settings
            if getattr(settings, "TESTING", False):
                return True
        except Exception:
            pass
        return False

    def check(self, request: HttpRequest) -> tuple[bool, int, int]:
        """Check if a request is allowed.

        Returns:
            (allowed, remaining_tokens, reset_ms)
        """
        if self._is_bypassed:
            return (True, self.capacity, 0)
        key = self.key_func(request)
        if isinstance(key, str):
            key = key.encode("utf-8")
        return self._backend.check(key)

    def check_key(self, key: str | bytes) -> tuple[bool, int, int]:
        """Check a raw key (no request object needed)."""
        if self._is_bypassed:
            return (True, self.capacity, 0)
        if isinstance(key, str):
            key = key.encode("utf-8")
        return self._backend.check(key)

    def cleanup(self, max_idle_seconds: float = 3600.0) -> int:
        """Remove idle buckets. Returns count removed."""
        return self._backend.cleanup(max_idle_seconds)

    @staticmethod
    def _default_key(request: HttpRequest) -> str:
        """Extract client IP from request."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
