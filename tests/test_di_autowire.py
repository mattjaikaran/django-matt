"""
Tests for DI auto-wiring integration in router and controller.

Verifies that Depends() markers are resolved automatically when
DI_AUTO_WIRE is enabled in DJANGO_MATT settings, and that existing
behavior is unchanged when disabled (the default).
"""

import asyncio
import inspect
from unittest.mock import MagicMock, patch

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.core.controller import (
    Controller,
)
from django_matt.core.controller import (
    _get_di_config as controller_get_di_config,
)
from django_matt.core.controller import (
    _reset_di_config as controller_reset_di_config,
)
from django_matt.core.router import (
    APIRouter,
    _analyze_di_params,
)
from django_matt.core.router import (
    _get_di_config as router_get_di_config,
)
from django_matt.core.router import (
    _reset_di_config as router_reset_di_config,
)
from django_matt.di import Container, Depends, Scoped, Singleton, Transient
from django_matt.di.container import _scoped_instances
from django_matt.di.container import container as default_container
from django_matt.di.depends import DependencyMarker

# =============================================================================
# Test Service Classes
# =============================================================================


class FakeService:
    """Simple service for DI testing."""

    def get_data(self):
        return "hello"


class FakeScopedService:
    """Service that tracks instance count for scoped lifetime testing."""

    _instance_count = 0

    def __init__(self):
        FakeScopedService._instance_count += 1
        self.id = FakeScopedService._instance_count


class FakeSingletonService:
    """Service for singleton lifetime testing."""

    _instance_count = 0

    def __init__(self):
        FakeSingletonService._instance_count += 1
        self.id = FakeSingletonService._instance_count


class FakeTransientService:
    """Service for transient lifetime testing."""

    _instance_count = 0

    def __init__(self):
        FakeTransientService._instance_count += 1
        self.id = FakeTransientService._instance_count


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_di_config():
    """Reset cached DI config before and after each test."""
    router_reset_di_config()
    controller_reset_di_config()
    yield
    router_reset_di_config()
    controller_reset_di_config()


@pytest.fixture(autouse=True)
def reset_instance_counts():
    """Reset instance counters before each test."""
    FakeScopedService._instance_count = 0
    FakeSingletonService._instance_count = 0
    FakeTransientService._instance_count = 0
    yield


@pytest.fixture
def di_container():
    """Provide a fresh DI container for tests."""
    c = Container()
    c.register(FakeService, lifetime=Singleton)
    c.register(FakeScopedService, lifetime=Scoped)
    c.register(FakeSingletonService, lifetime=Singleton)
    c.register(FakeTransientService, lifetime=Transient)
    return c


@pytest.fixture
def rf():
    """Provide a Django RequestFactory."""
    return RequestFactory()


# =============================================================================
# _get_di_config Tests
# =============================================================================


class TestGetDIConfig:
    """Tests for the cached DI config reader."""

    def test_default_is_false(self):
        """DI_AUTO_WIRE defaults to False when not set."""
        assert router_get_di_config() is False

    def test_reads_from_settings(self, settings):
        """DI_AUTO_WIRE reads from DJANGO_MATT settings dict."""
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": True}
        router_reset_di_config()
        assert router_get_di_config() is True

    def test_caches_result(self, settings):
        """Config is cached after first call — subsequent calls don't re-read."""
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": True}
        router_reset_di_config()
        result1 = router_get_di_config()

        # Change settings - cached value should persist
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": False}
        result2 = router_get_di_config()
        assert result1 is True
        assert result2 is True  # Still cached as True

    def test_reset_clears_cache(self, settings):
        """_reset_di_config clears the cache so next call re-reads."""
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": True}
        router_reset_di_config()
        router_get_di_config()

        router_reset_di_config()
        # Remove the setting so it falls back to default
        if hasattr(settings, "DJANGO_MATT"):
            del settings.DJANGO_MATT
        assert router_get_di_config() is False

    def test_controller_config_independent(self, settings):
        """Controller and router have independent config caches."""
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": True}
        controller_reset_di_config()
        assert controller_get_di_config() is True

        # Router should also read True from the same settings
        router_reset_di_config()
        assert router_get_di_config() is True

        # Now verify they cache independently
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": False}
        controller_reset_di_config()
        assert controller_get_di_config() is False
        # Router still cached as True
        assert router_get_di_config() is True


