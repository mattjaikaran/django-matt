"""
Benchmark utilities for Django Matt.

This module provides common utilities for all benchmark scripts.
"""

import gc
import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Storage directory for results
BENCHMARK_DIR = Path(__file__).parent.parent / ".matt" / "benchmarks"


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    total_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float
    ops_per_second: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time_ms, 4),
            "mean_time_ms": round(self.mean_time_ms, 6),
            "median_time_ms": round(self.median_time_ms, 6),
            "min_time_ms": round(self.min_time_ms, 6),
            "max_time_ms": round(self.max_time_ms, 6),
            "std_dev_ms": round(self.std_dev_ms, 6),
            "ops_per_second": round(self.ops_per_second, 2),
            "metadata": self.metadata,
        }


def run_benchmark(
    name: str,
    func: Callable[..., Any],
    *args,
    iterations: int = 1000,
    warmup: int = 10,
    **kwargs,
) -> BenchmarkResult:
    """
    Run a benchmark on a function.

    Args:
        name: Name of the benchmark
        func: Function to benchmark
        *args: Arguments to pass to the function
        iterations: Number of iterations to run
        warmup: Number of warmup iterations
        **kwargs: Keyword arguments to pass to the function

    Returns:
        BenchmarkResult with timing statistics
    """
    # Warmup phase
    for _ in range(warmup):
        func(*args, **kwargs)

    # Force garbage collection before measuring
    gc.collect()
    gc.disable()

    try:
        times: list[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

    finally:
        gc.enable()

    # Calculate statistics
    total_time = sum(times)
    mean_time = statistics.mean(times)
    median_time = statistics.median(times)
    min_time = min(times)
    max_time = max(times)
    std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
    ops_per_second = 1000 / mean_time if mean_time > 0 else float("inf")

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_ms=total_time,
        mean_time_ms=mean_time,
        median_time_ms=median_time,
        min_time_ms=min_time,
        max_time_ms=max_time,
        std_dev_ms=std_dev,
        ops_per_second=ops_per_second,
    )


def format_time(ms: float) -> str:
    """Format time in milliseconds to human-readable string."""
    if ms < 0.001:
        return f"{ms * 1_000_000:.2f}ns"
    if ms < 1:
        return f"{ms * 1000:.2f}us"
    if ms < 1000:
        return f"{ms:.3f}ms"
    return f"{ms / 1000:.3f}s"


def format_ops(ops: float) -> str:
    """Format operations per second to human-readable string."""
    if ops >= 1_000_000:
        return f"{ops / 1_000_000:.2f}M ops/s"
    if ops >= 1_000:
        return f"{ops / 1_000:.2f}K ops/s"
    return f"{ops:.2f} ops/s"


def print_result(result: BenchmarkResult, indent: int = 0) -> None:
    """Print a benchmark result to console."""
    prefix = " " * indent
    print(f"{prefix}{result.name}")
    print(f"{prefix}  Mean:   {format_time(result.mean_time_ms)}")
    print(f"{prefix}  Ops/s:  {format_ops(result.ops_per_second)}")
    print(f"{prefix}  Min:    {format_time(result.min_time_ms)}")
    print(f"{prefix}  Max:    {format_time(result.max_time_ms)}")
    print(f"{prefix}  StdDev: {format_time(result.std_dev_ms)}")


def print_table(results: list[BenchmarkResult], title: str = "") -> None:
    """Print benchmark results as a formatted table."""
    if title:
        print(f"\n{'=' * 70}")
        print(f" {title}")
        print(f"{'=' * 70}")

    # Header
    print(f"\n{'Benchmark':<35} {'Mean':>12} {'Ops/s':>15} {'StdDev':>12}")
    print("-" * 74)

    # Rows
    for result in sorted(results, key=lambda r: r.mean_time_ms):
        name = result.name[:34]
        mean = format_time(result.mean_time_ms)
        ops = format_ops(result.ops_per_second)
        std = format_time(result.std_dev_ms)
        print(f"{name:<35} {mean:>12} {ops:>15} {std:>12}")

    print()


