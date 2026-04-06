from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.middleware.builtins import (
    ScopedAuthMiddleware,
    ScopedCacheMiddleware,
    ScopedCorsMiddleware,
    ScopedRateLimitMiddleware,
)
from django_matt.middleware.scoped import (
    MiddlewareStack,
    RouteMiddleware,
    _resolve_middleware_stack,
    skip_middleware,
    use_middleware,
)

# --- Test helpers ---

class TrackingMiddleware(RouteMiddleware):
    calls: list[str] = []

    def __init__(self) -> None:
        TrackingMiddleware.calls = []

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        TrackingMiddleware.calls.append("request")
        return None

    async def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        TrackingMiddleware.calls.append("response")
        return response


class BlockingMiddleware(RouteMiddleware):
    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        return JsonResponse({"detail": "blocked"}, status=403)


class ExceptionCatchMiddleware(RouteMiddleware):
    caught: Exception | None = None

    def __init__(self) -> None:
        ExceptionCatchMiddleware.caught = None

    async def process_exception(
        self, request: HttpRequest, exc: Exception
    ) -> HttpResponse | None:
        ExceptionCatchMiddleware.caught = exc
        return JsonResponse({"detail": "caught"}, status=500)


class OrderTracker(RouteMiddleware):
    order: list[tuple[str, str]] = []

    def __init__(self, name: str = "default") -> None:
        self._name = name

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        OrderTracker.order.append((self._name, "request"))
        return None

    async def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        OrderTracker.order.append((self._name, "response"))
        return response


@pytest.fixture
def rf():
    return RequestFactory()


# --- RouteMiddleware base ---

class TestRouteMiddlewareBase:
    @pytest.mark.asyncio
    async def test_default_process_request_returns_none(self, rf):
        mw = RouteMiddleware()
        result = await mw.process_request(rf.get("/"))
        assert result is None

    @pytest.mark.asyncio
    async def test_default_process_response_passes_through(self, rf):
        mw = RouteMiddleware()
        response = HttpResponse("ok")
        result = await mw.process_response(rf.get("/"), response)
        assert result is response

    @pytest.mark.asyncio
    async def test_default_process_exception_returns_none(self, rf):
        mw = RouteMiddleware()
        result = await mw.process_exception(rf.get("/"), ValueError("test"))
        assert result is None


# --- MiddlewareStack ---

class TestMiddlewareStack:
    @pytest.mark.asyncio
    async def test_execute_calls_handler(self, rf):
        stack = MiddlewareStack([])
        called = False

        async def handler(request):
            nonlocal called
            called = True
            return JsonResponse({"ok": True})

        await stack.execute(rf.get("/"), handler)
        assert called

    @pytest.mark.asyncio
    async def test_request_hooks_run(self, rf):
        TrackingMiddleware.calls = []
        stack = MiddlewareStack([TrackingMiddleware()])

        async def handler(request):
            return JsonResponse({"ok": True})

        await stack.execute(rf.get("/"), handler)
        assert "request" in TrackingMiddleware.calls
        assert "response" in TrackingMiddleware.calls

    @pytest.mark.asyncio
    async def test_blocking_middleware_short_circuits(self, rf):
        stack = MiddlewareStack([BlockingMiddleware()])
        handler_called = False

        async def handler(request):
            nonlocal handler_called
            handler_called = True
            return JsonResponse({"ok": True})

        response = await stack.execute(rf.get("/"), handler)
        assert not handler_called
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_exception_middleware_catches(self, rf):
        stack = MiddlewareStack([ExceptionCatchMiddleware()])

        async def handler(request):
            raise ValueError("boom")

        response = await stack.execute(rf.get("/"), handler)
        assert response.status_code == 500
        assert ExceptionCatchMiddleware.caught is not None

    @pytest.mark.asyncio
    async def test_exception_reraises_if_not_caught(self, rf):
        stack = MiddlewareStack([TrackingMiddleware()])

        async def handler(request):
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await stack.execute(rf.get("/"), handler)

    @pytest.mark.asyncio
    async def test_onion_order(self, rf):
        OrderTracker.order = []

        class First(OrderTracker):
            def __init__(self):
                super().__init__("first")

        class Second(OrderTracker):
            def __init__(self):
                super().__init__("second")

        stack = MiddlewareStack([First(), Second()])

        async def handler(request):
            return JsonResponse({"ok": True})

        await stack.execute(rf.get("/"), handler)
        assert OrderTracker.order == [
            ("first", "request"),
            ("second", "request"),
            ("second", "response"),
            ("first", "response"),
        ]

    @pytest.mark.asyncio
    async def test_handler_args_kwargs_passed(self, rf):
        stack = MiddlewareStack([])
        received_args = None
        received_kwargs = None

        async def handler(request, *args, **kwargs):
            nonlocal received_args, received_kwargs
            received_args = args
            received_kwargs = kwargs
            return JsonResponse({"ok": True})

        await stack.execute(rf.get("/"), handler, "a", "b", key="val")
        assert received_args == ("a", "b")
        assert received_kwargs == {"key": "val"}


