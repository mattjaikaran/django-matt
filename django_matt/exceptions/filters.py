from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.exceptions")


class ExceptionFilter(ABC):
    exception_types: tuple[type[Exception], ...] = ()
    order: int = 0

    def can_handle(self, exc: Exception) -> bool:
        return isinstance(exc, self.exception_types)

    @abstractmethod
    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse: ...


class ExceptionFilterChain:
    def __init__(self, filters: list[ExceptionFilter] | None = None) -> None:
        self._filters: list[ExceptionFilter] = []
        if filters:
            for f in filters:
                self.add(f)

    def add(self, filter_: ExceptionFilter) -> None:
        self._filters.append(filter_)
        self._filters.sort(key=lambda f: f.order)

    def remove(self, filter_type: type[ExceptionFilter]) -> None:
        self._filters = [f for f in self._filters if not isinstance(f, filter_type)]

    @property
    def filters(self) -> list[ExceptionFilter]:
        return list(self._filters)

    async def handle(self, exc: Exception, request: HttpRequest) -> HttpResponse | None:
        for f in self._filters:
            if f.can_handle(exc):
                try:
                    return await f.catch(exc, request)
                except Exception as inner:
                    logger.error(f"Exception filter {f.__class__.__name__} raised: {inner}")
                    continue
        return None


class FunctionExceptionFilter(ExceptionFilter):
    def __init__(
        self,
        exception_types: tuple[type[Exception], ...],
        handler: Any,
        order: int = 0,
    ) -> None:
        self.exception_types = exception_types
        self._handler = handler
        self.order = order

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        import inspect

        if inspect.iscoroutinefunction(self._handler):
            return await self._handler(exc, request)
        return self._handler(exc, request)
