"""Base exception filter classes and filter chain for ordered exception handling."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.exceptions")


class ExceptionFilter(ABC):
    """Abstract base for exception filters that convert exceptions to HTTP responses."""

    exception_types: tuple[type[Exception], ...] = ()
    order: int = 0

    def can_handle(self, exc: Exception) -> bool:
        """Return whether this filter handles the given exception type."""
        return isinstance(exc, self.exception_types)

    @abstractmethod
    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse: ...


class ExceptionFilterChain:
    """Ordered chain of exception filters that tries each filter in sequence."""

    def __init__(self, filters: list[ExceptionFilter] | None = None) -> None:
        self._filters: list[ExceptionFilter] = []
        if filters:
            for f in filters:
                self.add(f)

    def add(self, filter_: ExceptionFilter) -> None:
        """Add a filter to the chain, maintaining sort order."""
        self._filters.append(filter_)
        self._filters.sort(key=lambda f: f.order)

    def remove(self, filter_type: type[ExceptionFilter]) -> None:
        """Remove all filters of the given type from the chain."""
        self._filters = [f for f in self._filters if not isinstance(f, filter_type)]

    @property
    def filters(self) -> list[ExceptionFilter]:
        return list(self._filters)

    async def handle(self, exc: Exception, request: HttpRequest) -> HttpResponse | None:
        """Try each filter in order; return the first successful response or None."""
        for f in self._filters:
            if f.can_handle(exc):
                try:
                    return await f.catch(exc, request)
                except Exception as inner:
                    logger.error(f"Exception filter {f.__class__.__name__} raised: {inner}")
                    continue
        return None


class FunctionExceptionFilter(ExceptionFilter):
    """Exception filter that wraps a plain callable as its catch handler."""

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
