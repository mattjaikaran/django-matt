"""Tests for Slim Mode — ModuleRegistry and MattAPI mode parameter."""

import pytest

from django_matt.slim import CORE_MODULES, ModuleRegistry

# ---------------------------------------------------------------------------
# ModuleRegistry unit tests
# ---------------------------------------------------------------------------

class TestModuleRegistry:
    """Tests for the ModuleRegistry class."""

    def test_default_mode_is_full(self):
        reg = ModuleRegistry()
        assert reg.mode == "full"

    def test_full_mode_all_active(self):
        reg = ModuleRegistry(mode="full")
        assert reg.is_active("auth")
        assert reg.is_active("cors")
        assert reg.is_active("observability")
        assert reg.is_active("anything_at_all")

    def test_minimal_mode_core_only(self):
        reg = ModuleRegistry(mode="minimal")
        # Core modules are always active
        for mod in CORE_MODULES:
            assert reg.is_active(mod), f"Core module {mod!r} should be active"
        # Non-core modules are inactive
        assert not reg.is_active("auth")
        assert not reg.is_active("cors")
        assert not reg.is_active("observability")
        assert not reg.is_active("billing")

    def test_activate_single(self):
        reg = ModuleRegistry(mode="minimal")
        assert not reg.is_active("auth")
        reg.activate("auth")
        assert reg.is_active("auth")

    def test_activate_multiple(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("auth", "cors", "timing")
        assert reg.is_active("auth")
        assert reg.is_active("cors")
        assert reg.is_active("timing")
        assert not reg.is_active("billing")

    def test_deactivate(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("auth")
        assert reg.is_active("auth")
        reg.deactivate("auth")
        assert not reg.is_active("auth")

    def test_deactivate_core_raises(self):
        reg = ModuleRegistry(mode="minimal")
        with pytest.raises(ValueError, match="Cannot deactivate core module"):
            reg.deactivate("core")

    def test_active_modules_property_minimal(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("auth", "cors")
        mods = reg.active_modules
        assert isinstance(mods, frozenset)
        assert "auth" in mods
        assert "cors" in mods
        assert "core" in mods  # core always present
        assert "billing" not in mods

    def test_active_modules_property_full(self):
        reg = ModuleRegistry(mode="full")
        mods = reg.active_modules
        # Full mode includes at least all MODULE_MIDDLEWARE keys
        assert "auth" in mods
        assert "cors" in mods

    def test_get_active_middleware_minimal(self):
        reg = ModuleRegistry(mode="minimal")
        # No middleware modules active
        middleware = reg.get_active_middleware()
        assert middleware == []

    def test_get_active_middleware_with_cors(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        middleware = reg.get_active_middleware()
        assert any("CORSMiddleware" in m for m in middleware)

    def test_get_active_middleware_full(self):
        reg = ModuleRegistry(mode="full")
        middleware = reg.get_active_middleware()
        # Full mode includes everything
        assert len(middleware) > 0
        assert any("CORSMiddleware" in m for m in middleware)
        assert any("SecurityHeadersMiddleware" in m for m in middleware)

    def test_freeze(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("auth")
        reg.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            reg.activate("cors")
        with pytest.raises(RuntimeError, match="frozen"):
            reg.deactivate("auth")

    def test_repr(self):
        reg = ModuleRegistry(mode="minimal")
        r = repr(reg)
        assert "minimal" in r
        assert "ModuleRegistry" in r

    def test_auto_mode_no_settings(self):
        """Auto mode without DJANGO_MATT settings should have only core modules."""
        # settings.DJANGO_MATT is likely {} or not set in test env
        reg = ModuleRegistry(mode="auto")
        assert reg.mode == "auto"
        # Core modules still active
        assert reg.is_active("core")


class TestModuleRegistryAutoDetection:
    """Test auto-detection from Django settings."""

    def test_auto_detects_middleware_stack_production(self, settings):
        settings.DJANGO_MATT = {"MIDDLEWARE_STACK": "production"}
        reg = ModuleRegistry(mode="auto")
        assert reg.is_active("security")
        assert reg.is_active("cors")
        assert reg.is_active("request_id")
        assert reg.is_active("logging")
        assert reg.is_active("timing")

    def test_auto_detects_middleware_stack_development(self, settings):
        settings.DJANGO_MATT = {"MIDDLEWARE_STACK": "development"}
        reg = ModuleRegistry(mode="auto")
        assert reg.is_active("cors")
        assert reg.is_active("request_id")
        assert not reg.is_active("security")

    def test_auto_detects_auth(self, settings):
        settings.DJANGO_MATT = {"AUTH_BACKEND": "jwt"}
        reg = ModuleRegistry(mode="auto")
        assert reg.is_active("auth")

    def test_auto_detects_cors(self, settings):
        settings.DJANGO_MATT = {"CORS": {"ENABLED": True}}
        reg = ModuleRegistry(mode="auto")
        assert reg.is_active("cors")

    def test_auto_detects_di(self, settings):
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": True}
        reg = ModuleRegistry(mode="auto")
        assert reg.is_active("di")

    def test_auto_false_value_not_detected(self, settings):
        settings.DJANGO_MATT = {"DI_AUTO_WIRE": False}
        reg = ModuleRegistry(mode="auto")
        assert not reg.is_active("di")


# ---------------------------------------------------------------------------
# MattAPI integration tests
# ---------------------------------------------------------------------------

class TestMattAPISlimMode:
    """Test MattAPI integration with slim mode."""

    def test_default_mode_is_full(self):
        from django_matt.api import MattAPI
        api = MattAPI()
        assert api.mode == "full"

    def test_minimal_mode(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        assert api.mode == "minimal"

    def test_auto_mode(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="auto")
        assert api.mode == "auto"

    def test_modules_property(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        assert isinstance(api.modules, frozenset)
        assert "core" in api.modules

    def test_activate_returns_self(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        result = api.activate("auth", "cors")
        assert result is api

    def test_activate_modules(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        api.activate("auth")
        assert "auth" in api.modules

    def test_deactivate_modules(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        api.activate("auth")
        api.deactivate("auth")
        assert "auth" not in api.modules

    def test_auth_param_activates_auth_module(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal", auth="jwt")
        assert "auth" in api.modules

    def test_registry_property(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        assert isinstance(api.registry, ModuleRegistry)


class TestMattAPIURLsSlimMode:
    """Test that slim mode controls which URL patterns are registered."""

    def test_full_mode_includes_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="full", health_url="/health")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" in names

    def test_minimal_mode_excludes_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal", health_url="/health")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" not in names

    def test_minimal_mode_with_observability_includes_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal", health_url="/health")
        api.activate("observability")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" in names

    def test_full_mode_includes_docs(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="full")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "swagger-ui" in names
        assert "redoc" in names
        assert "openapi-schema" in names

    def test_minimal_mode_includes_docs(self):
        """Core modules (openapi, docs, redoc) are always active in minimal mode."""
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        # openapi/docs/redoc are core modules, should still be present
        assert "swagger-ui" in names
        assert "redoc" in names
        assert "openapi-schema" in names

    def test_health_url_none_no_health(self):
        """health_url=None means no health check regardless of mode."""
        from django_matt.api import MattAPI
        api = MattAPI(mode="full", health_url=None)
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" not in names


class TestDjangoMattMiddlewareSlimMode:
    """Test that DjangoMattMiddleware respects SLIM_REGISTRY."""

    def test_middleware_chain_filters_by_registry(self, settings):
        """When SLIM_REGISTRY is set, only active modules get middleware."""
        from django_matt.middleware.chaining import DjangoMattMiddleware

        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors", "timing")  # activate only cors and timing

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "production",
            "SLIM_REGISTRY": reg,
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        # The inner chain should exist (cors + timing are active)
        assert mw._inner_chain is not None

    def test_middleware_chain_none_when_no_active_modules(self, settings):
        """When no middleware modules are active, inner chain should be None."""
        from django_matt.middleware.chaining import DjangoMattMiddleware

        reg = ModuleRegistry(mode="minimal")
        # Don't activate any middleware modules

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "production",
            "SLIM_REGISTRY": reg,
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        assert mw._inner_chain is None

    def test_middleware_chain_no_registry_loads_all(self, settings):
        """Without SLIM_REGISTRY, all middleware loads (backward-compat)."""
        from django_matt.middleware.chaining import DjangoMattMiddleware

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "development",
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        assert mw._inner_chain is not None
