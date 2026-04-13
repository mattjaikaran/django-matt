"""JSON reporter — machine-readable output for review findings."""

from __future__ import annotations

import orjson

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Finding, Location, ReviewSummary


def _location_dict(loc: Location) -> dict[str, object]:
    return {
        "file": loc.file,
        "line": loc.line,
        "end_line": loc.end_line,
        "column": loc.column,
        "function": loc.function,
        "class_name": loc.class_name,
    }


def _finding_dict(finding: Finding) -> dict[str, object]:
    return {
        "rule_id": finding.rule_id,
        "message": finding.message,
        "severity": finding.severity.name,
        "severity_level": int(finding.severity),
        "category": finding.category.value,
        "location": _location_dict(finding.location),
        "suggestion": finding.suggestion,
        "context": finding.context,
        "metadata": finding.metadata,
    }


def report_json(summary: ReviewSummary, config: ReviewConfig) -> str:
    """Generate a JSON report from review findings."""
    data = {
        "summary": {
            "files_analyzed": summary.files_analyzed,
            "total_findings": summary.total,
            "analyzers_run": summary.analyzers_run,
            "duration_ms": summary.duration_ms,
            "by_severity": {
                sev.name: count for sev, count in summary.by_severity.items()
            },
            "by_category": {
                cat.value: count for cat, count in summary.by_category.items()
            },
            "exit_code": summary.exit_code,
        },
        "findings": [_finding_dict(f) for f in summary.findings],
        "config": {
            "min_severity": config.min_severity.name,
            "analyzers": sorted(config.analyzers),
            "output_format": config.output_format,
        },
    }
    return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()
