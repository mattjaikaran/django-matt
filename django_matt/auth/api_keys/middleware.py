"""
API Key authentication middleware.

Provides global API key authentication and rate limiting.
"""

import time
from typing import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from .utils import get_api_key_from_request, get_client_ip, api_key_config


class APIKeyAuthenticationMiddleware:
    """
    Middleware for automatic API key authentication.

    If a valid API key is present in the request, authenticates the user.
    Does NOT block requests without API keys - use decorators for that.

    Usage:
        MIDDLEWARE = [
            ...
            'django_matt.auth.api_keys.APIKeyAuthenticationMiddleware',
        ]

    The middleware will:
    1. Extract API key from headers/query params
    2. Validate the key
    3. Attach user and api_key to request
    4. Optionally track usage
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self._authenticate(request)
        return self.get_response(request)

    def _authenticate(self, request: HttpRequest):
        """Try to authenticate the request with an API key."""
        raw_key = get_api_key_from_request(request)
        if not raw_key:
            return

        from .models import APIKey

        api_key = APIKey.objects.get_valid(raw_key)
        if api_key is None:
            return

        if not api_key.is_valid:
            return

        # Check IP restrictions
        if api_key.allowed_ips:
            client_ip = get_client_ip(request)
            if not api_key.is_ip_allowed(client_ip):
                return

        # Attach to request
        request.user = api_key.user
        request.api_key = api_key

        # Track usage if enabled
        if api_key_config.track_usage:
            api_key.record_usage()


class APIKeyRateLimitMiddleware:
    """
    Middleware for API key rate limiting.

    Enforces rate limits based on the API key's plan tier.

    Usage:
        MIDDLEWARE = [
            ...
            'django_matt.auth.api_keys.APIKeyAuthenticationMiddleware',
            'django_matt.auth.api_keys.APIKeyRateLimitMiddleware',
        ]

    Response headers:
        X-RateLimit-Limit: Maximum requests per period
        X-RateLimit-Remaining: Requests remaining in current period
        X-RateLimit-Reset: Unix timestamp when the limit resets
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Only rate limit if API key is present
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return self.get_response(request)

        # Check if rate limiting is enabled
        if not api_key_config.rate_limiting:
            return self.get_response(request)

        # Get rate limit info
        limit = api_key.rate_limit
        period = api_key.rate_limit_period
        cache_key = api_key.get_rate_limit_key()

        # Get current usage from cache
        now = time.time()
        window_start = int(now // period) * period
        window_cache_key = f"{cache_key}:{window_start}"

        current_count = cache.get(window_cache_key, 0)

        # Check if rate limited
        if current_count >= limit:
            reset_time = window_start + period
            response = JsonResponse(
                {
                    "detail": "Rate limit exceeded",
                    "code": "rate_limit_exceeded",
                    "limit": limit,
                    "period": period,
                    "retry_after": int(reset_time - now),
                },
                status=429,
            )
            response["X-RateLimit-Limit"] = str(limit)
            response["X-RateLimit-Remaining"] = "0"
            response["X-RateLimit-Reset"] = str(int(reset_time))
            response["Retry-After"] = str(int(reset_time - now))
            return response

        # Increment counter
        new_count = current_count + 1
        cache.set(window_cache_key, new_count, timeout=period)

        # Process request
        response = self.get_response(request)

        # Add rate limit headers
        reset_time = window_start + period
        response["X-RateLimit-Limit"] = str(limit)
        response["X-RateLimit-Remaining"] = str(max(0, limit - new_count))
        response["X-RateLimit-Reset"] = str(int(reset_time))

        return response


class APIKeyUsageTrackingMiddleware:
    """
    Middleware for detailed API usage tracking.

    Tracks request/response metrics per API key for analytics and billing.

    Usage:
        MIDDLEWARE = [
            ...
            'django_matt.auth.api_keys.APIKeyAuthenticationMiddleware',
            'django_matt.auth.api_keys.APIKeyUsageTrackingMiddleware',
        ]

    Note: This middleware has some overhead. Only enable if you need
    detailed usage analytics.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return self.get_response(request)

        # Record start time
        start_time = time.time()

        # Get request size
        bytes_received = len(request.body) if hasattr(request, "body") else 0

        # Process request
        response = self.get_response(request)

        # Calculate metrics
        response_time_ms = (time.time() - start_time) * 1000
        is_error = response.status_code >= 400

        # Get response size
        bytes_sent = len(response.content) if hasattr(response, "content") else 0

        # Get endpoint path
        endpoint = request.path

        # Record usage
        from .models import APIKeyUsage

        try:
            APIKeyUsage.record(
                api_key=api_key,
                endpoint=endpoint,
                response_time_ms=response_time_ms,
                is_error=is_error,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received,
            )
        except Exception:
            # Don't fail the request if tracking fails
            pass

        return response
