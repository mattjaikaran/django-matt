"""Tests for Slim Mode — ModuleRegistry, SlimConfig, LazyModuleProxy, StartupProfiler."""

import pytest

from django_matt.slim import (
    CORE_MODULES,
    ModuleRegistry,
    SlimConfig,
    get_slim_config,
    is_module_enabled,
    reset_slim_config,
)

# ---------------------------------------------------------------------------
# SlimConfig unit tests
# ---------------------------------------------------------------------------

class TestSlimConfig:
    def test_defaults(self):
        cfg = SlimConfig()
        assert cfg.mode == "full"
        assert cfg.enabled_modules is None
        assert cfg.disabled_modules == []
        assert cfg.lazy_imports is True

    def test_slim_mode_with_modules(self):
        cfg = SlimConfig(mode="slim", enabled_modules=["auth", "billing"])
        assert cfg.mode == "slim"
        assert cfg.enabled_modules == ["auth", "billing"]

    def test_minimal_mode(self):
        cfg = SlimConfig(mode="minimal")
        assert cfg.mode == "minimal"

    def test_disabled_modules(self):
        cfg = SlimConfig(disabled_modules=["graphql", "websockets"])
        assert "graphql" in cfg.disabled_modules

    def test_lazy_imports_false(self):
        cfg = SlimConfig(lazy_imports=False)
        assert cfg.lazy_imports is False


class TestGetSlimConfig:
    def setup_method(self):
        reset_slim_config()

    def teardown_method(self):
        reset_slim_config()

    def test_default_config(self):
        cfg = get_slim_config()
        assert cfg.mode == "full"

    def test_from_settings(self, settings):
        settings.DJANGO_MATT = {
            "SLIM_MODE": {
                "mode": "slim",
                "enabled_modules": ["auth", "cors"],
                "lazy_imports": False,
            }
        }
        reset_slim_config()
        cfg = get_slim_config()
        assert cfg.mode == "slim"
        assert cfg.enabled_modules == ["auth", "cors"]
        assert cfg.lazy_imports is False

    def test_caches_result(self):
        cfg1 = get_slim_config()
        cfg2 = get_slim_config()
        assert cfg1 is cfg2

    def test_reset_clears_cache(self):
        cfg1 = get_slim_config()
        reset_slim_config()
        cfg2 = get_slim_config()
        assert cfg1 is not cfg2


class TestIsModuleEnabled:
    def setup_method(self):
        reset_slim_config()

    def teardown_method(self):
        reset_slim_config()

    def test_core_always_enabled(self, settings):
        settings.DJANGO_MATT = {"SLIM_MODE": {"mode": "minimal"}}
        reset_slim_config()
        for mod in CORE_MODULES:
            assert is_module_enabled(mod), f"Core module {mod!r} should always be enabled"

    def test_full_mode_all_enabled(self):
        assert is_module_enabled("billing")
        assert is_module_enabled("graphql")
        assert is_module_enabled("websockets")

    def test_full_mode_respects_disabled(self, settings):
        settings.DJANGO_MATT = {
            "SLIM_MODE": {"mode": "full", "disabled_modules": ["graphql"]}
        }
        reset_slim_config()
        assert not is_module_enabled("graphql")
        assert is_module_enabled("billing")

    def test_minimal_mode_auth_only(self, settings):
        settings.DJANGO_MATT = {"SLIM_MODE": {"mode": "minimal"}}
        reset_slim_config()
        assert is_module_enabled("auth")
        assert not is_module_enabled("billing")
        assert not is_module_enabled("graphql")

    def test_slim_mode_with_enabled_list(self, settings):
        settings.DJANGO_MATT = {
            "SLIM_MODE": {
                "mode": "slim",
                "enabled_modules": ["auth", "billing"],
            }
        }
        reset_slim_config()
        assert is_module_enabled("auth")
        assert is_module_enabled("billing")
        assert not is_module_enabled("graphql")

    def test_slim_mode_disabled_overrides_enabled(self, settings):
        settings.DJANGO_MATT = {
            "SLIM_MODE": {
                "mode": "slim",
                "enabled_modules": ["auth", "billing"],
                "disabled_modules": ["billing"],
            }
        }
        reset_slim_config()
        assert is_module_enabled("auth")
        assert not is_module_enabled("billing")


