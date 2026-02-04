"""
Django Matt benchmark CLI command.

This command runs performance benchmarks for the Django Matt framework.

Usage:
    python manage.py benchmark                    # Run all benchmarks
    python manage.py benchmark --scenario json    # Run specific scenario
    python manage.py benchmark --compare          # Compare with last run
    python manage.py benchmark --output results.json
    python manage.py benchmark --output report.md --format markdown
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run performance benchmarks for Django Matt framework"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            "-s",
            type=str,
            nargs="+",
            help="Specific scenario(s) to run (json, schema, routing, database, caching)",
        )
        parser.add_argument(
            "--iterations",
            "-n",
            type=int,
            help="Number of iterations for each benchmark",
        )
        parser.add_argument(
            "--warmup",
            "-w",
            type=int,
            default=10,
            help="Number of warmup iterations (default: 10)",
        )
        parser.add_argument(
            "--compare",
            "-c",
            action="store_true",
            help="Compare results with the last run",
        )
        parser.add_argument(
            "--baseline",
            "-b",
            type=str,
            help="Baseline file to compare against (default: latest.json)",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file for results",
        )
        parser.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["console", "json", "markdown", "html"],
            default="console",
            help="Output format (default: console)",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results for future comparison",
        )
        parser.add_argument(
            "--list",
            "-l",
            action="store_true",
            help="List available scenarios",
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            help="Disable colored output",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=5.0,
            help="Percentage threshold for 'same' status in comparisons (default: 5.0)",
        )
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Minimal output (only show results)",
        )

    def handle(self, *args, **options):
        from django_matt.benchmarks import (
            BenchmarkRunner,
            BenchmarkSuite,
            ConsoleReporter,
            HTMLReporter,
            JSONReporter,
            MarkdownReporter,
        )

        # Handle --list
        if options["list"]:
            self._list_scenarios()
            return

        # Create suite and runner
        suite = BenchmarkSuite()
        runner = BenchmarkRunner(suite)

        # Validate scenarios
        scenarios = options.get("scenario")
        if scenarios:
            available = suite.list_scenarios()
            for s in scenarios:
                if s not in available:
                    raise CommandError(f"Unknown scenario: {s}. Available: {', '.join(available)}")

        # Apply warmup setting to all scenarios
        warmup = options["warmup"]
        for scenario in suite.scenarios.values():
            scenario.warmup = warmup

        # Show header
        if not options["quiet"]:
            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO("=" * 60))
            self.stdout.write(self.style.HTTP_INFO(" Django Matt Benchmark Suite"))
            self.stdout.write(self.style.HTTP_INFO("=" * 60))
            self.stdout.write("")

            if scenarios:
                self.stdout.write(f"Scenarios: {', '.join(scenarios)}")
            else:
                self.stdout.write("Running all scenarios...")

            if options["iterations"]:
                self.stdout.write(f"Iterations: {options['iterations']}")

            self.stdout.write("")
            self.stdout.write("Running benchmarks...")
            self.stdout.write("")

        # Run benchmarks
        try:
            results = runner.run(
                scenarios=scenarios,
                iterations=options.get("iterations"),
            )
        except Exception as e:
            raise CommandError(f"Benchmark failed: {e}")

        if not results:
            self.stdout.write(self.style.WARNING("No benchmark results generated"))
            return

        # Handle comparison
        comparisons = None
        if options["compare"]:
            baseline_file = options.get("baseline") or "latest.json"
            baseline = runner.load_baseline(baseline_file)

            if not baseline:
                self.stdout.write(
                    self.style.WARNING(f"No baseline found at .matt/benchmarks/{baseline_file}")
                )
            else:
                comparisons = runner.compare(
                    baseline=baseline,
                    threshold_percent=options["threshold"],
                )

        # Get environment metadata
        metadata = runner._get_environment_metadata()

        # Select reporter based on format
        output_format = options["format"]
        use_colors = not options["no_color"] and output_format == "console"

        if output_format == "json":
            reporter = JSONReporter()
        elif output_format == "markdown":
            reporter = MarkdownReporter(include_charts=True)
        elif output_format == "html":
            reporter = HTMLReporter()
        else:
            reporter = ConsoleReporter(use_colors=use_colors)

        # Generate report
        report = reporter.report(results, comparisons, metadata)

        # Output report
        output_file = options.get("output")
        if output_file:
            output_path = Path(output_file)
            reporter.save(output_path, results, comparisons, metadata)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {output_path}"))
        else:
            self.stdout.write(report)

        # Save results if requested
        if options["save"] or options["compare"]:
            runner.save_results()
            if not options["quiet"]:
                self.stdout.write(
                    self.style.SUCCESS("Results saved to .matt/benchmarks/ for future comparison")
                )

        # Show summary for console output
        if output_format == "console" and not options["quiet"]:
            self._show_summary(results, comparisons)

    def _list_scenarios(self):
        """List available benchmark scenarios."""
        from django_matt.benchmarks import BenchmarkSuite

        suite = BenchmarkSuite()

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Available Benchmark Scenarios:"))
        self.stdout.write("")

        for name, scenario in suite.scenarios.items():
            self.stdout.write(f"  {self.style.SUCCESS(name)}")
            self.stdout.write(f"    {scenario.description}")
            self.stdout.write(f"    Default iterations: {scenario.iterations}")
            self.stdout.write("")

    def _show_summary(self, results, comparisons):
        """Show summary of benchmark results."""
        non_skipped = [r for r in results if not r.metadata.get("skipped")]
        skipped = [r for r in results if r.metadata.get("skipped")]

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("-" * 60))
        self.stdout.write(self.style.SUCCESS(f"Completed {len(non_skipped)} benchmarks"))

        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped {len(skipped)} benchmarks"))

        if comparisons:
            faster = len([c for c in comparisons if c.status == "faster"])
            slower = len([c for c in comparisons if c.status == "slower"])

            if faster > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Performance improved in {faster} benchmarks")
                )
            if slower > 0:
                self.stdout.write(
                    self.style.WARNING(f"Performance regressed in {slower} benchmarks")
                )

        # Find fastest and slowest
        if non_skipped:
            fastest = min(non_skipped, key=lambda r: r.mean_time_ms)
            slowest = max(non_skipped, key=lambda r: r.mean_time_ms)

            self.stdout.write("")
            self.stdout.write(f"Fastest: {fastest.name} ({fastest.ops_per_second:,.0f} ops/s)")
            self.stdout.write(f"Slowest: {slowest.name} ({slowest.ops_per_second:,.0f} ops/s)")

        self.stdout.write("")
