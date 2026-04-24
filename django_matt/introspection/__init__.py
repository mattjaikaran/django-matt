"""Health checks, infrastructure reporting, and readiness/liveness probes."""

from __future__ import annotations

from django_matt.introspection.checks import (
    check_cache,
    check_celery,
    check_database,
    check_email,
    check_redis,
    check_storage,
)
from django_matt.introspection.endpoints import get_health_urls
from django_matt.introspection.middleware import HealthCheckMiddleware
from django_matt.introspection.registry import (
    ComponentInfo,
    ComponentStatus,
    InfraRegistry,
    registry,
)
from django_matt.introspection.report import InfraReport, generate_report

__all__ = [
    "ComponentInfo",
    "ComponentStatus",
    "HealthCheckMiddleware",
    "InfraRegistry",
    "InfraReport",
    "check_cache",
    "check_celery",
    "check_database",
    "check_email",
    "check_redis",
    "check_storage",
    "generate_report",
    "get_health_urls",
    "registry",
]
