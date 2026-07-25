"""
Code health scoring — per-file and per-project numeric health (1-10).

Scores are derived from review findings weighted by severity and category.
HealthTrend stores scores over git commits in a SQLite database for trending.
"""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from django_matt.review.findings import Category, Finding, ReviewSummary, Severity

# -- Weight matrix: (severity, category) -> point deduction ----------------

_SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 3.0,
    Severity.ERROR: 2.0,
    Severity.WARNING: 1.0,
    Severity.HINT: 0.3,
    Severity.INFO: 0.1,
}

_CATEGORY_MULTIPLIER: dict[Category, float] = {
    Category.SECURITY: 1.5,
    Category.ASYNC_SAFETY: 1.3,
    Category.N_PLUS_ONE: 1.2,
    Category.COMPLEXITY: 1.0,
    Category.SOLID: 1.0,
    Category.DJANGO: 1.0,
    Category.PERFORMANCE: 1.0,
    Category.MODULARITY: 0.8,
    Category.API_DESIGN: 0.8,
    Category.AI_FRIENDLY: 0.7,
    Category.MIGRATION: 0.7,
    Category.STYLE: 0.5,
    Category.TESTING: 0.5,
}

_GRADES = [
    (9.5, "A+"),
    (9.0, "A"),
    (8.5, "A-"),
    (8.0, "B+"),
    (7.5, "B"),
    (7.0, "B-"),
    (6.5, "C+"),
    (6.0, "C"),
    (5.5, "C-"),
    (5.0, "D+"),
    (4.5, "D"),
    (4.0, "D-"),
    (0.0, "F"),
]


def _score_to_grade(score: float) -> str:
    for threshold, grade in _GRADES:
        if score >= threshold:
            return grade
    return "F"


# -- Data classes ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FileHealth:
    """Health score for a single file."""

    file: str
    score: float
    grade: str
    loc: int
    finding_count: int
    deductions: dict[str, float] = field(default_factory=dict)

    @property
    def score_rounded(self) -> float:
        return round(self.score, 1)


@dataclass(frozen=True, slots=True)
class ProjectHealth:
    """Aggregate health score across the project."""

    score: float
    grade: str
    file_scores: list[FileHealth]
    total_findings: int
    total_files: int
    total_loc: int

    @property
    def score_rounded(self) -> float:
        return round(self.score, 1)

    @property
    def worst_files(self) -> list[FileHealth]:
        return sorted(self.file_scores, key=lambda f: f.score)[:10]

    @property
    def best_files(self) -> list[FileHealth]:
        return sorted(self.file_scores, key=lambda f: -f.score)[:10]


@dataclass(frozen=True, slots=True)
class HealthRegression:
    """A file whose health score dropped."""

    file: str
    old_score: float
    new_score: float
    delta: float
    new_findings: list[str]  # rule_ids of new findings


@dataclass(frozen=True, slots=True)
class CommitHealth:
    """Health snapshot for a single commit."""

    commit_sha: str
    score: float
    grade: str
    total_findings: int
    total_files: int
    timestamp: str


# -- Scorer ----------------------------------------------------------------


class CodeHealthScorer:
    """Calculate health scores from review findings."""

    def __init__(
        self,
        severity_weights: dict[Severity, float] | None = None,
        category_multipliers: dict[Category, float] | None = None,
    ) -> None:
        self._sev_w = severity_weights or _SEVERITY_WEIGHT
        self._cat_m = category_multipliers or _CATEGORY_MULTIPLIER

    def finding_deduction(self, finding: Finding) -> float:
        """Calculate point deduction for a single finding."""
        sev = self._sev_w.get(finding.severity, 1.0)
        cat = self._cat_m.get(finding.category, 1.0)
        return sev * cat

    def score_file(self, file_path: str, findings: list[Finding], loc: int) -> FileHealth:
        """Score a single file. Start at 10, deduct for findings, floor at 0."""
        deductions: dict[str, float] = {}
        total_deduction = 0.0

        for f in findings:
            d = self.finding_deduction(f)
            deductions[f.rule_id] = deductions.get(f.rule_id, 0.0) + d
            total_deduction += d

        # Scale deduction by file size — small files penalized more per-finding
        # Baseline: 100 LOC. Files < 100 LOC get slightly harsher scoring.
        scale = max(1.0, loc / 100.0)
        adjusted = total_deduction / scale

        score = max(0.0, min(10.0, 10.0 - adjusted))
        return FileHealth(
            file=file_path,
            score=score,
            grade=_score_to_grade(score),
            loc=loc,
            finding_count=len(findings),
            deductions=deductions,
        )

    def score_project(self, file_scores: list[FileHealth]) -> ProjectHealth:
        """Aggregate file scores into project health, weighted by LOC."""
        if not file_scores:
            return ProjectHealth(
                score=10.0,
                grade="A+",
                file_scores=[],
                total_findings=0,
                total_files=0,
                total_loc=0,
            )

        total_loc = sum(f.loc for f in file_scores)
        if total_loc == 0:
            avg = sum(f.score for f in file_scores) / len(file_scores)
        else:
            avg = sum(f.score * f.loc for f in file_scores) / total_loc

        return ProjectHealth(
            score=avg,
            grade=_score_to_grade(avg),
            file_scores=file_scores,
            total_findings=sum(f.finding_count for f in file_scores),
            total_files=len(file_scores),
            total_loc=total_loc,
        )

    def score_summary(self, summary: ReviewSummary, file_loc: dict[str, int]) -> ProjectHealth:
        """Score a full ReviewSummary, given a map of file -> LOC."""
        by_file = summary.by_file
        scores = []
        for file_path, findings in by_file.items():
            loc = file_loc.get(file_path, 1)
            scores.append(self.score_file(file_path, findings, loc))

        # Include clean files (analyzed but no findings)
        finding_files = set(by_file.keys())
        for file_path, loc in file_loc.items():
            if file_path not in finding_files:
                scores.append(
                    FileHealth(
                        file=file_path,
                        score=10.0,
                        grade="A+",
                        loc=loc,
                        finding_count=0,
                        deductions={},
                    )
                )

        return self.score_project(scores)


