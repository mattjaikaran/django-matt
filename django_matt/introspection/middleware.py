"""Middleware that short-circuits health/liveness probes before Django routing."""

from __future__ import annotations

import time

from django.http import HttpRequest, HttpResponse

import orjson


class HealthCheckMiddleware:
    """Short-circuit middleware that responds to health probe paths without full dispatch."""
    def __init__(self, get_response) -> None:
        self.get_response = get_response
        self._health_paths = frozenset({"/health/", "/health/live/"})

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path in self._health_paths:
            return self._short_circuit(request)
        return self.get_response(request)

    def _short_circuit(self, request: HttpRequest) -> HttpResponse:
        if request.path == "/health/live/":
            body = orjson.dumps({"alive": True, "timestamp": time.time()})
        else:
            body = orjson.dumps({"status": "ok"})
        return HttpResponse(body, content_type="application/json", status=200)
