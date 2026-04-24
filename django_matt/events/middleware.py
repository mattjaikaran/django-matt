"""Django middleware that emits collected events and a RequestEvent after each request."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from django.http import HttpRequest, HttpResponse

from django_matt.events.bus import Event, get_event_bus
from django_matt.events.types import RequestEvent

logger = logging.getLogger("django_matt.events")

_request_events: dict[int, list[Event]] = {}


def collect_event(request: HttpRequest, event: Event) -> None:
    """Attach an event to the current request for deferred emission after response."""
    req_id = id(request)
    if req_id not in _request_events:
        _request_events[req_id] = []
    _request_events[req_id].append(event)


class EventMiddleware:
    """Middleware that collects events during a request and emits them on success."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self._is_async = asyncio.iscoroutinefunction(get_response)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._is_async:
            return self._async_call(request)
        return self._sync_call(request)

    def _sync_call(self, request: HttpRequest) -> HttpResponse:
        req_id = id(request)
        _request_events[req_id] = []
        start = time.monotonic()

        response = self.get_response(request)

        duration = (time.monotonic() - start) * 1000
        events = _request_events.pop(req_id, [])

        user_id = None
        if hasattr(request, "user") and hasattr(request.user, "pk"):
            user_id = request.user.pk

        if response.status_code < 400:
            bus = get_event_bus()
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop and loop.is_running():
                _tasks: list[asyncio.Task] = []
                for event in events:
                    _tasks.append(loop.create_task(bus.emit(event)))
                _tasks.append(
                    loop.create_task(
                        bus.emit(
                            RequestEvent(
                                method=request.method or "",
                                path=request.path,
                                status_code=response.status_code,
                                duration_ms=duration,
                                user_id=user_id,
                            )
                        )
                    )
                )
            else:
                async def _emit_all():
                    for event in events:
                        await bus.emit(event)
                    await bus.emit(
                        RequestEvent(
                            method=request.method or "",
                            path=request.path,
                            status_code=response.status_code,
                            duration_ms=duration,
                            user_id=user_id,
                        )
                    )

                asyncio.run(_emit_all())

        return response

    async def _async_call(self, request: HttpRequest) -> HttpResponse:
        req_id = id(request)
        _request_events[req_id] = []
        start = time.monotonic()

        response = await self.get_response(request)

        duration = (time.monotonic() - start) * 1000
        events = _request_events.pop(req_id, [])

        user_id = None
        if hasattr(request, "user") and hasattr(request.user, "pk"):
            user_id = request.user.pk

        if response.status_code < 400:
            bus = get_event_bus()
            for event in events:
                await bus.emit(event)
            await bus.emit(
                RequestEvent(
                    method=request.method or "",
                    path=request.path,
                    status_code=response.status_code,
                    duration_ms=duration,
                    user_id=user_id,
                )
            )

        return response
