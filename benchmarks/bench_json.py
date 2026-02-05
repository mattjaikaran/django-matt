#!/usr/bin/env python
"""
JSON Serialization Benchmarks for Django Matt.

Compares performance of:
- Standard library json
- orjson (if available)
- ujson (if available)
- Django Matt FastJSONRenderer

Usage:
    python benchmarks/bench_json.py
    python benchmarks/bench_json.py --iterations 10000
"""

import argparse
import json
import random
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import (
    BenchmarkResult,
    print_environment,
    print_table,
    run_benchmark,
)


def generate_random_string(length: int = 10) -> str:
    """Generate a random string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_small_data() -> dict:
    """Generate small sample data."""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
    }


def generate_medium_data() -> dict:
    """Generate medium sample data."""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "profile": {
            "bio": "A test user biography " * 10,
            "website": "https://example.com",
            "location": "New York, NY",
            "social": {
                "twitter": "@testuser",
                "github": "testuser",
                "linkedin": "testuser",
            },
        },
        "tags": ["python", "django", "api", "testing"],
        "settings": {
            "notifications": True,
            "theme": "dark",
            "language": "en",
            "timezone": "America/New_York",
        },
    }


def generate_large_data() -> dict:
    """Generate large sample data with nested items."""
    return {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "items": [
            {
                "id": i,
                "title": f"Item {i}",
                "description": f"Description for item {i} " * 20,
                "price": random.uniform(10, 1000),
                "quantity": random.randint(1, 100),
                "categories": [generate_random_string(8) for _ in range(5)],
                "metadata": {
                    "weight": random.uniform(0.1, 10.0),
                    "dimensions": {
                        "width": random.uniform(1, 100),
                        "height": random.uniform(1, 100),
                        "depth": random.uniform(1, 100),
                    },
                },
            }
            for i in range(100)
        ],
    }


def generate_list_data(count: int = 100) -> list:
    """Generate a list of sample objects."""
    return [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "active": random.choice([True, False]),
            "score": random.uniform(0, 100),
            "created_at": (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
        }
        for i in range(count)
    ]


def run_json_benchmarks(iterations: int = 5000) -> list[BenchmarkResult]:
    """Run all JSON serialization benchmarks."""
    results = []

    # Generate test data
    small_data = generate_small_data()
    medium_data = generate_medium_data()
    large_data = generate_large_data()
    list_data = generate_list_data(100)

    # --- Standard library json ---
    print("Benchmarking json (stdlib)...")

    results.append(
        run_benchmark(
            "json.dumps (small)",
            json.dumps,
            small_data,
            iterations=iterations,
        )
    )

    results.append(
        run_benchmark(
            "json.dumps (medium)",
            json.dumps,
            medium_data,
            iterations=iterations,
        )
    )

    results.append(
        run_benchmark(
            "json.dumps (large)",
            json.dumps,
            large_data,
            iterations=iterations // 10,
        )
    )

    results.append(
        run_benchmark(
            "json.dumps (list 100)",
            json.dumps,
            list_data,
            iterations=iterations,
        )
    )

    # json.loads
    small_json = json.dumps(small_data)
    results.append(
        run_benchmark(
            "json.loads (small)",
            json.loads,
            small_json,
            iterations=iterations,
        )
    )

    # --- orjson ---
    try:
        import orjson

        print("Benchmarking orjson...")

        results.append(
            run_benchmark(
                "orjson.dumps (small)",
                orjson.dumps,
                small_data,
                iterations=iterations,
            )
        )

        results.append(
            run_benchmark(
                "orjson.dumps (medium)",
                orjson.dumps,
                medium_data,
                iterations=iterations,
            )
        )

        results.append(
            run_benchmark(
                "orjson.dumps (large)",
                orjson.dumps,
                large_data,
                iterations=iterations // 10,
            )
        )

        results.append(
            run_benchmark(
                "orjson.dumps (list 100)",
                orjson.dumps,
                list_data,
                iterations=iterations,
            )
        )

        # orjson.loads
        small_orjson = orjson.dumps(small_data)
        results.append(
            run_benchmark(
                "orjson.loads (small)",
                orjson.loads,
                small_orjson,
                iterations=iterations,
            )
        )

    except ImportError:
        print("  orjson not installed, skipping...")

    # --- ujson ---
    try:
        import ujson

        print("Benchmarking ujson...")

        results.append(
            run_benchmark(
                "ujson.dumps (small)",
                ujson.dumps,
                small_data,
                iterations=iterations,
            )
        )

        results.append(
            run_benchmark(
                "ujson.dumps (medium)",
                ujson.dumps,
                medium_data,
                iterations=iterations,
            )
        )

        results.append(
            run_benchmark(
                "ujson.dumps (list 100)",
                ujson.dumps,
                list_data,
                iterations=iterations,
            )
        )

        small_ujson = ujson.dumps(small_data)
        results.append(
            run_benchmark(
                "ujson.loads (small)",
                ujson.loads,
                small_ujson,
                iterations=iterations,
            )
        )

    except ImportError:
        print("  ujson not installed, skipping...")

    # --- Django Matt FastJSONRenderer ---
    try:
        # Configure Django settings if not already configured
        import django
        from django.conf import settings

        if not settings.configured:
            settings.configure(DEBUG=False)

        from django_matt.utils.performance import FastJSONRenderer

        print("Benchmarking FastJSONRenderer...")

        results.append(
            run_benchmark(
                f"FastJSONRenderer.dumps (medium)",
                FastJSONRenderer.dumps,
                medium_data,
                iterations=iterations,
            )
        )

    except (ImportError, Exception) as e:
        print(f"  FastJSONRenderer skipped: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="JSON serialization benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5000,
        help="Number of iterations (default: 5000)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" JSON Serialization Benchmarks")
    print("=" * 70)

    print_environment()

    results = run_json_benchmarks(iterations=args.iterations)

    print_table(results, "JSON Serialization Results")

    # Summary
    if results:
        fastest = min(results, key=lambda r: r.mean_time_ms)
        print(f"Fastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")


if __name__ == "__main__":
    main()
