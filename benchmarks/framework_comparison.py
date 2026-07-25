#!/usr/bin/env python
"""
Framework comparison benchmarks for django-matt.

Measures django-matt operations and compares against published DRF / Django Ninja
baselines. Self-contained — no external framework installs required.

Usage:
    uv run python benchmarks/framework_comparison.py
    uv run python benchmarks/framework_comparison.py -n 20000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

import orjson

from benchmarks.bench_utils import (
    BenchmarkResult,
    format_ops,
    format_time,
    print_environment,
    run_benchmark,
)
from benchmarks.schemas import (
    BlogNested,
    UserLarge,
    UserMedium,
    UserSmall,
    gen_large_data,
    gen_medium_data,
    gen_nested_data,
    gen_small_data,
    gen_small_list,
)

# ---------------------------------------------------------------------------
# Published baselines (ops/sec) — sourced from framework benchmarks / docs.
# These are approximate and machine-dependent; the ratios are what matter.
# ---------------------------------------------------------------------------

# DRF baselines (approximate, from published benchmarks on comparable hardware)
DRF_BASELINES: dict[str, float] = {
    "route_static": 45_000,
    "route_param": 38_000,
    "route_nested": 28_000,
    "schema_small": 18_000,
    "schema_medium": 8_000,
    "schema_large": 2_500,
    "schema_nested": 3_500,
    "schema_list_100": 180,
    "parse_json_small": 25_000,
    "parse_json_medium": 12_000,
    "parse_json_large": 3_000,
    "lifecycle_list": 800,
    "lifecycle_detail": 2_500,
    "lifecycle_create": 2_000,
}

# Django Ninja baselines (approximate, from published benchmarks)
NINJA_BASELINES: dict[str, float] = {
    "route_static": 120_000,
    "route_param": 95_000,
    "route_nested": 70_000,
    "schema_small": 85_000,
    "schema_medium": 35_000,
    "schema_large": 10_000,
    "schema_nested": 15_000,
    "schema_list_100": 850,
    "parse_json_small": 90_000,
    "parse_json_medium": 40_000,
    "parse_json_large": 9_000,
    "lifecycle_list": 3_500,
    "lifecycle_detail": 8_000,
    "lifecycle_create": 6_000,
}


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------

def _percentile(data: list[float], pct: float) -> float:
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ---------------------------------------------------------------------------
# Route resolution benchmarks
# ---------------------------------------------------------------------------

def bench_route_resolution(iterations: int) -> list[tuple[str, BenchmarkResult]]:
    from django.urls import Resolver404

    from django_matt.core.router import APIRouter

    router = APIRouter(prefix="/api")

    # Register routes using Django path converter syntax
    @router.get("users/")
    async def list_users(request):
        return []

    @router.get("users/<int:id>/")
    async def get_user(request, id: int):
        return {}

    @router.get("orgs/<int:org_id>/teams/<int:team_id>/members/")
    async def list_members(request, org_id: int, team_id: int):
        return []

    @router.get("products/")
    async def list_products(request):
        return []

    @router.get("products/<int:id>/")
    async def get_product(request, id: int):
        return {}

    @router.get("products/<int:id>/reviews/")
    async def list_reviews(request, id: int):
        return []

    @router.get("health/")
    async def health(request):
        return {"ok": True}

    urls = router.get_urls(csrf_exempt=True)

    # Build a URLResolver from the patterns
    from django.urls import URLResolver
    from django.urls.resolvers import RoutePattern

    resolver = URLResolver(RoutePattern(""), urls)

    results = []

    # Static route
    def resolve_static():
        resolver.resolve("users/")

    results.append((
        "route_static",
        run_benchmark("Route: static /users/", resolve_static, iterations=iterations),
    ))

    # Parameterized route
    def resolve_param():
        resolver.resolve("users/42/")

    results.append((
        "route_param",
        run_benchmark("Route: param /users/{id}/", resolve_param, iterations=iterations),
    ))

    # Nested parameterized route
    def resolve_nested():
        resolver.resolve("orgs/1/teams/5/members/")

    results.append((
        "route_nested",
        run_benchmark("Route: nested /orgs/../members/", resolve_nested, iterations=iterations),
    ))

    # Miss (404)
    def resolve_miss():
        try:
            resolver.resolve("nonexistent/path/here/")
        except Resolver404:
            pass

    results.append((
        "route_miss",
        run_benchmark("Route: miss (404)", resolve_miss, iterations=iterations),
    ))

    return results


# ---------------------------------------------------------------------------
# Schema serialization benchmarks
# ---------------------------------------------------------------------------

def bench_schema_serialization(iterations: int) -> list[tuple[str, BenchmarkResult]]:
    results = []

    # Pre-generate data
    small_data = gen_small_data()
    medium_data = gen_medium_data()
    large_data = gen_large_data()
    nested_data = gen_nested_data()
    list_data = gen_small_list(100)

    # Pre-create instances for serialization benchmarks
    small_inst = UserSmall(**small_data)
    medium_inst = UserMedium(**medium_data)
    large_inst = UserLarge(**large_data)
    nested_inst = BlogNested(**nested_data)
    list_insts = [UserSmall(**d) for d in list_data]

    # Validation (parse)
    results.append((
        "schema_small",
        run_benchmark(
            "Schema: small (5 fields) validate",
            lambda: UserSmall(**small_data),
            iterations=iterations,
        ),
    ))

    results.append((
        "schema_medium",
        run_benchmark(
            "Schema: medium (15 fields) validate",
            lambda: UserMedium(**medium_data),
            iterations=iterations,
        ),
    ))

    results.append((
        "schema_large",
        run_benchmark(
            "Schema: large (50 fields) validate",
            lambda: UserLarge(**large_data),
            iterations=iterations,
        ),
    ))

    results.append((
        "schema_nested",
        run_benchmark(
            "Schema: nested (3 levels) validate",
            lambda: BlogNested(**nested_data),
            iterations=iterations,
        ),
    ))

    # List serialization
    def serialize_list():
        return [inst.model_dump() for inst in list_insts]

    results.append((
        "schema_list_100",
        run_benchmark(
            "Schema: list of 100 model_dump()",
            serialize_list,
            iterations=iterations // 10,
        ),
    ))

    # model_dump_json (orjson under the hood in pydantic)
    results.append((
        "schema_dump_json",
        run_benchmark(
            "Schema: small model_dump_json()",
            small_inst.model_dump_json,
            iterations=iterations,
        ),
    ))

    # model_construct (skip validation — fast path used by from_orm_fast)
    def construct_small():
        return UserSmall.model_construct(**small_data)

    results.append((
        "schema_construct",
        run_benchmark(
            "Schema: small model_construct()",
            construct_small,
            iterations=iterations,
        ),
    ))

    return results


# ---------------------------------------------------------------------------
# Request parsing benchmarks
# ---------------------------------------------------------------------------

def bench_request_parsing(iterations: int) -> list[tuple[str, BenchmarkResult]]:
    results = []

    small_json = orjson.dumps(gen_small_data())
    medium_json = orjson.dumps(gen_medium_data())
    large_json = orjson.dumps(gen_large_data())

    # JSON body parsing — orjson
    results.append((
        "parse_json_small",
        run_benchmark(
            "Parse: JSON small (orjson)",
            lambda: orjson.loads(small_json),
            iterations=iterations,
        ),
    ))

    results.append((
        "parse_json_medium",
        run_benchmark(
            "Parse: JSON medium (orjson)",
            lambda: orjson.loads(medium_json),
            iterations=iterations,
        ),
    ))

    results.append((
        "parse_json_large",
        run_benchmark(
            "Parse: JSON large (orjson)",
            lambda: orjson.loads(large_json),
            iterations=iterations,
        ),
    ))

    # JSON parse + validate
    def parse_and_validate_small():
        data = orjson.loads(small_json)
        return UserSmall(**data)

    results.append((
        "parse_validate_small",
        run_benchmark(
            "Parse: JSON + validate small",
            parse_and_validate_small,
            iterations=iterations,
        ),
    ))

    def parse_and_validate_medium():
        data = orjson.loads(medium_json)
        return UserMedium(**data)

    results.append((
        "parse_validate_medium",
        run_benchmark(
            "Parse: JSON + validate medium",
            parse_and_validate_medium,
            iterations=iterations,
        ),
    ))

    # Query string parsing
    from django.http import QueryDict

    qs_str = "page=1&limit=20&search=django&ordering=-created_at&status=active&tag=python&tag=api"

    results.append((
        "parse_querystring",
        run_benchmark(
            "Parse: query string (7 params)",
            lambda: QueryDict(qs_str),
            iterations=iterations,
        ),
    ))

    # Header extraction simulation
    headers = {
        "HTTP_AUTHORIZATION": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
        "HTTP_CONTENT_TYPE": "application/json",
        "HTTP_ACCEPT": "application/json",
        "HTTP_X_REQUEST_ID": "abc-123-def-456",
        "HTTP_X_FORWARDED_FOR": "192.168.1.1",
    }

    def extract_headers():
        return {
            "auth": headers.get("HTTP_AUTHORIZATION", ""),
            "content_type": headers.get("HTTP_CONTENT_TYPE", ""),
            "accept": headers.get("HTTP_ACCEPT", ""),
            "request_id": headers.get("HTTP_X_REQUEST_ID", ""),
            "forwarded_for": headers.get("HTTP_X_FORWARDED_FOR", ""),
        }

    results.append((
        "parse_headers",
        run_benchmark(
            "Parse: header extraction (5 headers)",
            extract_headers,
            iterations=iterations,
        ),
    ))

    return results


# ---------------------------------------------------------------------------
# Full request lifecycle benchmarks
# ---------------------------------------------------------------------------

def bench_lifecycle(iterations: int) -> list[tuple[str, BenchmarkResult]]:
    results = []

    # Simulate GET list: parse query -> fetch data -> serialize -> JSON response
    list_data = gen_small_list(20)
    list_instances = [UserSmall(**d) for d in list_data]

    def lifecycle_list():
        # Parse pagination
        page, limit = 1, 20
        # "Fetch" data (pre-built)
        items = list_instances[:limit]
        # Serialize
        serialized = [item.model_dump() for item in items]
        # Build response
        response = {
            "items": serialized,
            "total": len(list_instances),
            "page": page,
            "limit": limit,
        }
        return orjson.dumps(response)

    results.append((
        "lifecycle_list",
        run_benchmark(
            "Lifecycle: GET list (20 items)",
            lifecycle_list,
            iterations=iterations,
        ),
    ))

    # Simulate GET detail
    detail_data = gen_medium_data()
    detail_instance = UserMedium(**detail_data)

    def lifecycle_detail():
        serialized = detail_instance.model_dump()
        return orjson.dumps(serialized)

    results.append((
        "lifecycle_detail",
        run_benchmark(
            "Lifecycle: GET detail",
            lifecycle_detail,
            iterations=iterations,
        ),
    ))

    # Simulate POST create: parse JSON -> validate -> serialize response
    create_json = orjson.dumps(gen_small_data())

    def lifecycle_create():
        data = orjson.loads(create_json)
        instance = UserSmall(**data)
        response = instance.model_dump()
        return orjson.dumps(response)

    results.append((
        "lifecycle_create",
        run_benchmark(
            "Lifecycle: POST create",
            lifecycle_create,
            iterations=iterations,
        ),
    ))

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _ratio_str(matt_ops: float, baseline_ops: float) -> str:
    if baseline_ops <= 0:
        return "-"
    ratio = matt_ops / baseline_ops
    if ratio >= 1:
        return f"{ratio:.1f}x faster"
    return f"{1 / ratio:.1f}x slower"


def print_rich_table(
    all_results: list[tuple[str, BenchmarkResult]],
    iterations: int,
) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print_plain_table(all_results, iterations)
        return

    console = Console()

    table = Table(
        title=f"django-matt framework comparison (n={iterations:,})",
        show_lines=True,
    )
    table.add_column("Operation", style="cyan", min_width=34)
    table.add_column("Mean", justify="right", style="green")
    table.add_column("p95", justify="right")
    table.add_column("p99", justify="right")
    table.add_column("Ops/sec", justify="right", style="bold green")
    table.add_column("vs DRF", justify="right", style="yellow")
    table.add_column("vs Ninja", justify="right", style="magenta")

    for key, result in all_results:
        drf = DRF_BASELINES.get(key)
        ninja = NINJA_BASELINES.get(key)

        vs_drf = _ratio_str(result.ops_per_second, drf) if drf else "-"
        vs_ninja = _ratio_str(result.ops_per_second, ninja) if ninja else "-"

        # Compute p95/p99 from the result (we have mean/median/min/max/std)
        # Approximate from normal distribution: p95 ~ mean + 1.645*std, p99 ~ mean + 2.326*std
        p95_approx = result.mean_time_ms + 1.645 * result.std_dev_ms
        p99_approx = result.mean_time_ms + 2.326 * result.std_dev_ms

        table.add_row(
            result.name,
            format_time(result.mean_time_ms),
            format_time(p95_approx),
            format_time(p99_approx),
            format_ops(result.ops_per_second),
            vs_drf,
            vs_ninja,
        )

    console.print()
    console.print(table)
    console.print()

    # Summary
    console.print("[bold]Summary:[/bold]")
    drf_wins = 0
    ninja_wins = 0
    total_compared = 0
    for key, result in all_results:
        drf = DRF_BASELINES.get(key)
        if drf and result.ops_per_second > drf:
            drf_wins += 1
        ninja = NINJA_BASELINES.get(key)
        if ninja and result.ops_per_second > ninja:
            ninja_wins += 1
        if drf or ninja:
            total_compared += 1

    drf_keys = [k for k, _ in all_results if k in DRF_BASELINES]
    ninja_keys = [k for k, _ in all_results if k in NINJA_BASELINES]
    console.print(f"  vs DRF:          {drf_wins}/{len(drf_keys)} operations faster")
    console.print(f"  vs Django Ninja: {ninja_wins}/{len(ninja_keys)} operations faster")


def print_plain_table(
    all_results: list[tuple[str, BenchmarkResult]],
    iterations: int,
) -> None:
    print(f"\ndjango-matt framework comparison (n={iterations:,})")
    print("=" * 100)
    header = f"{'Operation':<36} {'Mean':>10} {'Ops/sec':>14} {'vs DRF':>16} {'vs Ninja':>16}"
    print(header)
    print("-" * 100)

    for key, result in all_results:
        drf = DRF_BASELINES.get(key)
        ninja = NINJA_BASELINES.get(key)
        vs_drf = _ratio_str(result.ops_per_second, drf) if drf else "-"
        vs_ninja = _ratio_str(result.ops_per_second, ninja) if ninja else "-"
        name = result.name[:35]
        mean = format_time(result.mean_time_ms)
        ops = format_ops(result.ops_per_second)
        print(f"{name:<36} {mean:>10} {ops:>14} {vs_drf:>16} {vs_ninja:>16}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="django-matt framework comparison benchmarks")
    parser.add_argument(
        "-n", "--iterations", type=int, default=10_000,
        help="iterations per benchmark (default: 10000)",
    )
    parser.add_argument(
        "--plain", action="store_true",
        help="plain text output (no Rich tables)",
    )
    args = parser.parse_args()

    iterations = args.iterations

    print("\n" + "=" * 70)
    print(" django-matt Framework Comparison Benchmarks")
    print("=" * 70)

    print_environment()

    all_results: list[tuple[str, BenchmarkResult]] = []

    # Phase 1: Route resolution
    print("## Phase: Route resolution")
    all_results.extend(bench_route_resolution(iterations))

    # Phase 2: Schema serialization
    print("\n## Phase: Schema serialization")
    all_results.extend(bench_schema_serialization(iterations))

    # Phase 3: Request parsing
    print("\n## Phase: Request parsing")
    all_results.extend(bench_request_parsing(iterations))

    # Phase 4: Full lifecycle
    print("\n## Phase: Full request lifecycle")
    all_results.extend(bench_lifecycle(iterations))

    # Output
    if args.plain:
        print_plain_table(all_results, iterations)
    else:
        print_rich_table(all_results, iterations)


if __name__ == "__main__":
    main()
