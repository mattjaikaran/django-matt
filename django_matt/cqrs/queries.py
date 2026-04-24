"""Query bus with single-handler dispatch, caching support, and middleware pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("django_matt.cqrs.queries")

Q = TypeVar("Q", bound="Query")
R = TypeVar("R")


class Query(BaseModel):
    """Immutable base model for CQRS queries."""

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class QueryHandler(Protocol[Q, R]):
    async def execute(self, query: Q) -> R: ...


class QueryBus:
    """Dispatches queries to their registered handler with middleware support."""

    def __init__(self) -> None:
        self._handlers: dict[type[Query], QueryHandler] = {}
        self._middleware: list[Any] = []

    def use(self, middleware: Any) -> QueryBus:
        self._middleware.append(middleware)
        return self

    def register(self, query_type: type[Query], handler: QueryHandler) -> QueryBus:
        if query_type in self._handlers:
            raise ValueError(
                f"Handler already registered for {query_type.__name__}. "
                "Queries must have exactly one handler."
            )
        self._handlers[query_type] = handler
        return self

    async def dispatch(self, query: Query) -> Any:
        from .middleware import _CacheHit

        query_type = type(query)
        handler = self._handlers.get(query_type)
        if handler is None:
            raise LookupError(f"No handler registered for {query_type.__name__}")

        try:
            for mw in self._middleware:
                if hasattr(mw, "before"):
                    await mw.before(query)
        except _CacheHit as hit:
            return hit.value

        result = await handler.execute(query)

        for mw in reversed(self._middleware):
            if hasattr(mw, "after"):
                result = await mw.after(query, result) or result

        return result

    @property
    def handlers(self) -> dict[type[Query], QueryHandler]:
        return dict(self._handlers)


_default_query_bus = QueryBus()


def get_query_bus() -> QueryBus:
    """Return the default global QueryBus singleton."""
    return _default_query_bus


def query_handler(
    query_type: type[Query],
    *,
    bus: QueryBus | None = None,
) -> Callable:
    """Class decorator that registers a query handler with the bus."""
    def decorator(cls: type) -> type:
        target_bus = bus or _default_query_bus
        target_bus.register(query_type, cls())
        return cls

    return decorator