# -- Trend tracking --------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_sha TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    project_score REAL NOT NULL,
    project_grade TEXT NOT NULL,
    total_findings INTEGER NOT NULL,
    total_files INTEGER NOT NULL,
    total_loc INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS file_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES health_snapshots(id),
    file TEXT NOT NULL,
    score REAL NOT NULL,
    grade TEXT NOT NULL,
    loc INTEGER NOT NULL,
    finding_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_sha ON health_snapshots(commit_sha);
CREATE INDEX IF NOT EXISTS idx_file_health_snapshot ON file_health(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_file_health_file ON file_health(file);
"""


class HealthTrend:
    """Track health scores over git commits in SQLite."""

    def __init__(self, db_path: Path = Path(".matthealth.db")) -> None:
        self.db_path = db_path
        self._db: sqlite3.Connection | None = None

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(str(self.db_path))
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(_SCHEMA_SQL)
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def record(self, commit_sha: str, health: ProjectHealth) -> int:
        """Record a health snapshot. Returns the snapshot ID."""
        cur = self.db.execute(
            "INSERT INTO health_snapshots (commit_sha, project_score, project_grade, "
            "total_findings, total_files, total_loc) VALUES (?, ?, ?, ?, ?, ?)",
            (
                commit_sha,
                health.score,
                health.grade,
                health.total_findings,
                health.total_files,
                health.total_loc,
            ),
        )
        snapshot_id = cur.lastrowid
        assert snapshot_id is not None

        for fs in health.file_scores:
            self.db.execute(
                "INSERT INTO file_health (snapshot_id, file, score, grade, loc, finding_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (snapshot_id, fs.file, fs.score, fs.grade, fs.loc, fs.finding_count),
            )

        self.db.commit()
        return snapshot_id

    def trend(self, limit: int = 10) -> list[CommitHealth]:
        """Get recent health snapshots, newest first."""
        rows = self.db.execute(
            "SELECT commit_sha, project_score, project_grade, total_findings, "
            "total_files, timestamp FROM health_snapshots "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            CommitHealth(
                commit_sha=r[0],
                score=r[1],
                grade=r[2],
                total_findings=r[3],
                total_files=r[4],
                timestamp=r[5],
            )
            for r in rows
        ]

    def regressions(
        self, current: ProjectHealth, previous_sha: str | None = None
    ) -> list[HealthRegression]:
        """Find files whose health regressed vs. the previous snapshot."""
        if previous_sha:
            row = self.db.execute(
                "SELECT id FROM health_snapshots WHERE commit_sha = ? ORDER BY id DESC LIMIT 1",
                (previous_sha,),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT id FROM health_snapshots ORDER BY id DESC LIMIT 1",
            ).fetchone()

        if not row:
            return []

        snapshot_id = row[0]
        prev_scores: dict[str, float] = {}
        for r in self.db.execute(
            "SELECT file, score FROM file_health WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall():
            prev_scores[r[0]] = r[1]

        regressions = []
        for fs in current.file_scores:
            prev = prev_scores.get(fs.file)
            if prev is not None and fs.score < prev - 0.1:
                regressions.append(
                    HealthRegression(
                        file=fs.file,
                        old_score=prev,
                        new_score=fs.score,
                        delta=fs.score - prev,
                        new_findings=list(fs.deductions.keys()),
                    )
                )

        return sorted(regressions, key=lambda r: r.delta)

    @staticmethod
    def current_commit_sha() -> str:
        """Get the current git HEAD SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return "unknown"
