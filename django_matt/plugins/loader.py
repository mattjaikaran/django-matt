from __future__ import annotations

import importlib
import importlib.metadata
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django_matt.plugins.base import MattPlugin
from django_matt.plugins.registry import (
    PluginRegistry,
    PluginStatus,
    get_plugin_registry,
)

if TYPE_CHECKING:
    from django_matt.api import MattAPI

logger = logging.getLogger("django_matt.plugins")

ENTRY_POINT_GROUP = "matt.plugins"
FRAMEWORK_VERSION = "0.9.0"


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple."""
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts)


def _version_compatible(required: str, current: str) -> bool:
    """Check if current version satisfies the minimum required version."""
    req = _parse_version(required)
    cur = _parse_version(current)
    return cur >= req


def _satisfies_constraint(version: str, constraint: str) -> bool:
    """Check if version satisfies a constraint like '>=3.12' or '>=5.2,<6.0'."""
    ver = _parse_version(version)
    for part in constraint.split(","):
        part = part.strip()
        if part.startswith(">="):
            if ver < _parse_version(part[2:]):
                return False
        elif part.startswith("<="):
            if ver > _parse_version(part[2:]):
                return False
        elif part.startswith(">"):
            if ver <= _parse_version(part[1:]):
                return False
        elif part.startswith("<"):
            if ver >= _parse_version(part[1:]):
                return False
        elif part.startswith("=="):
            if ver != _parse_version(part[2:]):
                return False
        elif part.startswith("!="):
            if ver == _parse_version(part[2:]):
                return False
    return True


class PluginLoader:
    """Loads plugins from entry points, settings, and local directories."""

    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self.registry = registry or get_plugin_registry()

    def discover_entry_points(self) -> list[MattPlugin]:
        """Discover plugins registered via the matt.plugins entry point group."""
        discovered: list[MattPlugin] = []
        try:
            eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception as exc:
            logger.warning("Failed to query entry points: %s", exc)
            return discovered

        for ep in eps:
            try:
                plugin_cls = ep.load()
                plugin = self.registry.register(plugin_cls)
                discovered.append(plugin)
                logger.debug("Discovered entry point plugin: %s", ep.name)
            except Exception as exc:
                logger.warning("Failed to load entry point %s: %s", ep.name, exc)

        return discovered

    def discover_settings(self) -> list[MattPlugin]:
        """Discover plugins from MATT_PLUGINS in Django settings."""
        discovered: list[MattPlugin] = []
        try:
            from django.conf import settings

            plugin_paths = getattr(settings, "MATT_PLUGINS", None)
            if plugin_paths is None:
                matt_config = getattr(settings, "DJANGO_MATT", {})
                plugin_paths = matt_config.get("PLUGINS", [])
        except Exception:
            return discovered

        for path in plugin_paths:
            try:
                mod = importlib.import_module(path)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, MattPlugin)
                        and attr is not MattPlugin
                        and not self.registry.is_registered(
                            getattr(attr, "name", "") or attr_name.lower()
                        )
                    ):
                        plugin = self.registry.register(attr)
                        discovered.append(plugin)
            except Exception as exc:
                logger.warning("Failed to load plugin from %s: %s", path, exc)

        return discovered

    def discover_directories(self, dirs: list[str] | None = None) -> list[MattPlugin]:
        """Discover plugins from local directories."""
        discovered: list[MattPlugin] = []
        if dirs is None:
            try:
                from django.conf import settings

                dirs = getattr(settings, "MATT_PLUGIN_DIRS", [])
            except Exception:
                return discovered

        for dir_path in dirs:
            path = Path(dir_path).resolve()
            if not path.is_dir():
                logger.warning("Plugin directory does not exist: %s", path)
                continue

            # Add to sys.path temporarily if not there
            str_path = str(path)
            added = False
            if str_path not in sys.path:
                sys.path.insert(0, str_path)
                added = True

            try:
                for item in path.iterdir():
                    if item.is_file() and item.suffix == ".py" and item.stem != "__init__":
                        module_name = item.stem
                    elif item.is_dir() and (item / "__init__.py").exists():
                        module_name = item.name
                    else:
                        continue

                    try:
                        mod = importlib.import_module(module_name)
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, MattPlugin)
                                and attr is not MattPlugin
                                and not self.registry.is_registered(
                                    getattr(attr, "name", "") or attr_name.lower()
                                )
                            ):
                                plugin = self.registry.register(attr)
                                discovered.append(plugin)
                    except Exception as exc:
                        logger.warning(
                            "Failed to load plugin from %s: %s",
                            module_name,
                            exc,
                        )
            finally:
                if added:
                    sys.path.remove(str_path)

        return discovered

    def check_versions(self) -> list[str]:
        """Check version compatibility for all registered plugins."""
        import django

        errors: list[str] = []
        for plugin in self.registry.list_plugins():
            if plugin.django_matt_version and not _version_compatible(
                plugin.django_matt_version, FRAMEWORK_VERSION
            ):
                msg = (
                    f"Plugin {plugin.name!r} requires django-matt >= "
                    f"{plugin.django_matt_version}, but {FRAMEWORK_VERSION} "
                    f"is installed"
                )
                errors.append(msg)
                self.registry.set_error(plugin.name, msg)

            if plugin.django_matt_max_version:
                max_v = _parse_version(plugin.django_matt_max_version)
                cur_v = _parse_version(FRAMEWORK_VERSION)
                if cur_v > max_v:
                    msg = (
                        f"Plugin {plugin.name!r} requires django-matt <= "
                        f"{plugin.django_matt_max_version}, but {FRAMEWORK_VERSION} "
                        f"is installed"
                    )
                    errors.append(msg)
                    self.registry.set_error(plugin.name, msg)

            if plugin.python_requires:
                py_ver = (
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                )
                if not self._check_version_spec(plugin.python_requires, py_ver):
                    msg = (
                        f"Plugin {plugin.name!r} requires Python {plugin.python_requires}, "
                        f"but {py_ver} is installed"
                    )
                    errors.append(msg)
                    self.registry.set_error(plugin.name, msg)

            if plugin.django_requires:
                django_ver = f"{django.VERSION[0]}.{django.VERSION[1]}"
                if not self._check_version_spec(plugin.django_requires, django_ver):
                    msg = (
                        f"Plugin {plugin.name!r} requires Django {plugin.django_requires}, "
                        f"but {django_ver} is installed"
                    )
                    errors.append(msg)
                    self.registry.set_error(plugin.name, msg)

        return errors

    def compatibility_matrix(self) -> list[dict[str, Any]]:
        """Generate a compatibility matrix for all registered plugins."""
        matrix = []
        for plugin in self.registry.list_plugins():
            status = self.registry.get_status(plugin.name)
            compat = {
                "name": plugin.name,
                "version": plugin.version,
                "status": status.value if hasattr(status, "value") else str(status),
                "django_matt_min": plugin.django_matt_version or "any",
                "django_matt_max": plugin.django_matt_max_version or "any",
                "python_requires": plugin.python_requires or "any",
                "django_requires": plugin.django_requires or "any",
                "compatible": self._check_plugin_compat(plugin),
            }
            matrix.append(compat)
        return matrix

    def get_compatibility_matrix(self) -> list[dict[str, str]]:
        """Build a compatibility matrix for all registered plugins."""
        matrix: list[dict[str, str]] = []
        for plugin in self.registry.list_plugins():
            status = self.registry.get_status(plugin.name)
            matt_range = f">={plugin.django_matt_version}"
            if plugin.django_matt_max_version:
                matt_range += f",<={plugin.django_matt_max_version}"
            matrix.append(
                {
                    "name": plugin.name,
                    "version": plugin.version,
                    "django_matt": matt_range,
                    "python": plugin.python_requires or "any",
                    "django": plugin.django_requires or "any",
                    "status": status.value if hasattr(status, "value") else str(status),
                    "dependencies": ", ".join(plugin.dependencies)
                    if plugin.dependencies
                    else "none",
                }
            )
        return matrix

    def _check_plugin_compat(self, plugin: MattPlugin) -> bool:
        """Check if a single plugin is compatible with the current environment."""
        import django

        # Framework version
        if plugin.django_matt_version and not _version_compatible(
            plugin.django_matt_version, FRAMEWORK_VERSION
        ):
            return False
        if plugin.django_matt_max_version:
            max_v = _parse_version(plugin.django_matt_max_version)
            cur_v = _parse_version(FRAMEWORK_VERSION)
            if cur_v > max_v:
                return False
        # Python version
        if plugin.python_requires:
            py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            if not self._check_version_spec(plugin.python_requires, py_ver):
                return False
        # Django version
        if plugin.django_requires:
            django_ver = f"{django.VERSION[0]}.{django.VERSION[1]}"
            if not self._check_version_spec(plugin.django_requires, django_ver):
                return False
        return True

    @staticmethod
    def _check_version_spec(spec: str, current: str) -> bool:
        """Check if current version satisfies a version spec like '>=3.12' or '>=5.2,<6.0'."""
        cur = _parse_version(current)
        for part in spec.split(","):
            part = part.strip()
            if part.startswith(">="):
                if cur < _parse_version(part[2:]):
                    return False
            elif part.startswith("<="):
                if cur > _parse_version(part[2:]):
                    return False
            elif part.startswith(">"):
                if cur <= _parse_version(part[1:]):
                    return False
            elif part.startswith("<"):
                if cur >= _parse_version(part[1:]):
                    return False
            elif part.startswith("=="):
                if cur != _parse_version(part[2:]):
                    return False
            elif part.startswith("!="):
                if cur == _parse_version(part[2:]):
                    return False
        return True

    def load_all(self, api: MattAPI) -> list[MattPlugin]:
        """Load all registered plugins in dependency order."""
        version_errors = self.check_versions()
        if version_errors:
            for err in version_errors:
                logger.error(err)

        order = self.registry.resolve_dependencies()
        loaded: list[MattPlugin] = []

        for name in order:
            plugin = self.registry.get_plugin(name)
            status = self.registry.get_status(name)

            if status == PluginStatus.DISABLED:
                logger.info("Skipping disabled plugin: %s", name)
                continue

            if status == PluginStatus.FAILED:
                logger.warning("Skipping failed plugin: %s", name)
                continue

            # Check dependencies are loaded
            for dep in plugin.dependencies:
                if not self.registry.is_loaded(dep):
                    msg = f"Plugin {name!r} dependency {dep!r} is not loaded"
                    logger.error(msg)
                    self.registry.set_error(name, msg)
                    break
            else:
                try:
                    plugin.setup(api)
                    plugin.on_startup()
                    self.registry.set_status(name, PluginStatus.LOADED)
                    loaded.append(plugin)
                    logger.info("Loaded plugin %s v%s", name, plugin.version)
                except Exception as exc:
                    msg = f"Plugin {name!r} failed to load: {exc}"
                    logger.error(msg)
                    self.registry.set_error(name, msg)

        return loaded

    def unload_all(self) -> None:
        """Unload all plugins in reverse order."""
        for name in reversed(self.registry._load_order):
            if self.registry.is_loaded(name):
                plugin = self.registry.get_plugin(name)
                try:
                    plugin.on_shutdown()
                except Exception as exc:
                    logger.warning("Error shutting down plugin %s: %s", name, exc)
                self.registry.set_status(name, PluginStatus.REGISTERED)
