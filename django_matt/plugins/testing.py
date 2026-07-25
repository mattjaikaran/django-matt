from __future__ import annotations

import contextlib
from typing import Any, Generator
from unittest.mock import MagicMock

from django_matt.plugins.base import MattPlugin
from django_matt.plugins.hooks import clear_hooks
from django_matt.plugins.registry import (
    PluginRegistry,
    PluginStatus,
    get_plugin_registry,
    reset_plugin_registry,
)


class PluginTestCase:
    """Base test class for plugin tests.

    Provides setup/teardown of a clean plugin registry per test.
    """

    plugin_class: type[MattPlugin]
    plugin: MattPlugin
    registry: PluginRegistry

    def setup_method(self) -> None:
        reset_plugin_registry()
        clear_hooks()
        self.registry = get_plugin_registry()
        if hasattr(self, "plugin_class"):
            self.plugin = self.registry.register(self.plugin_class)

    def teardown_method(self) -> None:
        reset_plugin_registry()
        clear_hooks()

    def assert_plugin_loaded(self, name: str) -> None:
        assert self.registry.is_loaded(name), f"Plugin {name!r} is not loaded"

    def assert_plugin_registered(self, name: str) -> None:
        assert self.registry.is_registered(name), f"Plugin {name!r} is not registered"

    def assert_plugin_status(self, name: str, status: PluginStatus) -> None:
        actual = self.registry.get_status(name)
        assert actual == status, f"Plugin {name!r} status is {actual}, expected {status}"

    def assert_hook_count(self, event: str, expected: int) -> None:
        from django_matt.plugins.hooks import get_hooks

        hooks = get_hooks(event)
        assert len(hooks) == expected, (
            f"Event {event!r} has {len(hooks)} hooks, expected {expected}"
        )

    def assert_has_urls(self, name: str) -> None:
        plugin = self.registry.get_plugin(name)
        urls = plugin.get_urls()
        assert len(urls) > 0, f"Plugin {name!r} has no URL patterns"

    def assert_has_middleware(self, name: str) -> None:
        plugin = self.registry.get_plugin(name)
        mw = plugin.get_middleware()
        assert len(mw) > 0, f"Plugin {name!r} has no middleware"


@contextlib.contextmanager
def mock_plugin(
    name: str = "mock_plugin",
    version: str = "1.0.0",
    **kwargs: Any,
) -> Generator[MattPlugin, None, None]:
    """Context manager that creates and registers a mock plugin."""
    registry = get_plugin_registry()

    class MockPlugin(MattPlugin):
        def setup(self, api: Any) -> None:
            pass

    MockPlugin.name = name
    MockPlugin.version = version
    for key, value in kwargs.items():
        setattr(MockPlugin, key, value)

    plugin = registry.register(MockPlugin)
    try:
        yield plugin
    finally:
        try:
            registry.unregister(name)
        except Exception:
            pass


def create_test_api(
    plugins: list[type[MattPlugin]] | None = None,
) -> MagicMock:
    """Create a mock MattAPI with plugins loaded for testing."""
    api = MagicMock(spec=["register_controller", "add_middleware", "urls"])
    api.urls = []

    if plugins:
        from django_matt.plugins.loader import PluginLoader

        registry = get_plugin_registry()
        loader = PluginLoader(registry)

        for plugin_cls in plugins:
            registry.register(plugin_cls)

        loader.load_all(api)

    return api
