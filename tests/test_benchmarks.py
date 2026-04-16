"""
Tests for the Django Matt benchmark suite.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from django_matt.benchmarks import (
    Benchmark,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkScenario,
    BenchmarkSuite,
    ConsoleReporter,
    JSONReporter,
    MarkdownReporter,
)


class TestBenchmark:
    """Tests for the Benchmark class."""

    def test_benchmark_creation(self):
        """Test creating a benchmark."""
        benchmark = Benchmark(
            name="test_benchmark",
            scenario="test",
            iterations=100,
            warmup_iterations=5,
        )
        assert benchmark.name == "test_benchmark"
        assert benchmark.scenario == "test"
        assert benchmark.iterations == 100
        assert benchmark.warmup_iterations == 5

    def test_benchmark_run_simple(self):
        """Test running a simple benchmark."""
        benchmark = Benchmark(
            name="simple_test",
            scenario="test",
            iterations=100,
            warmup_iterations=5,
        )

        def simple_function():
            return sum(range(100))

        result = benchmark.run(simple_function)

        assert isinstance(result, BenchmarkResult)
        assert result.name == "simple_test"
        assert result.scenario == "test"
        assert result.iterations == 100
        assert result.mean_time_ms > 0
        assert result.ops_per_second > 0

    def test_benchmark_run_with_args(self):
        """Test running a benchmark with arguments."""
        benchmark = Benchmark(name="args_test", iterations=50)

        def add_numbers(a, b):
            return a + b

        result = benchmark.run(add_numbers, 1, 2)
        assert result.iterations == 50
        assert result.mean_time_ms >= 0

    def test_benchmark_run_with_setup_teardown(self):
        """Test running a benchmark with setup and teardown."""
        benchmark = Benchmark(name="setup_test", iterations=50, warmup_iterations=10)

        data = {"setup_called": 0, "teardown_called": 0}

        def setup():
            data["setup_called"] += 1

        def teardown():
            data["teardown_called"] += 1

        def my_function():
            pass

        benchmark.run(my_function, setup=setup, teardown=teardown)

        # Setup/teardown called for both warmup (10) and measurement (50) iterations
        assert data["setup_called"] == 60  # 10 warmup + 50 iterations
        assert data["teardown_called"] == 60

    def test_benchmark_metadata(self):
        """Test benchmark with metadata."""
        benchmark = Benchmark(
            name="metadata_test",
            iterations=10,
            metadata={"library": "test", "version": "1.0"},
        )

        result = benchmark.run(lambda: None)

        assert result.metadata["library"] == "test"
        assert result.metadata["version"] == "1.0"


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = BenchmarkResult(
            name="test",
            scenario="unit",
            iterations=100,
            total_time_ms=100.0,
            mean_time_ms=1.0,
            median_time_ms=0.9,
            min_time_ms=0.5,
            max_time_ms=2.0,
            std_dev_ms=0.3,
            ops_per_second=1000.0,
            memory_mb=50.5,
            metadata={"key": "value"},
        )

        data = result.to_dict()

        assert data["name"] == "test"
        assert data["scenario"] == "unit"
        assert data["iterations"] == 100
        assert data["mean_time_ms"] == 1.0
        assert data["ops_per_second"] == 1000.0
        assert data["metadata"]["key"] == "value"

    def test_result_from_dict(self):
        """Test creating result from dictionary."""
        data = {
            "name": "test",
            "scenario": "unit",
            "iterations": 100,
            "total_time_ms": 100.0,
            "mean_time_ms": 1.0,
            "median_time_ms": 0.9,
            "min_time_ms": 0.5,
            "max_time_ms": 2.0,
            "std_dev_ms": 0.3,
            "ops_per_second": 1000.0,
            "memory_mb": 50.5,
            "metadata": {"key": "value"},
        }

        result = BenchmarkResult.from_dict(data)

        assert result.name == "test"
        assert result.mean_time_ms == 1.0
        assert result.metadata["key"] == "value"


class TestBenchmarkScenario:
    """Tests for BenchmarkScenario."""

    def test_custom_scenario(self):
        """Test creating a custom scenario."""

        class CustomScenario(BenchmarkScenario):
            name = "custom"
            description = "Custom test scenario"

            def run(self):
                benchmark = self.create_benchmark("custom_test")
                result = benchmark.run(lambda: sum(range(100)))
                return [result]

        scenario = CustomScenario(iterations=100)
        results = scenario.run()

        assert len(results) == 1
        assert results[0].scenario == "custom"

    def test_scenario_setup_teardown(self):
        """Test scenario setup and teardown."""

        class SetupScenario(BenchmarkScenario):
            name = "setup"
            description = "Setup test"

            def setup(self):
                self.setup_called = True

            def teardown(self):
                self.teardown_called = True

            def run(self):
                return []

        scenario = SetupScenario()
        scenario.setup()
        scenario.run()
        scenario.teardown()

        assert scenario.setup_called
        assert scenario.teardown_called


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite."""

    def test_suite_creation(self):
        """Test creating a benchmark suite."""
        suite = BenchmarkSuite()
        assert len(suite.scenarios) > 0

    def test_suite_list_scenarios(self):
        """Test listing available scenarios."""
        suite = BenchmarkSuite()
        scenarios = suite.list_scenarios()

        assert "json" in scenarios
        assert "schema" in scenarios
        assert "routing" in scenarios

    def test_suite_get_scenario(self):
        """Test getting a specific scenario."""
        suite = BenchmarkSuite()
        scenario = suite.get_scenario("json")

        assert scenario is not None
        assert scenario.name == "json"

    def test_suite_register_custom(self):
        """Test registering a custom scenario."""

        class TestScenario(BenchmarkScenario):
            name = "test"
            description = "Test"

            def run(self):
                return []

        suite = BenchmarkSuite()
        suite.register(TestScenario())

        assert "test" in suite.list_scenarios()


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner."""

    def test_runner_creation(self):
        """Test creating a benchmark runner."""
        runner = BenchmarkRunner()
        assert runner.suite is not None

    def test_runner_run_specific_scenario(self):
        """Test running a specific scenario."""
        suite = BenchmarkSuite()
        runner = BenchmarkRunner(suite)

        # Run only JSON scenario with minimal iterations
        for scenario in suite.scenarios.values():
            scenario.iterations = 10  # Minimal iterations for testing

        results = runner.run(scenarios=["json"])

        assert len(results) > 0
        assert all(r.scenario == "json" for r in results)

    def test_runner_save_load_results(self):
        """Test saving and loading results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_dir = Path(tmpdir)
            runner = BenchmarkRunner(storage_dir=storage_dir)

            # Create mock results
            runner.results = [
                BenchmarkResult(
                    name="test1",
                    scenario="test",
                    iterations=100,
                    total_time_ms=100.0,
                    mean_time_ms=1.0,
                    median_time_ms=0.9,
                    min_time_ms=0.5,
                    max_time_ms=2.0,
                    std_dev_ms=0.3,
                    ops_per_second=1000.0,
                ),
            ]
            runner._run_timestamp = "2024-01-01T00:00:00"

            # Save results
            runner.save_results("test.json")

            # Load baseline
            baseline = runner.load_baseline("test.json")

            assert len(baseline) == 1
            assert baseline[0].name == "test1"

    def test_runner_compare_results(self):
        """Test comparing results with baseline."""
        runner = BenchmarkRunner()

        # Current results
        runner.results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=90.0,
                mean_time_ms=0.9,  # 10% faster
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1111.0,
            ),
        ]

        # Baseline results
        baseline = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        comparisons = runner.compare(baseline)

        assert len(comparisons) == 1
        assert comparisons[0].status == "faster"
        assert comparisons[0].mean_diff_percent < 0  # Negative means faster


