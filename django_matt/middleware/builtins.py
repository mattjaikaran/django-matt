from __future__ import annotations

import hashlib
import time

from django.http import HttpRequest, HttpResponse, JsonResponse

from django_matt.middleware.scoped import RouteMiddleware


class ScopedCorsMiddleware(RouteMiddleware):
    """CORS headers for specific routes."""

    allowed_origins: list[str] = ["*"]
    allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["Content-Type", "Authorization"]
    max_age: int = 86400

    def __init__(
        self,
        *,
        allowed_origins: list[str] | None = None,
        allowed_methods: list[str] | None = None,
        allowed_headers: list[str] | None = None,
        max_age: int | None = None,
    ) -> None:
        if allowed_origins is not None:
            self.allowed_origins = allowed_origins
        if allowed_methods is not None:
            self.allowed_methods = allowed_methods
        if allowed_headers is not None:
            self.allowed_headers = allowed_headers
        if max_age is not None:
            self.max_age = max_age

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
            self._set_cors_headers(request, response)
            return response
        return None

    async def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        self._set_cors_headers(request, response)
        return response

    def _set_cors_headers(self, request: HttpRequest, response: HttpResponse) -> None:
        origin = request.META.get("HTTP_ORIGIN", "")
        if "*" in self.allowed_origins or origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin or "*"
        response["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        response["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
        response["Access-Control-Max-Age"] = str(self.max_age)


class ScopedRateLimitMiddleware(RouteMiddleware):
    """Simple in-memory rate limiting per route.

    For production use, back this with Redis. This implementation uses
    a module-level dict — suitable for single-process dev servers.
    """

    _buckets: dict[str, list[float]] = {}

    def __init__(self, *, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_client_key(self, request: HttpRequest) -> str:
        ip = request.META.get("REMOTE_ADDR", "unknown")
        path = request.path
        return f"{ip}:{path}"

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        now = time.monotonic()
        key = self._get_client_key(request)
        bucket = self._buckets.setdefault(key, [])

        # Evict expired entries
        cutoff = now - self.window_seconds
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self.max_requests:
            return JsonResponse(
                {"detail": "Rate limit exceeded"},
                status=429,
            )

        bucket.append(now)
        return None


class ScopedCacheMiddleware(RouteMiddleware):
    """Response caching per route (GET only, in-memory)."""

    _cache: dict[str, tuple[float, HttpResponse]] = {}

    def __init__(self, *, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds

    def _cache_key(self, request: HttpRequest) -> str:
        raw = f"{request.method}:{request.get_full_path()}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        if request.method != "GET":
            return None

        key = self._cache_key(request)
        entry = self._cache.get(key)
        if entry is not None:
            cached_at, cached_response = entry
            if (time.monotonic() - cached_at) < self.ttl_seconds:
                return cached_response
            del self._cache[key]
        return None

    async def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if request.method == "GET" and 200 <= response.status_code < 300:
            key = self._cache_key(request)
            self._cache[key] = (time.monotonic(), response)
        return response


class ScopedAuthMiddleware(RouteMiddleware):
    """Require authenticated user on specific routes."""

    def __init__(self, *, login_url: str | None = None) -> None:
        self.login_url = login_url

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return JsonResponse(
                {"detail": "Authentication required"},
                status=401,
            )
        return None