# =============================================================================
# _analyze_di_params Tests
# =============================================================================


class TestAnalyzeDIParams:
    """Tests for the DI parameter analyzer."""

    def test_returns_none_when_disabled(self):
        """Returns None when DI_AUTO_WIRE is False (default)."""

        async def endpoint(request, svc: FakeService = Depends()):
            pass

        result = _analyze_di_params(endpoint)
        assert result is None

    def test_returns_none_for_no_di_params(self):
        """Returns None when endpoint has no Depends() markers."""
        with patch("django_matt.core.router._di_config", True):

            async def endpoint(request, name: str = "default"):
                pass

            result = _analyze_di_params(endpoint)
            assert result is None

    def test_returns_dict_for_depends_params(self):
        """Returns dict mapping param names to DependencyMarker instances."""
        with patch("django_matt.core.router._di_config", True):
            dep = Depends()

            async def endpoint(request, svc: FakeService = dep):
                pass

            result = _analyze_di_params(endpoint)
            assert result is not None
            assert "svc" in result
            assert result["svc"] is dep

    def test_skips_self_cls_request_body(self):
        """Skips self, cls, request, and body parameters."""
        with patch("django_matt.core.router._di_config", True):

            async def endpoint(self, request, body, svc: FakeService = Depends()):
                pass

            result = _analyze_di_params(endpoint)
            assert result is not None
            assert "self" not in result
            assert "request" not in result
            assert "body" not in result
            assert "svc" in result

    def test_skips_var_positional_and_keyword(self):
        """Skips *args and **kwargs."""
        with patch("django_matt.core.router._di_config", True):

            async def endpoint(request, *args, svc: FakeService = Depends(), **kwargs):
                pass

            result = _analyze_di_params(endpoint)
            assert result is not None
            assert "svc" in result
            assert len(result) == 1

    def test_multiple_depends_params(self):
        """Detects multiple Depends() markers."""
        with patch("django_matt.core.router._di_config", True):
            dep1 = Depends()
            dep2 = Depends(FakeService)

            async def endpoint(
                request,
                svc1: FakeService = dep1,
                svc2: FakeService = dep2,
            ):
                pass

            result = _analyze_di_params(endpoint)
            assert result is not None
            assert len(result) == 2
            assert result["svc1"] is dep1
            assert result["svc2"] is dep2


# =============================================================================
# Router DI Auto-Wire Tests
# =============================================================================