class TestConsoleReporter:
    """Tests for ConsoleReporter."""

    def test_reporter_report(self):
        """Test generating console report."""
        reporter = ConsoleReporter(use_colors=False)

        results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        report = reporter.report(results)

        assert "Django Matt Benchmark Results" in report
        assert "test1" in report
        assert "TEST" in report  # Scenario name uppercase

    def test_reporter_with_colors(self):
        """Test console reporter with colors."""
        reporter = ConsoleReporter(use_colors=True)

        results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        report = reporter.report(results)

        # Should contain ANSI codes
        assert "\033[" in report


class TestJSONReporter:
    """Tests for JSONReporter."""

    def test_json_reporter(self):
        """Test generating JSON report."""
        reporter = JSONReporter()

        results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        report = reporter.report(results)
        data = json.loads(report)

        assert "timestamp" in data
        assert "results" in data
        assert "summary" in data
        assert len(data["results"]) == 1

    def test_json_reporter_with_comparisons(self):
        """Test JSON reporter with comparisons."""
        from django_matt.benchmarks.runner import BenchmarkComparison

        reporter = JSONReporter()

        current = BenchmarkResult(
            name="test1",
            scenario="test",
            iterations=100,
            total_time_ms=90.0,
            mean_time_ms=0.9,
            median_time_ms=0.9,
            min_time_ms=0.5,
            max_time_ms=2.0,
            std_dev_ms=0.3,
            ops_per_second=1111.0,
        )

        baseline = BenchmarkResult(
            name="test1",
            scenario="test",
            iterations=100,
            total_time_ms=100.0,
            mean_time_ms=1.0,
            median_time_ms=0.9,
            min_time_ms=0.5,
            max_time_ms=2.0,
            std_dev_ms=0.3,
            ops_per_second=1000.0,
        )

        comparisons = [
            BenchmarkComparison(
                name="test1",
                scenario="test",
                current=current,
                baseline=baseline,
                mean_diff_percent=-10.0,
                ops_diff_percent=11.1,
                status="faster",
            )
        ]

        report = reporter.report([current], comparisons)
        data = json.loads(report)

        assert "comparisons" in data
        assert len(data["comparisons"]) == 1
        assert data["comparisons"][0]["status"] == "faster"


