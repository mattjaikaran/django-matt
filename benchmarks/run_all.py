#!/usr/bin/env python
"""
Run all Django Matt benchmarks.

This script runs all available benchmarks and generates a comprehensive report.

Usage:
    python benchmarks/run_all.py
    python benchmarks/run_all.py --comparison          # include framework comparison
    python benchmarks/run_all.py --rich                # use RichTableReporter output
    python benchmarks/run_all.py --format json --output results.json
    python benchmarks/run_all.py --compare
    python benchmarks/run_all.py --save
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_database import run_database_benchmarks
from benchmarks.bench_json import run_json_benchmarks
from benchmarks.bench_schema import run_schema_benchmarks
from benchmarks.bench_throughput import run_pydantic_throughput, run_throughput_benchmarks
from benchmarks.bench_utils import (
    BenchmarkResult,
    compare_results,
    get_environment_metadata,
    load_baseline,
    print_comparison,
    print_environment,
    print_table,
    save_results,
)


def run_all_benchmarks(
    iterations_multiplier: float = 1.0,
    skip: list[str] | None = None,
    include_comparison: bool = False,
) -> dict[str, list[BenchmarkResult]]:
    """
    Run all benchmark suites.

    Args:
        iterations_multiplier: Multiply default iterations by this factor
        skip: List of benchmark suites to skip
        include_comparison: Include FrameworkComparisonScenario results

    Returns:
        Dict mapping suite name to list of results
    """
    skip = skip or []
    results = {}

    # Framework comparison (django-matt vs DRF, ninja, FastAPI, Starlette)
    if include_comparison:
        print("\n" + "=" * 70)
        print(" Running Framework Comparison Benchmarks")
        print("=" * 70)
        try:
            from django_matt.benchmarks.comparison import FrameworkComparisonScenario

            scenario = FrameworkComparisonScenario(
                iterations=int(1000 * iterations_multiplier), warmup=10
            )
            comparison_results = scenario.run()
            # Convert to bench_utils BenchmarkResult for downstream compatibility
            converted: list[BenchmarkResult] = []
            for r in comparison_results:
                converted.append(
                    BenchmarkResult(
                        name=r.name,
                        total_time_ms=r.total_time_ms,
                        mean_time_ms=r.mean_time_ms,
                        median_time_ms=r.median_time_ms,
                        min_time_ms=r.min_time_ms,
                        max_time_ms=r.max_time_ms,
                        std_dev_ms=r.std_dev_ms,
                        ops_per_second=r.ops_per_second,
                        iterations=r.iterations,
                        metadata=r.metadata,
                    )
                )
            results["comparison"] = converted
        except Exception as exc:
            print(f"  Warning: framework comparison failed: {exc}")

    # JSON benchmarks
    if "json" not in skip:
        print("\n" + "=" * 70)
        print(" Running JSON Benchmarks")
        print("=" * 70)
        results["json"] = run_json_benchmarks(iterations=int(5000 * iterations_multiplier))

    # Schema benchmarks
    if "schema" not in skip:
        print("\n" + "=" * 70)
        print(" Running Schema Benchmarks")
        print("=" * 70)
        results["schema"] = run_schema_benchmarks(iterations=int(5000 * iterations_multiplier))

    # Database benchmarks
    if "database" not in skip:
        print("\n" + "=" * 70)
        print(" Running Database Benchmarks")
        print("=" * 70)
        results["database"] = run_database_benchmarks(iterations=int(500 * iterations_multiplier))

    # Throughput benchmarks
    if "throughput" not in skip:
        print("\n" + "=" * 70)
        print(" Running Throughput Benchmarks")
        print("=" * 70)
        throughput_results = run_throughput_benchmarks(iterations=int(5000 * iterations_multiplier))
        throughput_results.extend(
            run_pydantic_throughput(iterations=int(5000 * iterations_multiplier))
        )
        results["throughput"] = throughput_results

    return results


def flatten_results(grouped_results: dict[str, list[BenchmarkResult]]) -> list[BenchmarkResult]:
    """Flatten grouped results into a single list."""
    all_results = []
    for suite_results in grouped_results.values():
        all_results.extend(suite_results)
    return all_results


def generate_markdown_report(
    results: dict[str, list[BenchmarkResult]],
    metadata: dict,
) -> str:
    """Generate a Markdown report."""
    lines = []
    lines.append("# Django Matt Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Environment
    lines.append("## Environment")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    for key, value in metadata.items():
        if value:
            lines.append(f"| {key} | {value} |")
    lines.append("")

    # Results by suite
    lines.append("## Results")
    lines.append("")

    for suite_name, suite_results in results.items():
        lines.append(f"### {suite_name.title()}")
        lines.append("")
        lines.append("| Benchmark | Mean | Ops/s | Min | Max |")
        lines.append("|-----------|------|-------|-----|-----|")

        for result in sorted(suite_results, key=lambda r: r.mean_time_ms):
            from benchmarks.bench_utils import format_ops, format_time

            mean = format_time(result.mean_time_ms)
            ops = format_ops(result.ops_per_second)
            min_t = format_time(result.min_time_ms)
            max_t = format_time(result.max_time_ms)
            lines.append(f"| {result.name} | {mean} | {ops} | {min_t} | {max_t} |")

        lines.append("")

    # Summary
    all_results = flatten_results(results)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total benchmarks**: {len(all_results)}")
    lines.append(f"- **Total iterations**: {sum(r.iterations for r in all_results):,}")
    lines.append("")

    if all_results:
        fastest = min(all_results, key=lambda r: r.mean_time_ms)
        lines.append(f"**Fastest**: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")

    return "\n".join(lines)


def generate_json_report(
    results: dict[str, list[BenchmarkResult]],
    metadata: dict,
) -> str:
    """Generate a JSON report."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata,
        "suites": {},
        "summary": {},
    }

    all_results = []
    for suite_name, suite_results in results.items():
        data["suites"][suite_name] = [r.to_dict() for r in suite_results]
        all_results.extend(suite_results)

    data["summary"] = {
        "total_benchmarks": len(all_results),
        "total_iterations": sum(r.iterations for r in all_results),
    }

    if all_results:
        fastest = min(all_results, key=lambda r: r.mean_time_ms)
        data["summary"]["fastest"] = fastest.to_dict()

    return json.dumps(data, indent=2)


