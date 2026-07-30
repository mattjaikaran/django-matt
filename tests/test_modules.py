from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from django_matt.modules.base import MattModule
from django_matt.modules.decorators import module, optional_module, requires_module
from django_matt.modules.hooks import before_module_load, on_all_loaded, on_module_loaded
from django_matt.modules.registry import (
    CircularDependencyError,
    MissingDependencyError,
    ModuleError,
    ModuleNotFoundError,
    ModuleRegistry,
    get_registry,
    reset_registry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Module base class
# ---------------------------------------------------------------------------


class CoreModule(MattModule):
    name = "core"
    version = "1.0.0"


class AuthModule(MattModule):
    name = "auth"
    version = "2.0.0"
    dependencies = ["core"]


class BillingModule(MattModule):
    name = "billing"
    version = "1.5.0"
    dependencies = ["auth"]


class TestMattModuleBase:
    def test_auto_name_from_class(self):
        class MyFeatureModule(MattModule):
            pass

        mod = MyFeatureModule()
        assert mod.name == "myfeature"

    def test_explicit_name(self):
        mod = CoreModule()
        assert mod.name == "core"
        assert mod.version == "1.0.0"

    def test_repr(self):
        mod = CoreModule()
        assert "core" in repr(mod)
        assert "1.0.0" in repr(mod)

    def test_get_urls_default_empty(self):
        mod = CoreModule()
        assert mod.get_urls() == []

    def test_get_middleware_default_empty(self):
        mod = CoreModule()
        assert mod.get_middleware() == []

    def test_get_checks_default_empty(self):
        mod = CoreModule()
        assert mod.get_checks() == []

    def test_validate_config_no_schema(self):
        mod = CoreModule()
        assert mod.validate_config({"key": "value"}) is None

    def test_validate_config_with_schema(self):
        class MyConfig(BaseModel):
            api_key: str
            timeout: int = 30

        class ConfiguredModule(MattModule):
            name = "configured"
            config_schema = MyConfig

        mod = ConfiguredModule()
        result = mod.validate_config({"api_key": "abc123"})
        assert result is not None
        assert result.api_key == "abc123"
        assert result.timeout == 30

    def test_validate_config_invalid(self):
        class MyConfig(BaseModel):
            api_key: str

        class ConfiguredModule(MattModule):
            name = "configured"
            config_schema = MyConfig

        mod = ConfiguredModule()
        with pytest.raises(ValidationError):
            mod.validate_config({})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestModuleRegistry:
    def test_register_instance(self):
        registry = ModuleRegistry()
        mod = CoreModule()
        result = registry.register(mod)
        assert result is mod
        assert registry.is_registered("core")

    def test_register_class(self):
        registry = ModuleRegistry()
        mod = registry.register(CoreModule)
        assert isinstance(mod, CoreModule)
        assert registry.is_registered("core")

    def test_register_duplicate_raises(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        with pytest.raises(ModuleError, match="already registered"):
            registry.register(CoreModule())

    def test_register_bad_type(self):
        registry = ModuleRegistry()
        with pytest.raises(TypeError):
            registry.register("not a module")  # type: ignore[arg-type]

    def test_resolve_simple_chain(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        registry.register(AuthModule())
        registry.register(BillingModule())

        order = registry.resolve_dependencies()
        assert order.index("core") < order.index("auth")
        assert order.index("auth") < order.index("billing")

    def test_resolve_missing_dependency(self):
        registry = ModuleRegistry()
        registry.register(AuthModule())  # depends on "core" which isn't registered

        with pytest.raises(MissingDependencyError, match="core"):
            registry.resolve_dependencies()

    def test_resolve_circular_dependency(self):
        class A(MattModule):
            name = "a"
            dependencies = ["b"]

        class B(MattModule):
            name = "b"
            dependencies = ["a"]

        registry = ModuleRegistry()
        registry.register(A())
        registry.register(B())

        with pytest.raises(CircularDependencyError):
            registry.resolve_dependencies()

    @pytest.mark.asyncio
    async def test_load_all(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        registry.register(AuthModule())

        await registry.load_all()

        assert registry.is_loaded("core")
        assert registry.is_loaded("auth")

    @pytest.mark.asyncio
    async def test_load_order(self):
        load_order: list[str] = []

        class TrackedCore(MattModule):
            name = "core"

            async def on_ready(self):
                load_order.append("core")

        class TrackedAuth(MattModule):
            name = "auth"
            dependencies = ["core"]

            async def on_ready(self):
                load_order.append("auth")

        registry = ModuleRegistry()
        registry.register(TrackedCore())
        registry.register(TrackedAuth())
        await registry.load_all()

        assert load_order == ["core", "auth"]

    @pytest.mark.asyncio
    async def test_unload_all(self):
        shutdown_order: list[str] = []

        class TrackedCore(MattModule):
            name = "core"

            async def on_shutdown(self):
                shutdown_order.append("core")

        class TrackedAuth(MattModule):
            name = "auth"
            dependencies = ["core"]

            async def on_shutdown(self):
                shutdown_order.append("auth")

        registry = ModuleRegistry()
        registry.register(TrackedCore())
        registry.register(TrackedAuth())
        await registry.load_all()
        await registry.unload_all()

        # Shutdown in reverse order
        assert shutdown_order == ["auth", "core"]
        assert not registry.is_loaded("core")
        assert not registry.is_loaded("auth")

    def test_get_loaded(self):
        registry = ModuleRegistry()
        mod = CoreModule()
        registry.register(mod)

        with pytest.raises(ModuleNotFoundError):
            registry.get("core")

    @pytest.mark.asyncio
    async def test_get_after_load(self):
        registry = ModuleRegistry()
        mod = CoreModule()
        registry.register(mod)
        await registry.load_all()

        result = registry.get("core")
        assert result is mod

    @pytest.mark.asyncio
    async def test_list_loaded(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        registry.register(AuthModule())
        await registry.load_all()

        loaded = registry.list_loaded()
        names = [m.name for m in loaded]
        assert "core" in names
        assert "auth" in names

    def test_list_registered(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        registry.register(AuthModule())

        registered = registry.list_registered()
        assert len(registered) == 2

    def test_set_config(self):
        registry = ModuleRegistry()
        registry.set_config("billing", {"api_key": "sk_test"})
        assert registry._configs["billing"] == {"api_key": "sk_test"}

    def test_reset(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        registry.set_config("test", {"key": "val"})
        registry.reset()

        assert len(registry.list_registered()) == 0
        assert len(registry._configs) == 0

    def test_repr(self):
        registry = ModuleRegistry()
        registry.register(CoreModule())
        r = repr(registry)
        assert "registered=1" in r
        assert "loaded=0" in r


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_registry_returns_same_instance(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_reset_registry(self):
        r1 = get_registry()
        reset_registry()
        r2 = get_registry()
        assert r1 is not r2


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


class TestModuleDecorator:
    def test_module_decorator_on_matt_module(self):
        @module(name="my_feature", version="1.0.0", depends=["core"])
        class MyFeature(MattModule):
            async def on_ready(self):
                pass

        assert MyFeature.name == "my_feature"
        assert MyFeature.version == "1.0.0"
        assert MyFeature.dependencies == ["core"]

    def test_module_decorator_on_plain_class(self):
        @module(name="simple", depends=["auth"])
        class SimplePlugin:
            pass

        assert issubclass(SimplePlugin, MattModule)
        assert SimplePlugin.name == "simple"
        assert SimplePlugin.dependencies == ["auth"]


class TestRequiresModule:
    def test_requires_module_not_loaded(self):
        @requires_module("billing")
        def charge():
            return "charged"

        with pytest.raises(RuntimeError, match="billing"):
            charge()

    @pytest.mark.asyncio
    async def test_requires_module_not_loaded_async(self):
        @requires_module("billing")
        async def charge():
            return "charged"

        with pytest.raises(RuntimeError, match="billing"):
            await charge()

    @pytest.mark.asyncio
    async def test_requires_module_loaded(self):
        registry = get_registry()
        registry.register(CoreModule())
        registry.register(AuthModule())
        registry.register(BillingModule())
        await registry.load_all()

        @requires_module("billing")
        def charge():
            return "charged"

        assert charge() == "charged"


class TestOptionalModule:
    def test_optional_module_not_loaded(self):
        @optional_module("analytics", default={"events": []})
        def track():
            return "tracked"

        result = track()
        assert result == {"events": []}

    def test_optional_module_default_none(self):
        @optional_module("analytics")
        def track():
            return "tracked"

        assert track() is None

    @pytest.mark.asyncio
    async def test_optional_module_not_loaded_async(self):
        @optional_module("analytics", default="skipped")
        async def track():
            return "tracked"

        result = await track()
        assert result == "skipped"

    @pytest.mark.asyncio
    async def test_optional_module_loaded(self):
        class AnalyticsModule(MattModule):
            name = "analytics"

        registry = get_registry()
        registry.register(AnalyticsModule())
        await registry.load_all()

        @optional_module("analytics")
        def track():
            return "tracked"

        assert track() == "tracked"


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class TestHooks:
    @pytest.mark.asyncio
    async def test_on_module_loaded_hook(self):
        triggered: list[str] = []

        registry = get_registry()

        @on_module_loaded("core")
        async def handle_core(mod):
            triggered.append(mod.name)

        registry.register(CoreModule())
        await registry.load_all()

        assert triggered == ["core"]

    @pytest.mark.asyncio
    async def test_on_all_loaded_hook(self):
        triggered = []

        registry = get_registry()

        @on_all_loaded
        async def all_done():
            triggered.append("all_done")

        registry.register(CoreModule())
        await registry.load_all()

        assert triggered == ["all_done"]

    @pytest.mark.asyncio
    async def test_before_module_load_hook(self):
        triggered: list[str] = []

        registry = get_registry()

        @before_module_load("auth")
        async def before_auth(mod):
            triggered.append(f"before:{mod.name}")

        registry.register(CoreModule())
        registry.register(AuthModule())
        await registry.load_all()

        assert triggered == ["before:auth"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestModuleCLI:
    def test_modules_list_empty(self, capsys):
        from django_matt.modules.cli import modules_list

        modules_list()
        out = capsys.readouterr().out
        assert "No modules registered" in out

    def test_modules_list_with_modules(self, capsys):
        from django_matt.modules.cli import modules_list

        registry = get_registry()
        registry.register(CoreModule())
        registry.register(AuthModule())

        modules_list()
        out = capsys.readouterr().out
        assert "core" in out
        assert "auth" in out

    def test_modules_info(self, capsys):
        from django_matt.modules.cli import modules_info

        registry = get_registry()
        registry.register(CoreModule())

        modules_info("core")
        out = capsys.readouterr().out
        assert "core" in out
        assert "1.0.0" in out

    def test_modules_info_not_found(self, capsys):
        from django_matt.modules.cli import modules_info

        modules_info("nonexistent")
        out = capsys.readouterr().out
        assert "not found" in out

    def test_modules_check_ok(self, capsys):
        from django_matt.modules.cli import modules_check

        registry = get_registry()
        registry.register(CoreModule())
        registry.register(AuthModule())

        issues = modules_check()
        assert issues == []
        out = capsys.readouterr().out
        assert "All modules OK" in out

    def test_modules_check_missing_dep(self, capsys):
        from django_matt.modules.cli import modules_check

        registry = get_registry()
        registry.register(AuthModule())  # depends on core, not registered

        issues = modules_check()
        assert len(issues) == 1
        assert "core" in issues[0]


# ---------------------------------------------------------------------------
# Complex dependency graphs
# ---------------------------------------------------------------------------


class TestComplexDependencies:
    def test_diamond_dependency(self):
        class A(MattModule):
            name = "a"

        class B(MattModule):
            name = "b"
            dependencies = ["a"]

        class C(MattModule):
            name = "c"
            dependencies = ["a"]

        class D(MattModule):
            name = "d"
            dependencies = ["b", "c"]

        registry = ModuleRegistry()
        registry.register(A())
        registry.register(B())
        registry.register(C())
        registry.register(D())

        order = registry.resolve_dependencies()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    @pytest.mark.asyncio
    async def test_many_modules_load_correctly(self):
        loaded: list[str] = []

        class Base(MattModule):
            name = "base"

            async def on_ready(self):
                loaded.append("base")

        class Mid1(MattModule):
            name = "mid1"
            dependencies = ["base"]

            async def on_ready(self):
                loaded.append("mid1")

        class Mid2(MattModule):
            name = "mid2"
            dependencies = ["base"]

            async def on_ready(self):
                loaded.append("mid2")

        class Top(MattModule):
            name = "top"
            dependencies = ["mid1", "mid2"]

            async def on_ready(self):
                loaded.append("top")

        registry = ModuleRegistry()
        registry.register(Base())
        registry.register(Mid1())
        registry.register(Mid2())
        registry.register(Top())
        await registry.load_all()

        assert loaded[0] == "base"
        assert loaded[-1] == "top"
        assert set(loaded) == {"base", "mid1", "mid2", "top"}

    def test_self_dependency_raises(self):
        class SelfRef(MattModule):
            name = "selfref"
            dependencies = ["selfref"]

        registry = ModuleRegistry()
        registry.register(SelfRef())

        with pytest.raises(CircularDependencyError):
            registry.resolve_dependencies()


# ---------------------------------------------------------------------------
# Config validation during load
# ---------------------------------------------------------------------------


class TestConfigValidation:
    @pytest.mark.asyncio
    async def test_config_validated_on_load(self):
        class MyConfig(BaseModel):
            api_key: str

        class ConfigMod(MattModule):
            name = "configmod"
            config_namespace = "configmod"
            config_schema = MyConfig

        registry = ModuleRegistry()
        registry.register(ConfigMod())
        registry.set_config("configmod", {"api_key": "test123"})

        await registry.load_all()
        assert registry.is_loaded("configmod")

    @pytest.mark.asyncio
    async def test_invalid_config_raises_on_load(self):
        class MyConfig(BaseModel):
            api_key: str

        class ConfigMod(MattModule):
            name = "configmod"
            config_namespace = "configmod"
            config_schema = MyConfig

        registry = ModuleRegistry()
        registry.register(ConfigMod())
        registry.set_config("configmod", {})

        with pytest.raises(ValidationError):
            await registry.load_all()