class TestMarkdownReporter:
    """Tests for MarkdownReporter."""

    def test_markdown_reporter(self):
        """Test generating Markdown report."""
        reporter = MarkdownReporter()

        results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        report = reporter.report(results)

        assert "# Django Matt Benchmark Report" in report
        assert "| Benchmark |" in report
        assert "| test1 |" in report

    def test_markdown_reporter_with_charts(self):
        """Test Markdown reporter with charts."""
        reporter = MarkdownReporter(include_charts=True)

        results = [
            BenchmarkResult(
                name="test1",
                scenario="test",
                iterations=100,
                total_time_ms=100.0,
                mean_time_ms=1.0,
                median_time_ms=0.9,
                min_time_ms=0.5,
                max_time_ms=2.0,
                std_dev_ms=0.3,
                ops_per_second=1000.0,
            ),
        ]

        report = reporter.report(results)

        assert "## Performance Charts" in report
        assert "```" in report


class TestJSONSerializationScenario:
    """Tests for JSON serialization scenario."""

    def test_json_scenario_runs(self):
        """Test that JSON scenario runs without error."""
        from django_matt.benchmarks import JSONSerializationScenario

        scenario = JSONSerializationScenario(iterations=10, warmup=1)
        results = scenario.run()

        assert len(results) > 0
        assert all(r.scenario == "json" for r in results)

    def test_json_scenario_detects_libraries(self):
        """Test that JSON scenario detects available libraries."""
        from django_matt.benchmarks import JSONSerializationScenario

        scenario = JSONSerializationScenario()

        # At minimum, stdlib json should work
        assert scenario.small_data is not None
        assert scenario.medium_data is not None
        assert scenario.large_data is not None


class TestSchemaValidationScenario:
    """Tests for schema validation scenario."""

    def test_schema_scenario_runs(self):
        """Test that schema scenario runs without error."""
        from django_matt.benchmarks import SchemaValidationScenario

        scenario = SchemaValidationScenario(iterations=10, warmup=1)
        results = scenario.run()

        assert len(results) > 0
        assert all(r.scenario == "schema" for r in results)


class TestRoutingScenario:
    """Tests for routing scenario."""

    def test_routing_scenario_runs(self):
        """Test that routing scenario runs without error."""
        from django_matt.benchmarks import RoutingScenario

        scenario = RoutingScenario(iterations=10, warmup=1)
        results = scenario.run()

        assert len(results) > 0
        assert all(r.scenario == "routing" for r in results)


class TestReporterSave:
    """Tests for reporter file saving."""

    def test_save_json_report(self):
        """Test saving JSON report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = JSONReporter()

            results = [
                BenchmarkResult(
                    name="test1",
                    scenario="test",
                    iterations=100,
                    total_time_ms=100.0,
                    mean_time_ms=1.0,
                    median_time_ms=0.9,
                    min_time_ms=0.5,
                    max_time_ms=2.0,
                    std_dev_ms=0.3,
                    ops_per_second=1000.0,
                ),
            ]

            filepath = Path(tmpdir) / "report.json"
            reporter.save(filepath, results)

            assert filepath.exists()
            with open(filepath) as f:
                data = json.load(f)
                assert len(data["results"]) == 1

    def test_save_markdown_report(self):
        """Test saving Markdown report to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = MarkdownReporter()

            results = [
                BenchmarkResult(
                    name="test1",
                    scenario="test",
                    iterations=100,
                    total_time_ms=100.0,
                    mean_time_ms=1.0,
                    median_time_ms=0.9,
                    min_time_ms=0.5,
                    max_time_ms=2.0,
                    std_dev_ms=0.3,
                    ops_per_second=1000.0,
                ),
            ]

            filepath = Path(tmpdir) / "report.md"
            reporter.save(filepath, results)

            assert filepath.exists()
            content = filepath.read_text()
            assert "# Django Matt Benchmark Report" in content


