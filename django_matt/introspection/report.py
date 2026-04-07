from __future__ import annotations

import platform
import sys
import time
from typing import Any

import django

from pydantic import BaseModel, Field

import django_matt


class InfraReport(BaseModel):
    timestamp: float
    framework_version: str
    python_version: str
    django_version: str
    platform: str
    debug: bool = False
    installed_apps: list[str] = Field(default_factory=list)
    middleware_stack: list[str] = Field(default_factory=list)
    enabled_modules: list[str] = Field(default_factory=list)
    database_backend: str = ""
    cache_backend: str = ""
    route_count: int = 0
    health: dict[str, Any] = Field(default_factory=dict)


async def generate_report() -> InfraReport:
    from django.conf import settings

    from django_matt.introspection.registry import registry

    health_result = await registry.health_check()

    enabled_modules = _detect_modules()

    db_conf = getattr(settings, "DATABASES", {}).get("default", {})
    cache_conf = getattr(settings, "CACHES", {}).get("default", {})
    middleware = list(getattr(settings, "MIDDLEWARE", []))
    installed_apps = list(getattr(settings, "INSTALLED_APPS", []))
    route_count = _count_routes()

    return InfraReport(
        timestamp=time.time(),
        framework_version=django_matt.__version__,
        python_version=sys.version,
        django_version=django.__version__,
        platform=platform.platform(),
        debug=getattr(settings, "DEBUG", False),
        installed_apps=installed_apps,
        middleware_stack=middleware,
        enabled_modules=enabled_modules,
        database_backend=db_conf.get("ENGINE", ""),
        cache_backend=cache_conf.get("BACKEND", ""),
        route_count=route_count,
        health={
            "status": health_result.status.value,
            "components": {
                name: {
                    "status": comp.status.value,
                    "latency_ms": comp.latency_ms,
                    "error": comp.error,
                }
                for name, comp in health_result.components.items()
            },
        },
    )


def _detect_modules() -> list[str]:
    import importlib

    modules = []
    candidates = [
        "auth", "billing", "websockets", "flags", "analytics",
        "experiments", "graphql", "messaging", "notifications",
        "email", "ai", "ml", "files", "tasks", "audit", "htmx",
        "multitenancy", "observability", "inspector", "introspection",
    ]
    for mod_name in candidates:
        try:
            importlib.import_module(f"django_matt.{mod_name}")
            modules.append(mod_name)
        except ImportError:
            pass
    return modules


def _count_routes() -> int:
    try:
        from django.urls import get_resolver

        resolver = get_resolver()
        return _count_url_patterns(resolver.url_patterns)
    except Exception:
        return 0


def _count_url_patterns(patterns: list) -> int:
    count = 0
    for pattern in patterns:
        if hasattr(pattern, "url_patterns"):
            count += _count_url_patterns(pattern.url_patterns)
        else:
            count += 1
    return count
