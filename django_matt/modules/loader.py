from __future__ import annotations

from django_matt.modules.registry import discover_modules, get_registry


async def load_modules() -> None:
    discover_modules()
    registry = get_registry()
    registry.resolve_dependencies()
    await registry.load_all()


async def shutdown_modules() -> None:
    registry = get_registry()
    await registry.unload_all()
