"""
Pre-commit audit integration for django-matt.

Provides :func:`run_precommit_audit` for use in ``.pre-commit-config.yaml``
hooks and the ``matt audit precommit`` CLI subcommand.

Configuration via environment variables:
  - ``MATT_AUDIT_LEVEL`` — audit strictness (default: ``strict``)
  - ``MATT_AUDIT_FAIL_ON`` — comma-separated severity names that cause failure
    (default: ``CRITICAL,HIGH``)

Example:
    >>> from django_matt.guardrails.precommit import run_precommit_audit
    >>> passed, message = run_precommit_audit()
    >>> if not passed:
    ...     print(message)
"""

from __future__ import annotations

import os
from pathlib import Path


def _default_fail_on() -> set[str]:
    """Severity levels that cause pre-commit failure by default."""
    return {"CRITICAL", "HIGH"}


def _get_audit_level(default: str = "strict") -> str:
    """Resolve audit level from env var or fallback to *default*."""
    return os.environ.get("MATT_AUDIT_LEVEL", default)


def _get_fail_on_severities() -> set[str]:
    """Resolve fail-on severities from env var or fallback to defaults."""
    raw = os.environ.get("MATT_AUDIT_FAIL_ON")
    if raw:
        return {s.strip().upper() for s in raw.split(",") if s.strip()}
    return _default_fail_on()


def run_precommit_audit(
    project_path: str | Path | None = None,
    audit_level: str = "strict",
    fail_on: set[str] | None = None,
) -> tuple[bool, str]:
    """
    Run all auditors and format findings for pre-commit display.

    Args:
        project_path: Path to the project. Defaults to ``MATT_PROJECT_PATH``
                      env var, then the current working directory.
        audit_level: Audit strictness. Overridable via ``MATT_AUDIT_LEVEL``
                     env var (default: ``"strict"``).
        fail_on: Severity names that trigger failure. Overridable via
                 ``MATT_AUDIT_FAIL_ON`` env var (default: ``{"CRITICAL", "HIGH"}``).

    Returns:
        ``(passed, message)`` tuple — *passed* is ``True`` when no finding
        at or above the *fail_on* thresholds exists; *message* is formatted
        for pre-commit hook display.
    """
    # Resolve env overrides
    level_str = _get_audit_level(audit_level)
    fail_on_severities = (
        fail_on if fail_on is not None else _get_fail_on_severities()
    )

    # Resolve project path
    if project_path is None:
        project_path = os.environ.get("MATT_PROJECT_PATH") or os.getcwd()

    # Run the audit — import is deferred to keep the module usable even
    # when the audit framework is not installed (e.g. in a minimal env).
    from django_matt.audits.framework import (
        AuditLevel,
        AuditReport,
        AuditSeverity,
        run_audit,
    )

    # Validate level
    try:
        level = AuditLevel(level_str.lower())
    except ValueError:
        valid = ", ".join(lv.value for lv in AuditLevel)
        return (
            False,
            f"Invalid MATT_AUDIT_LEVEL={level_str!r}. Valid: {valid}",
        )

    # Validate fail_on severities
    valid_severities = {sev.value.upper() for sev in AuditSeverity}
    invalid = fail_on_severities - valid_severities
    if invalid:
        return (
            False,
            f"Invalid MATT_AUDIT_FAIL_ON severities: {sorted(invalid)}. "
            f"Valid: {sorted(valid_severities)}",
        )

    report = run_audit("all", level=level, project_path=project_path)

    return _build_result(report, fail_on_severities)


def _build_result(
    report: "AuditReport",
    fail_on_severities: set[str],
) -> tuple[bool, str]:
    """Build the (passed, message) tuple from a completed audit report."""
    from django_matt.audits.framework import AuditSeverity

    # Check for auditor errors
    auditor_errors = [r for r in report.results if r.error]
    if auditor_errors:
        error_lines = ["Auditor errors encountered:"]
        for result in auditor_errors:
            error_lines.append(f"  - {result.auditor_name}: {result.error}")
        return (False, "\n".join(error_lines))

    message = format_precommit_output(report, fail_on_severities)

    # Determine pass/fail
    for finding in report.all_findings:
        if finding.severity.value.upper() in fail_on_severities:
            return (False, message)

    return (True, message)


def format_precommit_output(
    report: "AuditReport",
    fail_on_severities: set[str],
) -> str:
    """
    Format an audit report for pre-commit hook display.

    Each finding whose severity is in *fail_on_severities* gets a line:
    ``{file}:{line}: [{SEVERITY}] <id>: <message>``

    A trailing summary line reports total finding counts by severity.

    Args:
        report: Completed audit report.
        fail_on_severities: Severity names whose findings get detailed lines.

    Returns:
        Formatted string suitable for pre-commit hook output.
    """
    lines: list[str] = []
    counts: dict[str, int] = {}

    for finding in report.all_findings:
        sev = finding.severity.value.upper()
        counts[sev] = counts.get(sev, 0) + 1

        if sev not in fail_on_severities:
            continue

        # Build location string
        if finding.file:
            location = finding.file
            if finding.line is not None:
                location = f"{location}:{finding.line}"
        else:
            location = "?"

        lines.append(f"{location}: [{sev}] {finding.id}: {finding.message}")

    # Summary
    total = sum(counts.values())
    if total == 0:
        lines.append("No findings.")
    else:
        parts = []
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            n = counts.get(sev)
            if n is not None:
                parts.append(f"{sev}={n}")
        lines.append(f"Total findings: {total} ({', '.join(parts)})")

    return "\n".join(lines)
