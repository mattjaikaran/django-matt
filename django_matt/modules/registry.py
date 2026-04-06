from __future__ import annotations

import importlib
import logging
import sys
from collections import defaultdict
from typing import Any

from django_matt.modules.base import MattModule

logger = logging.getLogger("django_matt.modules")

_registry: ModuleRegistry | None = None


class ModuleError(Exception):
    pass


class CircularDependencyError(ModuleError):
    pass


class MissingDependencyError(ModuleError):
    pass


class ModuleNotFoundError(ModuleError):
    pass


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, MattModule] = {}
        self._loaded: dict[str, MattModule] = {}
        self._load_order: list[str] = []
        self._hooks: dict[str, list] = defaultdict(list)
        self._all_loaded_hooks: list = []
        self._before_load_hooks: dict[str, list] = defaultdict(list)
        self._configs: dict[str, Any] = {}

    def register(self, module: MattModule | type[MattModule]) -> MattModule:
        if isinstance(module, type):
            module = module()
        if not isinstance(module, MattModule):
            raise TypeError(f"Expected MattModule instance, got {type(module).__name__}")
        if module.name in self._modules:
            raise ModuleError(f"Module {module.name!r} is already registered")
        self._modules[module.name] = module
        logger.debug("Registered module %s v%s", module.name, module.version)
        return module

    def resolve_dependencies(self) -> list[str]:
        graph: dict[str, list[str]] = {}
        for name, mod in self._modules.items():
            for dep in mod.dependencies:
                if dep not in self._modules:
                    raise MissingDependencyError(
                        f"Module {name!r} depends on {dep!r}, which is not registered"
                    )
            graph[name] = list(mod.dependencies)

        order: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise CircularDependencyError(
                    f"Circular dependency detected involving {name!r}"
                )
            visiting.add(name)
            for dep in graph.get(name, []):
                visit(dep)
            visiting.discard(name)
            visited.add(name)
            order.append(name)

        for name in graph:
            visit(name)

        self._load_order = order
        return order

    async def load_all(self) -> None:
        if not self._load_order:
            self.resolve_dependencies()

        for name in self._load_order:
            await self._load_module(name)

        for hook in self._all_loaded_hooks:
            await hook()

    async def _load_module(self, name: str) -> None:
        if name in self._loaded:
            return
        module = self._modules[name]

        for hook in self._before_load_hooks.get(name, []):
            await hook(module)

        if module.config_namespace:
            config = self._configs.get(module.config_namespace, {})
            module.validate_config(config)

        await module.on_ready()
        self._loaded[name] = module
        logger.info("Loaded module %s v%s", module.name, module.version)

        for hook in self._hooks.get(name, []):
            await hook(module)

    async def unload_all(self) -> None:
        for name in reversed(self._load_order):
            if name in self._loaded:
                await self._loaded[name].on_shutdown()
                del self._loaded[name]
        self._load_order.clear()

    def get(self, name: str) -> MattModule:
        if name not in self._loaded:
            raise ModuleNotFoundError(f"Module {name!r} is not loaded")
        return self._loaded[name]

    def is_loaded(self, name: str) -> bool:
        return name in self._loaded

    def is_registered(self, name: str) -> bool:
        return name in self._modules

    def list_loaded(self) -> list[MattModule]:
        return [self._loaded[name] for name in self._load_order if name in self._loaded]

    def list_registered(self) -> list[MattModule]:
        return list(self._modules.values())

    def add_on_loaded_hook(self, module_name: str, hook: Any) -> None:
        self._hooks[module_name].append(hook)

    def add_all_loaded_hook(self, hook: Any) -> None:
        self._all_loaded_hooks.append(hook)

    def add_before_load_hook(self, module_name: str, hook: Any) -> None:
        self._before_load_hooks[module_name].append(hook)

    def set_config(self, namespace: str, config: dict[str, Any]) -> None:
        self._configs[namespace] = config

    def reset(self) -> None:
        self._modules.clear()
        self._loaded.clear()
        self._load_order.clear()
        self._hooks.clear()
        self._all_loaded_hooks.clear()
        self._before_load_hooks.clear()
        self._configs.clear()

    def __repr__(self) -> str:
        return (
            f"<ModuleRegistry registered={len(self._modules)} "
            f"loaded={len(self._loaded)}>"
        )


def get_registry() -> ModuleRegistry:
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    if _registry is not None:
        _registry.reset()
    _registry = None


def discover_modules() -> list[MattModule]:
    registry = get_registry()
    discovered: list[MattModule] = []

    # 1. Entry points
    if sys.version_info >= (3, 12):
        from importlib.metadata import entry_points
        eps = entry_points(group="django_matt.modules")
        for ep in eps:
            try:
                module_cls = ep.load()
                mod = registry.register(module_cls)
                discovered.append(mod)
            except Exception as exc:
                logger.warning("Failed to load entry point %s: %s", ep.name, exc)

    # 2. Django settings explicit list
    try:
        from django.conf import settings
        matt_config = getattr(settings, "DJANGO_MATT", {})
        module_paths = matt_config.get("MODULES", [])
        for path in module_paths:
            try:
                mod_module = importlib.import_module(path)
                for attr_name in dir(mod_module):
                    attr = getattr(mod_module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, MattModule)
                        and attr is not MattModule
                        and not registry.is_registered(attr.name or attr_name.lower())
                    ):
                        mod = registry.register(attr)
                        discovered.append(mod)
            except Exception as exc:
                logger.warning("Failed to load module from %s: %s", path, exc)
    except Exception:
        pass

    # 3. Convention: scan installed apps for matt_module.py
    try:
        from django.apps import apps
        for app_config in apps.get_app_configs():
            module_path = f"{app_config.name}.matt_module"
            try:
                mod_module = importlib.import_module(module_path)
                for attr_name in dir(mod_module):
                    attr = getattr(mod_module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, MattModule)
                        and attr is not MattModule
                        and not registry.is_registered(attr.name or attr_name.lower())
                    ):
                        mod = registry.register(attr)
                        discovered.append(mod)
            except ImportError:
                continue
            except Exception as exc:
                logger.warning(
                    "Error scanning %s for modules: %s", app_config.name, exc
                )
    except Exception:
        pass

    return discovered
