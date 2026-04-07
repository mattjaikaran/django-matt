from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Protocol, runtime_checkable

import orjson

logger = logging.getLogger("django_matt.cqrs.middleware")


@runtime_checkable
class BusMiddleware(Protocol):
    async def before(self, message: Any) -> None: ...
    async def after(self, message: Any, result: Any) -> Any: ...


class LoggingMiddleware:
    def __init__(self, log: logging.Logger | None = None) -> None:
        self._log = log or logger

    async def before(self, message: Any) -> None:
        self._start = time.monotonic()
        self._log.info("dispatching %s", type(message).__name__)

    async def after(self, message: Any, result: Any) -> Any:
        elapsed = (time.monotonic() - self._start) * 1000
        self._log.info(
            "completed %s in %.1fms", type(message).__name__, elapsed
        )
        return result


class ValidationMiddleware:
    async def before(self, message: Any) -> None:
        if hasattr(message, "model_validate"):
            type(message).model_validate(message.model_dump())

    async def after(self, message: Any, result: Any) -> Any:
        return result


class TransactionMiddleware:
    async def before(self, message: Any) -> None:
        from django.db import connection

        if not connection.in_atomic_block:
            from django.db import transaction

            self._atomic = transaction.atomic()
            await self._atomic.__aenter__()
        else:
            self._atomic = None

    async def after(self, message: Any, result: Any) -> Any:
        if self._atomic is not None:
            await self._atomic.__aexit__(None, None, None)
            self._atomic = None
        return result


class CachingMiddleware:
    def __init__(self, ttl: int = 300) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl
        self._current_key: str | None = None

    def _make_key(self, message: Any) -> str:
        name = type(message).__name__
        data = orjson.dumps(message.model_dump(), option=orjson.OPT_SORT_KEYS)
        digest = hashlib.md5(data).hexdigest()
        return f"{name}:{digest}"

    async def before(self, message: Any) -> None:
        key = self._make_key(message)
        self._current_key = key
        if key in self._cache:
            ts, value = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                raise _CacheHit(value)
            del self._cache[key]

    async def after(self, message: Any, result: Any) -> Any:
        if self._current_key is not None:
            self._cache[self._current_key] = (time.monotonic(), result)
            self._current_key = None
        return result

    def invalidate(self) -> None:
        self._cache.clear()


class _CacheHit(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value
        super().__init__()
