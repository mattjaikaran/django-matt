"""
Throttle middleware for django-matt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.http import JsonResponse

from django_matt.throttling.backends import get_default_backend
from django_matt.throttling.base import BaseThrottle
from django_matt.throttling.decorators import ThrottleError
from django_matt.throttling.throttles import AnonRateThrottle, UserRateThrottle

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class ThrottleMiddleware:
    """
    Middleware to apply global rate limiting to all requests.

    Configure in settings:
        MIDDLEWARE = [
            ...
            'django_matt.throttling.middleware.ThrottleMiddleware',
            ...
        ]

        # Optional configuration
        THROTTLE_MIDDLEWARE = {
            'default_rate': '1000/hour',
            'anon_rate': '100/hour',
            'user_rate': '1000/hour',
            'exclude_paths': ['/health/', '/api/docs/'],
            'exclude_methods': ['OPTIONS'],
        }

    The middleware applies different rates to anonymous and authenticated users,
    and can exclude specific paths or methods from throttling.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.backend = get_default_backend()
        self._config: dict[str, Any] | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Get middleware configuration from Django settings."""
        if self._config is None:
            try:
                from django.conf import settings

                self._config = getattr(settings, "THROTTLE_MIDDLEWARE", {})
            except Exception:
                self._config = {}
        return self._config

    def get_throttle_for_request(self, request: HttpRequest) -> BaseThrottle | None:
        """
        Get the appropriate throttle for the request.

        Args:
            request: The Django HTTP request

        Returns:
            Throttle instance or None if throttling should be skipped
        """
        # Check excluded methods
        excluded_methods = self.config.get("exclude_methods", ["OPTIONS"])
        if request.method.upper() in [m.upper() for m in excluded_methods]:
            return None

        # Check excluded paths
        excluded_paths = self.config.get("exclude_paths", [])
        for path in excluded_paths:
            if request.path.startswith(path):
                return None

        # Determine throttle class and rate
        if hasattr(request, "user") and request.user.is_authenticated:
            rate = self.config.get("user_rate", self.config.get("default_rate", "1000/hour"))
            throttle = UserRateThrottle(rate=rate)
        else:
            rate = self.config.get("anon_rate", self.config.get("default_rate", "100/hour"))
            throttle = AnonRateThrottle(rate=rate)

        throttle.backend = self.backend
        return throttle

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and apply throttling.

        Args:
            request: The Django HTTP request

        Returns:
            HttpResponse from the view or a 429 error if throttled
        """
        throttle = self.get_throttle_for_request(request)

        if throttle is not None:
            if not throttle.allow_request(request):
                return self.throttled_response(request, throttle)

        response = self.get_response(request)

        # Add rate limit headers
        if throttle is not None:
            for key, value in throttle.get_throttle_headers().items():
                response[key] = value

        return response

    def throttled_response(self, request: HttpRequest, throttle: BaseThrottle) -> JsonResponse:
        """
        Create a 429 Too Many Requests response.

        Args:
            request: The Django HTTP request
            throttle: The throttle that denied the request

        Returns:
            JsonResponse with 429 status
        """
        wait = throttle.wait()
        headers = throttle.get_throttle_headers()

        retry_after = int(wait) + 1 if wait is not None and wait > 0 else None

        response = JsonResponse(
            {
                "error": "too_many_requests",
                "message": f"Request was throttled. Expected available in {int(wait or 0)} seconds.",
                "retry_after": retry_after,
            },
            status=429,
        )

        for key, value in headers.items():
            response[key] = value

        # Ensure Retry-After header is set on 429 responses (RFC 6585)
        if retry_after is not None and "Retry-After" not in response:
            response["Retry-After"] = str(retry_after)

        return response


class PathSpecificThrottleMiddleware:
    """
    Middleware to apply different rate limits to different URL paths.

    Configure in settings:
        MIDDLEWARE = [
            ...
            'django_matt.throttling.middleware.PathSpecificThrottleMiddleware',
            ...
        ]

        THROTTLE_PATH_RATES = {
            '/api/auth/': '10/minute',
            '/api/upload/': '5/hour',
            '/api/search/': '30/minute',
            '/api/': '1000/hour',  # Default for /api/*
        }

    Paths are matched in order, so more specific paths should come first.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.backend = get_default_backend()
        self._path_rates: dict[str, str] | None = None

    @property
    def path_rates(self) -> dict[str, str]:
        """Get path-specific rates from Django settings."""
        if self._path_rates is None:
            try:
                from django.conf import settings

                self._path_rates = getattr(settings, "THROTTLE_PATH_RATES", {})
            except Exception:
                self._path_rates = {}
        return self._path_rates

    def get_rate_for_path(self, path: str) -> str | None:
        """
        Get the rate limit for a given path.

        Args:
            path: The request path

        Returns:
            Rate string or None if no rate configured
        """
        # Check paths in order (most specific first based on settings order)
        for configured_path, rate in self.path_rates.items():
            if path.startswith(configured_path):
                return rate
        return None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and apply path-specific throttling.

        Args:
            request: The Django HTTP request

        Returns:
            HttpResponse from the view or a 429 error if throttled
        """
        rate = self.get_rate_for_path(request.path)

        if rate is not None:
            # Create a scoped throttle for this path
            from django_matt.throttling.throttles import ScopedRateThrottle

            # Use path as scope (normalized)
            scope = request.path.replace("/", "_").strip("_")
            throttle = ScopedRateThrottle(rate=rate, scope=scope)
            throttle.backend = self.backend

            if not throttle.allow_request(request):
                return self._throttled_response(throttle)

            response = self.get_response(request)

            # Add rate limit headers
            for key, value in throttle.get_throttle_headers().items():
                response[key] = value

            return response

        return self.get_response(request)

    def _throttled_response(self, throttle: BaseThrottle) -> JsonResponse:
        """Create a 429 response."""
        wait = throttle.wait()
        headers = throttle.get_throttle_headers()
        retry_after = int(wait) + 1 if wait is not None and wait > 0 else None

        response = JsonResponse(
            {
                "error": "too_many_requests",
                "message": f"Request was throttled. Expected available in {int(wait or 0)} seconds.",
                "retry_after": retry_after,
            },
            status=429,
        )

        for key, value in headers.items():
            response[key] = value

        # Ensure Retry-After header is set on 429 responses (RFC 6585)
        if retry_after is not None and "Retry-After" not in response:
            response["Retry-After"] = str(retry_after)

        return response


def throttle_exception_handler(exc: Exception, context: Any = None) -> JsonResponse | None:
    """
    Exception handler for ThrottleError.

    Use with django-matt's exception handling:
        from django_matt.throttling import throttle_exception_handler

        api = API(
            exception_handlers={
                ThrottleError: throttle_exception_handler,
            }
        )

    Args:
        exc: The exception
        context: Optional context dict

    Returns:
        JsonResponse with 429 status or None if not a ThrottleError
    """
    if not isinstance(exc, ThrottleError):
        return None

    retry_after = int(exc.wait) + 1 if exc.wait is not None and exc.wait > 0 else None

    response = JsonResponse(
        {
            "error": "too_many_requests",
            "message": exc.message,
            "retry_after": retry_after,
        },
        status=429,
    )

    for key, value in exc.headers.items():
        response[key] = value

    # Ensure Retry-After header is set on 429 responses (RFC 6585)
    if retry_after is not None and "Retry-After" not in response:
        response["Retry-After"] = str(retry_after)

    return response
