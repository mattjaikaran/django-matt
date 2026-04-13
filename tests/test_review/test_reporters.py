from __future__ import annotations

import pytest

import orjson

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import (
    Category,
    Finding,
    Location,
    ReviewSummary,
    Severity,
)
from django_matt.review.reporters.json_reporter import report_json
from django_matt.review.reporters.markdown import report_markdown
from django_matt.review.reporters.github import report_github
from django_matt.review.reporters.console import report_console


@pytest.fixture
def config() -> ReviewConfig:
    return ReviewConfig()


@pytest.fixture
def sample_findings() -> list[Finding]:
    return [
        Finding(
            rule_id="CX001",
            message="High cyclomatic complexity",
            severity=Severity.WARNING,
            category=Category.COMPLEXITY,
            location=Location(file="app/views.py", line=42, function="process"),
            suggestion="Break into smaller functions",
        ),
        Finding(
            rule_id="SEC001",
            message="Hardcoded secret",
            severity=Severity.CRITICAL,
            category=Category.SECURITY,
            location=Location(file="app/settings.py", line=10),
            suggestion="Use environment variable",
        ),
    ]


@pytest.fixture
def sample_summary(sample_findings: list[Finding]) -> ReviewSummary:
    return ReviewSummary(
        findings=sample_findings,
        files_analyzed=5,
        analyzers_run=["complexity", "security"],
        duration_ms=123.4,
    )


@pytest.fixture
def empty_summary() -> ReviewSummary:
    return ReviewSummary(
        findings=[],
        files_analyzed=3,
        analyzers_run=["complexity"],
        duration_ms=10.0,
    )


@pytest.fixture
def single_finding_summary() -> ReviewSummary:
    finding = Finding(
        rule_id="DJ001",
        message="Missing select_related",
        severity=Severity.HINT,
        category=Category.DJANGO,
        location=Location(file="app/models.py", line=5, class_name="UserManager"),
    )
    return ReviewSummary(
        findings=[finding],
        files_analyzed=1,
        analyzers_run=["django"],
        duration_ms=50.0,
    )


# ---------------------------------------------------------------------------
# Markdown reporter
# ---------------------------------------------------------------------------


class TestMarkdownReporter:
    def test_returns_string(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert isinstance(result, str)

    def test_has_heading(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "# Code Review" in result

    def test_has_summary_table(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "Files analyzed" in result
        assert "Total findings" in result
        assert "| 5 |" in result

    def test_severity_table(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "By Severity" in result
        assert "CRITICAL" in result
        assert "WARNING" in result

    def test_includes_suggestion(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "Break into smaller functions" in result
        assert "Use environment variable" in result

    def test_includes_finding_details(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "CX001" in result
        assert "SEC001" in result
        assert "app/views.py:42" in result
        assert "app/settings.py:10" in result

    def test_empty_findings(self, empty_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(empty_summary, config)
        assert "# Code Review" in result
        assert "No findings" in result

    def test_single_finding(self, single_finding_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(single_finding_summary, config)
        assert "DJ001" in result
        assert "1 finding" in result

    def test_function_name_in_output(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "process" in result

    def test_category_table(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_markdown(sample_summary, config)
        assert "By Category" in result
        assert "complexity" in result
        assert "security" in result


# ---------------------------------------------------------------------------
# JSON reporter
# ---------------------------------------------------------------------------


class TestJSONReporter:
    def test_returns_valid_json(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_json(sample_summary, config)
        parsed = orjson.loads(result)
        assert isinstance(parsed, dict)

    def test_has_findings_array(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        assert "findings" in parsed
        assert isinstance(parsed["findings"], list)
        assert len(parsed["findings"]) == 2

    def test_has_summary_object(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        summary = parsed["summary"]
        assert summary["files_analyzed"] == 5
        assert summary["total_findings"] == 2
        assert summary["duration_ms"] == pytest.approx(123.4)
        assert "exit_code" in summary

    def test_finding_fields_present(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        finding = parsed["findings"][0]
        expected_keys = {"rule_id", "message", "severity", "severity_level", "category", "location", "suggestion", "context", "metadata"}
        assert expected_keys <= set(finding.keys())

    def test_location_fields(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        loc = parsed["findings"][0]["location"]
        assert "file" in loc
        assert "line" in loc
        assert "function" in loc

    def test_severity_values(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        severities = {f["severity"] for f in parsed["findings"]}
        assert "WARNING" in severities
        assert "CRITICAL" in severities

    def test_config_section(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        assert "config" in parsed
        assert parsed["config"]["output_format"] == "console"

    def test_empty_findings(self, empty_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(empty_summary, config))
        assert parsed["findings"] == []
        assert parsed["summary"]["total_findings"] == 0

    def test_single_finding(self, single_finding_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(single_finding_summary, config))
        assert len(parsed["findings"]) == 1
        assert parsed["findings"][0]["rule_id"] == "DJ001"

    def test_by_severity_in_summary(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_json(sample_summary, config))
        by_sev = parsed["summary"]["by_severity"]
        assert by_sev["CRITICAL"] == 1
        assert by_sev["WARNING"] == 1


# ---------------------------------------------------------------------------
# GitHub reporter
# ---------------------------------------------------------------------------


class TestGitHubReporter:
    def test_returns_valid_json(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        result = report_github(sample_summary, config)
        parsed = orjson.loads(result)
        assert isinstance(parsed, dict)

    def test_has_body_and_comments(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        assert "body" in parsed
        assert "comments" in parsed
        assert "event" in parsed

    def test_body_has_summary_section(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        body = parsed["body"]
        assert "Code Review Summary" in body
        assert "Files analyzed" in body

    def test_comments_have_file_and_line(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        comments = parsed["comments"]
        assert len(comments) == 2
        paths = {c["path"] for c in comments}
        assert "app/views.py" in paths
        assert "app/settings.py" in paths
        for c in comments:
            if c["path"] == "app/views.py":
                assert c["line"] == 42

    def test_suggestion_in_comment_body(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        bodies = [c["body"] for c in parsed["comments"]]
        all_text = "\n".join(bodies)
        assert "Break into smaller functions" in all_text
        assert "Use environment variable" in all_text

    def test_event_request_changes_on_critical(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        assert parsed["event"] == "REQUEST_CHANGES"

    def test_event_comment_when_no_errors(self, single_finding_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(single_finding_summary, config))
        assert parsed["event"] == "COMMENT"

    def test_empty_findings(self, empty_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(empty_summary, config))
        assert parsed["comments"] == []
        assert "No findings" in parsed["body"]

    def test_single_finding(self, single_finding_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(single_finding_summary, config))
        assert len(parsed["comments"]) == 1

    def test_critical_warning_in_body(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        parsed = orjson.loads(report_github(sample_summary, config))
        assert "Critical issues found" in parsed["body"]


# ---------------------------------------------------------------------------
# Console reporter
# ---------------------------------------------------------------------------


class TestConsoleReporter:
    def test_runs_without_error(self, sample_summary: ReviewSummary, config: ReviewConfig) -> None:
        report_console(sample_summary, config)

    def test_empty_findings_no_error(self, empty_summary: ReviewSummary, config: ReviewConfig) -> None:
        report_console(empty_summary, config)

    def test_single_finding_no_error(self, single_finding_summary: ReviewSummary, config: ReviewConfig) -> None:
        report_console(single_finding_summary, config)
