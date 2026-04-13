from __future__ import annotations

import ast
from pathlib import Path

import pytest

from django_matt.review.analyzers.base import BaseAnalyzer
from django_matt.review.config import ReviewConfig
from django_matt.review.engine import ReviewEngine
from django_matt.review.findings import (
    Category,
    Finding,
    Location,
    ReviewSummary,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    *,
    severity: Severity = Severity.WARNING,
    category: Category = Category.COMPLEXITY,
    file: str = "app.py",
    line: int | None = 1,
    rule_id: str = "TST001",
    message: str = "test finding",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        category=category,
        location=Location(file=file, line=line),
    )


class StubAnalyzer(BaseAnalyzer):
    """Analyzer that returns pre-configured findings for every file."""

    name = "stub"
    description = "stub analyzer for tests"

    def __init__(self, config: ReviewConfig, findings: list[Finding] | None = None) -> None:
        super().__init__(config)
        self._findings = findings or []

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        return self._findings


class CrashingAnalyzer(BaseAnalyzer):
    """Analyzer that always raises."""

    name = "crasher"
    description = "always raises"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Finding / Location
# ---------------------------------------------------------------------------

class TestFinding:
    def test_creation_and_str(self) -> None:
        f = _make_finding(severity=Severity.ERROR, rule_id="E001", message="bad code")
        assert f.severity == Severity.ERROR
        assert f.rule_id == "E001"
        s = str(f)
        assert "[ERROR]" in s
        assert "E001" in s
        assert "bad code" in s

    def test_str_includes_location(self) -> None:
        f = _make_finding(file="views.py", line=42)
        assert "views.py:42" in str(f)


class TestLocation:
    def test_file_only(self) -> None:
        loc = Location(file="models.py")
        assert str(loc) == "models.py"

    def test_file_and_line(self) -> None:
        loc = Location(file="models.py", line=10)
        assert str(loc) == "models.py:10"

    def test_with_function(self) -> None:
        loc = Location(file="views.py", line=5, function="get_user")
        assert str(loc) == "views.py:5 (get_user)"

    def test_with_class(self) -> None:
        loc = Location(file="views.py", line=5, class_name="UserView")
        assert str(loc) == "views.py:5 (UserView)"

    def test_function_takes_precedence_over_class(self) -> None:
        loc = Location(file="a.py", line=1, function="fn", class_name="Cls")
        # function branch checked first
        assert "(fn)" in str(loc)
        assert "(Cls)" not in str(loc)


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------

class TestSeverity:
    def test_ordering(self) -> None:
        assert Severity.INFO < Severity.HINT < Severity.WARNING < Severity.ERROR < Severity.CRITICAL

    def test_int_values(self) -> None:
        assert int(Severity.INFO) == 0
        assert int(Severity.CRITICAL) == 4

    def test_sortable(self) -> None:
        vals = [Severity.ERROR, Severity.INFO, Severity.CRITICAL, Severity.WARNING]
        assert sorted(vals) == [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL]


# ---------------------------------------------------------------------------
# ReviewSummary
# ---------------------------------------------------------------------------