def _save_to_matt_benchmarks(all_results: list[BenchmarkResult], metadata: dict) -> Path:
    """Save results to .matt/benchmarks/ as a timestamped JSON file."""
    import orjson

    storage_dir = Path(".matt/benchmarks")
    storage_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = storage_dir / f"benchmark_{timestamp}.json"

    data = {
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata,
        "results": [r.to_dict() for r in all_results],
        "summary": {
            "total_benchmarks": len(all_results),
            "total_iterations": sum(r.iterations for r in all_results),
        },
    }

    with open(filepath, "wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    # Also keep a "latest" copy
    latest_path = storage_dir / "latest.json"
    with open(latest_path, "wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Run all Django Matt benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=float,
        default=1.0,
        help="Iterations multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        choices=["json", "schema", "database", "throughput"],
        help="Benchmark suites to skip",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["console", "json", "markdown"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results for future comparison",
    )
    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Compare with baseline",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Regression threshold percentage (default: 5.0)",
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        default=True,
        help="Use RichTableReporter for terminal output (default: True)",
    )
    parser.add_argument(
        "--no-rich",
        dest="rich",
        action="store_false",
        help="Disable RichTableReporter; fall back to ANSI console output",
    )
    parser.add_argument(
        "--comparison",
        action="store_true",
        help="Include FrameworkComparisonScenario (django-matt vs DRF/ninja/FastAPI/Starlette)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Django Matt Benchmark Suite")
    print("=" * 70)

    print_environment()

    # Run benchmarks
    results = run_all_benchmarks(
        iterations_multiplier=args.iterations,
        skip=args.skip,
        include_comparison=args.comparison,
    )

    all_results = flatten_results(results)
    metadata = get_environment_metadata()

    # Generate output
    if args.format == "json":
        output = generate_json_report(results, metadata)
    elif args.format == "markdown":
        output = generate_markdown_report(results, metadata)
    elif args.rich and args.comparison and results.get("comparison"):
        # Use RichTableReporter for the comparison section
        try:
            from django_matt.benchmarks.comparison import FrameworkComparisonScenario
            from django_matt.benchmarks.reporters import RichTableReporter

            # Re-run comparison scenario to get proper BenchmarkResult objects
            scenario = FrameworkComparisonScenario(
                iterations=int(1000 * args.iterations), warmup=10
            )
            rich_results = scenario.run()

            reporter = RichTableReporter()
            reporter.print_report(rich_results)
        except Exception as exc:
            print(f"Rich reporter failed, falling back: {exc}")
            for suite_name, suite_results in results.items():
                print_table(suite_results, f"{suite_name.title()} Results")

        # Also print standard suites
        for suite_name, suite_results in results.items():
            if suite_name != "comparison":
                print_table(suite_results, f"{suite_name.title()} Results")
        output = None
    else:
        # Console output
        for suite_name, suite_results in results.items():
            print_table(suite_results, f"{suite_name.title()} Results")

        # Summary
        print("\n" + "=" * 70)
        print(" Summary")
        print("=" * 70)
        print(f"\nTotal benchmarks: {len(all_results)}")
        print(f"Total iterations: {sum(r.iterations for r in all_results):,}")

        if all_results:
            non_skipped = [r for r in all_results if not r.metadata.get("skipped")]
            if non_skipped:
                fastest = min(non_skipped, key=lambda r: r.mean_time_ms)
                slowest = max(non_skipped, key=lambda r: r.mean_time_ms)
                print(f"\nFastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")
                print(f"Slowest: {slowest.name} ({slowest.ops_per_second:,.0f} ops/s)")

        output = None

    # Handle output
    if output:
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"\nResults saved to {args.output}")
        else:
            print(output)

    # Always save to .matt/benchmarks/ (timestamped JSON)
    saved_path = _save_to_matt_benchmarks(all_results, metadata)
    print(f"\nResults saved to {saved_path}")

    # Legacy save results
    if args.save:
        filepath = save_results(all_results)
        print(f"Legacy baseline saved to {filepath}")

    # Compare with baseline
    if args.compare:
        baseline = load_baseline()
        if baseline:
            comparisons = compare_results(all_results, baseline, args.threshold)
            print_comparison(comparisons)

            # Check for regressions
            regressions = [c for c in comparisons if c["status"] == "slower"]
            if regressions:
                print(f"\nWarning: {len(regressions)} performance regressions detected!")
                sys.exit(1)
        else:
            print("\nNo baseline found. Run with --save first to create a baseline.")


if __name__ == "__main__":
    main()
