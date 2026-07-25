"""CLI commands for listing, inspecting, and checking module health."""

from __future__ import annotations

from typing import Any


def get_module_commands() -> dict[str, Any]:
    """Return the CLI command mapping for module management."""
    return {
        "modules list": modules_list,
        "modules info": modules_info,
        "modules check": modules_check,
    }


def modules_list() -> None:
    """Print a table of all registered modules with their status."""
    from django_matt.modules.registry import get_registry

    registry = get_registry()

    registered = registry.list_registered()
    if not registered:
        print("No modules registered.")
        return

    loaded = {m.name for m in registry.list_loaded()}

    print(f"{'Name':<20} {'Version':<10} {'Status':<10} {'Dependencies'}")
    print("-" * 70)
    for mod in registered:
        status = "loaded" if mod.name in loaded else "registered"
        deps = ", ".join(mod.dependencies) if mod.dependencies else "-"
        print(f"{mod.name:<20} {mod.version:<10} {status:<10} {deps}")


def modules_info(name: str) -> None:
    """Print detailed information about a specific module."""
    from django_matt.modules.registry import get_registry

    registry = get_registry()

    if not registry.is_registered(name):
        print(f"Module {name!r} not found.")
        return

    mod = registry._modules[name]
    is_loaded = registry.is_loaded(name)

    print(f"Name:         {mod.name}")
    print(f"Version:      {mod.version}")
    print(f"Class:        {mod.__class__.__qualname__}")
    print(f"Status:       {'loaded' if is_loaded else 'registered'}")
    print(f"Dependencies: {', '.join(mod.dependencies) or 'none'}")
    print(f"Config NS:    {mod.config_namespace or 'none'}")
    print(f"URLs:         {len(mod.get_urls())} patterns")
    print(f"Middleware:    {len(mod.get_middleware())} classes")
    print(f"Checks:       {len(mod.get_checks())} checks")


def modules_check() -> list[str]:
    """Check all modules for missing dependencies and config validation errors."""
    from django_matt.modules.registry import get_registry

    registry = get_registry()
    issues: list[str] = []

    for mod in registry.list_registered():
        for dep in mod.dependencies:
            if not registry.is_registered(dep):
                issues.append(f"Module {mod.name!r} depends on {dep!r}, which is not registered")

        if mod.config_schema and mod.config_namespace:
            config = registry._configs.get(mod.config_namespace, {})
            try:
                mod.validate_config(config)
            except Exception as exc:
                issues.append(f"Module {mod.name!r} config validation failed: {exc}")

    if not issues:
        print("All modules OK.")
    else:
        for issue in issues:
            print(f"  ERROR: {issue}")

    return issues
