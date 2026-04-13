"""
Benchmark management command.

Usage:
    python manage.py matt_benchmark                     # Run all benchmarks
    python manage.py matt_benchmark --scenario json     # Run specific scenario
    python manage.py matt_benchmark --iterations 5000   # Custom iteration count
    python manage.py matt_benchmark --compare            # Compare against saved baseline
    python manage.py matt_benchmark --save-baseline      # Save results as baseline
    python manage.py matt_benchmark --format json        # Output as JSON
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Run framework benchmarks against your API."""

    help = "Run django-matt benchmarks and optionally compare against baselines"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            type=str,
            nargs="*",
            default=None,
            help="Specific scenarios to run (e.g., json schema routing database caching)",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=None,
            help="Number of iterations per benchmark (default: 1000)",
        )
        parser.add_argument(
            "--compare",
            action="store_true",
            help="Compare results against the saved baseline.",
        )
        parser.add_argument(
            "--save-baseline",
            action="store_true",
            help="Save current results as the baseline for future comparisons.",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["table", "json", "markdown"],
            default="table",
            help="Output format (default: table)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_scenarios",
            help="List available benchmark scenarios.",
        )

    def handle(self, *args, **options):
        from django_matt.benchmarks.runner import BenchmarkRunner, BenchmarkSuite

        suite = BenchmarkSuite()
        runner = BenchmarkRunner(suite=suite)

        # List scenarios
        if options["list_scenarios"]:
            self.stdout.write(self.style.MIGRATE_HEADING("\nAvailable benchmark scenarios:\n"))
            for name in suite.list_scenarios():
                scenario = suite.get_scenario(name)
                desc = getattr(scenario, "description", "") if scenario else ""
                self.stdout.write(f"  {name:20s} {desc}")
            self.stdout.write("")
            return

        scenarios = options["scenario"]
        iterations = options["iterations"]
        output_format = options["format"]

        # Validate scenario names
        if scenarios:
            available = suite.list_scenarios()
            for s in scenarios:
                if s not in available:
                    self.stderr.write(self.style.ERROR(
                        f"Unknown scenario: {s}. Available: {', '.join(available)}"
                    ))
                    return

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Django Matt Benchmarks ===\n"))

        if scenarios:
            self.stdout.write(f"  Scenarios: {', '.join(scenarios)}")
        else:
            self.stdout.write("  Scenarios: all")
        if iterations:
            self.stdout.write(f"  Iterations: {iterations}")
        self.stdout.write("  Running...\n")

        # Run benchmarks
        results = runner.run(scenarios=scenarios, iterations=iterations)

        if not results:
            self.stdout.write(self.style.WARNING("  No benchmark results."))
            return

        # Output results
        if output_format == "json":
            self._output_json(results)
        elif output_format == "markdown":
            self._output_markdown(results)
        else:
            self._output_table(results)

        # Compare against baseline
        if options["compare"]:
            self._compare_baseline(runner)

        # Save baseline
        if options["save_baseline"]:
            runner.save_results("baseline.json")
            self.stdout.write(self.style.SUCCESS(
                "\n  Baseline saved to .matt/benchmarks/baseline.json"
            ))

    def _output_table(self, results):
        """Print results as a formatted table."""
        self.stdout.write(
            f"  {'Scenario':<20s} {'Benchmark':<30s} {'Mean (ms)':>10s} "
            f"{'Median (ms)':>12s} {'Ops/sec':>12s} {'Std Dev':>10s}"
        )
        self.stdout.write("  " + "-" * 96)

        for r in results:
            self.stdout.write(
                f"  {r.scenario:<20s} {r.name:<30s} {r.mean_time_ms:>10.4f} "
                f"{r.median_time_ms:>12.4f} {r.ops_per_second:>12.1f} {r.std_dev_ms:>10.4f}"
            )

        self.stdout.write("")

    def _output_json(self, results):
        """Print results as JSON."""
        import orjson

        data = [r.to_dict() for r in results]
        self.stdout.write(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode())

    def _output_markdown(self, results):
        """Print results as a markdown table."""
        self.stdout.write("| Scenario | Benchmark | Mean (ms) | Ops/sec | Std Dev |")
        self.stdout.write("|----------|-----------|-----------|---------|---------|")
        for r in results:
            self.stdout.write(
                f"| {r.scenario} | {r.name} | {r.mean_time_ms:.4f} | "
                f"{r.ops_per_second:.1f} | {r.std_dev_ms:.4f} |"
            )
        self.stdout.write("")

    def _compare_baseline(self, runner):
        """Compare current results against saved baseline."""
        try:
            comparisons = runner.compare_with_baseline("baseline.json")
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(
                "\n  No baseline found. Run with --save-baseline first."
            ))
            return

        if not comparisons:
            self.stdout.write(self.style.WARNING("\n  No matching benchmarks to compare."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Baseline Comparison ---\n"))
        self.stdout.write(
            f"  {'Benchmark':<30s} {'Current (ms)':>12s} {'Baseline (ms)':>14s} "
            f"{'Diff':>8s} {'Status':>10s}"
        )
        self.stdout.write("  " + "-" * 76)

        for c in comparisons:
            diff_str = f"{c.mean_diff_percent:+.1f}%"
            if c.status == "faster":
                status = self.style.SUCCESS(f"{'faster':>10s}")
            elif c.status == "slower":
                status = self.style.ERROR(f"{'slower':>10s}")
            else:
                status = f"{'same':>10s}"

            self.stdout.write(
                f"  {c.name:<30s} {c.current.mean_time_ms:>12.4f} "
                f"{c.baseline.mean_time_ms:>14.4f} {diff_str:>8s} {status}"
            )
        self.stdout.write("")
