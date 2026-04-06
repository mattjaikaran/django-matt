from __future__ import annotations

import importlib
import logging
import time
from typing import Any

logger = logging.getLogger("django_matt.startup")

# Module-level storage for profiling results
_profile_results: dict[str, float] | None = None


def profile_imports() -> dict[str, float]:
    from django_matt.slim import CORE_MODULES, MODULE_MIDDLEWARE

    all_modules = sorted(
        set(CORE_MODULES)
        | set(MODULE_MIDDLEWARE.keys())
        | {
            "views", "permissions", "config", "pagination", "filtering",
            "billing", "ai", "ml", "graphql", "websockets", "analytics",
            "experiments", "notifications", "email", "messaging", "files",
            "tasks", "audit", "htmx", "components", "deployment",
            "observability", "throttling", "versioning", "di",
            "multitenancy", "typegen", "testing", "utils", "admin",
            "resources", "inspector",
        }
    )

    results: dict[str, float] = {}
    for module_name in all_modules:
        full_path = f"django_matt.{module_name}"
        start = time.perf_counter()
        try:
            importlib.import_module(full_path)
            elapsed = time.perf_counter() - start
            results[module_name] = round(elapsed * 1000, 3)  # ms
        except ImportError:
            results[module_name] = -1.0  # not importable
        except Exception as e:
            logger.debug("Failed to import %s: %s", full_path, e)
            results[module_name] = -1.0

    return results


class StartupProfiler:
    def __init__(self) -> None:
        self._results: dict[str, float] = {}
        self._total_ms: float = 0.0
        self._start_time: float = 0.0

    def __enter__(self) -> StartupProfiler:
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        global _profile_results
        self._results = profile_imports()
        self._total_ms = round((time.perf_counter() - self._start_time) * 1000, 3)
        _profile_results = self._results
        logger.info(
            "Startup profiling complete: %d modules in %.1fms",
            len(self._results),
            self._total_ms,
        )

    @property
    def results(self) -> dict[str, float]:
        return dict(self._results)

    @property
    def total_ms(self) -> float:
        return self._total_ms

    @property
    def slowest(self, n: int = 5) -> list[tuple[str, float]]:
        importable = {k: v for k, v in self._results.items() if v >= 0}
        return sorted(importable.items(), key=lambda x: x[1], reverse=True)[:n]

    def summary(self) -> dict[str, Any]:
        importable = {k: v for k, v in self._results.items() if v >= 0}
        failed = [k for k, v in self._results.items() if v < 0]
        return {
            "total_ms": self._total_ms,
            "module_count": len(importable),
            "failed_count": len(failed),
            "failed_modules": failed,
            "slowest_5": sorted(
                importable.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }


def get_profile_results() -> dict[str, float] | None:
    return _profile_results
