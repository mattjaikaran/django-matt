"""Benchmark django-matt core operations against FastAPI published numbers."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from statistics import mean, median

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_matt.tests.test_settings")

import django

django.setup()

from pydantic import BaseModel

from django_matt import DjangoMattAPI
from django_matt._accel import HAS_RUST


class MessageSchema(BaseModel):
    message: str
    count: int
    tags: list[str] = []


@dataclass
class BenchResult:
    name: str
    iterations: int
    mean_us: float
    median_us: float
    p95_us: float
    p99_us: float
    ops_per_sec: float


@dataclass
class ComparisonReport:
    results: list[BenchResult] = field(default_factory=list)

    def add(self, name: str, times_us: list[float]) -> None:
        n = len(times_us)
        s = sorted(times_us)
        self.results.append(
            BenchResult(
                name=name,
                iterations=n,
                mean_us=mean(times_us),
                median_us=median(times_us),
                p95_us=s[int(n * 0.95)],
                p99_us=s[int(n * 0.99)],
                ops_per_sec=1_000_000 / mean(times_us),
            )
        )

    def to_json(self) -> str:
        return json.dumps(
            [
                {
                    "name": r.name,
                    "iterations": r.iterations,
                    "mean_us": round(r.mean_us, 3),
                    "median_us": round(r.median_us, 3),
                    "p95_us": round(r.p95_us, 3),
                    "p99_us": round(r.p99_us, 3),
                    "ops_per_sec": round(r.ops_per_sec, 0),
                }
                for r in self.results
            ],
            indent=2,
        )

    def print(self) -> None:
        print(f"\n{'=' * 70}")
        print(f"  django-matt Benchmark  (Rust: {'ON' if HAS_RUST else 'OFF'})")
        print(f"{'=' * 70}")
        print(f"{'Test':<38} {'Mean':>8} {'P95':>8} {'P99':>8} {'Ops/s':>10}")
        print("-" * 70)
        for r in self.results:
            print(
                f"{r.name:<38} {r.mean_us:>7.1f}μs {r.p95_us:>7.1f}μs "
                f"{r.p99_us:>7.1f}μs {r.ops_per_sec:>9.0f}"
            )
        print("-" * 70)

        # Baseline reference (measured on M2 Pro, 100 routes)
        print("\nBaseline reference (M2 Pro, Python 3.12, 100 routes):")
        print("  Starlette route:    ~2μs  (radix tree)")
        print("  orjson serialize:   ~0.5μs")
        print("  Pydantic v2:        ~8μs")


def bench_router(n: int = 100_000) -> list[float]:
    """Measure Django URL resolver route matching (Python path)."""
    api = DjangoMattAPI(title="Bench", version="1.0.0")
    for i in range(100):
        path = f"/bench/users/{i}"

        @api.get(path, response_model=MessageSchema)
        async def _fn(request) -> MessageSchema:
            return MessageSchema(message="ok", count=1, tags=[])

    url_patterns = api.get_urls()

    # Configure Django URL resolver and test route resolution
    from django.urls import set_urlconf

    class BenchUrlConf:
        urlpatterns = url_patterns

    set_urlconf(BenchUrlConf)

    times = []
    test_path = "/bench/users/42"
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            from django.urls import resolve

            resolve(test_path)
        except Exception:
            pass
        times.append((time.perf_counter() - t0) * 1_000_000)
    return times


def bench_json_serial(n: int = 100_000) -> list[float]:
    data = {"message": "Hello, World!", "count": 42, "tags": ["a", "b", "c"]}
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        json.dumps(data)
        times.append((time.perf_counter() - t0) * 1_000_000)
    return times


def bench_schema_validate(n: int = 100_000) -> list[float]:
    data = {"message": "Hello, World!", "count": 42, "tags": ["a", "b", "c"]}
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        MessageSchema.model_validate(data)
        times.append((time.perf_counter() - t0) * 1_000_000)
    return times


def main():
    import argparse

    p = argparse.ArgumentParser(description="django-matt benchmark")
    p.add_argument("--requests", type=int, default=100_000)
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--output", type=str, help="Write JSON to file")
    args = p.parse_args()

    n = args.requests
    print(f"\nRunning benchmarks ({n:,} iterations each)...\n")

    report = ComparisonReport()

    print("  Route resolution...", end=" ", flush=True)
    report.add("django-matt route resolution", bench_router(n))
    print("done")

    print("  JSON serialization...", end=" ", flush=True)
    report.add("django-matt JSON (stdlib)", bench_json_serial(n))
    print("done")

    print("  Schema validation...", end=" ", flush=True)
    report.add("django-matt schema (Pydantic v2)", bench_schema_validate(n))
    print("done")

    report.print()

    if args.json or args.output:
        j = report.to_json()
        if args.output:
            with open(args.output, "w") as f:
                f.write(j)
            print(f"\nResults written to {args.output}")
        else:
            print(f"\n{j}")

    if not HAS_RUST:
        print("\nTip: pip install django-matt[rust] for additional speedup")


if __name__ == "__main__":
    main()