class TestReviewSummary:
    def test_empty_summary(self) -> None:
        s = ReviewSummary()
        assert s.total == 0
        assert s.by_severity == {}
        assert s.by_category == {}
        assert s.by_file == {}
        assert not s.has_errors
        assert s.exit_code == 0

    def test_by_severity(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(severity=Severity.WARNING),
            _make_finding(severity=Severity.WARNING),
            _make_finding(severity=Severity.ERROR),
        ])
        assert s.by_severity == {Severity.WARNING: 2, Severity.ERROR: 1}

    def test_by_category(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(category=Category.COMPLEXITY),
            _make_finding(category=Category.SECURITY),
            _make_finding(category=Category.COMPLEXITY),
        ])
        assert s.by_category == {Category.COMPLEXITY: 2, Category.SECURITY: 1}

    def test_by_file(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(file="a.py"),
            _make_finding(file="b.py"),
            _make_finding(file="a.py"),
        ])
        assert len(s.by_file["a.py"]) == 2
        assert len(s.by_file["b.py"]) == 1

    def test_has_errors_true(self) -> None:
        s = ReviewSummary(findings=[_make_finding(severity=Severity.ERROR)])
        assert s.has_errors

    def test_has_errors_false_on_warning(self) -> None:
        s = ReviewSummary(findings=[_make_finding(severity=Severity.WARNING)])
        assert not s.has_errors

    def test_exit_code_zero(self) -> None:
        s = ReviewSummary(findings=[_make_finding(severity=Severity.WARNING)])
        assert s.exit_code == 0

    def test_exit_code_one_on_error(self) -> None:
        s = ReviewSummary(findings=[_make_finding(severity=Severity.ERROR)])
        assert s.exit_code == 1

    def test_exit_code_two_on_critical(self) -> None:
        s = ReviewSummary(findings=[_make_finding(severity=Severity.CRITICAL)])
        assert s.exit_code == 2

    def test_filter_min_severity(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(severity=Severity.INFO),
            _make_finding(severity=Severity.WARNING),
            _make_finding(severity=Severity.ERROR),
        ])
        result = s.filter(min_severity=Severity.WARNING)
        assert len(result) == 2
        assert all(f.severity >= Severity.WARNING for f in result)

    def test_filter_categories(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(category=Category.COMPLEXITY),
            _make_finding(category=Category.SECURITY),
            _make_finding(category=Category.STYLE),
        ])
        result = s.filter(categories={Category.SECURITY, Category.STYLE})
        assert len(result) == 2

    def test_filter_files(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(file="a.py"),
            _make_finding(file="b.py"),
            _make_finding(file="c.py"),
        ])
        result = s.filter(files={"a.py", "c.py"})
        assert len(result) == 2

    def test_filter_combined(self) -> None:
        s = ReviewSummary(findings=[
            _make_finding(severity=Severity.INFO, category=Category.STYLE, file="a.py"),
            _make_finding(severity=Severity.ERROR, category=Category.STYLE, file="a.py"),
            _make_finding(severity=Severity.ERROR, category=Category.SECURITY, file="b.py"),
        ])
        result = s.filter(
            min_severity=Severity.WARNING,
            categories={Category.STYLE},
            files={"a.py"},
        )
        assert len(result) == 1
        assert result[0].severity == Severity.ERROR


# ---------------------------------------------------------------------------
# ReviewConfig
# ---------------------------------------------------------------------------

class TestReviewConfig:
    def test_should_analyze_file_includes_py(self) -> None:
        cfg = ReviewConfig()
        assert cfg.should_analyze_file("myapp/views.py")

    def test_should_analyze_file_excludes_migrations(self) -> None:
        cfg = ReviewConfig()
        assert not cfg.should_analyze_file("myapp/migrations/0001_initial.py")

    def test_should_analyze_file_excludes_pycache(self) -> None:
        cfg = ReviewConfig()
        assert not cfg.should_analyze_file("myapp/__pycache__/views.cpython-312.pyc")

    def test_should_analyze_file_excludes_manage_py(self) -> None:
        cfg = ReviewConfig()
        assert not cfg.should_analyze_file("myproject/manage.py")

    def test_should_analyze_file_rejects_non_py(self) -> None:
        cfg = ReviewConfig()
        assert not cfg.should_analyze_file("readme.txt")

    def test_should_analyze_file_custom_exclude(self) -> None:
        cfg = ReviewConfig(exclude_patterns=["**/generated/**"])
        assert not cfg.should_analyze_file("myapp/generated/models.py")

    def test_should_analyze_file_custom_include(self) -> None:
        cfg = ReviewConfig(include_patterns=["**/*.pyi"])
        assert cfg.should_analyze_file("myapp/types.pyi")

    def test_should_report_finding_passes(self) -> None:
        cfg = ReviewConfig(min_severity=Severity.WARNING)
        assert cfg.should_report_finding("R001", Severity.ERROR)

    def test_should_report_finding_below_min_severity(self) -> None:
        cfg = ReviewConfig(min_severity=Severity.WARNING)
        assert not cfg.should_report_finding("R001", Severity.INFO)

    def test_should_report_finding_ignored_rule(self) -> None:
        cfg = ReviewConfig(ignore_rules={"R001"})
        assert not cfg.should_report_finding("R001", Severity.CRITICAL)

    def test_should_report_finding_at_threshold(self) -> None:
        cfg = ReviewConfig(min_severity=Severity.WARNING)
        assert cfg.should_report_finding("R001", Severity.WARNING)


