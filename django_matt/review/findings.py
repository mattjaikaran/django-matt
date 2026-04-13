"""
Review findings — structured representation of code audit results.

Each Finding has a severity, category, location, and actionable message.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Severity(enum.IntEnum):
    """Finding severity levels, ordered by importance."""

    INFO = 0
    HINT = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class Category(str, enum.Enum):
    """Categories of code review findings."""

    COMPLEXITY = "complexity"
    SOLID = "solid"
    DJANGO = "django"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MODULARITY = "modularity"
    AI_FRIENDLY = "ai_friendly"
    STYLE = "style"
    TESTING = "testing"


@dataclass(frozen=True, slots=True)
class Location:
    """Source code location for a finding."""

    file: str
    line: int | None = None
    end_line: int | None = None
    column: int | None = None
    function: str | None = None
    class_name: str | None = None

    def __str__(self) -> str:
        parts = [self.file]
        if self.line is not None:
            parts.append(str(self.line))
        loc = ":".join(parts)
        if self.function:
            loc += f" ({self.function})"
        elif self.class_name:
            loc += f" ({self.class_name})"
        return loc


@dataclass(frozen=True, slots=True)
class Finding:
    """A single code review finding."""

    rule_id: str
    message: str
    severity: Severity
    category: Category
    location: Location
    suggestion: str | None = None
    context: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        sev = self.severity.name
        return f"[{sev}] {self.rule_id}: {self.message} at {self.location}"


@dataclass
class ReviewSummary:
    """Aggregated summary of a code review run."""

    findings: list[Finding] = field(default_factory=list)
    files_analyzed: int = 0
    analyzers_run: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def by_severity(self) -> dict[Severity, int]:
        counts: dict[Severity, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    @property
    def by_category(self) -> dict[Category, int]:
        counts: dict[Category, int] = {}
        for f in self.findings:
            counts[f.category] = counts.get(f.category, 0) + 1
        return counts

    @property
    def by_file(self) -> dict[str, list[Finding]]:
        result: dict[str, list[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.location.file, []).append(f)
        return result

    @property
    def has_errors(self) -> bool:
        return any(f.severity >= Severity.ERROR for f in self.findings)

    @property
    def has_critical(self) -> bool:
        return any(f.severity >= Severity.CRITICAL for f in self.findings)

    @property
    def exit_code(self) -> int:
        """Return non-zero if any findings exceed error threshold."""
        if self.has_critical:
            return 2
        if self.has_errors:
            return 1
        return 0

    def filter(
        self,
        min_severity: Severity = Severity.INFO,
        categories: set[Category] | None = None,
        files: set[str] | None = None,
    ) -> list[Finding]:
        results = [f for f in self.findings if f.severity >= min_severity]
        if categories:
            results = [f for f in results if f.category in categories]
        if files:
            results = [f for f in results if f.location.file in files]
        return results
