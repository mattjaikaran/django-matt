#!/usr/bin/env python
"""
Framework Comparison Benchmarks.

Compares Django Matt against other frameworks (when available):
- Django REST Framework
- FastAPI (simulated)
- Raw Django

This provides a baseline for performance comparison.

Usage:
    python benchmarks/bench_comparison.py
    python benchmarks/bench_comparison.py --iterations 1000
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import (
    BenchmarkResult,
    format_ops,
    print_environment,
    run_benchmark,
)


def run_comparison_benchmarks(iterations: int = 1000) -> dict[str, list[BenchmarkResult]]:
    """Run comparison benchmarks across frameworks."""
    results = {
        "baseline": [],
        "django_matt": [],
        "drf": [],
        "fastapi": [],
    }

    # Sample data for all tests
    sample_data = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
        "created_at": "2024-01-15T10:30:00Z",
    }

    sample_list = [
        {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"}
        for i in range(20)
    ]

    # ===========================================
    # BASELINE: Pure Python + stdlib json
    # ===========================================
    print("\nBaseline (Pure Python)...")

    results["baseline"].append(
        run_benchmark(
            "json.dumps (dict)",
            json.dumps,
            sample_data,
            iterations=iterations,
        )
    )

    results["baseline"].append(
        run_benchmark(
            "json.dumps (list 20)",
            json.dumps,
            sample_list,
            iterations=iterations,
        )
    )

    json_str = json.dumps(sample_data)
    results["baseline"].append(
        run_benchmark(
            "json.loads (dict)",
            json.loads,
            json_str,
            iterations=iterations,
        )
    )

    # ===========================================
    # DJANGO MATT
    # ===========================================
    try:
        from pydantic import BaseModel

        print("\nDjango Matt (Pydantic)...")

        class UserSchema(BaseModel):
            id: int
            name: str
            email: str
            active: bool = True
            created_at: str | None = None

        # Validation
        results["django_matt"].append(
            run_benchmark(
                "Pydantic validation (dict)",
                lambda: UserSchema(**sample_data),
                iterations=iterations,
            )
        )

        # Serialization
        user_instance = UserSchema(**sample_data)
        results["django_matt"].append(
            run_benchmark(
                "Pydantic model_dump()",
                user_instance.model_dump,
                iterations=iterations,
            )
        )

        results["django_matt"].append(
            run_benchmark(
                "Pydantic model_dump_json()",
                user_instance.model_dump_json,
                iterations=iterations,
            )
        )

        # List serialization
        user_list = [UserSchema(**item, active=True, created_at=None) for item in sample_list]

        def serialize_list():
            return [u.model_dump() for u in user_list]

        results["django_matt"].append(
            run_benchmark(
                "Pydantic list serialize (20)",
                serialize_list,
                iterations=iterations,
            )
        )

        # Check for orjson
        try:
            import orjson

            results["django_matt"].append(
                run_benchmark(
                    "orjson.dumps (dict)",
                    orjson.dumps,
                    sample_data,
                    iterations=iterations,
                )
            )

            results["django_matt"].append(
                run_benchmark(
                    "orjson.dumps (list 20)",
                    orjson.dumps,
                    sample_list,
                    iterations=iterations,
                )
            )
        except ImportError:
            pass

    except ImportError:
        print("\nPydantic not installed, skipping Django Matt benchmarks...")

    # ===========================================
    # DJANGO REST FRAMEWORK
    # ===========================================
    try:
        # Check if DRF is installed
        import rest_framework
        from rest_framework import serializers

        print("\nDjango REST Framework...")

        class UserSerializer(serializers.Serializer):
            id = serializers.IntegerField()
            name = serializers.CharField()
            email = serializers.EmailField()
            active = serializers.BooleanField(default=True)
            created_at = serializers.CharField(required=False, allow_null=True)

        # Validation
        def drf_validate():
            s = UserSerializer(data=sample_data)
            s.is_valid()
            return s.validated_data

        results["drf"].append(
            run_benchmark(
                "DRF validation (dict)",
                drf_validate,
                iterations=iterations,
            )
        )

        # Serialization
        def drf_serialize():
            s = UserSerializer(sample_data)
            return s.data

        results["drf"].append(
            run_benchmark(
                "DRF serialization (dict)",
                drf_serialize,
                iterations=iterations,
            )
        )

        # List serialization
        def drf_serialize_list():
            s = UserSerializer(sample_list, many=True)
            return s.data

        results["drf"].append(
            run_benchmark(
                "DRF serialization (list 20)",
                drf_serialize_list,
                iterations=iterations,
            )
        )

    except ImportError:
        print("\nDjango REST Framework not installed, skipping DRF benchmarks...")

    # ===========================================
    # FASTAPI (simulated with Pydantic)
    # ===========================================
    try:
        from pydantic import BaseModel

        print("\nFastAPI (simulated with Pydantic)...")

        # FastAPI uses Pydantic internally, so we simulate its behavior

        class FastAPIUserModel(BaseModel):
            id: int
            name: str
            email: str
            active: bool = True
            created_at: str | None = None

            class Config:
                from_attributes = True

        # Request validation (similar to FastAPI dependency injection)
        results["fastapi"].append(
            run_benchmark(
                "FastAPI-style validation",
                lambda: FastAPIUserModel.model_validate(sample_data),
                iterations=iterations,
            )
        )

        # Response serialization (FastAPI uses .dict() or .model_dump())
        fastapi_user = FastAPIUserModel(**sample_data)

        results["fastapi"].append(
            run_benchmark(
                "FastAPI-style response",
                fastapi_user.model_dump,
                iterations=iterations,
            )
        )

        # JSONResponse simulation (using orjson if available)
        try:
            import orjson

            def fastapi_json_response():
                data = fastapi_user.model_dump()
                return orjson.dumps(data)

            results["fastapi"].append(
                run_benchmark(
                    "FastAPI JSONResponse (orjson)",
                    fastapi_json_response,
                    iterations=iterations,
                )
            )
        except ImportError:
            def fastapi_json_response():
                data = fastapi_user.model_dump()
                return json.dumps(data)

            results["fastapi"].append(
                run_benchmark(
                    "FastAPI JSONResponse (stdlib)",
                    fastapi_json_response,
                    iterations=iterations,
                )
            )

    except ImportError:
        pass

    return results


def print_comparison_table(results: dict[str, list[BenchmarkResult]]) -> None:
    """Print comparison table across frameworks."""
    print("\n" + "=" * 80)
    print(" Framework Comparison")
    print("=" * 80)

    # Group by operation type
    operations = {}
    for framework, benchmarks in results.items():
        for bench in benchmarks:
            op_name = bench.name.split("(")[0].strip()
            if op_name not in operations:
                operations[op_name] = {}
            operations[op_name][framework] = bench

    # Print header
    frameworks = ["baseline", "django_matt", "drf", "fastapi"]
    header = f"{'Operation':<30}"
    for fw in frameworks:
        if results.get(fw):
            header += f" {fw:>12}"
    print(f"\n{header}")
    print("-" * len(header))

    # Print rows
    for op_name in sorted(operations.keys()):
        row = f"{op_name[:29]:<30}"
        for fw in frameworks:
            if fw in operations[op_name]:
                bench = operations[op_name][fw]
                row += f" {format_ops(bench.ops_per_second):>12}"
            elif results.get(fw):
                row += f" {'N/A':>12}"
        print(row)

    # Print summary
    print("\n" + "-" * 80)
    print("Summary by Framework:")

    for fw in frameworks:
        if results.get(fw):
            benchmarks = results[fw]
            avg_ops = sum(b.ops_per_second for b in benchmarks) / len(benchmarks)
            print(f"  {fw}: {len(benchmarks)} benchmarks, avg {format_ops(avg_ops)}")


def main():
    parser = argparse.ArgumentParser(description="Framework comparison benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=1000,
        help="Number of iterations (default: 1000)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Framework Comparison Benchmarks")
    print("=" * 70)

    print_environment()

    results = run_comparison_benchmarks(iterations=args.iterations)

    print_comparison_table(results)

    # Calculate speedup vs DRF if available
    if results.get("django_matt") and results.get("drf"):
        print("\nSpeedup vs Django REST Framework:")
        dm_benchmarks = {b.name: b for b in results["django_matt"]}
        drf_benchmarks = {b.name: b for b in results["drf"]}

        # Compare similar operations
        comparisons = [
            ("Pydantic validation (dict)", "DRF validation (dict)"),
            ("Pydantic model_dump()", "DRF serialization (dict)"),
        ]

        for dm_name, drf_name in comparisons:
            if dm_name in dm_benchmarks and drf_name in drf_benchmarks:
                dm_ops = dm_benchmarks[dm_name].ops_per_second
                drf_ops = drf_benchmarks[drf_name].ops_per_second
                speedup = dm_ops / drf_ops
                print(f"  {dm_name}: {speedup:.1f}x faster than DRF")


if __name__ == "__main__":
    main()
