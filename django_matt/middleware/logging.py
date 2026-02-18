"""Structured request logging middleware."""

import logging
import time

from django.conf import settings

logger = logging.getLogger("django_matt.requests")


class RequestLoggingMiddleware:
    """
    Log every request with structured data: method, path, status, duration.

    Config via settings.DJANGO_MATT["REQUEST_LOGGING"]. Cached at __init__.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        matt_config = getattr(settings, "DJANGO_MATT", {})
        log_config = matt_config.get("REQUEST_LOGGING", {})

        self.enabled = log_config.get("ENABLED", True)
        self.log_level = getattr(logging, log_config.get("LEVEL", "INFO").upper(), logging.INFO)
        self.exclude_paths = set(log_config.get("EXCLUDE_PATHS", ["/health/", "/ready/", "/favicon.ico"]))
        self.log_headers = log_config.get("LOG_HEADERS", False)
        self.log_body = log_config.get("LOG_BODY", False)

    def __call__(self, request):
        if not self.enabled or request.path in self.exclude_paths:
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        log_data = {
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user": getattr(request, "user", None) and str(getattr(request.user, "pk", "anonymous")),
        }

        # Optionally include request ID
        rid = getattr(request, "request_id", None)
        if rid:
            log_data["request_id"] = rid

        logger.log(
            self.log_level,
            "%s %s %s %.1fms",
            log_data["method"],
            log_data["path"],
            log_data["status"],
            log_data["duration_ms"],
            extra=log_data,
        )

        return response
