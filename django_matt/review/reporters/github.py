"""GitHub reporter — PR review comment format for review findings."""

from __future__ import annotations

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Finding, ReviewSummary, Severity

_SEVERITY_EMOJI: dict[Severity, str] = {
    Severity.INFO: "information_source",
    Severity.HINT: "bulb",
    Severity.WARNING: "warning",
    Severity.ERROR: "x",
    Severity.CRITICAL: "rotating_light",
}


def _format_comment(finding: Finding) -> str:
    """Format a single finding as a GitHub inline comment."""
    emoji = _SEVERITY_EMOJI.get(finding.severity, "grey_question")
    loc = finding.location
    loc_str = loc.file
    if loc.line is not None:
        loc_str += f":{loc.line}"

    lines = [
        f"**:{emoji}: {finding.severity.name}** `{finding.rule_id}`",
        "",
        finding.message,
    ]
    if finding.suggestion:
        lines.append("")
        lines.append(f"> **Suggestion:** {finding.suggestion}")
    if finding.context:
        lines.append("")
        lines.append(f"Context: {finding.context}")
    return "\n".join(lines)


def _pr_body(summary: ReviewSummary) -> str:
    """Generate the PR review body/summary."""
    lines = ["## Code Review Summary", ""]

    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Files analyzed | {summary.files_analyzed} |")
    lines.append(f"| Total findings | {summary.total} |")
    lines.append(f"| Duration | {summary.duration_ms:.0f}ms |")
    lines.append("")

    # Severity counts inline
    sev_parts: list[str] = []
    for sev in reversed(Severity):
        count = summary.by_severity.get(sev, 0)
        if count:
            emoji = _SEVERITY_EMOJI[sev]
            sev_parts.append(f":{emoji}: {sev.name}: **{count}**")
    if sev_parts:
        lines.append(" | ".join(sev_parts))
        lines.append("")

    if summary.has_critical:
        lines.append(":rotating_light: **Critical issues found — must fix before merge.**")
    elif summary.has_errors:
        lines.append(":x: **Errors found — review required.**")
    elif summary.total:
        lines.append(":white_check_mark: No blocking issues found.")
    else:
        lines.append(":white_check_mark: No findings — code looks clean!")

    return "\n".join(lines)


def report_github(summary: ReviewSummary, config: ReviewConfig) -> str:
    """Generate GitHub PR review output.

    Returns a JSON-like structure with the PR body and individual line comments
    that can be posted via the GitHub API.
    """
    import orjson

    comments: list[dict[str, object]] = []
    for finding in summary.findings:
        loc = finding.location
        comment: dict[str, object] = {
            "path": loc.file,
            "body": _format_comment(finding),
        }
        if loc.line is not None:
            comment["line"] = loc.line
        if loc.end_line is not None and loc.end_line != loc.line:
            comment["start_line"] = loc.line
            comment["line"] = loc.end_line
        comments.append(comment)

    payload = {
        "body": _pr_body(summary),
        "event": "COMMENT" if not summary.has_errors else "REQUEST_CHANGES",
        "comments": comments,
    }
    return orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode()
