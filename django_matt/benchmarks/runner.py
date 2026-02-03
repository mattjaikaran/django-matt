"""
Benchmark runner for Django Matt framework.

This module provides the core infrastructure for running benchmarks,
collecting results, and managing benchmark suites.
"""

import gc
import json
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Storage directory for benchmark results
BENCHMARK_STORAGE_DIR = Path(".matt/benchmarks")


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    scenario: str
    iterations: int
    total_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float
    ops_per_second: float
    memory_mb: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "scenario": self.scenario,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time_ms, 4),
            "mean_time_ms": round(self.mean_time_ms, 4),
            "median_time_ms": round(self.median_time_ms, 4),
            "min_time_ms": round(self.min_time_ms, 4),
            "max_time_ms": round(self.max_time_ms, 4),
            "std_dev_ms": round(self.std_dev_ms, 4),
            "ops_per_second": round(self.ops_per_second, 2),
            "memory_mb": round(self.memory_mb, 2) if self.memory_mb else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkResult":
        """Create result from dictionary."""
        return cls(
            name=data["name"],
            scenario=data["scenario"],
            iterations=data["iterations"],
            total_time_ms=data["total_time_ms"],
            mean_time_ms=data["mean_time_ms"],
            median_time_ms=data["median_time_ms"],
            min_time_ms=data["min_time_ms"],
            max_time_ms=data["max_time_ms"],
            std_dev_ms=data["std_dev_ms"],
            ops_per_second=data["ops_per_second"],
            memory_mb=data.get("memory_mb"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark results."""

    name: str
    scenario: str
    current: BenchmarkResult
    baseline: BenchmarkResult
    mean_diff_percent: float
    ops_diff_percent: float
    status: str  # "faster", "slower", "same"

    def to_dict(self) -> dict[str, Any]:
        """Convert comparison to dictionary."""
        return {
            "name": self.name,
            "scenario": self.scenario,
            "current": self.current.to_dict(),
            "baseline": self.baseline.to_dict(),
            "mean_diff_percent": round(self.mean_diff_percent, 2),
            "ops_diff_percent": round(self.ops_diff_percent, 2),
            "status": self.status,
        }


class Benchmark:
    """
    A single benchmark that measures execution time.

    Usage:
        benchmark = Benchmark("my_operation", iterations=1000)
        result = benchmark.run(my_function, arg1, arg2)
    """

    def __init__(
        self,
        name: str,
        scenario: str = "default",
        iterations: int = 1000,
        warmup_iterations: int = 10,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize a benchmark.

        Args:
            name: Name of the benchmark
            scenario: Scenario category this benchmark belongs to
            iterations: Number of times to run the benchmark
            warmup_iterations: Number of warmup runs before measuring
            metadata: Additional metadata to include in results
        """
        self.name = name
        self.scenario = scenario
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.metadata = metadata or {}

    def run(
        self,
        func: Callable[..., Any],
        *args,
        setup: Callable[[], None] | None = None,
        teardown: Callable[[], None] | None = None,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Run the benchmark.

        Args:
            func: The function to benchmark
            *args: Positional arguments to pass to the function
            setup: Optional setup function to call before each iteration
            teardown: Optional teardown function to call after each iteration
            **kwargs: Keyword arguments to pass to the function

        Returns:
            BenchmarkResult with timing statistics
        """
        # Warmup phase
        for _ in range(self.warmup_iterations):
            if setup:
                setup()
            func(*args, **kwargs)
            if teardown:
                teardown()

        # Force garbage collection before measuring
        gc.collect()
        gc.disable()

        try:
            # Measurement phase
            times: list[float] = []

            for _ in range(self.iterations):
                if setup:
                    setup()

                start = time.perf_counter()
                func(*args, **kwargs)
                end = time.perf_counter()

                times.append((end - start) * 1000)  # Convert to milliseconds

                if teardown:
                    teardown()

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

        # Try to get memory usage (requires psutil)
        memory_mb = None
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except ImportError:
            pass

        return BenchmarkResult(
            name=self.name,
            scenario=self.scenario,
            iterations=self.iterations,
            total_time_ms=total_time,
            mean_time_ms=mean_time,
            median_time_ms=median_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            std_dev_ms=std_dev,
            ops_per_second=ops_per_second,
            memory_mb=memory_mb,
            metadata=self.metadata,
        )

    def run_async(
        self,
        func: Callable[..., Any],
        *args,
        setup: Callable[[], None] | None = None,
        teardown: Callable[[], None] | None = None,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Run an async function benchmark.

        Args:
            func: The async function to benchmark
            *args: Positional arguments to pass to the function
            setup: Optional setup function to call before each iteration
            teardown: Optional teardown function to call after each iteration
            **kwargs: Keyword arguments to pass to the function

        Returns:
            BenchmarkResult with timing statistics
        """
        import asyncio

        async def run_iterations():
            # Warmup phase
            for _ in range(self.warmup_iterations):
                if setup:
                    setup()
                await func(*args, **kwargs)
                if teardown:
                    teardown()

            # Measurement phase
            times: list[float] = []

            for _ in range(self.iterations):
                if setup:
                    setup()

                start = time.perf_counter()
                await func(*args, **kwargs)
                end = time.perf_counter()

                times.append((end - start) * 1000)

                if teardown:
                    teardown()

            return times

        # Force garbage collection before measuring
        gc.collect()
        gc.disable()

        try:
            times = asyncio.run(run_iterations())
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

        # Try to get memory usage
        memory_mb = None
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except ImportError:
            pass

        return BenchmarkResult(
            name=self.name,
            scenario=self.scenario,
            iterations=self.iterations,
            total_time_ms=total_time,
            mean_time_ms=mean_time,
            median_time_ms=median_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            std_dev_ms=std_dev,
            ops_per_second=ops_per_second,
            memory_mb=memory_mb,
            metadata=self.metadata,
        )


class BenchmarkScenario(ABC):
    """
    Abstract base class for benchmark scenarios.

    A scenario groups related benchmarks together and provides
    setup/teardown for the entire scenario.
    """

    name: str = "base"
    description: str = "Base scenario"

    def __init__(self, iterations: int = 1000, warmup: int = 10):
        """
        Initialize the scenario.

        Args:
            iterations: Default number of iterations for benchmarks
            warmup: Default number of warmup iterations
        """
        self.iterations = iterations
        self.warmup = warmup
        self.results: list[BenchmarkResult] = []

    def setup(self):
        """Called once before running all benchmarks in this scenario."""
        pass

    def teardown(self):
        """Called once after running all benchmarks in this scenario."""
        pass

    @abstractmethod
    def run(self) -> list[BenchmarkResult]:
        """
        Run all benchmarks in this scenario.

        Returns:
            List of benchmark results
        """
        pass

    def create_benchmark(
        self,
        name: str,
        iterations: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Benchmark:
        """Create a benchmark with scenario defaults."""
        return Benchmark(
            name=name,
            scenario=self.name,
            iterations=iterations or self.iterations,
            warmup_iterations=self.warmup,
            metadata=metadata or {},
        )


class BenchmarkSuite:
    """
    A collection of benchmark scenarios.

    The suite manages registration and execution of multiple scenarios.
    """

    def __init__(self):
        """Initialize the benchmark suite."""
        self.scenarios: dict[str, BenchmarkScenario] = {}
        self._register_default_scenarios()

    def _register_default_scenarios(self):
        """Register the default benchmark scenarios."""
        # Import here to avoid circular imports
        from django_matt.benchmarks.scenarios import (
            CachingScenario,
            DatabaseScenario,
            JSONSerializationScenario,
            RoutingScenario,
            SchemaValidationScenario,
        )

        self.register(JSONSerializationScenario())
        self.register(SchemaValidationScenario())
        self.register(RoutingScenario())
        self.register(DatabaseScenario())
        self.register(CachingScenario())

    def register(self, scenario: BenchmarkScenario):
        """
        Register a scenario with the suite.

        Args:
            scenario: The scenario to register
        """
        self.scenarios[scenario.name] = scenario

    def get_scenario(self, name: str) -> BenchmarkScenario | None:
        """
        Get a scenario by name.

        Args:
            name: The scenario name

        Returns:
            The scenario or None if not found
        """
        return self.scenarios.get(name)

    def list_scenarios(self) -> list[str]:
        """Get list of available scenario names."""
        return list(self.scenarios.keys())


class BenchmarkRunner:
    """
    Runs benchmarks and manages results.

    The runner handles:
    - Executing benchmark scenarios
    - Storing results for historical comparison
    - Loading baseline results for comparison
    """

    def __init__(
        self,
        suite: BenchmarkSuite | None = None,
        storage_dir: Path | None = None,
    ):
        """
        Initialize the benchmark runner.

        Args:
            suite: The benchmark suite to run
            storage_dir: Directory for storing results (default: .matt/benchmarks)
        """
        self.suite = suite or BenchmarkSuite()
        self.storage_dir = storage_dir or BENCHMARK_STORAGE_DIR
        self.results: list[BenchmarkResult] = []
        self._run_timestamp: str | None = None

    def run(
        self,
        scenarios: list[str] | None = None,
        iterations: int | None = None,
    ) -> list[BenchmarkResult]:
        """
        Run benchmarks.

        Args:
            scenarios: List of scenario names to run (default: all)
            iterations: Override default iterations

        Returns:
            List of all benchmark results
        """
        self._run_timestamp = datetime.now().isoformat()
        self.results = []

        # Determine which scenarios to run
        if scenarios is None:
            scenarios = self.suite.list_scenarios()

        for scenario_name in scenarios:
            scenario = self.suite.get_scenario(scenario_name)
            if scenario is None:
                continue

            # Override iterations if specified
            if iterations is not None:
                scenario.iterations = iterations

            # Run scenario
            try:
                scenario.setup()
                results = scenario.run()
                self.results.extend(results)
            finally:
                scenario.teardown()

        return self.results

    def save_results(self, filename: str | None = None):
        """
        Save results to storage.

        Args:
            filename: Custom filename (default: timestamp-based)
        """
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{timestamp}.json"

        filepath = self.storage_dir / filename

        data = {
            "timestamp": self._run_timestamp,
            "results": [r.to_dict() for r in self.results],
            "metadata": self._get_environment_metadata(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        # Also save as "latest" for easy comparison
        latest_path = self.storage_dir / "latest.json"
        with open(latest_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_baseline(self, filename: str = "latest.json") -> list[BenchmarkResult]:
        """
        Load baseline results for comparison.

        Args:
            filename: The baseline file to load

        Returns:
            List of baseline results
        """
        filepath = self.storage_dir / filename

        if not filepath.exists():
            return []

        with open(filepath) as f:
            data = json.load(f)

        return [BenchmarkResult.from_dict(r) for r in data.get("results", [])]

    def compare(
        self,
        baseline: list[BenchmarkResult] | None = None,
        threshold_percent: float = 5.0,
    ) -> list[BenchmarkComparison]:
        """
        Compare current results with baseline.

        Args:
            baseline: Baseline results (default: load from latest.json)
            threshold_percent: Threshold for "same" status

        Returns:
            List of comparisons
        """
        if baseline is None:
            baseline = self.load_baseline()

        if not baseline:
            return []

        # Create lookup by name
        baseline_map = {r.name: r for r in baseline}
        comparisons = []

        for current in self.results:
            baseline_result = baseline_map.get(current.name)
            if baseline_result is None:
                continue

            # Calculate differences (handle division by zero)
            if baseline_result.mean_time_ms > 0:
                mean_diff = ((current.mean_time_ms - baseline_result.mean_time_ms) /
                            baseline_result.mean_time_ms * 100)
            else:
                mean_diff = 0.0 if current.mean_time_ms == 0 else 100.0

            if baseline_result.ops_per_second > 0:
                ops_diff = ((current.ops_per_second - baseline_result.ops_per_second) /
                           baseline_result.ops_per_second * 100)
            else:
                ops_diff = 0.0 if current.ops_per_second == 0 else 100.0

            # Determine status
            if abs(mean_diff) <= threshold_percent:
                status = "same"
            elif mean_diff < 0:
                status = "faster"
            else:
                status = "slower"

            comparisons.append(
                BenchmarkComparison(
                    name=current.name,
                    scenario=current.scenario,
                    current=current,
                    baseline=baseline_result,
                    mean_diff_percent=mean_diff,
                    ops_diff_percent=ops_diff,
                    status=status,
                )
            )

        return comparisons

    def _get_environment_metadata(self) -> dict[str, Any]:
        """Get environment information for the benchmark run."""
        import platform
        import sys

        metadata = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
        }

        # Check for optional JSON libraries
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

        # Django version
        try:
            import django
            metadata["django_version"] = django.__version__
        except ImportError:
            metadata["django_version"] = None

        # Pydantic version
        try:
            import pydantic
            metadata["pydantic_version"] = pydantic.__version__
        except ImportError:
            metadata["pydantic_version"] = None

        return metadata

    def get_results_by_scenario(self) -> dict[str, list[BenchmarkResult]]:
        """Group results by scenario."""
        grouped: dict[str, list[BenchmarkResult]] = {}
        for result in self.results:
            if result.scenario not in grouped:
                grouped[result.scenario] = []
            grouped[result.scenario].append(result)
        return grouped
