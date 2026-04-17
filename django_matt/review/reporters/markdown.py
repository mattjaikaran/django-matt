"""Markdown reporter — structured markdown output for review findings."""

from __future__ import annotations

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Finding, ReviewSummary, Severity


def _finding_row(finding: Finding) -> str:
    loc = finding.location
    loc_str = loc.file
    if loc.line is not None:
        loc_str += f":{loc.line}"
    parts = [
        f"- **{finding.severity.name}** `{finding.rule_id}` — {finding.message}",
        f"  - Location: `{loc_str}`",
    ]
    if loc.function:
        parts.append(f"  - Function: `{loc.function}`")
    elif loc.class_name:
        parts.append(f"  - Class: `{loc.class_name}`")
    if finding.suggestion:
        parts.append(f"  - Suggestion: {finding.suggestion}")
    if finding.context:
        parts.append(f"  - Context: {finding.context}")
    return "\n".join(parts)


def report_markdown(summary: ReviewSummary, config: ReviewConfig) -> str:
    """Generate a markdown report from review findings."""
    lines: list[str] = ["# Code Review Report", ""]

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Files analyzed | {summary.files_analyzed} |")
    lines.append(f"| Total findings | {summary.total} |")
    lines.append(f"| Analyzers | {', '.join(summary.analyzers_run)} |")
    lines.append(f"| Duration | {summary.duration_ms:.0f}ms |")
    lines.append("")

    # Severity breakdown
    lines.append("### By Severity")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("| --- | --- |")
    for sev in reversed(Severity):
        count = summary.by_severity.get(sev, 0)
        if count:
            lines.append(f"| {sev.name} | {count} |")
    lines.append("")

    # Category breakdown
    lines.append("### By Category")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("| --- | --- |")
    for cat, count in sorted(summary.by_category.items(), key=lambda x: -x[1]):
        lines.append(f"| {cat.value} | {count} |")
    lines.append("")

    if not summary.findings:
        lines.append("No findings — code looks clean!")
        return "\n".join(lines)

    # Findings by severity
    lines.append("## Findings by Severity")
    lines.append("")
    for sev in reversed(Severity):
        sev_findings = [f for f in summary.findings if f.severity == sev]
        if not sev_findings:
            continue
        lines.append(f"### {sev.name} ({len(sev_findings)})")
        lines.append("")
        for finding in sev_findings:
            lines.append(_finding_row(finding))
            lines.append("")

    # Findings by file
    lines.append("## Findings by File")
    lines.append("")
    by_file = summary.by_file
    for file_path in sorted(by_file):
        findings = sorted(by_file[file_path], key=lambda f: (-f.severity, f.location.line or 0))
        lines.append(f"### `{file_path}` ({len(findings)} finding{'s' if len(findings) != 1 else ''})")
        lines.append("")
        for finding in findings:
            lines.append(_finding_row(finding))
            lines.append("")

    # Refactor suggestions (from AI review)
    if summary.refactor_suggestions:
        lines.append("## Refactoring Suggestions")
        lines.append("")
        for sug in summary.refactor_suggestions:
            title = sug.get("title", "Suggestion")
            effort = sug.get("effort", "unknown")
            files = ", ".join(f"`{f}`" for f in sug.get("files", []))
            desc = sug.get("description", "")
            lines.append(f"### {title}")
            lines.append("")
            if files:
                lines.append(f"**Files:** {files}")
            lines.append(f"**Effort:** {effort}")
            lines.append("")
            if desc:
                lines.append(desc)
                lines.append("")

    return "\n".join(lines)
