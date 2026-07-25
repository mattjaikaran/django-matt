"""Tests for django_matt/interceptors/ — base, chain, decorators, builtins."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import RequestFactory

import orjson
import pytest

from django_matt.interceptors.base import Interceptor
from django_matt.interceptors.builtins import (
    CachingInterceptor,
    LoggingInterceptor,
    RateLimitInterceptor,
    RetryInterceptor,
    TimingInterceptor,
    TransformInterceptor,
)
from django_matt.interceptors.chain import InterceptorChain
from django_matt.interceptors.decorators import intercept, intercept_controller

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(method: str = "GET", path: str = "/test", body: bytes = b"") -> HttpRequest:
    factory = RequestFactory()
    fn = getattr(factory, method.lower())
    if method.upper() in ("POST", "PUT", "PATCH") and body:
        return fn(path, data=body, content_type="application/json")
    return fn(path)


async def _dummy_handler(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
    return JsonResponse({"ok": True})


async def _error_handler(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
    raise ValueError("boom")


# ---------------------------------------------------------------------------
# Base Interceptor
# ---------------------------------------------------------------------------


class TestBaseInterceptor:
    @pytest.mark.asyncio
    async def test_defaults(self) -> None:
        i = Interceptor()
        request = _make_request()
        assert i.order == 0
        assert i.enabled(request) is True
        assert await i.before_request(request) is None
        resp = HttpResponse("ok")
        assert await i.after_response(request, resp) is resp
        assert await i.on_error(request, Exception("x")) is None

    def test_subclass_override(self) -> None:
        class Custom(Interceptor):
            order = 10

            def enabled(self, request: HttpRequest) -> bool:
                return request.method == "POST"

        c = Custom()
        assert c.order == 10
        assert c.enabled(_make_request("GET")) is False
        assert c.enabled(_make_request("POST")) is True


# ---------------------------------------------------------------------------
# InterceptorChain
# ---------------------------------------------------------------------------


class TestInterceptorChain:
    @pytest.mark.asyncio
    async def test_empty_chain_calls_handler(self) -> None:
        chain = InterceptorChain()
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_ordering(self) -> None:
        calls: list[str] = []

        class A(Interceptor):
            order = 10

            async def before_request(self, request: HttpRequest, **kw: Any) -> Any:
                calls.append("A")
                return None

        class B(Interceptor):
            order = 5

            async def before_request(self, request: HttpRequest, **kw: Any) -> Any:
                calls.append("B")
                return None

        chain = InterceptorChain([A(), B()])
        await chain.execute(_make_request(), _dummy_handler)
        assert calls == ["B", "A"]  # B has lower order, runs first

    @pytest.mark.asyncio
    async def test_before_request_short_circuit(self) -> None:
        class Blocker(Interceptor):
            async def before_request(self, request: HttpRequest, **kw: Any) -> Any:
                return JsonResponse({"blocked": True}, status=403)

        handler = AsyncMock(return_value=JsonResponse({"ok": True}))
        chain = InterceptorChain([Blocker()])
        resp = await chain.execute(_make_request(), handler)
        assert resp.status_code == 403
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_after_response_reverse_order(self) -> None:
        calls: list[str] = []

        class A(Interceptor):
            order = 1

            async def after_response(
                self, request: HttpRequest, response: HttpResponse, **kw: Any
            ) -> HttpResponse:
                calls.append("A")
                return response

        class B(Interceptor):
            order = 2

            async def after_response(
                self, request: HttpRequest, response: HttpResponse, **kw: Any
            ) -> HttpResponse:
                calls.append("B")
                return response

        chain = InterceptorChain([A(), B()])
        await chain.execute(_make_request(), _dummy_handler)
        assert calls == ["B", "A"]  # reverse order

    @pytest.mark.asyncio
    async def test_on_error_handling(self) -> None:
        class ErrorCatcher(Interceptor):
            async def on_error(
                self, request: HttpRequest, exc: Exception, **kw: Any
            ) -> HttpResponse | None:
                return JsonResponse({"error": str(exc)}, status=500)

        chain = InterceptorChain([ErrorCatcher()])
        resp = await chain.execute(_make_request(), _error_handler)
        assert resp.status_code == 500
        data = orjson.loads(resp.content)
        assert data["error"] == "boom"

    @pytest.mark.asyncio
    async def test_on_error_propagates_if_unhandled(self) -> None:
        chain = InterceptorChain([Interceptor()])
        with pytest.raises(ValueError, match="boom"):
            await chain.execute(_make_request(), _error_handler)

    @pytest.mark.asyncio
    async def test_disabled_interceptor_skipped(self) -> None:
        class Disabled(Interceptor):
            def enabled(self, request: HttpRequest) -> bool:
                return False

            async def before_request(self, request: HttpRequest, **kw: Any) -> Any:
                return JsonResponse({"blocked": True}, status=403)

        chain = InterceptorChain([Disabled()])
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert resp.status_code == 200

    def test_merge(self) -> None:
        a = InterceptorChain([Interceptor()])
        b = InterceptorChain([Interceptor(), Interceptor()])
        merged = a.merge(b)
        assert len(merged) == 3

    def test_len_and_bool(self) -> None:
        assert not InterceptorChain()
        assert InterceptorChain([Interceptor()])
        assert len(InterceptorChain([Interceptor(), Interceptor()])) == 2


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


class TestDecorators:
    @pytest.mark.asyncio
    async def test_intercept_decorator(self) -> None:
        calls: list[str] = []

        class Marker(Interceptor):
            async def before_request(self, request: HttpRequest, **kw: Any) -> Any:
                calls.append("before")
                return None

            async def after_response(
                self, request: HttpRequest, response: HttpResponse, **kw: Any
            ) -> HttpResponse:
                calls.append("after")
                return response

        @intercept(Marker())
        async def my_view(request: HttpRequest) -> HttpResponse:
            calls.append("handler")
            return JsonResponse({"ok": True})

        resp = await my_view(_make_request())
        assert resp.status_code == 200
        assert calls == ["before", "handler", "after"]
        assert hasattr(my_view, "_interceptors")

    def test_intercept_controller_decorator(self) -> None:
        i1 = Interceptor()
        i2 = Interceptor()

        @intercept_controller(i1, i2)
        class MyController:
            pass

        assert MyController.interceptors == [i1, i2]

    def test_intercept_controller_appends_to_existing(self) -> None:
        i_existing = Interceptor()
        i_new = Interceptor()

        class Base:
            interceptors = [i_existing]

        @intercept_controller(i_new)
        class Child(Base):
            pass

        assert Child.interceptors == [i_existing, i_new]


# ---------------------------------------------------------------------------
# Built-in: TimingInterceptor
# ---------------------------------------------------------------------------


class TestTimingInterceptor:
    @pytest.mark.asyncio
    async def test_adds_timing_header(self) -> None:
        chain = InterceptorChain([TimingInterceptor()])
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert "X-Interceptor-Time" in resp

    @pytest.mark.asyncio
    async def test_custom_header_name(self) -> None:
        chain = InterceptorChain([TimingInterceptor(header_name="X-My-Time")])
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert "X-My-Time" in resp
        assert resp["X-My-Time"].endswith("ms")


# ---------------------------------------------------------------------------
# Built-in: CachingInterceptor
# ---------------------------------------------------------------------------


class TestCachingInterceptor:
    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self) -> None:
        cache = CachingInterceptor(ttl=60)
        chain = InterceptorChain([cache])

        resp1 = await chain.execute(_make_request(), _dummy_handler)
        assert resp1["X-Cache"] == "MISS"

        resp2 = await chain.execute(_make_request(), _dummy_handler)
        assert resp2["X-Cache"] == "HIT"
        assert resp2.content == resp1.content

    @pytest.mark.asyncio
    async def test_post_not_cached(self) -> None:
        cache = CachingInterceptor()
        chain = InterceptorChain([cache])
        req = _make_request("POST", body=b'{"x": 1}')
        resp = await chain.execute(req, _dummy_handler)
        assert "X-Cache" not in resp

    @pytest.mark.asyncio
    async def test_cache_expiry(self) -> None:
        cache = CachingInterceptor(ttl=0)  # instant expiry
        chain = InterceptorChain([cache])

        await chain.execute(_make_request(), _dummy_handler)
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert resp["X-Cache"] == "MISS"


# ---------------------------------------------------------------------------
# Built-in: LoggingInterceptor
# ---------------------------------------------------------------------------


class TestLoggingInterceptor:
    @pytest.mark.asyncio
    async def test_logs_request_and_response(self, caplog: pytest.LogCaptureFixture) -> None:
        chain = InterceptorChain([LoggingInterceptor()])
        with caplog.at_level("INFO", logger="django_matt.interceptors"):
            await chain.execute(_make_request(), _dummy_handler)
        messages = [r.message for r in caplog.records]
        assert "request_start" in messages
        assert "request_end" in messages

    @pytest.mark.asyncio
    async def test_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        class ErrorCatcher(Interceptor):
            order = (
                -200
            )  # lower order than LoggingInterceptor so it runs first in forward, last in reverse

            async def on_error(
                self, request: HttpRequest, exc: Exception, **kw: Any
            ) -> HttpResponse | None:
                return JsonResponse({"error": str(exc)}, status=500)

        chain = InterceptorChain([LoggingInterceptor(), ErrorCatcher()])
        with caplog.at_level("ERROR", logger="django_matt.interceptors"):
            await chain.execute(_make_request(), _error_handler)
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) >= 1


# ---------------------------------------------------------------------------
# Built-in: TransformInterceptor
# ---------------------------------------------------------------------------


class TestTransformInterceptor:
    @pytest.mark.asyncio
    async def test_request_transform(self) -> None:
        captured: list[dict] = []

        async def handler(request: HttpRequest, *a: Any, **kw: Any) -> HttpResponse:
            captured.append(orjson.loads(request.body))
            return JsonResponse({"ok": True})

        transform = TransformInterceptor(
            request_transform=lambda d: {**d, "injected": True},
        )
        chain = InterceptorChain([transform])
        req = _make_request("POST", body=b'{"name": "test"}')
        await chain.execute(req, handler)
        assert captured[0]["injected"] is True
        assert captured[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_response_transform(self) -> None:
        transform = TransformInterceptor(
            response_transform=lambda d: {**d, "extra": "added"},
        )
        chain = InterceptorChain([transform])
        resp = await chain.execute(_make_request(), _dummy_handler)
        data = orjson.loads(resp.content)
        assert data["extra"] == "added"
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# Built-in: RateLimitInterceptor
# ---------------------------------------------------------------------------


class TestRateLimitInterceptor:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self) -> None:
        rl = RateLimitInterceptor(max_requests=5, window=60)
        chain = InterceptorChain([rl])
        for _ in range(5):
            resp = await chain.execute(_make_request(), _dummy_handler)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        rl = RateLimitInterceptor(max_requests=2, window=60)
        chain = InterceptorChain([rl])
        await chain.execute(_make_request(), _dummy_handler)
        await chain.execute(_make_request(), _dummy_handler)
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert resp.status_code == 429
        data = orjson.loads(resp.content)
        assert "rate limit" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_custom_key_func(self) -> None:
        rl = RateLimitInterceptor(
            max_requests=1,
            window=60,
            key_func=lambda r: "static-key",
        )
        chain = InterceptorChain([rl])
        await chain.execute(_make_request(), _dummy_handler)
        resp = await chain.execute(_make_request(), _dummy_handler)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Built-in: RetryInterceptor
# ---------------------------------------------------------------------------


class TestRetryInterceptor:
    @pytest.mark.asyncio
    async def test_sets_retry_count(self) -> None:
        ri = RetryInterceptor(max_retries=3)
        req = _make_request()
        await ri.before_request(req)
        assert req._interceptor_retry_count == 0  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_on_error_returns_none(self) -> None:
        ri = RetryInterceptor()
        result = await ri.on_error(_make_request(), ValueError("x"))
        assert result is None


# ---------------------------------------------------------------------------
# Integration: multiple interceptors composing
# ---------------------------------------------------------------------------


class TestComposition:
    @pytest.mark.asyncio
    async def test_timing_and_caching_together(self) -> None:
        chain = InterceptorChain(
            [
                TimingInterceptor(),
                CachingInterceptor(ttl=60),
            ]
        )
        resp1 = await chain.execute(_make_request(), _dummy_handler)
        assert "X-Interceptor-Time" in resp1
        assert resp1["X-Cache"] == "MISS"

        resp2 = await chain.execute(_make_request(), _dummy_handler)
        assert resp2["X-Cache"] == "HIT"

    @pytest.mark.asyncio
    async def test_rate_limit_before_handler(self) -> None:
        handler = AsyncMock(return_value=JsonResponse({"ok": True}))
        rl = RateLimitInterceptor(max_requests=1, window=60)
        chain = InterceptorChain([rl])

        await chain.execute(_make_request(), handler)
        assert handler.await_count == 1

        resp = await chain.execute(_make_request(), handler)
        assert resp.status_code == 429
        assert handler.await_count == 1  # handler not called on rate limit

    @pytest.mark.asyncio
    async def test_error_with_after_response_still_runs(self) -> None:
        calls: list[str] = []

        class AfterTracker(Interceptor):
            order = 1

            async def after_response(
                self, request: HttpRequest, response: HttpResponse, **kw: Any
            ) -> HttpResponse:
                calls.append("after")
                return response

        class ErrorCatcher(Interceptor):
            order = 2

            async def on_error(
                self, request: HttpRequest, exc: Exception, **kw: Any
            ) -> HttpResponse | None:
                return JsonResponse({"caught": True}, status=500)

        chain = InterceptorChain([AfterTracker(), ErrorCatcher()])
        resp = await chain.execute(_make_request(), _error_handler)
        assert resp.status_code == 500
        assert "after" in calls


# ---------------------------------------------------------------------------
# Public API imports
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_all_exports(self) -> None:
        from django_matt.interceptors import (
            CachingInterceptor,
            Interceptor,
            InterceptorChain,
            LoggingInterceptor,
            RateLimitInterceptor,
            RetryInterceptor,
            TimingInterceptor,
            TransformInterceptor,
            intercept,
            intercept_controller,
        )

        # all imported successfully
        assert all(
            [
                Interceptor,
                InterceptorChain,
                intercept,
                intercept_controller,
                LoggingInterceptor,
                TimingInterceptor,
                CachingInterceptor,
                TransformInterceptor,
                RetryInterceptor,
                RateLimitInterceptor,
            ]
        )