class TestRouterDIAutoWire:
    """Tests for DI auto-wiring in the router's _create_view_func."""

    def test_di_disabled_no_resolution(self, rf):
        """When DI_AUTO_WIRE=False, Depends() markers are NOT resolved."""
        call_log = {}
        marker = Depends()

        async def endpoint(request, svc: FakeService = marker):
            call_log["svc"] = svc
            return {"ok": True}

        router = APIRouter()
        view = router._create_view_func(endpoint, None, 200, methods=["GET"])

        request = rf.get("/test")
        asyncio.get_event_loop().run_until_complete(view(request))

        # svc should be the raw Depends() marker (not resolved to FakeService)
        assert call_log["svc"] is marker
        assert not isinstance(call_log["svc"], FakeService)

    def test_di_enabled_resolves_depends(self, rf, di_container):
        """When DI_AUTO_WIRE=True, Depends() markers are resolved."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            async def endpoint(request, svc: FakeService = Depends()):
                call_log["svc"] = svc
                return {"ok": True}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            response = asyncio.get_event_loop().run_until_complete(view(request))

            assert "svc" in call_log
            assert isinstance(call_log["svc"], FakeService)
            assert call_log["svc"].get_data() == "hello"

    def test_di_enabled_no_di_params_unaffected(self, rf):
        """Endpoints without Depends() params work normally when DI is enabled."""
        with patch("django_matt.core.router._di_config", True):
            call_log = {}

            async def endpoint(request):
                call_log["called"] = True
                return {"ok": True}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            response = asyncio.get_event_loop().run_until_complete(view(request))

            assert call_log["called"] is True

    def test_di_scoped_per_request(self, rf, di_container):
        """Scoped services get one instance per request scope."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            results = []

            async def endpoint(request, svc: FakeScopedService = Depends()):
                results.append(svc.id)
                return {"id": svc.id}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            # First request
            request1 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request1))

            # Second request
            request2 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request2))

            # Each request should get a different scoped instance
            assert len(results) == 2
            assert results[0] != results[1]

    def test_di_singleton_shared_across_requests(self, rf, di_container):
        """Singleton services are shared across requests."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            results = []

            async def endpoint(request, svc: FakeSingletonService = Depends()):
                results.append(svc.id)
                return {"id": svc.id}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            # First request
            request1 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request1))

            # Second request
            request2 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request2))

            # Singleton should be the same instance
            assert len(results) == 2
            assert results[0] == results[1]

    def test_di_scope_cleanup_in_finally(self, rf, di_container):
        """Scope token is cleaned up even when endpoint raises."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):

            async def failing_endpoint(request, svc: FakeService = Depends()):
                raise ValueError("test error")

            router = APIRouter()
            view = router._create_view_func(failing_endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")

            with pytest.raises(ValueError, match="test error"):
                asyncio.get_event_loop().run_until_complete(view(request))

            # Scoped instances should be cleaned up (reset to None)
            assert _scoped_instances.get() is None

    def test_di_sync_endpoint(self, rf, di_container):
        """DI works with sync endpoints."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            def endpoint(request, svc: FakeService = Depends()):
                call_log["svc"] = svc
                return {"ok": True}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request))

            assert "svc" in call_log
            assert isinstance(call_log["svc"], FakeService)

    def test_di_preserves_existing_kwargs(self, rf, di_container):
        """DI resolution does not overwrite existing kwargs (e.g., URL params)."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            async def endpoint(request, pk: int = None, svc: FakeService = Depends()):
                call_log["pk"] = pk
                call_log["svc"] = svc
                return {"pk": pk}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request, pk=42))

            assert call_log["pk"] == 42
            assert isinstance(call_log["svc"], FakeService)

    def test_di_does_not_create_scope_if_already_exists(self, rf, di_container):
        """If a scope already exists (e.g., from middleware), don't create a new one."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            scope_ids = []

            async def endpoint(request, svc: FakeScopedService = Depends()):
                scope_ids.append(svc.id)
                return {"id": svc.id}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            # Pre-set a scope (simulating middleware)
            token = _scoped_instances.set({})
            try:
                request = rf.get("/test")
                asyncio.get_event_loop().run_until_complete(view(request))

                # Second call in same scope should get same scoped instance
                request2 = rf.get("/test")
                asyncio.get_event_loop().run_until_complete(view(request2))

                assert len(scope_ids) == 2
                assert scope_ids[0] == scope_ids[1]  # Same scope = same instance
            finally:
                _scoped_instances.reset(token)


# =============================================================================
# Controller DI Auto-Wire Tests
# =============================================================================


class TestControllerDIAutoWire:
    """Tests for DI auto-wiring in the controller's _setup_methods.

    The controller wrapper captures `request` as a named parameter and calls
    `_method(*args, **kwargs)`. This means controller methods accessed directly
    via the wrapper need the request passed as the first positional arg.
    The wrapper itself handles request-level concerns (body parsing, DI, errors).
    """

    def test_controller_di_disabled(self, rf):
        """When DI_AUTO_WIRE=False, controller methods work normally."""
        from django_matt.core.router import get as route_get

        call_log = {}

        class TestController(Controller):
            prefix = "/test"
            auto_error_handling = False

            @route_get("/items")
            async def list_items(self):
                call_log["called"] = True
                return JsonResponse({"items": []})

        controller = TestController()
        request = rf.get("/test/items")
        result = asyncio.get_event_loop().run_until_complete(
            controller.list_items(request)
        )
        assert call_log["called"] is True
        assert result.status_code == 200

    def test_controller_di_enabled_resolves(self, rf, di_container):
        """When DI_AUTO_WIRE=True, controller method Depends() are resolved."""
        from django_matt.core.router import get as route_get

        with (
            patch("django_matt.core.controller._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            class TestController(Controller):
                prefix = "/test"
                auto_error_handling = False

                @route_get("/items")
                async def list_items(self, svc: FakeService = Depends()):
                    call_log["svc"] = svc
                    return JsonResponse({"ok": True})

            controller = TestController()
            request = rf.get("/test/items")
            result = asyncio.get_event_loop().run_until_complete(
                controller.list_items(request)
            )

            assert "svc" in call_log
            assert isinstance(call_log["svc"], FakeService)
            assert call_log["svc"].get_data() == "hello"

    def test_controller_di_scope_cleanup(self, rf, di_container):
        """Controller cleans up DI scope in finally block."""
        from django_matt.core.router import get as route_get

        with (
            patch("django_matt.core.controller._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):

            class TestController(Controller):
                prefix = "/test"
                auto_error_handling = False

                @route_get("/fail")
                async def fail_endpoint(self, svc: FakeService = Depends()):
                    raise RuntimeError("boom")

            controller = TestController()
            request = rf.get("/test/fail")

            with pytest.raises(RuntimeError, match="boom"):
                asyncio.get_event_loop().run_until_complete(
                    controller.fail_endpoint(request)
                )

            # Scope should be cleaned up
            assert _scoped_instances.get() is None

    def test_controller_method_without_depends_unaffected(self, rf):
        """Controller methods without Depends() are not affected by DI."""
        from django_matt.core.router import get as route_get

        with patch("django_matt.core.controller._di_config", True):
            call_log = {}

            class TestController(Controller):
                prefix = "/test"
                auto_error_handling = False

                @route_get("/plain")
                async def plain_endpoint(self):
                    call_log["called"] = True
                    return JsonResponse({"ok": True})

            controller = TestController()
            request = rf.get("/test/plain")
            result = asyncio.get_event_loop().run_until_complete(
                controller.plain_endpoint(request)
            )

            assert call_log["called"] is True
            assert result.status_code == 200

    def test_controller_di_multiple_services(self, rf, di_container):
        """Controller can resolve multiple Depends() params."""
        from django_matt.core.router import get as route_get

        with (
            patch("django_matt.core.controller._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            class TestController(Controller):
                prefix = "/test"
                auto_error_handling = False

                @route_get("/multi")
                async def multi_endpoint(
                    self,
                    svc: FakeService = Depends(),
                    singleton: FakeSingletonService = Depends(),
                ):
                    call_log["svc"] = svc
                    call_log["singleton"] = singleton
                    return JsonResponse({"ok": True})

            controller = TestController()
            request = rf.get("/test/multi")
            asyncio.get_event_loop().run_until_complete(
                controller.multi_endpoint(request)
            )

            assert isinstance(call_log["svc"], FakeService)
            assert isinstance(call_log["singleton"], FakeSingletonService)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDIAutoWireIntegration:
    """Integration tests combining router and controller DI auto-wiring."""

    def test_router_add_route_with_di(self, rf, di_container):
        """Full flow: add_route -> get_urls -> call view with DI."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            async def my_endpoint(request, svc: FakeService = Depends()):
                call_log["svc"] = svc
                return {"data": svc.get_data()}

            router = APIRouter()
            router.add_route("test/", my_endpoint, methods=["GET"])

            urls = router.get_urls()
            assert len(urls) == 1

            # Simulate calling the view
            request = rf.get("/test/")
            view = urls[0].callback
            response = asyncio.get_event_loop().run_until_complete(view(request))

            assert "svc" in call_log
            assert isinstance(call_log["svc"], FakeService)

    def test_depends_with_explicit_type(self, rf, di_container):
        """Depends(ExplicitType) resolves the explicit type."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            async def endpoint(request, svc=Depends(FakeService)):
                call_log["svc"] = svc
                return {"ok": True}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request))

            assert isinstance(call_log["svc"], FakeService)

    def test_depends_with_factory(self, rf, di_container):
        """Depends(factory_fn) calls the factory function."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            call_log = {}

            def create_service():
                svc = FakeService()
                return svc

            async def endpoint(request, svc=Depends(create_service)):
                call_log["svc"] = svc
                return {"ok": True}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request))

            assert isinstance(call_log["svc"], FakeService)

    def test_transient_service_new_each_resolve(self, rf, di_container):
        """Transient services get a new instance each time they are resolved."""
        with (
            patch("django_matt.core.router._di_config", True),
            patch("django_matt.di.depends.default_container", di_container),
        ):
            results = []

            async def endpoint(request, svc: FakeTransientService = Depends()):
                results.append(svc.id)
                return {"id": svc.id}

            router = APIRouter()
            view = router._create_view_func(endpoint, None, 200, methods=["GET"])

            request1 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request1))

            request2 = rf.get("/test")
            asyncio.get_event_loop().run_until_complete(view(request2))

            assert len(results) == 2
            assert results[0] != results[1]
