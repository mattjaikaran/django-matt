"""DEPRECATED: Use `django_matt.plugins` instead. The modules system will be removed in v1.0."""

from __future__ import annotations

from django_matt.modules.base import MattModule
from django_matt.modules.decorators import module, optional_module, requires_module
from django_matt.modules.hooks import before_module_load, on_all_loaded, on_module_loaded
from django_matt.modules.loader import load_modules, shutdown_modules
from django_matt.modules.registry import (
    CircularDependencyError,
    MissingDependencyError,
    ModuleError,
    ModuleNotFoundError,
    ModuleRegistry,
    discover_modules,
    get_registry,
    reset_registry,
)

__all__ = [
    "MattModule",
    "ModuleRegistry",
    "ModuleError",
    "CircularDependencyError",
    "MissingDependencyError",
    "ModuleNotFoundError",
    "get_registry",
    "reset_registry",
    "discover_modules",
    "load_modules",
    "shutdown_modules",
    "module",
    "requires_module",
    "optional_module",
    "on_module_loaded",
    "on_all_loaded",
    "before_module_load",
]
