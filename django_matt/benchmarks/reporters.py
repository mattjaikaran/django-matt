"""
Benchmark result reporters for Django Matt framework.

This module provides various output formats for benchmark results:
- Console output with colors and formatting
- JSON export
- Markdown report generation
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

import orjson

from django_matt.benchmarks.runner import (
    BenchmarkComparison,
    BenchmarkResult,
)


class BenchmarkReporter(ABC):
    """Abstract base class for benchmark reporters."""

    @abstractmethod
    def report(
        self,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a report from benchmark results.

        Args:
            results: List of benchmark results
            comparisons: Optional list of comparisons with baseline
            metadata: Optional metadata about the run

        Returns:
            The formatted report string
        """

    def save(
        self,
        filepath: str | Path,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Save report to a file."""
        content = self.report(results, comparisons, metadata)
        with open(filepath, "w") as f:
            f.write(content)


class ConsoleReporter(BenchmarkReporter):
    """
    Console reporter with colored output.

    Produces formatted tables suitable for terminal display.
    """

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

    def __init__(self, use_colors: bool = True, stream: TextIO | None = None):
        """
        Initialize the console reporter.

        Args:
            use_colors: Whether to use ANSI colors
            stream: Output stream (default: stdout)
        """
        self.use_colors = use_colors
        self.stream = stream

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_colors:
            return f"{color}{text}{self.RESET}"
        return text

    def _format_time(self, ms: float) -> str:
        """Format time in milliseconds."""
        if ms < 0.001 or ms < 1:
            return f"{ms * 1000:.2f}us"
        if ms < 1000:
            return f"{ms:.3f}ms"
        return f"{ms / 1000:.3f}s"

    def _format_ops(self, ops: float) -> str:
        """Format operations per second."""
        if ops >= 1_000_000:
            return f"{ops / 1_000_000:.2f}M"
        if ops >= 1_000:
            return f"{ops / 1_000:.2f}K"
        return f"{ops:.2f}"

    def _format_diff(self, diff: float) -> str:
        """Format percentage difference with color."""
        if diff < -5:
            # Faster (improvement)
            return self._color(f"{diff:+.1f}%", self.GREEN)
        if diff > 5:
            # Slower (regression)
            return self._color(f"{diff:+.1f}%", self.RED)
        # Same
        return self._color(f"{diff:+.1f}%", self.DIM)

    def report(
        self,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate console report."""
        lines = []

        # Header
        lines.append("")
        lines.append(self._color("=" * 80, self.BLUE))
        lines.append(self._color(" Django Matt Benchmark Results", self.BOLD))
        lines.append(self._color("=" * 80, self.BLUE))
        lines.append("")

        # Metadata
        if metadata:
            lines.append(self._color("Environment:", self.BOLD))
            for key, value in metadata.items():
                if value:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        # Group results by scenario
        scenarios: dict[str, list[BenchmarkResult]] = {}
        for result in results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        # Build comparison lookup
        comparison_map: dict[str, BenchmarkComparison] = {}
        if comparisons:
            for comp in comparisons:
                comparison_map[comp.name] = comp

        # Report each scenario
        for scenario_name, scenario_results in scenarios.items():
            lines.append(self._color(f"[{scenario_name.upper()}]", self.CYAN + self.BOLD))
            lines.append("-" * 80)

            # Header row
            if comparisons:
                header = f"{'Benchmark':<40} {'Mean':>10} {'Ops/s':>10} {'vs Baseline':>12}"
            else:
                header = f"{'Benchmark':<40} {'Mean':>10} {'Min':>10} {'Max':>10} {'Ops/s':>10}"
            lines.append(self._color(header, self.DIM))

            # Results rows
            for result in sorted(scenario_results, key=lambda r: r.mean_time_ms):
                if result.metadata.get("skipped"):
                    lines.append(
                        self._color(
                            f"  {result.name:<38} (skipped: {result.metadata.get('reason', 'unknown')})",
                            self.YELLOW,
                        )
                    )
                    continue

                mean = self._format_time(result.mean_time_ms)
                ops = self._format_ops(result.ops_per_second)

                if comparisons and result.name in comparison_map:
                    comp = comparison_map[result.name]
                    diff = self._format_diff(comp.mean_diff_percent)
                    line = f"  {result.name:<38} {mean:>10} {ops:>10} {diff:>12}"
                else:
                    min_t = self._format_time(result.min_time_ms)
                    max_t = self._format_time(result.max_time_ms)
                    line = f"  {result.name:<38} {mean:>10} {min_t:>10} {max_t:>10} {ops:>10}"

                lines.append(line)

            lines.append("")

        # Summary
        if results:
            total_benchmarks = len([r for r in results if not r.metadata.get("skipped")])
            total_iterations = sum(r.iterations for r in results if not r.metadata.get("skipped"))

            lines.append(self._color("Summary:", self.BOLD))
            lines.append(f"  Total benchmarks: {total_benchmarks}")
            lines.append(f"  Total iterations: {total_iterations:,}")

            if comparisons:
                faster = len([c for c in comparisons if c.status == "faster"])
                slower = len([c for c in comparisons if c.status == "slower"])
                same = len([c for c in comparisons if c.status == "same"])

                lines.append("")
                lines.append(self._color("Comparison with baseline:", self.BOLD))
                lines.append(self._color(f"  Faster: {faster}", self.GREEN))
                lines.append(self._color(f"  Slower: {slower}", self.RED))
                lines.append(f"  Same: {same}")

        lines.append("")
        lines.append(self._color("=" * 80, self.BLUE))
        lines.append("")

        return "\n".join(lines)


class JSONReporter(BenchmarkReporter):
    """
    JSON reporter for machine-readable output.

    Produces structured JSON suitable for further processing.
    """

    def __init__(self, indent: int = 2, include_metadata: bool = True):
        """
        Initialize the JSON reporter.

        Args:
            indent: JSON indentation level
            include_metadata: Whether to include full metadata
        """
        self.indent = indent
        self.include_metadata = include_metadata

    def report(
        self,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate JSON report."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in results],
        }

        if comparisons:
            data["comparisons"] = [c.to_dict() for c in comparisons]

        if metadata and self.include_metadata:
            data["metadata"] = metadata

        # Add summary
        if results:
            non_skipped = [r for r in results if not r.metadata.get("skipped")]
            data["summary"] = {
                "total_benchmarks": len(non_skipped),
                "total_iterations": sum(r.iterations for r in non_skipped),
                "scenarios": list(set(r.scenario for r in non_skipped)),
            }

            if comparisons:
                data["summary"]["comparison"] = {
                    "faster": len([c for c in comparisons if c.status == "faster"]),
                    "slower": len([c for c in comparisons if c.status == "slower"]),
                    "same": len([c for c in comparisons if c.status == "same"]),
                }

        return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()


class MarkdownReporter(BenchmarkReporter):
    """
    Markdown reporter for documentation.

    Produces formatted Markdown suitable for GitHub, documentation sites, etc.
    """

    def __init__(self, include_charts: bool = False):
        """
        Initialize the Markdown reporter.

        Args:
            include_charts: Whether to include ASCII charts
        """
        self.include_charts = include_charts

    def _format_time(self, ms: float) -> str:
        """Format time in milliseconds."""
        if ms < 1:
            return f"{ms * 1000:.2f}us"
        if ms < 1000:
            return f"{ms:.3f}ms"
        return f"{ms / 1000:.3f}s"

    def _format_ops(self, ops: float) -> str:
        """Format operations per second."""
        if ops >= 1_000_000:
            return f"{ops / 1_000_000:.2f}M ops/s"
        if ops >= 1_000:
            return f"{ops / 1_000:.2f}K ops/s"
        return f"{ops:.2f} ops/s"

    def report(
        self,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate Markdown report."""
        lines = []

        # Header
        lines.append("# Django Matt Benchmark Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Metadata
        if metadata:
            lines.append("## Environment")
            lines.append("")
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            for key, value in metadata.items():
                if value:
                    lines.append(f"| {key} | {value} |")
            lines.append("")

        # Group results by scenario
        scenarios: dict[str, list[BenchmarkResult]] = {}
        for result in results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        # Build comparison lookup
        comparison_map: dict[str, BenchmarkComparison] = {}
        if comparisons:
            for comp in comparisons:
                comparison_map[comp.name] = comp

        # Report each scenario
        lines.append("## Results")
        lines.append("")

        for scenario_name, scenario_results in scenarios.items():
            lines.append(f"### {scenario_name.replace('_', ' ').title()}")
            lines.append("")

            # Table header
            if comparisons:
                lines.append("| Benchmark | Mean | Ops/s | vs Baseline | Status |")
                lines.append("|-----------|------|-------|-------------|--------|")
            else:
                lines.append("| Benchmark | Mean | Min | Max | Ops/s | Iterations |")
                lines.append("|-----------|------|-----|-----|-------|------------|")

            # Results rows
            for result in sorted(scenario_results, key=lambda r: r.mean_time_ms):
                if result.metadata.get("skipped"):
                    lines.append(f"| {result.name} | - | - | - | (skipped) |")
                    continue

                mean = self._format_time(result.mean_time_ms)
                ops = self._format_ops(result.ops_per_second)

                if comparisons and result.name in comparison_map:
                    comp = comparison_map[result.name]
                    diff = f"{comp.mean_diff_percent:+.1f}%"
                    status = self._get_status_emoji(comp.status)
                    lines.append(f"| {result.name} | {mean} | {ops} | {diff} | {status} |")
                else:
                    min_t = self._format_time(result.min_time_ms)
                    max_t = self._format_time(result.max_time_ms)
                    lines.append(
                        f"| {result.name} | {mean} | {min_t} | {max_t} | {ops} | {result.iterations:,} |"
                    )

            lines.append("")

        # Summary
        if results:
            non_skipped = [r for r in results if not r.metadata.get("skipped")]

            lines.append("## Summary")
            lines.append("")
            lines.append(f"- **Total benchmarks**: {len(non_skipped)}")
            lines.append(f"- **Total iterations**: {sum(r.iterations for r in non_skipped):,}")
            lines.append(f"- **Scenarios**: {', '.join(scenarios.keys())}")
            lines.append("")

            if comparisons:
                faster = len([c for c in comparisons if c.status == "faster"])
                slower = len([c for c in comparisons if c.status == "slower"])
                same = len([c for c in comparisons if c.status == "same"])

                lines.append("### Comparison Summary")
                lines.append("")
                lines.append(f"- Faster: {faster}")
                lines.append(f"- Slower: {slower}")
                lines.append(f"- Same: {same}")
                lines.append("")

        # Charts (if enabled)
        if self.include_charts:
            lines.extend(self._generate_charts(results))

        return "\n".join(lines)

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for comparison status."""
        if status == "faster":
            return "faster"
        if status == "slower":
            return "slower"
        return "same"

    def _generate_charts(self, results: list[BenchmarkResult]) -> list[str]:
        """Generate ASCII bar charts for results."""
        lines = []
        lines.append("## Performance Charts")
        lines.append("")
        lines.append("```")

        # Group by scenario and show top 5 in each
        scenarios: dict[str, list[BenchmarkResult]] = {}
        for result in results:
            if result.metadata.get("skipped"):
                continue
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        for scenario_name, scenario_results in scenarios.items():
            lines.append(f"\n{scenario_name.upper()}:")
            lines.append("-" * 60)

            # Sort by ops/s (higher is better)
            sorted_results = sorted(
                scenario_results,
                key=lambda r: r.ops_per_second,
                reverse=True,
            )[:5]

            # Find max ops for scaling
            max_ops = max(r.ops_per_second for r in sorted_results)

            for result in sorted_results:
                bar_length = int((result.ops_per_second / max_ops) * 40)
                bar = "#" * bar_length
                ops_str = f"{result.ops_per_second:,.0f} ops/s"
                name = result.name[:25].ljust(25)
                lines.append(f"  {name} | {bar.ljust(40)} | {ops_str}")

        lines.append("```")
        lines.append("")

        return lines


class HTMLReporter(BenchmarkReporter):
    """
    HTML reporter for web display.

    Produces styled HTML with interactive charts.
    """

    def report(
        self,
        results: list[BenchmarkResult],
        comparisons: list[BenchmarkComparison] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate HTML report."""
        # Group results by scenario
        scenarios: dict[str, list[BenchmarkResult]] = {}
        for result in results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = []
            scenarios[result.scenario].append(result)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Django Matt Benchmark Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .scenario {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .faster {{ color: #28a745; }}
        .slower {{ color: #dc3545; }}
        .same {{ color: #6c757d; }}
        .metadata {{ background: #e9ecef; padding: 15px; border-radius: 4px; margin-bottom: 20px; }}
        .summary {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; flex: 1; min-width: 200px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Django Matt Benchmark Report</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
"""

        # Metadata
        if metadata:
            html += '<div class="metadata"><strong>Environment:</strong><br>'
            for key, value in metadata.items():
                if value:
                    html += f"{key}: {value}<br>"
            html += "</div>"

        # Summary stats
        non_skipped = [r for r in results if not r.metadata.get("skipped")]
        html += '<div class="summary">'
        html += f'<div class="stat"><div class="stat-value">{len(non_skipped)}</div><div class="stat-label">Benchmarks</div></div>'
        html += f'<div class="stat"><div class="stat-value">{sum(r.iterations for r in non_skipped):,}</div><div class="stat-label">Iterations</div></div>'
        html += f'<div class="stat"><div class="stat-value">{len(scenarios)}</div><div class="stat-label">Scenarios</div></div>'
        html += "</div>"

        # Build comparison lookup
        comparison_map: dict[str, BenchmarkComparison] = {}
        if comparisons:
            for comp in comparisons:
                comparison_map[comp.name] = comp

        # Results tables
        for scenario_name, scenario_results in scenarios.items():
            html += f'<div class="scenario"><h2>{scenario_name.replace("_", " ").title()}</h2>'
            html += "<table><thead><tr>"

            if comparisons:
                html += "<th>Benchmark</th><th>Mean</th><th>Ops/s</th><th>vs Baseline</th><th>Status</th>"
            else:
                html += "<th>Benchmark</th><th>Mean</th><th>Min</th><th>Max</th><th>Ops/s</th>"

            html += "</tr></thead><tbody>"

            for result in sorted(scenario_results, key=lambda r: r.mean_time_ms):
                if result.metadata.get("skipped"):
                    html += f'<tr><td>{result.name}</td><td colspan="4">Skipped</td></tr>'
                    continue

                mean = self._format_time(result.mean_time_ms)
                ops = self._format_ops(result.ops_per_second)

                if comparisons and result.name in comparison_map:
                    comp = comparison_map[result.name]
                    diff = f"{comp.mean_diff_percent:+.1f}%"
                    status_class = comp.status
                    html += f"<tr><td>{result.name}</td><td>{mean}</td><td>{ops}</td>"
                    html += f'<td class="{status_class}">{diff}</td><td class="{status_class}">{comp.status}</td></tr>'
                else:
                    min_t = self._format_time(result.min_time_ms)
                    max_t = self._format_time(result.max_time_ms)
                    html += f"<tr><td>{result.name}</td><td>{mean}</td><td>{min_t}</td><td>{max_t}</td><td>{ops}</td></tr>"

            html += "</tbody></table></div>"

        html += """
    </div>
</body>
</html>"""

        return html

    def _format_time(self, ms: float) -> str:
        """Format time in milliseconds."""
        if ms < 1:
            return f"{ms * 1000:.2f}us"
        if ms < 1000:
            return f"{ms:.3f}ms"
        return f"{ms / 1000:.3f}s"

    def _format_ops(self, ops: float) -> str:
        """Format operations per second."""
        if ops >= 1_000_000:
            return f"{ops / 1_000_000:.2f}M"
        if ops >= 1_000:
            return f"{ops / 1_000:.2f}K"
        return f"{ops:.2f}"