class TestBenchmarkRegressionGate:
    """Tests for --fail-on-regression CI gate."""

    def _make_baseline(self, tmpdir: Path, names: list[tuple[str, float]]) -> None:
        """Write a latest.json baseline with the given (name, mean_time_ms) entries."""
        baseline_dir = tmpdir / ".matt" / "benchmarks"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": "2026-04-16T00:00:00",
            "results": [
                {
                    "name": name,
                    "scenario": "test",
                    "iterations": 100,
                    "total_time_ms": mean * 100,
                    "mean_time_ms": mean,
                    "median_time_ms": mean,
                    "min_time_ms": mean * 0.9,
                    "max_time_ms": mean * 1.1,
                    "std_dev_ms": mean * 0.05,
                    "ops_per_second": 1000.0 / mean if mean else 0.0,
                    "memory_mb": None,
                    "metadata": {},
                }
                for name, mean in names
            ],
            "metadata": {},
        }
        (baseline_dir / "latest.json").write_text(json.dumps(data))

    def test_fail_on_regression_requires_compare(self, tmp_path, monkeypatch):
        """Flag without --compare raises CommandError."""
        from django.core.management import call_command
        from django.core.management.base import CommandError

        monkeypatch.chdir(tmp_path)
        with pytest.raises(CommandError, match="--fail-on-regression requires --compare"):
            call_command(
                "benchmark",
                "--scenario",
                "json",
                "--iterations",
                "10",
                "--warmup",
                "1",
                "--fail-on-regression",
                "--quiet",
                "--no-color",
            )

    def test_fail_on_regression_no_baseline_is_noop(self, tmp_path, monkeypatch):
        """No baseline = nothing to compare against = no error."""
        from django.core.management import call_command

        monkeypatch.chdir(tmp_path)
        # No baseline file written — should pass with a warning, not raise
        call_command(
            "benchmark",
            "--scenario",
            "json",
            "--iterations",
            "10",
            "--warmup",
            "1",
            "--compare",
            "--fail-on-regression",
            "--quiet",
            "--no-color",
        )

    def test_fail_on_regression_raises_on_slowdown(self, tmp_path, monkeypatch):
        """A baseline 100x faster than the current run must trigger the gate."""
        from django.core.management import call_command
        from django.core.management.base import CommandError

        monkeypatch.chdir(tmp_path)
        # Seed baselines that are absurdly fast — guarantees every scenario regresses
        self._make_baseline(
            tmp_path,
            [
                ("orjson.dumps (small)", 0.000001),
                ("orjson.loads (small)", 0.000001),
                ("orjson.dumps (medium)", 0.000001),
            ],
        )
        with pytest.raises(CommandError, match="Benchmark regression gate failed"):
            call_command(
                "benchmark",
                "--scenario",
                "json",
                "--iterations",
                "10",
                "--warmup",
                "1",
                "--compare",
                "--threshold",
                "5.0",
                "--fail-on-regression",
                "--quiet",
                "--no-color",
            )

    def test_no_regression_when_baseline_matches(self, tmp_path, monkeypatch):
        """A baseline within threshold must NOT trigger the gate."""
        from django.core.management import call_command

        monkeypatch.chdir(tmp_path)
        # Seed baselines that are absurdly slow — guarantees every scenario is "faster"
        self._make_baseline(
            tmp_path,
            [
                ("orjson.dumps (small)", 1000.0),
                ("orjson.loads (small)", 1000.0),
                ("orjson.dumps (medium)", 1000.0),
            ],
        )
        # Should pass cleanly
        call_command(
            "benchmark",
            "--scenario",
            "json",
            "--iterations",
            "10",
            "--warmup",
            "1",
            "--compare",
            "--threshold",
            "5.0",
            "--fail-on-regression",
            "--quiet",
            "--no-color",
        )