# ---------------------------------------------------------------------------
# ModuleRegistry unit tests
# ---------------------------------------------------------------------------

class TestModuleRegistry:
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
        for mod in CORE_MODULES:
            assert reg.is_active(mod), f"Core module {mod!r} should be active"
        # auth is auto-activated in minimal mode
        assert reg.is_active("auth")
        assert not reg.is_active("cors")
        assert not reg.is_active("observability")
        assert not reg.is_active("billing")

    def test_slim_mode_core_plus_auth(self):
        reg = ModuleRegistry(mode="slim")
        assert reg.is_active("auth")
        for mod in CORE_MODULES:
            assert reg.is_active(mod)
        assert not reg.is_active("billing")
        assert not reg.is_active("graphql")

    def test_slim_mode_activate_modules(self):
        reg = ModuleRegistry(mode="slim")
        reg.activate("billing", "cors")
        assert reg.is_active("billing")
        assert reg.is_active("cors")
        assert not reg.is_active("graphql")

    def test_activate_single(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        assert reg.is_active("cors")

    def test_activate_multiple(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors", "timing")
        assert reg.is_active("cors")
        assert reg.is_active("timing")
        assert not reg.is_active("billing")

    def test_deactivate(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        assert reg.is_active("cors")
        reg.deactivate("cors")
        assert not reg.is_active("cors")

    def test_deactivate_core_raises(self):
        reg = ModuleRegistry(mode="minimal")
        with pytest.raises(ValueError, match="Cannot deactivate core module"):
            reg.deactivate("core")

    def test_active_modules_property_minimal(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        mods = reg.active_modules
        assert isinstance(mods, frozenset)
        assert "cors" in mods
        assert "core" in mods
        assert "auth" in mods  # auto-activated in minimal
        assert "billing" not in mods

    def test_active_modules_property_full(self):
        reg = ModuleRegistry(mode="full")
        mods = reg.active_modules
        assert "auth" in mods
        assert "cors" in mods

    def test_get_active_middleware_minimal(self):
        reg = ModuleRegistry(mode="minimal")
        middleware = reg.get_active_middleware()
        # auth is auto-activated, so JWT middleware should be present
        assert any("JWTAuthentication" in m for m in middleware)

    def test_get_active_middleware_with_cors(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        middleware = reg.get_active_middleware()
        assert any("CORSMiddleware" in m for m in middleware)

    def test_get_active_middleware_full(self):
        reg = ModuleRegistry(mode="full")
        middleware = reg.get_active_middleware()
        assert len(middleware) > 0
        assert any("CORSMiddleware" in m for m in middleware)
        assert any("SecurityHeadersMiddleware" in m for m in middleware)

    def test_freeze(self):
        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors")
        reg.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            reg.activate("billing")
        with pytest.raises(RuntimeError, match="frozen"):
            reg.deactivate("cors")

    def test_repr(self):
        reg = ModuleRegistry(mode="minimal")
        r = repr(reg)
        assert "minimal" in r
        assert "ModuleRegistry" in r

    def test_auto_mode_no_settings(self):
        reg = ModuleRegistry(mode="auto")
        assert reg.mode == "auto"
        assert reg.is_active("core")


class TestModuleRegistryAutoDetection:
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
# LazyModuleProxy tests
# ---------------------------------------------------------------------------

class TestLazyModuleProxy:
    def test_deferred_import(self):
        from django_matt.loader import LazyModuleProxy
        proxy = LazyModuleProxy("json")
        assert not proxy._is_loaded
        # Access triggers import
        result = proxy.dumps({"a": 1})
        assert proxy._is_loaded
        assert '"a"' in result

    def test_repr_deferred(self):
        from django_matt.loader import LazyModuleProxy
        proxy = LazyModuleProxy("json")
        assert "deferred" in repr(proxy)

    def test_repr_loaded(self):
        from django_matt.loader import LazyModuleProxy
        proxy = LazyModuleProxy("json")
        proxy._load()
        assert "loaded" in repr(proxy)

    def test_thread_safety(self):
        import threading
        from django_matt.loader import LazyModuleProxy

        proxy = LazyModuleProxy("json")
        results = []
        errors = []

        def access():
            try:
                result = proxy.dumps([1, 2, 3])
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r == "[1, 2, 3]" for r in results)

    def test_invalid_module_raises(self):
        from django_matt.loader import LazyModuleProxy
        proxy = LazyModuleProxy("nonexistent_module_xyz")
        with pytest.raises(ModuleNotFoundError):
            proxy.some_attr


class TestLazyImport:
    def test_returns_proxy(self):
        from django_matt.loader import lazy_import
        proxy = lazy_import("json")
        assert not proxy._is_loaded
        assert proxy.dumps({"x": 1}) == '{"x": 1}'
        assert proxy._is_loaded


# ---------------------------------------------------------------------------
# DeferredLoader tests
# ---------------------------------------------------------------------------

class TestDeferredLoader:
    def setup_method(self):
        reset_slim_config()

    def teardown_method(self):
        reset_slim_config()

    def test_get_light_module(self):
        from django_matt.loader import DeferredLoader
        loader = DeferredLoader()
        mod = loader.get("core")
        # Light modules are eagerly loaded (real module, not proxy)
        assert mod is not None
        assert not hasattr(mod, "_is_loaded")  # it's a real module

    def test_get_heavy_module_returns_proxy(self):
        from django_matt.loader import DeferredLoader, LazyModuleProxy
        loader = DeferredLoader()
        proxy = loader.get("billing")
        assert isinstance(proxy, LazyModuleProxy)
        assert not proxy._is_loaded

    def test_get_disabled_module_returns_none(self, settings):
        from django_matt.loader import DeferredLoader
        settings.DJANGO_MATT = {
            "SLIM_MODE": {"mode": "full", "disabled_modules": ["billing"]}
        }
        reset_slim_config()
        loader = DeferredLoader()
        result = loader.get("billing")
        assert result is None

    def test_preload(self):
        from django_matt.loader import DeferredLoader
        loader = DeferredLoader()
        loader.get("billing")  # create proxy
        assert not loader.is_loaded("billing")
        loader.preload("billing")
        assert loader.is_loaded("billing")

    def test_deferred_modules_list(self):
        from django_matt.loader import DeferredLoader
        loader = DeferredLoader()
        loader.get("billing")
        loader.get("analytics")
        assert "billing" in loader.deferred_modules
        assert "analytics" in loader.deferred_modules

    def test_repr(self):
        from django_matt.loader import DeferredLoader
        loader = DeferredLoader()
        r = repr(loader)
        assert "DeferredLoader" in r


# ---------------------------------------------------------------------------
# MattAPI integration tests
# ---------------------------------------------------------------------------

class TestMattAPISlimMode:
    def test_default_mode_is_full(self):
        from django_matt.api import MattAPI
        api = MattAPI()
        assert api.mode == "full"

    def test_minimal_mode(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        assert api.mode == "minimal"

    def test_slim_mode(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="slim")
        assert api.mode == "slim"
        assert "auth" in api.modules

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
        result = api.activate("cors")
        assert result is api

    def test_activate_modules(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        api.activate("cors")
        assert "cors" in api.modules

    def test_deactivate_modules(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        api.activate("cors")
        api.deactivate("cors")
        assert "cors" not in api.modules

    def test_auth_param_activates_auth_module(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal", auth="jwt")
        assert "auth" in api.modules

    def test_registry_property(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        assert isinstance(api.registry, ModuleRegistry)

    def test_slim_mode_activate_specific_modules(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="slim")
        api.activate("billing", "cors")
        assert "billing" in api.modules
        assert "cors" in api.modules
        assert "graphql" not in api.modules

    def test_full_mode_backwards_compatible(self):
        from django_matt.api import MattAPI
        api = MattAPI()
        assert api.mode == "full"
        assert api.registry.is_active("billing")
        assert api.registry.is_active("graphql")
        assert api.registry.is_active("websockets")


class TestMattAPIURLsSlimMode:
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

    def test_slim_mode_excludes_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="slim", health_url="/health")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" not in names

    def test_slim_mode_with_observability_includes_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="slim", health_url="/health")
        api.activate("observability")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" in names

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
        from django_matt.api import MattAPI
        api = MattAPI(mode="minimal")
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "swagger-ui" in names
        assert "redoc" in names
        assert "openapi-schema" in names

    def test_health_url_none_no_health(self):
        from django_matt.api import MattAPI
        api = MattAPI(mode="full", health_url=None)
        urls = api.get_urls()
        names = [u.name for u in urls if hasattr(u, "name")]
        assert "health-check" not in names


# ---------------------------------------------------------------------------
# StartupProfiler tests
# ---------------------------------------------------------------------------

class TestStartupProfiler:
    def test_profile_imports_returns_dict(self):
        from django_matt.startup import profile_imports
        results = profile_imports()
        assert isinstance(results, dict)
        assert len(results) > 0
        # core should be importable
        assert "core" in results
        assert results["core"] >= 0

    def test_context_manager(self):
        from django_matt.startup import StartupProfiler
        with StartupProfiler() as profiler:
            pass
        assert profiler.total_ms >= 0
        assert len(profiler.results) > 0

    def test_summary(self):
        from django_matt.startup import StartupProfiler
        with StartupProfiler() as profiler:
            pass
        summary = profiler.summary()
        assert "total_ms" in summary
        assert "module_count" in summary
        assert "failed_count" in summary
        assert "slowest_5" in summary
        assert summary["module_count"] > 0

    def test_get_profile_results(self):
        from django_matt.startup import StartupProfiler, get_profile_results
        with StartupProfiler():
            pass
        results = get_profile_results()
        assert results is not None
        assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# DjangoMattMiddleware integration
# ---------------------------------------------------------------------------

class TestDjangoMattMiddlewareSlimMode:
    def test_middleware_chain_filters_by_registry(self, settings):
        from django_matt.middleware.chaining import DjangoMattMiddleware

        reg = ModuleRegistry(mode="minimal")
        reg.activate("cors", "timing")

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "production",
            "SLIM_REGISTRY": reg,
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        assert mw._inner_chain is not None

    def test_middleware_chain_keeps_error_middleware_when_no_active_modules(self, settings):
        """ErrorEnhancementMiddleware is always-on — even in minimal slim mode.

        Error visibility is a core framework guarantee: users should never see
        Django's bare ``Server Error (500)`` page because of slim-mode filtering.
        """
        from django_matt.errors.middleware import ErrorEnhancementMiddleware
        from django_matt.middleware.chaining import DjangoMattMiddleware

        reg = ModuleRegistry(mode="minimal")
        # deactivate auth so all slim-filterable middleware modules are inactive
        reg.deactivate("auth")

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "production",
            "SLIM_REGISTRY": reg,
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        # The chain is non-None because ErrorEnhancementMiddleware always survives.
        assert mw._inner_chain is not None
        assert isinstance(mw._inner_chain, ErrorEnhancementMiddleware)

    def test_middleware_chain_no_registry_loads_all(self, settings):
        from django_matt.middleware.chaining import DjangoMattMiddleware

        settings.DJANGO_MATT = {
            "MIDDLEWARE_STACK": "development",
        }

        def dummy_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = DjangoMattMiddleware(dummy_response)
        assert mw._inner_chain is not None
