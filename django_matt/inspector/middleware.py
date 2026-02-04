"""
Request capture middleware for the Request Inspector.

This middleware captures HTTP requests and responses for debugging
and inspection purposes during development.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import TYPE_CHECKING, Optional

from django.conf import settings

from django_matt.inspector.storage import CapturedRequest, get_storage

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.inspector")


class RequestCaptureMiddleware:
    """
    Middleware to capture HTTP requests and responses.

    Configuration (settings.py):
        DJANGO_MATT_INSPECTOR = {
            'ENABLED': DEBUG,
            'MAX_BODY_SIZE': 65536,  # Max request/response body size to capture
            'IGNORE_PATHS': ['/_matt/', '/static/', '/media/'],
            'IGNORE_EXTENSIONS': ['.css', '.js', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2'],
            'CAPTURE_HEADERS': True,
            'CAPTURE_BODY': True,
            'CAPTURE_RESPONSE': True,
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._config = self._get_config()

    def _get_config(self) -> dict:
        """Get inspector configuration from settings."""
        config = getattr(settings, "DJANGO_MATT_INSPECTOR", {})
        return {
            "enabled": config.get("ENABLED", getattr(settings, "DEBUG", False)),
            "max_body_size": config.get("MAX_BODY_SIZE", 65536),
            "ignore_paths": config.get("IGNORE_PATHS", ["/_matt/", "/static/", "/media/"]),
            "ignore_extensions": config.get(
                "IGNORE_EXTENSIONS",
                [".css", ".js", ".png", ".jpg", ".gif", ".ico", ".woff", ".woff2", ".svg"],
            ),
            "capture_headers": config.get("CAPTURE_HEADERS", True),
            "capture_body": config.get("CAPTURE_BODY", True),
            "capture_response": config.get("CAPTURE_RESPONSE", True),
        }

    def _should_capture(self, request: HttpRequest) -> bool:
        """Determine if the request should be captured."""
        if not self._config["enabled"]:
            return False

        path = request.path

        # Check ignored paths
        for ignore_path in self._config["ignore_paths"]:
            if path.startswith(ignore_path):
                return False

        # Check ignored extensions
        for ext in self._config["ignore_extensions"]:
            if path.endswith(ext):
                return False

        return True

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _get_request_headers(self, request: HttpRequest) -> dict[str, str]:
        """Extract headers from request."""
        if not self._config["capture_headers"]:
            return {}

        headers = {}
        for key, value in request.META.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                headers[header_name] = value
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                header_name = key.replace("_", "-").title()
                headers[header_name] = value

        return headers

    def _get_request_body(self, request: HttpRequest) -> Optional[str]:
        """Extract request body."""
        if not self._config["capture_body"]:
            return None

        try:
            body = request.body
            if not body:
                return None

            # Limit body size
            max_size = self._config["max_body_size"]
            if len(body) > max_size:
                return (
                    body[:max_size].decode("utf-8", errors="replace")
                    + f"... [truncated, total {len(body)} bytes]"
                )

            return body.decode("utf-8", errors="replace")
        except Exception:
            return None

    def _get_response_headers(self, response: HttpResponse) -> dict[str, str]:
        """Extract headers from response."""
        if not self._config["capture_headers"]:
            return {}

        headers = {}
        for key, value in response.items():
            headers[key] = value
        return headers

    def _get_response_body(self, response: HttpResponse) -> Optional[str]:
        """Extract response body."""
        if not self._config["capture_response"]:
            return None

        try:
            content_type = response.get("Content-Type", "")

            # Only capture text-based responses
            if not any(
                ct in content_type
                for ct in ["text/", "application/json", "application/xml", "application/javascript"]
            ):
                return f"[Binary content: {content_type}]"

            content = response.content
            if not content:
                return None

            # Limit body size
            max_size = self._config["max_body_size"]
            if len(content) > max_size:
                return (
                    content[:max_size].decode("utf-8", errors="replace")
                    + f"... [truncated, total {len(content)} bytes]"
                )

            return content.decode("utf-8", errors="replace")
        except Exception:
            return None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request."""
        if not self._should_capture(request):
            return self.get_response(request)

        # Capture start time
        start_time = time.time()

        # Capture request data before processing
        captured = CapturedRequest(
            method=request.method,
            path=request.path,
            full_url=request.build_absolute_uri(),
            query_string=request.META.get("QUERY_STRING", ""),
            request_headers=self._get_request_headers(request),
            request_body=self._get_request_body(request),
            request_content_type=request.content_type if hasattr(request, "content_type") else None,
            client_ip=self._get_client_ip(request),
        )

        # Add user info if available
        if hasattr(request, "user") and request.user.is_authenticated:
            captured.user_id = request.user.pk
            captured.user_email = getattr(request.user, "email", None)

        exception_info = None
        response = None

        try:
            response = self.get_response(request)
        except Exception as e:
            exception_info = e
            raise
        finally:
            # Calculate duration
            end_time = time.time()
            captured.duration_ms = (end_time - start_time) * 1000

            if response is not None:
                # Capture response data
                captured.response_status = response.status_code
                captured.response_headers = self._get_response_headers(response)
                captured.response_body = self._get_response_body(response)
                captured.response_content_type = response.get("Content-Type")
            elif exception_info is not None:
                # Capture exception info
                captured.response_status = 500
                captured.exception = str(exception_info)
                captured.traceback = traceback.format_exc()

            # Store the captured request
            try:
                storage = get_storage()
                storage.add(captured)
            except Exception as e:
                logger.warning(f"Failed to store captured request: {e}")

        return response

    def process_exception(self, request: HttpRequest, exception: Exception):
        """Process exceptions (for additional capture if needed)."""
        # Exception handling is done in __call__
        return


__all__ = ["RequestCaptureMiddleware"]