# ---------------------------------------------------------------------------
# ReviewEngine
# ---------------------------------------------------------------------------

class TestReviewEngineSingleAnalyzer:
    def test_single_analyzer_produces_findings(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")

        finding = _make_finding(file=str(src))
        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg, [finding])])

        summary = engine.review_file(src)
        assert summary.files_analyzed == 1
        assert summary.total == 1
        assert summary.findings[0].rule_id == "TST001"

    def test_analyzer_name_recorded(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_file(src)
        assert "stub" in summary.analyzers_run


class TestReviewEngineMultipleAnalyzers:
    def test_multiple_analyzers_combined(self, tmp_path: Path) -> None:
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")

        f1 = _make_finding(rule_id="A001", file=str(src))
        f2 = _make_finding(rule_id="B001", file=str(src))

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(
            config=cfg,
            custom_analyzers=[
                StubAnalyzer(cfg, [f1]),
                StubAnalyzer(cfg, [f2]),
            ],
        )

        summary = engine.review_file(src)
        assert summary.total == 2
        rule_ids = {f.rule_id for f in summary.findings}
        assert rule_ids == {"A001", "B001"}


class TestReviewEngineFileCollection:
    def test_collects_py_files_from_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
        (tmp_path / "c.txt").write_text("not python\n", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_directory(tmp_path)
        assert summary.files_analyzed == 2

    def test_respects_exclude_patterns(self, tmp_path: Path) -> None:
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "views.py").write_text("y = 2\n", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_directory(tmp_path)
        assert summary.files_analyzed == 1

    def test_respects_ignore_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("x = 1\n", encoding="utf-8")
        b.write_text("y = 2\n", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set(), ignore_files={str(b)})
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_directory(tmp_path)
        assert summary.files_analyzed == 1


class TestReviewEngineSyntaxErrors:
    def test_syntax_error_skipped_gracefully(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.py"
        bad.write_text("def f(\n", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_file(bad)
        # file counted as analyzed but no findings since parse failed
        assert summary.files_analyzed == 1
        assert summary.total == 0

    def test_crashing_analyzer_does_not_break_run(self, tmp_path: Path) -> None:
        src = tmp_path / "ok.py"
        src.write_text("x = 1\n", encoding="utf-8")

        finding = _make_finding(file=str(src))
        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(
            config=cfg,
            custom_analyzers=[CrashingAnalyzer(cfg), StubAnalyzer(cfg, [finding])],
        )
        summary = engine.review_file(src)
        # crasher caught, stub still produces its finding
        assert summary.total == 1


class TestReviewEngineEmptyFiles:
    def test_empty_file_handled(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")

        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg)])
        summary = engine.review_file(empty)
        assert summary.files_analyzed == 1
        assert summary.total == 0

    def test_empty_file_with_findings_analyzer(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")

        finding = _make_finding(file=str(empty))
        cfg = ReviewConfig(analyzers=set())
        engine = ReviewEngine(config=cfg, custom_analyzers=[StubAnalyzer(cfg, [finding])])
        summary = engine.review_file(empty)
        assert summary.total == 1
