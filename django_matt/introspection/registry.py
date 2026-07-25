"""Infrastructure component registry with async health check orchestration."""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

logger = logging.getLogger("django_matt.introspection")


class ComponentStatus(str, Enum):
    """Health status values for infrastructure components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentInfo(BaseModel):
    """Health check result for a single infrastructure component."""

    name: str
    component_type: str
    status: ComponentStatus = ComponentStatus.UNKNOWN
    version: str | None = None
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    critical: bool = True


class HealthResult(BaseModel):
    """Aggregate health check result across all registered components."""

    status: ComponentStatus
    components: dict[str, ComponentInfo]
    timestamp: float


CheckFn = Callable[[], Coroutine[Any, Any, ComponentInfo]]


class InfraRegistry:
    """Registry of infrastructure components with parallel health check execution."""

    def __init__(self) -> None:
        self._components: dict[str, tuple[str, CheckFn, bool]] = {}

    def register(
        self,
        name: str,
        component_type: str,
        check_fn: CheckFn,
        *,
        critical: bool = True,
    ) -> None:
        """Register a component with its health check function."""
        self._components[name] = (component_type, check_fn, critical)

    def unregister(self, name: str) -> None:
        """Remove a component from the registry."""
        self._components.pop(name, None)

    def clear(self) -> None:
        self._components.clear()

    @property
    def registered(self) -> list[str]:
        return list(self._components.keys())

    async def health_check(self) -> HealthResult:
        """Run all registered health checks in parallel and return aggregate result."""
        components: dict[str, ComponentInfo] = {}
        tasks = {}

        for name, (component_type, check_fn, critical) in self._components.items():
            tasks[name] = (component_type, check_fn, critical)

        results = await asyncio.gather(
            *[self._run_check(name, ct, fn, crit) for name, (ct, fn, crit) in tasks.items()],
            return_exceptions=True,
        )

        overall = ComponentStatus.HEALTHY
        for name_key, result in zip(tasks.keys(), results):
            ct, _, crit = tasks[name_key]
            if isinstance(result, Exception):
                info = ComponentInfo(
                    name=name_key,
                    component_type=ct,
                    status=ComponentStatus.UNHEALTHY,
                    error=str(result),
                    critical=crit,
                )
            else:
                info = result

            components[name_key] = info

            if info.status == ComponentStatus.UNHEALTHY and info.critical:
                overall = ComponentStatus.UNHEALTHY
            elif info.status == ComponentStatus.DEGRADED and overall != ComponentStatus.UNHEALTHY:
                overall = ComponentStatus.DEGRADED

        return HealthResult(
            status=overall,
            components=components,
            timestamp=time.time(),
        )

    async def _run_check(
        self,
        name: str,
        component_type: str,
        check_fn: CheckFn,
        critical: bool,
    ) -> ComponentInfo:
        start = time.monotonic()
        try:
            info = await check_fn()
            info.latency_ms = (time.monotonic() - start) * 1000
            info.critical = critical
            return info
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.warning("Health check failed for %s: %s", name, e)
            return ComponentInfo(
                name=name,
                component_type=component_type,
                status=ComponentStatus.UNHEALTHY,
                latency_ms=elapsed,
                error=str(e),
                critical=critical,
            )


registry = InfraRegistry()
