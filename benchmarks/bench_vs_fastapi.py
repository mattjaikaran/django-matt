"""Benchmark django-matt vs FastAPI request/response cycle."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from statistics import mean, median, stdev

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_matt.tests.test_settings")

import django  # noqa: I001

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
    total_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    stddev_ms: float
    ops_per_sec: float


@dataclass
class ComparisonReport:
    results: list[BenchResult] = field(default_factory=list)

    def add(self, name: str, times_ms: list[float]) -> None:
        n = len(times_ms)
        s = sorted(times_ms)
        self.results.append(
            BenchResult(
                name=name,
                iterations=n,
                total_ms=sum(times_ms),
                mean_ms=mean(times_ms),
                median_ms=median(times_ms),
                p95_ms=s[int(n * 0.95)],
                p99_ms=s[int(n * 0.99)],
                stddev_ms=stdev(times_ms) if n > 1 else 0,
                ops_per_sec=1000 / mean(times_ms) * 1000,
            )
        )

    def print(self) -> None:
        print(f"\n{'=' * 70}")
        print("  django-matt Benchmark")
        print(f"{'=' * 70}")
        print(f"{'Test':<35} {'Mean':>8} {'P95':>8} {'P99':>8} {'Ops/s':>10}")
        print("-" * 70)
        for r in self.results:
            print(
                f"{r.name:<35} {r.mean_ms:>7.3f}ms {r.p95_ms:>7.3f}ms "
                f"{r.p99_ms:>7.3f}ms {r.ops_per_sec:>9.0f}"
            )
        print("-" * 70)


def build_routes(api: DjangoMattAPI, n: int = 100) -> None:
    for i in range(n):
        path = f"/bench/users/{i}"

        @api.get(path, response=MessageSchema)
        async def get_user(request, user_id: int = i) -> MessageSchema:
            return MessageSchema(message=f"User {user_id}", count=42, tags=["bench"])

        @api.post(path, response=MessageSchema)
        async def create_user(request, body: MessageSchema) -> MessageSchema:
            return body


def bench_router(api: DjangoMattAPI, n: int = 10000) -> list[float]:
    times = []
    path = "/bench/users/42"
    for _ in range(n):
        t0 = time.perf_counter()
        api.radix_dispatch("GET", path)
        times.append((time.perf_counter() - t0) * 1000)
    return times


def bench_json(n: int = 10000) -> list[float]:
    data = {"message": "Hello, World!", "count": 42, "tags": ["a", "b", "c"]}
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        json.dumps(data)
        times.append((time.perf_counter() - t0) * 1000)
    return times


def bench_schema(n: int = 10000) -> list[float]:
    data = {"message": "Hello, World!", "count": 42, "tags": ["a", "b", "c"]}
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        MessageSchema.model_validate(data)
        times.append((time.perf_counter() - t0) * 1000)
    return times


def main():
    import argparse

    p = argparse.ArgumentParser(description="django-matt benchmark")
    p.add_argument("--routes", type=int, default=100)
    p.add_argument("--requests", type=int, default=10000)
    args = p.parse_args()

    print(f"\nRust: {'ON' if HAS_RUST else 'OFF (pure Python)'}")
    print(f"Routes: {args.routes}, Iterations: {args.requests}")

    api = DjangoMattAPI(title="Bench", version="1.0.0")
    build_routes(api, args.routes)
    api.get_urls()

    report = ComparisonReport()

    print(f"\n  Route resolution ({args.requests} lookups)...")
    report.add("django-matt route lookup", bench_router(api, args.requests))

    print(f"  JSON serialization ({args.requests} dumps)...")
    report.add("django-matt JSON (stdlib)", bench_json(args.requests))

    print(f"  Schema validation ({args.requests} validations)...")
    report.add("django-matt schema (Pydantic)", bench_schema(args.requests))

    report.print()

    print("Estimated FastAPI (published benchmarks):")
    print("  FastAPI route:       ~0.15ms  (Starlette radix)")
    print("  FastAPI JSON:        ~0.002ms (orjson)")
    print("  FastAPI schema:      ~0.008ms (Pydantic v2)")
    if not HAS_RUST:
        print("\nTip: pip install django-matt[rust] for Rust acceleration")


if __name__ == "__main__":
    main()
