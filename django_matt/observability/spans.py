"""Lightweight in-process span tracking with sync and async context managers."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class Span:
    name: str
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    children: list[Span] = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    error: Exception | None = field(default=None, repr=False)
    _parent: Span | None = field(default=None, repr=False)

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.perf_counter() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def set_tag(self, key: str, value: Any) -> Span:
        self.tags[key] = value
        return self

    def set_tags(self, tags: dict[str, Any]) -> Span:
        self.tags.update(tags)
        return self

    def set_error(self, exc: Exception) -> Span:
        self.status = SpanStatus.ERROR
        self.error = exc
        self.tags["error"] = True
        self.tags["error.type"] = type(exc).__name__
        self.tags["error.message"] = str(exc)
        return self

    def finish(self) -> Span:
        self.end_time = time.perf_counter()
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK
        return self

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "tags": self.tags,
        }
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        if self.error:
            result["error"] = {
                "type": type(self.error).__name__,
                "message": str(self.error),
            }
        return result


_current_span: ContextVar[Span | None] = ContextVar("_current_span", default=None)
_span_listeners: list[Callable[[Span], None]] = []


def get_current_span() -> Span | None:
    return _current_span.get()


def add_span_listener(listener: Callable[[Span], None]) -> None:
    _span_listeners.append(listener)


def remove_span_listener(listener: Callable[[Span], None]) -> None:
    _span_listeners.remove(listener)


def _notify_listeners(s: Span) -> None:
    for listener in _span_listeners:
        try:
            listener(s)
        except Exception:
            pass


@contextmanager
def span(name: str, tags: dict[str, Any] | None = None):
    parent = _current_span.get()
    s = Span(name=name, tags=tags or {}, _parent=parent)
    if parent is not None:
        parent.children.append(s)
    token = _current_span.set(s)
    try:
        yield s
        s.finish()
    except Exception as exc:
        s.set_error(exc)
        s.finish()
        raise
    finally:
        _current_span.reset(token)
        if parent is None:
            _notify_listeners(s)


@asynccontextmanager
async def aspan(name: str, tags: dict[str, Any] | None = None):
    parent = _current_span.get()
    s = Span(name=name, tags=tags or {}, _parent=parent)
    if parent is not None:
        parent.children.append(s)
    token = _current_span.set(s)
    try:
        yield s
        s.finish()
    except Exception as exc:
        s.set_error(exc)
        s.finish()
        raise
    finally:
        _current_span.reset(token)
        if parent is None:
            _notify_listeners(s)


def traced(name: str | None = None, tags: dict[str, Any] | None = None):
    def decorator(func: F) -> F:
        span_name = name or func.__qualname__

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(span_name, tags=tags):
                return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            async with aspan(span_name, tags=tags):
                return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "Span",
    "SpanStatus",
    "aspan",
    "add_span_listener",
    "get_current_span",
    "remove_span_listener",
    "span",
    "traced",
]
