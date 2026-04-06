from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MetricsCollector(Protocol):
    name: str

    def collect(self) -> dict[str, Any]: ...

    def reset(self) -> None: ...


@dataclass
class _HistogramBucket:
    count: int = 0
    total: float = 0.0
    min_val: float = float("inf")
    max_val: float = float("-inf")
    values: list[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value
        self.values.append(value)

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count else 0.0

    def percentile(self, p: float) -> float:
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * p)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]


class RequestMetricsCollector:
    name: str = "requests"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_count = 0
        self._error_count = 0
        self._by_method: dict[str, int] = defaultdict(int)
        self._by_status: dict[int, int] = defaultdict(int)
        self._durations = _HistogramBucket()

    def record(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
    ) -> None:
        with self._lock:
            self._total_count += 1
            self._by_method[method] += 1
            self._by_status[status_code] += 1
            self._durations.observe(duration)
            if status_code >= 400:
                self._error_count += 1

    def collect(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_requests": self._total_count,
                "error_count": self._error_count,
                "error_rate": self._error_count / self._total_count if self._total_count else 0.0,
                "by_method": dict(self._by_method),
                "by_status": dict(self._by_status),
                "duration": {
                    "count": self._durations.count,
                    "avg_ms": self._durations.avg * 1000,
                    "min_ms": self._durations.min_val * 1000 if self._durations.count else 0.0,
                    "max_ms": self._durations.max_val * 1000 if self._durations.count else 0.0,
                    "p50_ms": self._durations.percentile(0.5) * 1000,
                    "p95_ms": self._durations.percentile(0.95) * 1000,
                    "p99_ms": self._durations.percentile(0.99) * 1000,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._total_count = 0
            self._error_count = 0
            self._by_method.clear()
            self._by_status.clear()
            self._durations = _HistogramBucket()


class DatabaseMetricsCollector:
    name: str = "database"

    def __init__(self, slow_query_threshold_ms: float = 100.0) -> None:
        self._lock = threading.Lock()
        self._query_count = 0
        self._by_operation: dict[str, int] = defaultdict(int)
        self._durations = _HistogramBucket()
        self._slow_queries: list[dict[str, Any]] = []
        self._slow_threshold = slow_query_threshold_ms

    def record(
        self,
        operation: str,
        table: str,
        duration: float,
        sql: str | None = None,
    ) -> None:
        with self._lock:
            self._query_count += 1
            self._by_operation[operation] += 1
            self._durations.observe(duration)
            duration_ms = duration * 1000
            if duration_ms > self._slow_threshold:
                self._slow_queries.append({
                    "operation": operation,
                    "table": table,
                    "duration_ms": duration_ms,
                    "sql": sql[:200] if sql else None,
                    "timestamp": time.time(),
                })
                if len(self._slow_queries) > 100:
                    self._slow_queries = self._slow_queries[-100:]

    def collect(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_queries": self._query_count,
                "by_operation": dict(self._by_operation),
                "duration": {
                    "count": self._durations.count,
                    "avg_ms": self._durations.avg * 1000,
                    "min_ms": self._durations.min_val * 1000 if self._durations.count else 0.0,
                    "max_ms": self._durations.max_val * 1000 if self._durations.count else 0.0,
                    "p50_ms": self._durations.percentile(0.5) * 1000,
                    "p95_ms": self._durations.percentile(0.95) * 1000,
                    "p99_ms": self._durations.percentile(0.99) * 1000,
                },
                "slow_queries": list(self._slow_queries),
            }

    def reset(self) -> None:
        with self._lock:
            self._query_count = 0
            self._by_operation.clear()
            self._durations = _HistogramBucket()
            self._slow_queries.clear()


class CacheMetricsCollector:
    name: str = "cache"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0
        self._latencies = _HistogramBucket()

    def record_hit(self, duration: float = 0.0) -> None:
        with self._lock:
            self._hits += 1
            if duration:
                self._latencies.observe(duration)

    def record_miss(self, duration: float = 0.0) -> None:
        with self._lock:
            self._misses += 1
            if duration:
                self._latencies.observe(duration)

    def record_set(self, duration: float = 0.0) -> None:
        with self._lock:
            self._sets += 1
            if duration:
                self._latencies.observe(duration)

    def record_delete(self, duration: float = 0.0) -> None:
        with self._lock:
            self._deletes += 1
            if duration:
                self._latencies.observe(duration)

    def collect(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "deletes": self._deletes,
                "hit_rate": self._hits / total if total else 0.0,
                "total_operations": total + self._sets + self._deletes,
                "latency": {
                    "count": self._latencies.count,
                    "avg_ms": self._latencies.avg * 1000,
                    "p50_ms": self._latencies.percentile(0.5) * 1000,
                    "p95_ms": self._latencies.percentile(0.95) * 1000,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._sets = 0
            self._deletes = 0
            self._latencies = _HistogramBucket()


class MetricsRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, MetricsCollector] = {}
        self._lock = threading.Lock()

    def register(self, collector: MetricsCollector) -> None:
        with self._lock:
            self._collectors[collector.name] = collector

    def unregister(self, name: str) -> None:
        with self._lock:
            self._collectors.pop(name, None)

    def get(self, name: str) -> MetricsCollector | None:
        return self._collectors.get(name)

    def collect_all(self) -> dict[str, Any]:
        with self._lock:
            return {name: c.collect() for name, c in self._collectors.items()}

    def reset_all(self) -> None:
        with self._lock:
            for c in self._collectors.values():
                c.reset()

    @property
    def collectors(self) -> dict[str, MetricsCollector]:
        return dict(self._collectors)


metrics_registry = MetricsRegistry()

__all__ = [
    "CacheMetricsCollector",
    "DatabaseMetricsCollector",
    "MetricsCollector",
    "MetricsRegistry",
    "RequestMetricsCollector",
    "metrics_registry",
]
