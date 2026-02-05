"""
Django Matt Benchmark Scripts.

This package contains standalone benchmark scripts for measuring
Django Matt framework performance.

Usage:
    python benchmarks/run_all.py        # Run all benchmarks
    python benchmarks/bench_json.py     # JSON serialization
    python benchmarks/bench_schema.py   # Schema validation
    python benchmarks/bench_database.py # Database operations
    python benchmarks/bench_throughput.py  # Request throughput
    python benchmarks/bench_comparison.py  # Framework comparison
"""

from benchmarks.bench_utils import (
    BenchmarkResult,
    compare_results,
    format_ops,
    format_time,
    get_environment_metadata,
    load_baseline,
    print_comparison,
    print_environment,
    print_result,
    print_table,
    run_benchmark,
    save_results,
)

__all__ = [
    "BenchmarkResult",
    "run_benchmark",
    "format_time",
    "format_ops",
    "print_result",
    "print_table",
    "save_results",
    "load_baseline",
    "compare_results",
    "print_comparison",
    "get_environment_metadata",
    "print_environment",
]
