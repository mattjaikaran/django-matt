"""Tests for django_matt.plugins — discovery, hooks, scaffolding, testing utilities."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from django_matt.plugins.base import CheckMessage, MattPlugin
from django_matt.plugins.config import PluginConfig
from django_matt.plugins.hooks import (
    BEFORE_REQUEST,
    clear_hooks,
    fire_hook,
    fire_hook_sync,
    get_hooks,
    hook,
    list_hook_events,
)
from django_matt.plugins.loader import PluginLoader, _version_compatible
from django_matt.plugins.registry import (
    PluginConflictError,
    PluginDependencyError,
    PluginError,
    PluginNotFoundError,
    PluginRegistry,
    PluginStatus,
    get_plugin_registry,
    reset_plugin_registry,
)
from django_matt.plugins.scaffold import PluginScaffolder
from django_matt.plugins.testing import (
    PluginTestCase,
    create_test_api,
    mock_plugin,
)

if TYPE_CHECKING:
    from django_matt.api import MattAPI


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class SamplePlugin(MattPlugin):
    name = "sample"
    version = "1.0.0"
    description = "A sample plugin"
    author = "Test"
    django_matt_version = "0.1.0"
    dependencies: list[str] = []
    settings_prefix = "MATT_SAMPLE"

    def setup(self, api: MattAPI) -> None:
        pass

    def get_settings_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "max_items": {"type": "integer", "default": 100},
            },
            "required": ["enabled"],
        }


class DependentPlugin(MattPlugin):
    name = "dependent"
    version = "0.1.0"
    dependencies = ["sample"]

    def setup(self, api: MattAPI) -> None:
        pass


class AnotherPlugin(MattPlugin):
    name = "another"
    version = "0.2.0"
    dependencies: list[str] = []

    def setup(self, api: MattAPI) -> None:
        pass


class CircularA(MattPlugin):
    name = "circular_a"
    dependencies = ["circular_b"]

    def setup(self, api: MattAPI) -> None:
        pass


class CircularB(MattPlugin):
    name = "circular_b"
    dependencies = ["circular_a"]

    def setup(self, api: MattAPI) -> None:
        pass


class FailingPlugin(MattPlugin):
    name = "failing"

    def setup(self, api: MattAPI) -> None:
        raise RuntimeError("Setup failed")


class CheckPlugin(MattPlugin):
    name = "checker"

    def setup(self, api: MattAPI) -> None:
        pass

    def check(self) -> list[CheckMessage]:
        return [
            CheckMessage("warning", "Something minor"),
            CheckMessage("error", "Something serious"),
        ]


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset plugin registry and hooks between tests."""
    reset_plugin_registry()
    clear_hooks()
    yield
    reset_plugin_registry()
    clear_hooks()


# ---------------------------------------------------------------------------
# Base class tests
# ---------------------------------------------------------------------------


class TestMattPluginBase:
    def test_auto_name_from_class(self):
        class MyCustomPlugin(MattPlugin):
            def setup(self, api: MattAPI) -> None:
                pass

        p = MyCustomPlugin()
        assert p.name == "mycustom"

    def test_explicit_name(self):
        p = SamplePlugin()
        assert p.name == "sample"

    def test_version(self):
        p = SamplePlugin()
        assert p.version == "1.0.0"

    def test_repr(self):
        p = SamplePlugin()
        assert "sample" in repr(p)
        assert "1.0.0" in repr(p)

    def test_default_get_urls(self):
        p = SamplePlugin()
        assert p.get_urls() == []

    def test_default_get_middleware(self):
        p = SamplePlugin()
        assert p.get_middleware() == []

    def test_default_check(self):
        p = AnotherPlugin()
        assert p.check() == []

    def test_on_startup_noop(self):
        p = SamplePlugin()
        p.on_startup()  # should not raise

    def test_on_shutdown_noop(self):
        p = SamplePlugin()
        p.on_shutdown()  # should not raise


