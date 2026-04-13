"""Console reporter — rich terminal output for review findings."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from django_matt.cli.console import console
from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Finding, ReviewSummary, Severity

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.INFO: "dim",
    Severity.HINT: "cyan",
    Severity.WARNING: "yellow",
    Severity.ERROR: "red",
    Severity.CRITICAL: "bold red",
}

_SEVERITY_ICONS: dict[Severity, str] = {
    Severity.INFO: "i",
    Severity.HINT: "?",
    Severity.WARNING: "!",
    Severity.ERROR: "X",
    Severity.CRITICAL: "!!",
}


def _severity_text(severity: Severity) -> Text:
    color = _SEVERITY_COLORS.get(severity, "white")
    icon = _SEVERITY_ICONS.get(severity, " ")
    return Text(f"[{icon}] {severity.name}", style=color)


def _render_finding(finding: Finding) -> Text:
    color = _SEVERITY_COLORS.get(finding.severity, "white")
    parts = Text()
    parts.append(f"  {finding.severity.name:<8}", style=color)
    parts.append(f" {finding.rule_id}", style="bold")
    parts.append(f"  {finding.message}")
    loc = finding.location
    if loc.line is not None:
        parts.append(f"  (line {loc.line}", style="dim")
        if loc.function:
            parts.append(f", {loc.function}", style="dim")
        elif loc.class_name:
            parts.append(f", {loc.class_name}", style="dim")
        parts.append(")", style="dim")
    if finding.suggestion:
        parts.append(f"\n           -> {finding.suggestion}", style="green")
    return parts


def report_console(summary: ReviewSummary, config: ReviewConfig) -> None:
    """Render review findings to the terminal using rich formatting."""
    rc = console._console

    console.header("Code Review Results")

    if not summary.findings:
        console.success("No findings — code looks clean!")
        _print_stats(summary, rc)
        return

    # Group by file, sorted by file path
    by_file = summary.by_file
    for file_path in sorted(by_file):
        findings = sorted(by_file[file_path], key=lambda f: (-f.severity, f.location.line or 0))
        count_text = Text(f" ({len(findings)})", style="dim")
        title = Text(file_path, style="bold blue")
        title.append_text(count_text)
        rc.print()
        rc.print(Panel(title, expand=False, border_style="blue"))

        for finding in findings:
            rc.print(_render_finding(finding))

    rc.print()

    # Severity breakdown
    sev_table = Table(title="Findings by Severity", show_edge=False, pad_edge=False)
    sev_table.add_column("Severity", style="bold")
    sev_table.add_column("Count", justify="right")
    for sev in reversed(Severity):
        count = summary.by_severity.get(sev, 0)
        if count:
            color = _SEVERITY_COLORS[sev]
            sev_table.add_row(Text(sev.name, style=color), str(count))
    rc.print(sev_table)

    # Category breakdown
    cat_table = Table(title="Findings by Category", show_edge=False, pad_edge=False)
    cat_table.add_column("Category", style="bold")
    cat_table.add_column("Count", justify="right")
    for cat, count in sorted(summary.by_category.items(), key=lambda x: -x[1]):
        cat_table.add_row(cat.value, str(count))
    rc.print(cat_table)

    _print_stats(summary, rc)

    # Final verdict
    rc.print()
    if summary.has_critical:
        console.error(f"{summary.total} finding(s) — critical issues found")
    elif summary.has_errors:
        console.warning(f"{summary.total} finding(s) — errors detected")
    else:
        console.info(f"{summary.total} finding(s) — no blocking issues")


def _print_stats(summary: ReviewSummary, rc: object) -> None:
    """Print run statistics."""
    stats_table = Table(title="Run Statistics", show_edge=False, pad_edge=False)
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", justify="right")
    stats_table.add_row("Files analyzed", str(summary.files_analyzed))
    stats_table.add_row("Analyzers run", ", ".join(summary.analyzers_run))
    stats_table.add_row("Total findings", str(summary.total))
    stats_table.add_row("Duration", f"{summary.duration_ms:.0f}ms")
    rc.print(stats_table)  # type: ignore[union-attr]
