"""TTL-based secret rotation scheduling and hook management."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("django_matt.secrets")

_rotation_registry: dict[str, list[Callable]] = {}


@dataclass
class RotationPolicy:
    """TTL-based rotation schedule for secrets."""

    key: str
    ttl_seconds: float
    callback: Callable | None = None
    last_rotated: float = field(default_factory=time.monotonic)

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.last_rotated > self.ttl_seconds

    @property
    def time_remaining(self) -> float:
        remaining = self.ttl_seconds - (time.monotonic() - self.last_rotated)
        return max(0.0, remaining)

    def mark_rotated(self) -> None:
        """Reset the rotation timer to now."""
        self.last_rotated = time.monotonic()


def on_rotation(key: str) -> Callable:
    """Decorator to register a callback when a secret rotates.

    Usage:
        @on_rotation("DATABASE_PASSWORD")
        async def handle_db_password_rotation(key: str):
            # reconnect to database
            ...
    """

    def decorator(func: Callable) -> Callable:
        _rotation_registry.setdefault(key, []).append(func)
        return func

    return decorator


def get_rotation_hooks(key: str) -> list[Callable]:
    """Return all registered rotation hooks for the given key."""
    return _rotation_registry.get(key, [])


async def fire_rotation_hooks(key: str) -> None:
    """Execute all rotation hooks for the given key."""
    hooks = get_rotation_hooks(key)
    for hook in hooks:
        if asyncio.iscoroutinefunction(hook):
            await hook(key)
        else:
            hook(key)


class RotationChecker:
    """Background task that checks for expiring secrets."""

    def __init__(self, check_interval: float = 60.0) -> None:
        self._policies: list[RotationPolicy] = []
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None

    def add_policy(self, policy: RotationPolicy) -> None:
        """Add a rotation policy to monitor."""
        self._policies.append(policy)

    def start(self) -> None:
        """Start the background rotation checking task."""
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._run())

    def stop(self) -> None:
        """Stop the background rotation checking task."""
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_policies()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("rotation check failed")

    async def _check_policies(self) -> None:
        for policy in self._policies:
            if policy.is_expired:
                logger.info("secret rotation due: %s", policy.key)
                await fire_rotation_hooks(policy.key)
                if policy.callback:
                    if asyncio.iscoroutinefunction(policy.callback):
                        await policy.callback(policy.key)
                    else:
                        policy.callback(policy.key)
                policy.mark_rotated()
