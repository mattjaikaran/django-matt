"""
Django Matt Benchmark Suite.

A comprehensive benchmarking framework for measuring and tracking performance
of the Django Matt framework across various scenarios.

Usage:
    # Run all benchmarks
    python manage.py benchmark

    # Run specific scenario
    python manage.py benchmark --scenario json

    # Compare with previous run
    python manage.py benchmark --compare

    # Export results
    python manage.py benchmark --output results.json

Programmatic usage:
    from django_matt.benchmarks import BenchmarkRunner, BenchmarkSuite

    # Create and run benchmarks
    suite = BenchmarkSuite()
    runner = BenchmarkRunner(suite)
    results = runner.run()

    # Access individual scenarios
    from django_matt.benchmarks import (
        JSONSerializationScenario,
        SchemaValidationScenario,
        RoutingScenario,
        DatabaseScenario,
    )
"""

from django_matt.benchmarks.comparison import FrameworkComparisonScenario
from django_matt.benchmarks.reporters import (
    BenchmarkReporter,
    ConsoleReporter,
    HTMLReporter,
    JSONReporter,
    MarkdownReporter,
    RichTableReporter,
)
from django_matt.benchmarks.runner import (
    Benchmark,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkScenario,
    BenchmarkSuite,
)
from django_matt.benchmarks.scenarios import (
    CachingScenario,
    DatabaseScenario,
    JSONSerializationScenario,
    RoutingScenario,
    SchemaValidationScenario,
)

__all__ = [
    # Core classes
    "BenchmarkRunner",
    "BenchmarkSuite",
    "BenchmarkScenario",
    "Benchmark",
    "BenchmarkResult",
    # Scenarios
    "JSONSerializationScenario",
    "SchemaValidationScenario",
    "RoutingScenario",
    "DatabaseScenario",
    "CachingScenario",
    "FrameworkComparisonScenario",
    # Reporters
    "BenchmarkReporter",
    "ConsoleReporter",
    "HTMLReporter",
    "JSONReporter",
    "MarkdownReporter",
    "RichTableReporter",
]