def save_results(results: list[BenchmarkResult], filename: str | None = None) -> Path:
    """Save benchmark results to JSON file."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{timestamp}.json"

    filepath = BENCHMARK_DIR / filename

    data = {
        "timestamp": datetime.now().isoformat(),
        "results": [r.to_dict() for r in results],
        "metadata": get_environment_metadata(),
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    # Also save as latest
    latest_path = BENCHMARK_DIR / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def load_baseline(filename: str = "latest.json") -> list[BenchmarkResult]:
    """Load baseline results from JSON file."""
    filepath = BENCHMARK_DIR / filename

    if not filepath.exists():
        return []

    with open(filepath) as f:
        data = json.load(f)

    results = []
    for r in data.get("results", []):
        results.append(
            BenchmarkResult(
                name=r["name"],
                iterations=r["iterations"],
                total_time_ms=r["total_time_ms"],
                mean_time_ms=r["mean_time_ms"],
                median_time_ms=r["median_time_ms"],
                min_time_ms=r["min_time_ms"],
                max_time_ms=r["max_time_ms"],
                std_dev_ms=r["std_dev_ms"],
                ops_per_second=r["ops_per_second"],
                metadata=r.get("metadata", {}),
            )
        )

    return results


def compare_results(
    current: list[BenchmarkResult],
    baseline: list[BenchmarkResult],
    threshold_percent: float = 5.0,
) -> list[dict[str, Any]]:
    """Compare current results with baseline."""
    baseline_map = {r.name: r for r in baseline}
    comparisons = []

    for curr in current:
        base = baseline_map.get(curr.name)
        if base is None:
            continue

        if base.mean_time_ms > 0:
            diff_percent = (curr.mean_time_ms - base.mean_time_ms) / base.mean_time_ms * 100
        else:
            diff_percent = 0.0

        if abs(diff_percent) <= threshold_percent:
            status = "same"
        elif diff_percent < 0:
            status = "faster"
        else:
            status = "slower"

        comparisons.append(
            {
                "name": curr.name,
                "current_mean_ms": curr.mean_time_ms,
                "baseline_mean_ms": base.mean_time_ms,
                "diff_percent": diff_percent,
                "status": status,
            }
        )

    return comparisons


def print_comparison(comparisons: list[dict[str, Any]]) -> None:
    """Print comparison results."""
    print(f"\n{'=' * 70}")
    print(" Comparison with Baseline")
    print(f"{'=' * 70}")

    print(f"\n{'Benchmark':<35} {'Current':>10} {'Baseline':>10} {'Diff':>10} {'Status':>8}")
    print("-" * 73)

    for comp in sorted(comparisons, key=lambda c: c["diff_percent"]):
        name = comp["name"][:34]
        curr = format_time(comp["current_mean_ms"])
        base = format_time(comp["baseline_mean_ms"])
        diff = f"{comp['diff_percent']:+.1f}%"
        status = comp["status"]

        # Color codes
        if status == "faster":
            status_str = f"\033[32m{status}\033[0m"
        elif status == "slower":
            status_str = f"\033[31m{status}\033[0m"
        else:
            status_str = status

        print(f"{name:<35} {curr:>10} {base:>10} {diff:>10} {status_str:>8}")

    # Summary
    faster = len([c for c in comparisons if c["status"] == "faster"])
    slower = len([c for c in comparisons if c["status"] == "slower"])
    same = len([c for c in comparisons if c["status"] == "same"])

    print(f"\nSummary: {faster} faster, {slower} slower, {same} same")


def get_environment_metadata() -> dict[str, Any]:
    """Get environment information."""
    import platform
    import sys

    metadata = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
    }

    # Check for optional libraries
    try:
        import orjson

        metadata["orjson_version"] = orjson.__version__
    except ImportError:
        metadata["orjson_version"] = None

    try:
        import ujson

        metadata["ujson_version"] = ujson.__version__
    except ImportError:
        metadata["ujson_version"] = None

    try:
        import pydantic

        metadata["pydantic_version"] = pydantic.__version__
    except ImportError:
        metadata["pydantic_version"] = None

    return metadata


def print_environment() -> None:
    """Print environment information."""
    metadata = get_environment_metadata()

    print("\nEnvironment:")
    print(f"  Python: {metadata['python_version']}")
    print(f"  Platform: {metadata['platform']}")
    if metadata.get("orjson_version"):
        print(f"  orjson: {metadata['orjson_version']}")
    if metadata.get("ujson_version"):
        print(f"  ujson: {metadata['ujson_version']}")
    if metadata.get("pydantic_version"):
        print(f"  pydantic: {metadata['pydantic_version']}")
    print()