# --- _resolve_middleware_stack ---

class TestResolveMiddlewareStack:
    def test_empty_returns_none(self):
        result = _resolve_middleware_stack([], None, None)
        assert result is None

    def test_controller_classes_only(self):
        result = _resolve_middleware_stack([TrackingMiddleware], None, None)
        assert result is not None
        assert len(result._middlewares) == 1

    def test_method_add(self):
        result = _resolve_middleware_stack(
            [TrackingMiddleware], [BlockingMiddleware], None
        )
        assert len(result._middlewares) == 2

    def test_method_skip(self):
        result = _resolve_middleware_stack(
            [TrackingMiddleware, BlockingMiddleware], None, [BlockingMiddleware]
        )
        assert len(result._middlewares) == 1
        assert isinstance(result._middlewares[0], TrackingMiddleware)

    def test_skip_all_returns_none(self):
        result = _resolve_middleware_stack(
            [TrackingMiddleware], None, [TrackingMiddleware]
        )
        assert result is None

    def test_add_deduplicates(self):
        result = _resolve_middleware_stack(
            [TrackingMiddleware], [TrackingMiddleware], None
        )
        assert len(result._middlewares) == 1


# --- Decorators ---

class TestDecorators:
    def test_use_middleware_sets_attr(self):
        @use_middleware(TrackingMiddleware, BlockingMiddleware)
        def my_func():
            pass

        assert my_func._use_middleware == [TrackingMiddleware, BlockingMiddleware]

    def test_skip_middleware_sets_attr(self):
        @skip_middleware(TrackingMiddleware)
        def my_func():
            pass

        assert my_func._skip_middleware == [TrackingMiddleware]

    def test_stacking_decorators(self):
        @use_middleware(TrackingMiddleware)
        @use_middleware(BlockingMiddleware)
        def my_func():
            pass

        assert set(my_func._use_middleware) == {TrackingMiddleware, BlockingMiddleware}


# --- Builtin middleware ---

class TestScopedCorsMiddleware:
    @pytest.mark.asyncio
    async def test_options_returns_204(self, rf):
        mw = ScopedCorsMiddleware()
        request = rf.options("/", HTTP_ORIGIN="http://example.com")
        response = await mw.process_request(request)
        assert response is not None
        assert response.status_code == 204
        assert "Access-Control-Allow-Origin" in response

    @pytest.mark.asyncio
    async def test_sets_cors_headers_on_response(self, rf):
        mw = ScopedCorsMiddleware()
        request = rf.get("/", HTTP_ORIGIN="http://example.com")
        response = HttpResponse("ok")
        result = await mw.process_response(request, response)
        assert "Access-Control-Allow-Origin" in result

    @pytest.mark.asyncio
    async def test_custom_origins(self, rf):
        mw = ScopedCorsMiddleware(allowed_origins=["http://allowed.com"])
        request = rf.get("/", HTTP_ORIGIN="http://allowed.com")
        response = HttpResponse("ok")
        result = await mw.process_response(request, response)
        assert result["Access-Control-Allow-Origin"] == "http://allowed.com"


class TestScopedRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, rf):
        mw = ScopedRateLimitMiddleware(max_requests=5, window_seconds=60)
        # Clear state
        ScopedRateLimitMiddleware._buckets.clear()
        request = rf.get("/test-rate")
        result = await mw.process_request(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, rf):
        mw = ScopedRateLimitMiddleware(max_requests=2, window_seconds=60)
        ScopedRateLimitMiddleware._buckets.clear()
        request = rf.get("/test-rate-block")
        await mw.process_request(request)
        await mw.process_request(request)
        result = await mw.process_request(request)
        assert result is not None
        assert result.status_code == 429


