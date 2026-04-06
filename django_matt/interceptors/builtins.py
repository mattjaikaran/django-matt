from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

import orjson

from django_matt.interceptors.base import Interceptor

logger = logging.getLogger("django_matt.interceptors")


class LoggingInterceptor(Interceptor):
    """Structured request/response logging."""

    order: int = -100

    def __init__(
        self,
        log_body: bool = False,
        log_headers: bool = False,
        logger_name: str | None = None,
    ) -> None:
        self.log_body = log_body
        self.log_headers = log_headers
        self._logger = logging.getLogger(logger_name) if logger_name else logger

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        extra: dict[str, Any] = {
            "method": request.method,
            "path": request.path,
        }
        if self.log_headers:
            extra["headers"] = dict(request.headers)
        if self.log_body and request.body:
            try:
                extra["body"] = orjson.loads(request.body)
            except (ValueError, orjson.JSONDecodeError):
                extra["body"] = "<non-json>"
        self._logger.info("request_start", extra=extra)
        request._interceptor_log_start = time.monotonic()  # type: ignore[attr-defined]
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        start = getattr(request, "_interceptor_log_start", None)
        duration_ms = (time.monotonic() - start) * 1000 if start else None
        self._logger.info(
            "request_end",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": f"{duration_ms:.1f}" if duration_ms else None,
            },
        )
        return response

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs: Any
    ) -> HttpResponse | None:
        self._logger.exception(
            "request_error",
            extra={"method": request.method, "path": request.path},
            exc_info=exc,
        )
        return None


class TimingInterceptor(Interceptor):
    """Inject X-Interceptor-Time header with handler duration."""

    order: int = -90

    def __init__(self, header_name: str = "X-Interceptor-Time") -> None:
        self.header_name = header_name

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        request._interceptor_timing_start = time.monotonic()  # type: ignore[attr-defined]
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        start = getattr(request, "_interceptor_timing_start", None)
        if start is not None:
            duration_ms = (time.monotonic() - start) * 1000
            response[self.header_name] = f"{duration_ms:.1f}ms"
        return response


class CachingInterceptor(Interceptor):
    """In-memory response cache keyed by method+path+query."""

    order: int = -80

    def __init__(
        self,
        ttl: float = 60.0,
        methods: set[str] | None = None,
    ) -> None:
        self.ttl = ttl
        self.methods = methods or {"GET"}
        self._cache: dict[str, tuple[float, bytes, int, str]] = {}

    def _cache_key(self, request: HttpRequest) -> str:
        raw = f"{request.method}:{request.get_full_path()}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        if request.method not in self.methods:
            return None
        key = self._cache_key(request)
        entry = self._cache.get(key)
        if entry is not None:
            cached_at, content, status, content_type = entry
            if (time.monotonic() - cached_at) < self.ttl:
                resp = HttpResponse(content, status=status, content_type=content_type)
                resp["X-Cache"] = "HIT"
                return resp
            del self._cache[key]
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        # Don't re-cache responses that were already served from cache
        if response.get("X-Cache") == "HIT":
            return response
        if request.method in self.methods and 200 <= response.status_code < 300:
            key = self._cache_key(request)
            self._cache[key] = (
                time.monotonic(),
                response.content,
                response.status_code,
                response.get("Content-Type", "application/json"),
            )
            response["X-Cache"] = "MISS"
        return response


class TransformInterceptor(Interceptor):
    """Apply sync callables to request body and/or response content."""

    order: int = 0

    def __init__(
        self,
        request_transform: Any | None = None,
        response_transform: Any | None = None,
    ) -> None:
        self.request_transform = request_transform
        self.response_transform = response_transform

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        if self.request_transform and request.body:
            try:
                data = orjson.loads(request.body)
                transformed = self.request_transform(data)
                request._body = orjson.dumps(transformed)  # type: ignore[attr-defined]
            except (ValueError, orjson.JSONDecodeError):
                pass
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        if self.response_transform and hasattr(response, "content"):
            try:
                data = orjson.loads(response.content)
                transformed = self.response_transform(data)
                response.content = orjson.dumps(transformed)
            except (ValueError, orjson.JSONDecodeError):
                pass
        return response


class RetryInterceptor(Interceptor):
    """Retry handler on specified exception types."""

    order: int = 50

    def __init__(
        self,
        max_retries: int = 3,
        retry_on: tuple[type[Exception], ...] = (Exception,),
    ) -> None:
        self.max_retries = max_retries
        self.retry_on = retry_on

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        request._interceptor_retry_count = 0  # type: ignore[attr-defined]
        return None

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs: Any
    ) -> HttpResponse | None:
        # RetryInterceptor signals retries via the chain — callers handle the loop.
        # For standalone use, return None to let the exception propagate.
        return None


class RateLimitInterceptor(Interceptor):
    """Simple in-memory per-route rate limiter."""

    order: int = -95

    def __init__(
        self,
        max_requests: int = 100,
        window: float = 60.0,
        key_func: Any | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window = window
        self.key_func = key_func or self._default_key
        self._hits: dict[str, list[float]] = {}

    @staticmethod
    def _default_key(request: HttpRequest) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        key = f"{self.key_func(request)}:{request.path}"
        now = time.monotonic()
        hits = self._hits.setdefault(key, [])
        # prune expired
        cutoff = now - self.window
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= self.max_requests:
            return JsonResponse(
                {"detail": "Rate limit exceeded"},
                status=429,
            )
        hits.append(now)
        return None
