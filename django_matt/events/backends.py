"""Event bus backend implementations (in-memory and Redis pub/sub)."""

from __future__ import annotations

import asyncio
import logging
from fnmatch import fnmatch
from typing import Any, Callable

from django_matt.events.bus import BackendProtocol, Event

logger = logging.getLogger("django_matt.events")


class InMemoryBackend(BackendProtocol):
    """In-process event backend using local subscriber dictionaries."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}

    async def publish(self, event: Event) -> None:
        for pattern, handlers in self._subscribers.items():
            if pattern == event.event_type or fnmatch(event.event_type, pattern):
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Backend handler failed: {e}")

    async def subscribe(self, pattern: str, handler: Callable) -> None:
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)

    async def close(self) -> None:
        self._subscribers.clear()


class RedisBackend(BackendProtocol):
    """Redis pub/sub event backend for distributed event delivery."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", **kwargs: Any) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._pubsub: Any = None
        self._handlers: dict[str, list[Callable]] = {}
        self._listen_task: asyncio.Task | None = None

    async def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError as e:
                raise ImportError(
                    "redis package required for RedisBackend. Install with: uv add redis"
                ) from e
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def publish(self, event: Event) -> None:
        r = await self._get_redis()
        channel = f"django_matt:events:{event.event_type}"
        await r.publish(channel, event.serialize())

    async def subscribe(self, pattern: str, handler: Callable) -> None:
        r = await self._get_redis()
        if self._pubsub is None:
            self._pubsub = r.pubsub()

        channel_pattern = f"django_matt:events:{pattern}"
        if "*" in pattern or "?" in pattern:
            await self._pubsub.psubscribe(channel_pattern)
        else:
            await self._pubsub.subscribe(channel_pattern)

        if pattern not in self._handlers:
            self._handlers[pattern] = []
        self._handlers[pattern].append(handler)

        if self._listen_task is None or self._listen_task.done():
            self._listen_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        if self._pubsub is None:
            return
        try:
            async for message in self._pubsub.listen():
                if message["type"] not in ("message", "pmessage"):
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    event = Event.deserialize(data)
                    for pattern, handlers in self._handlers.items():
                        if pattern == event.event_type or fnmatch(
                            event.event_type, pattern
                        ):
                            for handler in handlers:
                                try:
                                    if asyncio.iscoroutinefunction(handler):
                                        await handler(event)
                                    else:
                                        handler(event)
                                except Exception as e:
                                    logger.error(f"Redis handler failed: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def close(self) -> None:
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        self._handlers.clear()