class TestScopedCacheMiddleware:
    @pytest.mark.asyncio
    async def test_caches_get_response(self, rf):
        mw = ScopedCacheMiddleware(ttl_seconds=60)
        ScopedCacheMiddleware._cache.clear()
        request = rf.get("/cache-test")

        # First call — no cache
        result = await mw.process_request(request)
        assert result is None

        # Store response
        response = JsonResponse({"data": "cached"})
        await mw.process_response(request, response)

        # Second call — should hit cache
        cached = await mw.process_request(request)
        assert cached is not None
        assert cached is response

    @pytest.mark.asyncio
    async def test_does_not_cache_post(self, rf):
        mw = ScopedCacheMiddleware(ttl_seconds=60)
        ScopedCacheMiddleware._cache.clear()
        request = rf.post("/cache-test")
        result = await mw.process_request(request)
        assert result is None


class TestScopedAuthMiddleware:
    @pytest.mark.asyncio
    async def test_rejects_unauthenticated(self, rf):
        mw = ScopedAuthMiddleware()
        request = rf.get("/auth-test")
        # No user set
        result = await mw.process_request(request)
        assert result is not None
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_allows_authenticated(self, rf):
        mw = ScopedAuthMiddleware()
        request = rf.get("/auth-test")

        class FakeUser:
            is_authenticated = True

        request.user = FakeUser()
        result = await mw.process_request(request)
        assert result is None


# --- Controller integration ---

class TestControllerIntegration:
    def test_controller_middleware_classes_default_empty(self):
        from django_matt.core.controller import Controller

        class MyController(Controller):
            pass

        assert MyController.middleware_classes == []

    def test_controller_middleware_classes_inherited(self):
        from django_matt.core.controller import Controller

        class ParentController(Controller):
            middleware_classes = [TrackingMiddleware]

        class ChildController(ParentController):
            pass

        # Child gets its own copy
        assert ChildController.middleware_classes == [TrackingMiddleware]
        assert ChildController.middleware_classes is not ParentController.middleware_classes

    @pytest.mark.asyncio
    async def test_controller_middleware_executes(self, rf):
        from django_matt.core.controller import Controller
        from django_matt.core.router import get

        TrackingMiddleware.calls = []

        class TestController(Controller):
            middleware_classes = [TrackingMiddleware]

            @get("/test")
            async def test_endpoint(self, request):
                return JsonResponse({"ok": True})

        ctrl = TestController()
        request = rf.get("/test")
        response = await ctrl.test_endpoint(request)

        assert "request" in TrackingMiddleware.calls
        assert "response" in TrackingMiddleware.calls
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_controller_blocking_middleware(self, rf):
        from django_matt.core.controller import Controller
        from django_matt.core.router import get

        class TestController(Controller):
            middleware_classes = [BlockingMiddleware]

            @get("/test")
            async def test_endpoint(self, request):
                return JsonResponse({"ok": True})

        ctrl = TestController()
        request = rf.get("/test")
        response = await ctrl.test_endpoint(request)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_use_middleware_decorator_on_method(self, rf):
        from django_matt.core.controller import Controller
        from django_matt.core.router import get

        TrackingMiddleware.calls = []

        class TestController(Controller):
            @use_middleware(TrackingMiddleware)
            @get("/test")
            async def test_endpoint(self, request):
                return JsonResponse({"ok": True})

        ctrl = TestController()
        request = rf.get("/test")
        response = await ctrl.test_endpoint(request)
        assert "request" in TrackingMiddleware.calls
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_skip_middleware_decorator(self, rf):
        from django_matt.core.controller import Controller
        from django_matt.core.router import get

        class TestController(Controller):
            middleware_classes = [TrackingMiddleware, BlockingMiddleware]

            @skip_middleware(BlockingMiddleware)
            @get("/test")
            async def test_endpoint(self, request):
                return JsonResponse({"ok": True})

        ctrl = TestController()
        request = rf.get("/test")
        response = await ctrl.test_endpoint(request)
        # BlockingMiddleware was skipped, so handler runs
        assert response.status_code == 200
        assert "request" in TrackingMiddleware.calls
