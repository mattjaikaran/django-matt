"""Response timing middleware — X-Response-Time header."""

import time

from django.conf import settings


class TimingMiddleware:
    """
    Add X-Response-Time header to every response.

    Works with both sync and async Django. Config cached at __init__.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        matt_config = getattr(settings, "DJANGO_MATT", {})
        timing = matt_config.get("TIMING", {})
        self.header_name = timing.get("HEADER_NAME", "X-Response-Time")
        self.enabled = timing.get("ENABLED", True)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000
        response[self.header_name] = f"{duration_ms:.1f}ms"
        return response
