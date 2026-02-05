#!/usr/bin/env python
"""
Pydantic Schema Validation Benchmarks for Django Matt.

Tests performance of:
- Simple schema validation
- Nested schema validation
- Schema with custom validators
- Model serialization (model_dump)
- Bulk validation

Usage:
    python benchmarks/bench_schema.py
    python benchmarks/bench_schema.py --iterations 10000
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import (
    BenchmarkResult,
    print_environment,
    print_table,
    run_benchmark,
)


def run_schema_benchmarks(iterations: int = 5000) -> list[BenchmarkResult]:
    """Run all schema validation benchmarks."""
    results = []

    try:
        from pydantic import BaseModel, Field, field_validator
    except ImportError:
        print("Pydantic not installed, skipping schema benchmarks")
        return results

    # Define test schemas
    class SimpleSchema(BaseModel):
        id: int
        name: str
        email: str
        active: bool = True

    class AddressSchema(BaseModel):
        street: str
        city: str
        state: str
        zip_code: str = Field(pattern=r"^\d{5}$")

    class NestedSchema(BaseModel):
        id: int
        name: str
        email: str
        address: AddressSchema
        tags: list[str] = []

    class ValidatedSchema(BaseModel):
        id: int
        name: str = Field(min_length=1, max_length=100)
        email: str
        age: int = Field(ge=0, le=150)
        score: float = Field(ge=0.0, le=100.0)

        @field_validator("email")
        @classmethod
        def validate_email(cls, v: str) -> str:
            if "@" not in v:
                raise ValueError("Invalid email format")
            return v.lower()

    # Sample data
    simple_data = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
    }

    nested_data = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "address": {
            "street": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
        },
        "tags": ["python", "django", "pydantic"],
    }

    validated_data = {
        "id": 1,
        "name": "Test User",
        "email": "test@example.com",
        "age": 30,
        "score": 85.5,
    }

    # --- Simple Schema ---
    print("Benchmarking SimpleSchema...")

    results.append(
        run_benchmark(
            "SimpleSchema validation",
            lambda: SimpleSchema(**simple_data),
            iterations=iterations,
        )
    )

    simple_instance = SimpleSchema(**simple_data)
    results.append(
        run_benchmark(
            "SimpleSchema.model_dump()",
            simple_instance.model_dump,
            iterations=iterations,
        )
    )

    results.append(
        run_benchmark(
            "SimpleSchema.model_dump_json()",
            simple_instance.model_dump_json,
            iterations=iterations,
        )
    )

    # --- Nested Schema ---
    print("Benchmarking NestedSchema...")

    results.append(
        run_benchmark(
            "NestedSchema validation",
            lambda: NestedSchema(**nested_data),
            iterations=iterations,
        )
    )

    nested_instance = NestedSchema(**nested_data)
    results.append(
        run_benchmark(
            "NestedSchema.model_dump()",
            nested_instance.model_dump,
            iterations=iterations,
        )
    )

    # --- Validated Schema (with custom validators) ---
    print("Benchmarking ValidatedSchema...")

    results.append(
        run_benchmark(
            "ValidatedSchema validation",
            lambda: ValidatedSchema(**validated_data),
            iterations=iterations,
        )
    )

    # --- Bulk Validation ---
    print("Benchmarking bulk validation...")

    bulk_items = [
        {
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "active": True,
        }
        for i in range(100)
    ]

    def validate_bulk():
        return [SimpleSchema(**item) for item in bulk_items]

    results.append(
        run_benchmark(
            "SimpleSchema bulk validation (100)",
            validate_bulk,
            iterations=iterations // 10,
        )
    )

    # --- Model construction from dict ---
    print("Benchmarking model_validate...")

    results.append(
        run_benchmark(
            "SimpleSchema.model_validate(dict)",
            lambda: SimpleSchema.model_validate(simple_data),
            iterations=iterations,
        )
    )

    # --- JSON parsing ---
    print("Benchmarking model_validate_json...")

    simple_json = simple_instance.model_dump_json()
    results.append(
        run_benchmark(
            "SimpleSchema.model_validate_json()",
            lambda: SimpleSchema.model_validate_json(simple_json),
            iterations=iterations,
        )
    )

    # --- Django Matt ModelSchema (if available) ---
    try:
        from django_matt.core.schema import ModelSchema

        print("Benchmarking Django Matt ModelSchema...")

        class TestModelSchema(ModelSchema):
            id: int
            name: str
            email: str

            class Config:
                from_attributes = True

        test_data = {"id": 1, "name": "Test", "email": "test@example.com"}

        results.append(
            run_benchmark(
                "ModelSchema validation",
                lambda: TestModelSchema(**test_data),
                iterations=iterations,
            )
        )

    except ImportError:
        print("  django_matt not available, skipping ModelSchema...")

    return results


def main():
    parser = argparse.ArgumentParser(description="Schema validation benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5000,
        help="Number of iterations (default: 5000)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Schema Validation Benchmarks")
    print("=" * 70)

    print_environment()

    results = run_schema_benchmarks(iterations=args.iterations)

    if results:
        print_table(results, "Schema Validation Results")

        # Summary
        fastest = min(results, key=lambda r: r.mean_time_ms)
        print(f"Fastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")


if __name__ == "__main__":
    main()
