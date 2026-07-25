#!/usr/bin/env python
"""
Framework Comparison Benchmarks.

Compares Django Matt against other frameworks (when available):
- Django REST Framework
- django-ninja
- FastAPI / Starlette

Uses FrameworkComparisonScenario from django_matt.benchmarks.comparison as the
implementation.  Missing frameworks are shown as [NOT INSTALLED] rows rather
than silently omitted.

Usage:
    python benchmarks/bench_comparison.py
    python benchmarks/bench_comparison.py --iterations 1000
    python benchmarks/bench_comparison.py --no-rich
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.bench_utils import print_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Framework comparison benchmarks")
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=1000,
        help="Number of iterations (default: 1000)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Number of warmup iterations (default: 10)",
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        default=True,
        help="Use RichTableReporter (default: True)",
    )
    parser.add_argument(
        "--no-rich",
        dest="rich",
        action="store_false",
        help="Disable RichTableReporter; use plain text output",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" Framework Comparison Benchmarks")
    print("=" * 70)

    print_environment()

    from django_matt.benchmarks.comparison import FrameworkComparisonScenario
    from django_matt.benchmarks.reporters import RichTableReporter

    print("\nRunning FrameworkComparisonScenario...")
    scenario = FrameworkComparisonScenario(iterations=args.iterations, warmup=args.warmup)
    results = scenario.run()

    # Print results
    if args.rich:
        reporter = RichTableReporter()
        reporter.print_report(results)
    else:
        # Plain text fallback
        print("\n" + "=" * 80)
        print(" Framework Comparison Results")
        print("=" * 80)
        header = f"{'Framework':<20} {'Name':<30} {'Ops/s':>12} {'Median (ms)':>12}"
        print(header)
        print("-" * len(header))
        for r in results:
            fw = r.metadata.get("framework", "-")
            if r.metadata.get("skipped"):
                print(f"  {fw:<18} {r.name:<30} {'[NOT INSTALLED]':>12}")
            else:
                ops = r.ops_per_second
                ops_str = f"{ops / 1_000:.1f}K" if ops >= 1_000 else f"{ops:.0f}"
                print(f"  {fw:<18} {r.name:<30} {ops_str:>12} {r.median_time_ms:>12.3f}")

    # Calculate speedup vs DRF
    list_by_fw: dict[str, float] = {}
    for r in results:
        if "list" in r.name.lower() and not r.metadata.get("skipped"):
            fw = r.metadata.get("framework", r.name)
            list_by_fw[fw] = r.ops_per_second

    if "django-matt" in list_by_fw and "DRF" in list_by_fw:
        speedup = list_by_fw["django-matt"] / list_by_fw["DRF"]
        print(f"\ndjango-matt list serialization is {speedup:.1f}x faster than DRF")


if __name__ == "__main__":
    main()
