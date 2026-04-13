from __future__ import annotations

import logging
from enum import Enum

from django_matt.plugins.base import MattPlugin

logger = logging.getLogger("django_matt.plugins")


class PluginStatus(str, Enum):
    REGISTERED = "registered"
    LOADED = "loaded"
    FAILED = "failed"
    DISABLED = "disabled"


class PluginError(Exception):
    pass


class PluginConflictError(PluginError):
    pass


class PluginDependencyError(PluginError):
    pass


class PluginVersionError(PluginError):
    pass


class PluginNotFoundError(PluginError):
    pass


class PluginRegistry:
    """Registry for managing django-matt plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, MattPlugin] = {}
        self._status: dict[str, PluginStatus] = {}
        self._errors: dict[str, str] = {}
        self._load_order: list[str] = []
        self._url_prefixes: dict[str, str] = {}

    def register(self, plugin: MattPlugin | type[MattPlugin]) -> MattPlugin:
        """Register a plugin instance or class."""
        if isinstance(plugin, type):
            plugin = plugin()
        if not isinstance(plugin, MattPlugin):
            raise TypeError(
                f"Expected MattPlugin instance, got {type(plugin).__name__}"
            )
        if plugin.name in self._plugins:
            raise PluginError(f"Plugin {plugin.name!r} is already registered")

        self._plugins[plugin.name] = plugin
        self._status[plugin.name] = PluginStatus.REGISTERED
        logger.debug("Registered plugin %s v%s", plugin.name, plugin.version)
        return plugin

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry."""
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        self._plugins.pop(name)
        self._status.pop(name, None)
        self._errors.pop(name, None)
        self._url_prefixes = {
            prefix: pname
            for prefix, pname in self._url_prefixes.items()
            if pname != name
        }
        if name in self._load_order:
            self._load_order.remove(name)

    def resolve_dependencies(self) -> list[str]:
        """Resolve plugin load order via topological sort."""
        active = {
            name
            for name, status in self._status.items()
            if status != PluginStatus.DISABLED
        }

        graph: dict[str, list[str]] = {}
        for name in active:
            plugin = self._plugins[name]
            for dep in plugin.dependencies:
                if dep not in self._plugins:
                    raise PluginDependencyError(
                        f"Plugin {name!r} depends on {dep!r}, which is not registered"
                    )
            # Only include active deps in the graph for ordering
            graph[name] = [d for d in plugin.dependencies if d in active]

        order: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                cycle = " -> ".join(sorted(visiting))
                raise PluginDependencyError(
                    f"Circular dependency detected: {cycle}"
                )
            visiting.add(name)
            for dep in graph.get(name, []):
                visit(dep)
            visiting.discard(name)
            visited.add(name)
            order.append(name)

        for name in sorted(graph.keys()):
            visit(name)

        self._load_order = order
        return order

    def detect_conflicts(self) -> list[str]:
        """Check for URL prefix conflicts between plugins."""
        conflicts: list[str] = []
        prefix_owners: dict[str, str] = {}

        for name in self._load_order or self._plugins:
            plugin = self._plugins[name]
            urls = plugin.get_urls()
            for url_pattern in urls:
                prefix = getattr(url_pattern, "pattern", str(url_pattern))
                prefix_str = str(prefix)
                if prefix_str in prefix_owners:
                    conflicts.append(
                        f"URL prefix {prefix_str!r} claimed by both "
                        f"{prefix_owners[prefix_str]!r} and {name!r}"
                    )
                else:
                    prefix_owners[prefix_str] = name

        self._url_prefixes = prefix_owners
        return conflicts

    def get_plugin(self, name: str) -> MattPlugin:
        """Get a registered plugin by name."""
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        return self._plugins[name]

    def list_plugins(self) -> list[MattPlugin]:
        """Return all registered plugins."""
        return list(self._plugins.values())

    def is_loaded(self, name: str) -> bool:
        return self._status.get(name) == PluginStatus.LOADED

    def is_registered(self, name: str) -> bool:
        return name in self._plugins

    def get_status(self, name: str) -> PluginStatus:
        if name not in self._status:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        return self._status[name]

    def set_status(self, name: str, status: PluginStatus) -> None:
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        self._status[name] = status

    def set_error(self, name: str, error: str) -> None:
        self._errors[name] = error
        self._status[name] = PluginStatus.FAILED

    def get_error(self, name: str) -> str | None:
        return self._errors.get(name)

    def enable(self, name: str) -> None:
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        self._status[name] = PluginStatus.REGISTERED

    def disable(self, name: str) -> None:
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin {name!r} is not registered")
        self._status[name] = PluginStatus.DISABLED

    def reset(self) -> None:
        self._plugins.clear()
        self._status.clear()
        self._errors.clear()
        self._load_order.clear()
        self._url_prefixes.clear()

    def __repr__(self) -> str:
        loaded = sum(1 for s in self._status.values() if s == PluginStatus.LOADED)
        return (
            f"<PluginRegistry registered={len(self._plugins)} loaded={loaded}>"
        )


# Global singleton
_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    global _registry
    if _registry is not None:
        _registry.reset()
    _registry = None
