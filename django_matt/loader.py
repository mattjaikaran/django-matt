from __future__ import annotations

import importlib
import threading
from types import ModuleType
from typing import Any

from django_matt.slim import is_module_enabled

# Heavy modules that benefit from deferred loading.
# These are never imported at startup — only when explicitly used.
HEAVY_MODULES: frozenset[str] = frozenset({
    "billing",
    "ai",
    "ml",
    "graphql",
    "websockets",
    "analytics",
    "experiments",
    "notifications",
    "email",
    "messaging",
    "files",
    "tasks",
    # Frontend integration modules — only needed if you use them
    "vite",
    "inertia",
    "unpoly",
    "components",
    "htmx",
    "livewire",
    "pages",
    "tailwind",
    "forms",
    # Dev-only modules
    "review",
    "codemods",
    "sdkgen",
    "typegen",
    "codegen",
})

# Light modules always loaded eagerly
LIGHT_MODULES: frozenset[str] = frozenset({
    "core",
    "auth",
    "views",
    "config",
    "permissions",
    "openapi",
    "pagination",
    "filtering",
})


class LazyModuleProxy:
    __slots__ = ("_lock", "_module", "_module_path")

    def __init__(self, module_path: str) -> None:
        object.__setattr__(self, "_module_path", module_path)
        object.__setattr__(self, "_module", None)
        object.__setattr__(self, "_lock", threading.Lock())

    def _load(self) -> ModuleType:
        mod = object.__getattribute__(self, "_module")
        if mod is not None:
            return mod
        lock = object.__getattribute__(self, "_lock")
        with lock:
            # Double-check after acquiring lock
            mod = object.__getattribute__(self, "_module")
            if mod is not None:
                return mod
            path = object.__getattribute__(self, "_module_path")
            mod = importlib.import_module(path)
            object.__setattr__(self, "_module", mod)
            return mod

    @property
    def _is_loaded(self) -> bool:
        return object.__getattribute__(self, "_module") is not None

    def __getattr__(self, name: str) -> Any:
        mod = self._load()
        return getattr(mod, name)

    def __repr__(self) -> str:
        path = object.__getattribute__(self, "_module_path")
        loaded = self._is_loaded
        state = "loaded" if loaded else "deferred"
        return f"<LazyModuleProxy {path!r} ({state})>"


def lazy_import(module_path: str) -> LazyModuleProxy:
    return LazyModuleProxy(module_path)


class DeferredLoader:
    def __init__(self) -> None:
        self._proxies: dict[str, LazyModuleProxy] = {}
        self._loaded: dict[str, ModuleType] = {}

    def get(self, module_name: str) -> LazyModuleProxy | ModuleType | None:
        if not is_module_enabled(module_name):
            return None
        full_path = f"django_matt.{module_name}"
        if module_name in LIGHT_MODULES:
            if module_name not in self._loaded:
                self._loaded[module_name] = importlib.import_module(full_path)
            return self._loaded[module_name]
        if module_name not in self._proxies:
            self._proxies[module_name] = LazyModuleProxy(full_path)
        return self._proxies[module_name]

    def preload(self, *module_names: str) -> None:
        for name in module_names:
            proxy = self.get(name)
            if isinstance(proxy, LazyModuleProxy):
                proxy._load()

    def is_loaded(self, module_name: str) -> bool:
        if module_name in self._loaded:
            return True
        proxy = self._proxies.get(module_name)
        if proxy is not None:
            return proxy._is_loaded
        return False

    @property
    def deferred_modules(self) -> list[str]:
        return [
            name for name, proxy in self._proxies.items()
            if not proxy._is_loaded
        ]

    def __repr__(self) -> str:
        loaded = sum(1 for n in self._proxies if self.is_loaded(n))
        loaded += len(self._loaded)
        total = len(self._proxies) + len(self._loaded)
        return f"<DeferredLoader loaded={loaded}/{total}>"
