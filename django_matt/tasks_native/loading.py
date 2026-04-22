"""
Conditional loading and tree-shaking for the native task engine.

Ensures zero overhead when tasks_native is not enabled:
- Models only imported when app is in INSTALLED_APPS
- Admin only registered when Django admin is available
- Heavy dependencies (redis, etc.) only loaded on first use
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .backends.base import BaseNativeBackend


@lru_cache(maxsize=1)
def is_tasks_native_installed() -> bool:
    """
    Check if tasks_native is in INSTALLED_APPS.

    Cached to avoid repeated app registry lookups.
    """
    try:
        from django.apps import apps

        return apps.is_installed("django_matt.tasks_native")
    except Exception:
        return False


@lru_cache(maxsize=1)
def is_admin_available() -> bool:
    """
    Check if Django admin is available and installed.
    """
    try:
        from django.apps import apps

        return apps.is_installed("django.contrib.admin")
    except Exception:
        return False


@lru_cache(maxsize=1)
def is_unfold_available() -> bool:
    """
    Check if Django Unfold is installed.
    """
    try:
        import unfold  # noqa: F401

        return True
    except ImportError:
        return False


class LazyBackendLoader:
    """
    Lazy loader for task backends.

    Delays importing heavy dependencies (redis, celery, etc.)
    until they're actually needed.
    """

    _backend: "BaseNativeBackend | None" = None
    _backend_type: str | None = None

    @classmethod
    def get_backend(cls) -> "BaseNativeBackend":
        """Get the configured backend, loading lazily."""
        if cls._backend is not None:
            return cls._backend

        from .config import get_backend

        cls._backend = get_backend()
        cls._backend_type = cls._backend.name
        return cls._backend

    @classmethod
    def reset(cls) -> None:
        """Reset the cached backend (for testing)."""
        cls._backend = None
        cls._backend_type = None


def should_load_models() -> bool:
    """
    Determine if task models should be loaded.

    Returns False if:
    - tasks_native not in INSTALLED_APPS
    - Running in slim mode with tasks disabled
    """
    if not is_tasks_native_installed():
        return False

    try:
        from django_matt.slim import get_slim_config, is_module_enabled

        config = get_slim_config()
        if config.mode == "full":
            return True
        return is_module_enabled("tasks_native")
    except ImportError:
        return True


def should_register_admin() -> bool:
    """
    Determine if admin classes should be registered.
    """
    return should_load_models() and is_admin_available()


def get_enabled_features() -> set[str]:
    """
    Get the set of enabled tasks_native features.

    Used for selective loading of sub-modules.
    """
    features = {"core", "registry", "scheduling", "retry"}

    if is_tasks_native_installed():
        features.add("models")

    if should_register_admin():
        features.add("admin")

    try:
        from .config import get_config

        config = get_config()
        if config.backend != "sync":
            features.add("workers")
    except Exception:
        pass

    return features


class ModuleLoader:
    """
    Controls which tasks_native sub-modules are loaded.

    Usage:
        loader = ModuleLoader()
        if loader.should_load("admin"):
            from .admin import register_admin
            register_admin()
    """

    def __init__(self):
        self._loaded: set[str] = set()
        self._features = get_enabled_features()

    def should_load(self, module: str) -> bool:
        """Check if a module should be loaded."""
        return module in self._features

    def mark_loaded(self, module: str) -> None:
        """Mark a module as loaded."""
        self._loaded.add(module)

    def is_loaded(self, module: str) -> bool:
        """Check if a module has been loaded."""
        return module in self._loaded

    @property
    def loaded_modules(self) -> set[str]:
        """Get set of loaded modules."""
        return self._loaded.copy()


# Global module loader
_loader: ModuleLoader | None = None


def get_loader() -> ModuleLoader:
    """Get the global module loader."""
    global _loader
    if _loader is None:
        _loader = ModuleLoader()
    return _loader


def estimate_import_cost() -> dict[str, str]:
    """
    Estimate the import cost of each sub-module.

    Returns a dict of module -> cost category.
    Useful for bundle size analysis.
    """
    return {
        "core": "minimal",
        "types": "minimal",
        "registry": "minimal",
        "config": "minimal",
        "scheduling": "minimal",
        "retry": "minimal",
        "models": "moderate",
        "admin": "moderate",
        "backends.sync": "minimal",
        "backends.django_native": "minimal",
        "backends.celery_compat": "heavy",
        "backends.dramatiq_compat": "heavy",
        "backends.django_q_compat": "moderate",
    }


def get_import_impact() -> dict[str, int]:
    """
    Get estimated KB impact of each module.

    These are rough estimates for documentation purposes.
    """
    return {
        "core": 15,
        "types": 5,
        "registry": 3,
        "config": 5,
        "scheduling": 10,
        "retry": 8,
        "models": 12,
        "admin": 25,
        "backends.sync": 5,
        "backends.django_native": 8,
        "backends.celery_compat": 150,
        "backends.dramatiq_compat": 80,
        "backends.django_q_compat": 40,
    }