class TestCheckMessage:
    def test_creation(self):
        msg = CheckMessage("error", "broken")
        assert msg.level == "error"
        assert msg.msg == "broken"

    def test_is_serious(self):
        assert CheckMessage("error", "x").is_serious()
        assert CheckMessage("critical", "x").is_serious()
        assert not CheckMessage("warning", "x").is_serious()
        assert not CheckMessage("info", "x").is_serious()

    def test_equality(self):
        a = CheckMessage("error", "broken")
        b = CheckMessage("error", "broken")
        assert a == b

    def test_repr(self):
        msg = CheckMessage("warning", "test")
        assert "warning" in repr(msg)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    def test_register_instance(self):
        registry = PluginRegistry()
        plugin = SamplePlugin()
        result = registry.register(plugin)
        assert result is plugin
        assert registry.is_registered("sample")

    def test_register_class(self):
        registry = PluginRegistry()
        result = registry.register(SamplePlugin)
        assert isinstance(result, SamplePlugin)
        assert registry.is_registered("sample")

    def test_register_duplicate_raises(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        with pytest.raises(PluginError, match="already registered"):
            registry.register(SamplePlugin)

    def test_register_invalid_type(self):
        registry = PluginRegistry()
        with pytest.raises(TypeError):
            registry.register("not a plugin")  # type: ignore[arg-type]

    def test_unregister(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.unregister("sample")
        assert not registry.is_registered("sample")

    def test_unregister_not_found(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.unregister("nonexistent")

    def test_get_plugin(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        plugin = registry.get_plugin("sample")
        assert plugin.name == "sample"

    def test_get_plugin_not_found(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.get_plugin("missing")

    def test_list_plugins(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.register(AnotherPlugin)
        plugins = registry.list_plugins()
        assert len(plugins) == 2

    def test_status_tracking(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        assert registry.get_status("sample") == PluginStatus.REGISTERED
        assert not registry.is_loaded("sample")

    def test_enable_disable(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.disable("sample")
        assert registry.get_status("sample") == PluginStatus.DISABLED
        registry.enable("sample")
        assert registry.get_status("sample") == PluginStatus.REGISTERED

    def test_enable_not_found(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.enable("missing")

    def test_disable_not_found(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.disable("missing")

    def test_set_error(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.set_error("sample", "something broke")
        assert registry.get_status("sample") == PluginStatus.FAILED
        assert registry.get_error("sample") == "something broke"

    def test_reset(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.reset()
        assert not registry.is_registered("sample")
        assert registry.list_plugins() == []

    def test_repr(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        r = repr(registry)
        assert "registered=1" in r
        assert "loaded=0" in r


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------


class TestDependencyResolution:
    def test_simple_order(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.register(DependentPlugin)
        order = registry.resolve_dependencies()
        assert order.index("sample") < order.index("dependent")

    def test_no_dependencies(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.register(AnotherPlugin)
        order = registry.resolve_dependencies()
        assert len(order) == 2

    def test_missing_dependency(self):
        registry = PluginRegistry()
        registry.register(DependentPlugin)
        with pytest.raises(PluginDependencyError, match="sample"):
            registry.resolve_dependencies()

    def test_circular_dependency(self):
        registry = PluginRegistry()
        registry.register(CircularA)
        registry.register(CircularB)
        with pytest.raises(PluginDependencyError, match="Circular"):
            registry.resolve_dependencies()

    def test_disabled_excluded_from_resolution(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.register(AnotherPlugin)
        registry.disable("another")
        order = registry.resolve_dependencies()
        assert "another" not in order
        assert "sample" in order


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflictDetection:
    def test_no_conflicts(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        conflicts = registry.detect_conflicts()
        assert conflicts == []

    def test_url_conflict_detected(self):
        class PluginA(MattPlugin):
            name = "plugin_a"

            def setup(self, api: MattAPI) -> None:
                pass

            def get_urls(self) -> list:
                return [MagicMock(pattern="/api/shared/")]

        class PluginB(MattPlugin):
            name = "plugin_b"

            def setup(self, api: MattAPI) -> None:
                pass

            def get_urls(self) -> list:
                return [MagicMock(pattern="/api/shared/")]

        registry = PluginRegistry()
        registry.register(PluginA)
        registry.register(PluginB)
        conflicts = registry.detect_conflicts()
        assert len(conflicts) == 1
        assert "plugin_a" in conflicts[0]
        assert "plugin_b" in conflicts[0]


# ---------------------------------------------------------------------------
# Plugin loading
# ---------------------------------------------------------------------------


class TestPluginLoading:
    def test_load_all(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        loader = PluginLoader(registry)
        api = MagicMock()
        loaded = loader.load_all(api)
        assert len(loaded) == 1
        assert registry.is_loaded("sample")

    def test_load_order_respects_dependencies(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.register(DependentPlugin)
        loader = PluginLoader(registry)
        api = MagicMock()
        loaded = loader.load_all(api)
        names = [p.name for p in loaded]
        assert names.index("sample") < names.index("dependent")

    def test_failing_plugin_marked_failed(self):
        registry = PluginRegistry()
        registry.register(FailingPlugin)
        loader = PluginLoader(registry)
        api = MagicMock()
        loaded = loader.load_all(api)
        assert len(loaded) == 0
        assert registry.get_status("failing") == PluginStatus.FAILED
        assert registry.get_error("failing") is not None

    def test_disabled_plugin_skipped(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        registry.disable("sample")
        loader = PluginLoader(registry)
        api = MagicMock()
        loaded = loader.load_all(api)
        assert len(loaded) == 0

    def test_unload_all(self):
        registry = PluginRegistry()
        registry.register(SamplePlugin)
        loader = PluginLoader(registry)
        api = MagicMock()
        loader.load_all(api)
        assert registry.is_loaded("sample")
        loader.unload_all()
        assert not registry.is_loaded("sample")

    def test_dependency_not_loaded_fails_dependent(self):
        registry = PluginRegistry()
        registry.register(FailingPlugin)

        class NeedsFailing(MattPlugin):
            name = "needs_failing"
            dependencies = ["failing"]

            def setup(self, api: MattAPI) -> None:
                pass

        registry.register(NeedsFailing)
        loader = PluginLoader(registry)
        api = MagicMock()
        loaded = loader.load_all(api)
        loaded_names = [p.name for p in loaded]
        assert "needs_failing" not in loaded_names


# ---------------------------------------------------------------------------
# Version compatibility
# ---------------------------------------------------------------------------


class TestVersionCompatibility:
    def test_compatible(self):
        assert _version_compatible("0.1.0", "0.9.0")
        assert _version_compatible("0.9.0", "0.9.0")
        assert _version_compatible("0.9.0", "1.0.0")

    def test_incompatible(self):
        assert not _version_compatible("1.0.0", "0.9.0")
        assert not _version_compatible("2.0.0", "1.5.0")

    def test_version_check_in_loader(self):
        registry = PluginRegistry()

        class FuturePlugin(MattPlugin):
            name = "future"
            django_matt_version = "99.0.0"

            def setup(self, api: MattAPI) -> None:
                pass

        registry.register(FuturePlugin)
        loader = PluginLoader(registry)
        errors = loader.check_versions()
        assert len(errors) == 1
        assert "99.0.0" in errors[0]
        assert registry.get_status("future") == PluginStatus.FAILED


# ---------------------------------------------------------------------------
# Hook system
# ---------------------------------------------------------------------------


class TestHookSystem:
    def test_register_hook(self):
        @hook("test_event")
        def handler() -> str:
            return "ok"

        hooks = get_hooks("test_event")
        assert len(hooks) == 1

    def test_hook_execution_sync(self):
        results = []

        @hook("sync_event")
        def handler() -> None:
            results.append("called")

        fire_hook_sync("sync_event")
        assert results == ["called"]

    @pytest.mark.asyncio
    async def test_hook_execution_async(self):
        results = []

        @hook("async_event")
        async def handler() -> None:
            results.append("async_called")

        await fire_hook("async_event")
        assert results == ["async_called"]

    def test_hook_priority_ordering(self):
        order: list[int] = []

        @hook("priority_event", priority=200)
        def low_priority() -> None:
            order.append(200)

        @hook("priority_event", priority=50)
        def high_priority() -> None:
            order.append(50)

        @hook("priority_event", priority=100)
        def mid_priority() -> None:
            order.append(100)

        fire_hook_sync("priority_event")
        assert order == [50, 100, 200]

    @pytest.mark.asyncio
    async def test_mixed_sync_async_hooks(self):
        results: list[str] = []

        @hook("mixed_event", priority=1)
        def sync_handler() -> None:
            results.append("sync")

        @hook("mixed_event", priority=2)
        async def async_handler() -> None:
            results.append("async")

        await fire_hook("mixed_event")
        assert results == ["sync", "async"]

    def test_sync_fire_skips_async(self):
        results: list[str] = []

        @hook("skip_event", priority=1)
        def sync_handler() -> None:
            results.append("sync")

        @hook("skip_event", priority=2)
        async def async_handler() -> None:
            results.append("async")

        fire_hook_sync("skip_event")
        assert results == ["sync"]

    @pytest.mark.asyncio
    async def test_fire_hook_returns_results(self):
        @hook("result_event", priority=1)
        def handler_a() -> int:
            return 1

        @hook("result_event", priority=2)
        async def handler_b() -> int:
            return 2

        results = await fire_hook("result_event")
        assert results == [1, 2]

    def test_clear_hooks_specific(self):
        @hook("clear_me")
        def handler() -> None:
            pass

        assert len(get_hooks("clear_me")) == 1
        clear_hooks("clear_me")
        assert len(get_hooks("clear_me")) == 0

    def test_clear_all_hooks(self):
        @hook("event_a")
        def handler_a() -> None:
            pass

        @hook("event_b")
        def handler_b() -> None:
            pass

        clear_hooks()
        assert get_hooks("event_a") == []
        assert get_hooks("event_b") == []

    def test_list_hook_events(self):
        @hook("alpha_event")
        def handler_a() -> None:
            pass

        @hook("beta_event")
        def handler_b() -> None:
            pass

        events = list_hook_events()
        assert "alpha_event" in events
        assert "beta_event" in events

    def test_no_hooks_for_event(self):
        assert get_hooks("nonexistent") == []

    def test_fire_empty_event(self):
        results = fire_hook_sync("empty_event")
        assert results == []


# ---------------------------------------------------------------------------
# Plugin configuration
# ---------------------------------------------------------------------------


class TestPluginConfig:
    def test_load_defaults(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        defaults = config.load_defaults(plugin)
        assert defaults["enabled"] is True
        assert defaults["max_items"] == 100

    def test_load_defaults_no_schema(self):
        config = PluginConfig()
        plugin = AnotherPlugin()
        defaults = config.load_defaults(plugin)
        assert defaults == {}

    def test_load_env(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        with patch.dict(os.environ, {"MATT_SAMPLE_DEBUG": "true"}):
            env = config.load_env(plugin)
        assert env["debug"] == "true"

    def test_load_env_no_prefix(self):
        config = PluginConfig()
        plugin = AnotherPlugin()
        env = config.load_env(plugin)
        assert env == {}

    def test_resolve_merges_sources(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        with patch.dict(os.environ, {"MATT_SAMPLE_EXTRA": "env_value"}):
            merged = config.resolve(plugin)
        assert merged["enabled"] is True
        assert merged["max_items"] == 100
        assert merged["extra"] == "env_value"

    def test_validate_valid_config(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        errors = config.validate(plugin, {"enabled": True, "max_items": 50})
        assert errors == []

    def test_validate_wrong_type(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        errors = config.validate(plugin, {"enabled": "yes", "max_items": 50})
        assert len(errors) == 1
        assert "enabled" in errors[0]

    def test_validate_missing_required(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        errors = config.validate(plugin, {"max_items": 50})
        assert len(errors) == 1
        assert "enabled" in errors[0]

    def test_validate_no_schema(self):
        config = PluginConfig()
        plugin = AnotherPlugin()
        errors = config.validate(plugin, {"anything": "goes"})
        assert errors == []

    def test_get_config(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        config.resolve(plugin)
        result = config.get("sample")
        assert "enabled" in result

    def test_reload(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        config.resolve(plugin)
        reloaded = config.reload(plugin)
        assert reloaded["enabled"] is True

    def test_reset(self):
        config = PluginConfig()
        plugin = SamplePlugin()
        config.resolve(plugin)
        config.reset()
        assert config.get("sample") == {}


# ---------------------------------------------------------------------------
# Plugin scaffolding
# ---------------------------------------------------------------------------


class TestPluginScaffolder:
    def test_scaffold_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scaffolder = PluginScaffolder("my-plugin", author="Test", description="Test plugin")
            created = scaffolder.generate(tmpdir)
            assert len(created) == 10

            # Check key files exist
            base = Path(tmpdir) / "my-plugin"
            assert (base / "pyproject.toml").exists()
            assert (base / "README.md").exists()
            assert (base / "my_plugin" / "__init__.py").exists()
            assert (base / "my_plugin" / "plugin.py").exists()
            assert (base / "my_plugin" / "controllers.py").exists()
            assert (base / "my_plugin" / "schemas.py").exists()
            assert (base / "my_plugin" / "services.py").exists()
            assert (base / "tests" / "test_plugin.py").exists()
            assert (base / ".github" / "workflows" / "ci.yml").exists()

    def test_pyproject_has_entry_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scaffolder = PluginScaffolder("my-plugin")
            scaffolder.generate(tmpdir)
            content = (Path(tmpdir) / "my-plugin" / "pyproject.toml").read_text()
            assert "matt.plugins" in content
            assert "my_plugin.plugin:MyPluginPlugin" in content

    def test_plugin_class_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scaffolder = PluginScaffolder("my-plugin")
            scaffolder.generate(tmpdir)
            content = (Path(tmpdir) / "my-plugin" / "my_plugin" / "plugin.py").read_text()
            assert "class MyPluginPlugin(MattPlugin):" in content
            assert 'name = "my_plugin"' in content

    def test_class_name_generation(self):
        scaffolder = PluginScaffolder("my-awesome-plugin")
        assert scaffolder.class_name == "MyAwesomePlugin"
        assert scaffolder.package_name == "my_awesome_plugin"


# ---------------------------------------------------------------------------
# Plugin testing utilities
# ---------------------------------------------------------------------------


class TestPluginTestCase:
    def test_setup_teardown(self):
        tc = PluginTestCase()
        tc.plugin_class = SamplePlugin
        tc.setup_method()
        assert tc.registry is not None
        assert tc.plugin.name == "sample"
        tc.teardown_method()

    def test_assert_plugin_registered(self):
        tc = PluginTestCase()
        tc.plugin_class = SamplePlugin
        tc.setup_method()
        tc.assert_plugin_registered("sample")
        tc.teardown_method()

    def test_assert_plugin_status(self):
        tc = PluginTestCase()
        tc.plugin_class = SamplePlugin
        tc.setup_method()
        tc.assert_plugin_status("sample", PluginStatus.REGISTERED)
        tc.teardown_method()


class TestMockPlugin:
    def test_mock_plugin_context(self):
        registry = get_plugin_registry()
        with mock_plugin("test_mock", version="2.0.0") as plugin:
            assert plugin.name == "test_mock"
            assert plugin.version == "2.0.0"
            assert registry.is_registered("test_mock")
        assert not registry.is_registered("test_mock")

    def test_mock_plugin_custom_attrs(self):
        with mock_plugin("custom", description="custom desc") as plugin:
            assert plugin.description == "custom desc"


class TestCreateTestApi:
    def test_creates_api_no_plugins(self):
        api = create_test_api()
        assert api is not None

    def test_creates_api_with_plugins(self):
        reset_plugin_registry()
        api = create_test_api(plugins=[SamplePlugin])
        registry = get_plugin_registry()
        assert registry.is_loaded("sample")


# ---------------------------------------------------------------------------
# Entry point discovery (mocked)
# ---------------------------------------------------------------------------


class TestEntryPointDiscovery:
    def test_discover_entry_points(self):
        registry = PluginRegistry()
        loader = PluginLoader(registry)

        mock_ep = MagicMock()
        mock_ep.name = "sample"
        mock_ep.load.return_value = SamplePlugin

        with patch(
            "django_matt.plugins.loader.importlib.metadata.entry_points",
            return_value=[mock_ep],
        ):
            discovered = loader.discover_entry_points()

        assert len(discovered) == 1
        assert discovered[0].name == "sample"

    def test_discover_entry_points_failure(self):
        registry = PluginRegistry()
        loader = PluginLoader(registry)

        mock_ep = MagicMock()
        mock_ep.name = "bad"
        mock_ep.load.side_effect = ImportError("not found")

        with patch(
            "django_matt.plugins.loader.importlib.metadata.entry_points",
            return_value=[mock_ep],
        ):
            discovered = loader.discover_entry_points()

        assert len(discovered) == 0


# ---------------------------------------------------------------------------
# Directory discovery
# ---------------------------------------------------------------------------


class TestDirectoryDiscovery:
    def test_discover_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a plugin module
            plugin_file = Path(tmpdir) / "my_local_plugin.py"
            plugin_file.write_text(
                "from django_matt.plugins.base import MattPlugin\n\n"
                "class LocalPlugin(MattPlugin):\n"
                "    name = 'local'\n"
                "    def setup(self, api): pass\n"
            )

            registry = PluginRegistry()
            loader = PluginLoader(registry)
            discovered = loader.discover_directories([tmpdir])
            assert len(discovered) == 1
            assert discovered[0].name == "local"

    def test_discover_nonexistent_directory(self):
        registry = PluginRegistry()
        loader = PluginLoader(registry)
        discovered = loader.discover_directories(["/nonexistent/path"])
        assert discovered == []


# ---------------------------------------------------------------------------
# Global registry singleton
# ---------------------------------------------------------------------------


class TestGlobalRegistry:
    def test_get_returns_same_instance(self):
        r1 = get_plugin_registry()
        r2 = get_plugin_registry()
        assert r1 is r2

    def test_reset_clears(self):
        registry = get_plugin_registry()
        registry.register(SamplePlugin)
        reset_plugin_registry()
        new_registry = get_plugin_registry()
        assert not new_registry.is_registered("sample")


# ---------------------------------------------------------------------------
# Check system integration
# ---------------------------------------------------------------------------


class TestCheckSystem:
    def test_check_plugin_returns_messages(self):
        plugin = CheckPlugin()
        messages = plugin.check()
        assert len(messages) == 2
        serious = [m for m in messages if m.is_serious()]
        assert len(serious) == 1
