"""Tests for django_matt.advisor — health scoring and refactoring prompts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from django_matt.advisor.health import (
    CodeHealthScorer,
    CommitHealth,
    FileHealth,
    HealthTrend,
    ProjectHealth,
    _score_to_grade,
)
from django_matt.advisor.prompts import RefactorPrompt, RefactorPromptGenerator
from django_matt.review.findings import (
    Category,
    Finding,
    Location,
    ReviewSummary,
    Severity,
)

# -- Helpers ---------------------------------------------------------------

def _f(
    *,
    rule_id: str = "TST001",
    severity: Severity = Severity.WARNING,
    category: Category = Category.COMPLEXITY,
    file: str = "app.py",
    line: int = 10,
    message: str = "test finding",
    suggestion: str | None = "fix it",
    function: str | None = None,
    class_name: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        category=category,
        location=Location(file=file, line=line, function=function, class_name=class_name),
        suggestion=suggestion,
    )


# -- Grade tests -----------------------------------------------------------

class TestScoreToGrade:
    def test_perfect_score(self) -> None:
        assert _score_to_grade(10.0) == "A+"

    def test_zero_score(self) -> None:
        assert _score_to_grade(0.0) == "F"

    def test_mid_score(self) -> None:
        assert _score_to_grade(7.5) == "B"

    def test_boundary(self) -> None:
        assert _score_to_grade(9.5) == "A+"
        assert _score_to_grade(9.4) == "A"

    def test_negative_score(self) -> None:
        assert _score_to_grade(-1.0) == "F"


# -- CodeHealthScorer tests ------------------------------------------------

class TestCodeHealthScorer:
    def setup_method(self) -> None:
        self.scorer = CodeHealthScorer()

    def test_no_findings_perfect_score(self) -> None:
        result = self.scorer.score_file("clean.py", [], loc=100)
        assert result.score == 10.0
        assert result.grade == "A+"
        assert result.finding_count == 0

    def test_single_warning_deducts(self) -> None:
        findings = [_f(severity=Severity.WARNING, category=Category.COMPLEXITY)]
        result = self.scorer.score_file("app.py", findings, loc=100)
        assert result.score < 10.0
        assert result.finding_count == 1

    def test_critical_security_heavy_deduction(self) -> None:
        findings = [_f(severity=Severity.CRITICAL, category=Category.SECURITY)]
        result = self.scorer.score_file("app.py", findings, loc=100)
        # 3.0 * 1.5 = 4.5 deduction
        assert result.score == pytest.approx(5.5)

    def test_score_floors_at_zero(self) -> None:
        findings = [
            _f(severity=Severity.CRITICAL, category=Category.SECURITY, rule_id=f"SEC{i}")
            for i in range(10)
        ]
        result = self.scorer.score_file("app.py", findings, loc=100)
        assert result.score == 0.0

    def test_larger_file_scales_deduction(self) -> None:
        findings = [_f(severity=Severity.WARNING)]
        small = self.scorer.score_file("small.py", findings, loc=50)
        large = self.scorer.score_file("large.py", findings, loc=500)
        # Same finding, larger file gets less deduction per LOC
        assert large.score > small.score

    def test_deductions_tracked_by_rule(self) -> None:
        findings = [
            _f(rule_id="CX001", severity=Severity.WARNING),
            _f(rule_id="CX001", severity=Severity.WARNING),
            _f(rule_id="SEC001", severity=Severity.ERROR),
        ]
        result = self.scorer.score_file("app.py", findings, loc=100)
        assert "CX001" in result.deductions
        assert "SEC001" in result.deductions
        # 2x WARNING (1.0 each) = 2.0, 1x ERROR (2.0) = 2.0
        assert result.deductions["CX001"] == pytest.approx(2.0)
        assert result.deductions["SEC001"] == pytest.approx(2.0)

    def test_finding_deduction_value(self) -> None:
        finding = _f(severity=Severity.ERROR, category=Category.SECURITY)
        d = self.scorer.finding_deduction(finding)
        # 2.0 * 1.5 = 3.0
        assert d == pytest.approx(3.0)


class TestProjectHealth:
    def setup_method(self) -> None:
        self.scorer = CodeHealthScorer()

    def test_empty_project(self) -> None:
        result = self.scorer.score_project([])
        assert result.score == 10.0
        assert result.grade == "A+"
        assert result.total_files == 0

    def test_single_file_project(self) -> None:
        fh = self.scorer.score_file("app.py", [], loc=100)
        result = self.scorer.score_project([fh])
        assert result.score == 10.0
        assert result.total_files == 1

    def test_loc_weighted_average(self) -> None:
        # Large clean file + small dirty file = weighted toward clean
        clean = FileHealth(file="clean.py", score=10.0, grade="A+", loc=1000, finding_count=0)
        dirty = FileHealth(file="dirty.py", score=2.0, grade="F", loc=100, finding_count=10)
        result = self.scorer.score_project([clean, dirty])
        # Weighted: (10*1000 + 2*100) / 1100 = 9.27...
        assert result.score > 9.0
        assert result.total_loc == 1100

    def test_score_summary_includes_clean_files(self) -> None:
        summary = ReviewSummary(files_analyzed=2)
        summary.findings = [_f(file="dirty.py")]
        file_loc = {"dirty.py": 100, "clean.py": 200}
        result = self.scorer.score_summary(summary, file_loc)
        assert result.total_files == 2
        # clean.py should have perfect score
        clean = next(f for f in result.file_scores if f.file == "clean.py")
        assert clean.score == 10.0

    def test_worst_files(self) -> None:
        files = [
            FileHealth(file=f"f{i}.py", score=float(i), grade="", loc=100, finding_count=0)
            for i in range(15)
        ]
        result = self.scorer.score_project(files)
        worst = result.worst_files
        assert len(worst) == 10
        assert worst[0].score == 0.0


# -- HealthTrend tests -----------------------------------------------------

class TestHealthTrend:
    def test_record_and_trend(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        trend = HealthTrend(db_path=db_path)

        health = ProjectHealth(
            score=7.5, grade="B", file_scores=[], total_findings=10,
            total_files=5, total_loc=500,
        )
        sid = trend.record("abc123", health)
        assert sid == 1

        snapshots = trend.trend(limit=5)
        assert len(snapshots) == 1
        assert snapshots[0].commit_sha == "abc123"
        assert snapshots[0].score == 7.5
        trend.close()

    def test_trend_ordering(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        trend = HealthTrend(db_path=db_path)

        for i, sha in enumerate(["aaa", "bbb", "ccc"]):
            health = ProjectHealth(
                score=float(7 + i), grade="B", file_scores=[], total_findings=0,
                total_files=1, total_loc=100,
            )
            trend.record(sha, health)

        snapshots = trend.trend(limit=10)
        assert len(snapshots) == 3
        # Newest first
        assert snapshots[0].commit_sha == "ccc"
        assert snapshots[2].commit_sha == "aaa"
        trend.close()

    def test_record_with_file_scores(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        trend = HealthTrend(db_path=db_path)

        files = [
            FileHealth(file="a.py", score=9.0, grade="A", loc=100, finding_count=1),
            FileHealth(file="b.py", score=5.0, grade="D+", loc=200, finding_count=5),
        ]
        health = ProjectHealth(
            score=6.3, grade="C+", file_scores=files, total_findings=6,
            total_files=2, total_loc=300,
        )
        trend.record("abc", health)

        # Verify file scores were stored
        rows = trend.db.execute(
            "SELECT file, score FROM file_health ORDER BY file"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0] == ("a.py", 9.0)
        assert rows[1] == ("b.py", 5.0)
        trend.close()

    def test_regressions(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        trend = HealthTrend(db_path=db_path)

        # Record a baseline
        files_v1 = [
            FileHealth(file="a.py", score=9.0, grade="A", loc=100, finding_count=1),
            FileHealth(file="b.py", score=7.0, grade="B-", loc=200, finding_count=3),
        ]
        health_v1 = ProjectHealth(
            score=7.7, grade="B+", file_scores=files_v1, total_findings=4,
            total_files=2, total_loc=300,
        )
        trend.record("v1", health_v1)

        # Current health: b.py regressed
        files_v2 = [
            FileHealth(file="a.py", score=9.0, grade="A", loc=100, finding_count=1),
            FileHealth(file="b.py", score=4.0, grade="D-", loc=200, finding_count=8,
                       deductions={"CX003": 2.0, "SEC001": 1.0}),
        ]
        health_v2 = ProjectHealth(
            score=5.7, grade="C-", file_scores=files_v2, total_findings=9,
            total_files=2, total_loc=300,
        )

        regs = trend.regressions(health_v2)
        assert len(regs) == 1
        assert regs[0].file == "b.py"
        assert regs[0].old_score == 7.0
        assert regs[0].new_score == 4.0
        assert regs[0].delta == pytest.approx(-3.0)
        trend.close()

    def test_no_regressions_when_no_history(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        trend = HealthTrend(db_path=db_path)
        health = ProjectHealth(
            score=5.0, grade="D+", file_scores=[], total_findings=0,
            total_files=0, total_loc=0,
        )
        regs = trend.regressions(health)
        assert regs == []
        trend.close()


# -- RefactorPromptGenerator tests -----------------------------------------

class TestRefactorPromptGenerator:
    def setup_method(self) -> None:
        self.gen = RefactorPromptGenerator(context_lines=3)

    def test_generate_basic_prompt(self) -> None:
        finding = _f(
            rule_id="CX003",
            severity=Severity.WARNING,
            category=Category.COMPLEXITY,
            file="app.py",
            line=5,
            message="Function too complex",
            suggestion="Extract helper functions",
            function="process_data",
        )
        source = "\n".join(f"line {i}" for i in range(1, 20))
        result = self.gen.generate(finding, source)

        assert isinstance(result, RefactorPrompt)
        assert result.finding_id == "CX003"
        assert "Function too complex" in result.summary
        assert result.file_path == "app.py"
        assert result.line_range == (5, 5)
        assert "line 5" in result.context
        assert result.priority >= 1
        assert result.health_impact > 0

    def test_prompt_contains_instructions(self) -> None:
        finding = _f(category=Category.ASYNC_SAFETY, message="Sync ORM call")
        source = "x = 1\n" * 20
        result = self.gen.generate(finding, source)
        assert "async equivalent" in result.instructions

    def test_prompt_constraints_for_function(self) -> None:
        finding = _f(function="authenticate")
        source = "x = 1\n" * 20
        result = self.gen.generate(finding, source)
        assert any("authenticate()" in c for c in result.constraints)

    def test_prompt_constraints_for_class(self) -> None:
        finding = _f(class_name="UserController")
        source = "x = 1\n" * 20
        result = self.gen.generate(finding, source)
        assert any("UserController" in c for c in result.constraints)

    def test_security_finding_constraint(self) -> None:
        finding = _f(category=Category.SECURITY)
        source = "x = 1\n" * 20
        result = self.gen.generate(finding, source)
        assert any("security" in c.lower() for c in result.constraints)

    def test_priority_scaling(self) -> None:
        low = self.gen.generate(
            _f(severity=Severity.HINT, category=Category.STYLE),
            "x = 1\n" * 20,
        )
        high = self.gen.generate(
            _f(severity=Severity.CRITICAL, category=Category.SECURITY),
            "x = 1\n" * 20,
        )
        assert high.priority > low.priority

    def test_effort_varies_by_severity(self) -> None:
        hint = self.gen.generate(_f(severity=Severity.HINT), "x=1\n" * 20)
        crit = self.gen.generate(_f(severity=Severity.CRITICAL), "x=1\n" * 20)
        assert hint.estimated_effort != crit.estimated_effort

    def test_health_impact_in_prompt_text(self) -> None:
        fh = FileHealth(file="app.py", score=6.0, grade="C", loc=100, finding_count=3)
        finding = _f(severity=Severity.ERROR, category=Category.SECURITY)
        result = self.gen.generate(finding, "x=1\n" * 20, file_health=fh)
        assert "Health impact" in result.prompt
        assert "6.0" in result.prompt


class TestRefactorPromptBatch:
    def setup_method(self) -> None:
        self.gen = RefactorPromptGenerator()

    def test_batch_filters_by_severity(self) -> None:
        findings = [
            _f(rule_id="A", severity=Severity.INFO, file="a.py"),
            _f(rule_id="B", severity=Severity.WARNING, file="a.py"),
            _f(rule_id="C", severity=Severity.ERROR, file="a.py"),
        ]
        sources = {"a.py": "x = 1\n" * 20}
        prompts = self.gen.generate_batch(findings, sources, min_severity=Severity.WARNING)
        assert len(prompts) == 2
        ids = {p.finding_id for p in prompts}
        assert ids == {"B", "C"}

    def test_batch_max_count(self) -> None:
        findings = [
            _f(rule_id=f"R{i}", severity=Severity.WARNING, file="a.py")
            for i in range(10)
        ]
        sources = {"a.py": "x = 1\n" * 20}
        prompts = self.gen.generate_batch(findings, sources, max_count=3)
        assert len(prompts) == 3

    def test_batch_sorted_by_priority(self) -> None:
        findings = [
            _f(rule_id="LOW", severity=Severity.HINT, category=Category.STYLE, file="a.py"),
            _f(rule_id="HIGH", severity=Severity.CRITICAL, category=Category.SECURITY, file="a.py"),
        ]
        sources = {"a.py": "x = 1\n" * 20}
        prompts = self.gen.generate_batch(findings, sources, min_severity=Severity.HINT)
        assert prompts[0].finding_id == "HIGH"

    def test_batch_skips_missing_sources(self) -> None:
        findings = [_f(file="missing.py")]
        prompts = self.gen.generate_batch(findings, {})
        assert prompts == []


class TestRefactorPromptFormatting:
    def setup_method(self) -> None:
        self.gen = RefactorPromptGenerator()

    def test_format_markdown(self) -> None:
        finding = _f(severity=Severity.WARNING, file="a.py")
        prompts = [self.gen.generate(finding, "x = 1\n" * 20)]
        md = self.gen.format_markdown(prompts)
        assert "# Refactoring Advisor" in md
        assert "1 suggestions" in md
        assert "test finding" in md

    def test_format_markdown_empty(self) -> None:
        md = self.gen.format_markdown([])
        assert "No refactoring suggestions" in md

    def test_format_json(self) -> None:
        import orjson

        finding = _f(severity=Severity.WARNING, file="a.py")
        prompts = [self.gen.generate(finding, "x = 1\n" * 20)]
        json_str = self.gen.format_json(prompts)
        data = orjson.loads(json_str)
        assert len(data) == 1
        assert data[0]["finding_id"] == "TST001"
        assert "priority" in data[0]
        assert "prompt" in data[0]


# -- Bug fix regression tests ----------------------------------------------

class TestBugFixes:
    """Regression tests for the 4 review/ bugs fixed in this session."""

    def test_ai_reviewer_unknown_category_skipped(self) -> None:
        """Bug #4: Unknown AI categories should be skipped, not defaulted to SOLID."""
        from django_matt.review.ai_reviewer import AIReviewer
        from django_matt.review.config import ReviewConfig

        reviewer = AIReviewer(ReviewConfig())
        # Simulate response with unknown category
        import orjson
        response_json = orjson.dumps({
            "findings": [
                {
                    "rule_id": "AIR-001",
                    "file": "test.py",
                    "line": 1,
                    "severity": "warning",
                    "message": "test",
                    "category": "completely_unknown_category",
                },
                {
                    "rule_id": "AIR-002",
                    "file": "test.py",
                    "line": 2,
                    "severity": "warning",
                    "message": "valid",
                    "category": "security",
                },
            ],
            "summary": "test",
        }).decode()
        result = reviewer._parse_response(response_json, 100)
        # Unknown category finding should be skipped
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "AIR-002"
        assert result.findings[0].category == Category.SECURITY

    def test_api_design_auth_scoped_to_class(self, tmp_path: Path) -> None:
        """Bug #2: Auth check should be scoped to enclosing class, not any class."""
        import ast

        from django_matt.review.analyzers.api_design import APIDesignAnalyzer
        from django_matt.review.config import ReviewConfig

        source = '''
class PublicAPI:
    @api.post("/public")
    def create_public(self):
        pass

class ProtectedAPI:
    permission_classes = [IsAuthenticated]

    @api.post("/protected")
    def create_protected(self):
        pass
'''
        tree = ast.parse(source)
        analyzer = APIDesignAnalyzer(ReviewConfig())
        findings = analyzer.analyze_file(Path("test.py"), tree, source)

        # Should flag PublicAPI.create_public (no auth) but NOT ProtectedAPI.create_protected
        api003 = [f for f in findings if f.rule_id == "API003"]
        assert len(api003) == 1
        assert "create_public" in api003[0].message

    def test_deduplication_same_message(self) -> None:
        """Bug #3: Same message at same location should be deduplicated."""
        from django_matt.review.engine import ReviewEngine

        findings = [
            _f(rule_id="PERF001", message="Sync ORM in async", file="a.py", line=10),
            _f(rule_id="ASYNC001", message="Sync ORM in async", file="a.py", line=10),
        ]
        deduped = ReviewEngine._deduplicate(findings)
        assert len(deduped) == 1

    def test_deduplication_different_messages_preserved(self) -> None:
        """Bug #3: Different messages at same location should be preserved."""
        from django_matt.review.engine import ReviewEngine

        findings = [
            _f(rule_id="CX001", message="Too complex", file="a.py", line=10),
            _f(rule_id="SEC001", message="Security issue", file="a.py", line=10),
        ]
        deduped = ReviewEngine._deduplicate(findings)
        assert len(deduped) == 2

    def test_dedup_keeps_highest_severity(self) -> None:
        """Bug #3: Dedup should keep the finding with highest severity."""
        from django_matt.review.engine import ReviewEngine

        findings = [
            _f(severity=Severity.WARNING, message="same issue", file="a.py", line=10),
            _f(severity=Severity.ERROR, message="same issue", file="a.py", line=10),
        ]
        deduped = ReviewEngine._deduplicate(findings)
        assert len(deduped) == 1
        assert deduped[0].severity == Severity.ERROR

    def test_refactor_suggestions_on_summary(self) -> None:
        """Bug #1: ReviewSummary should carry refactor_suggestions."""
        summary = ReviewSummary()
        assert hasattr(summary, "refactor_suggestions")
        summary.refactor_suggestions.append({"title": "test", "effort": "low"})
        assert len(summary.refactor_suggestions) == 1
