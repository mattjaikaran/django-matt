"""
Core audit framework for AI-assisted codebase analysis.

Provides the foundation for running multi-perspective audits with
configurable strictness levels and pluggable auditors.
"""

from __future__ import annotations

import ast
import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger("django_matt.audits")


class AuditLevel(str, Enum):
    """
    Strictness level for audits.

    Attributes:
        RELAXED: Only critical issues.
        STANDARD: Critical + important issues (default).
        STRICT: All issues including suggestions.
        PARANOID: Security-focused, treats warnings as errors.
    """

    RELAXED = "relaxed"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"


class AuditSeverity(str, Enum):
    """
    Severity level for audit findings.

    Attributes:
        CRITICAL: Must fix immediately. Security vulnerabilities, data loss risks.
        HIGH: Should fix soon. Performance issues, bad practices.
        MEDIUM: Consider fixing. Code quality, maintainability.
        LOW: Optional improvement. Style, minor optimizations.
        INFO: Informational. Suggestions, best practices.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

# Disambiguation alias: prefer FindingSeverity to avoid collision
# with django_matt.audit.AuditSeverity (operational log severity).
FindingSeverity = AuditSeverity


class AuditCategory(str, Enum):
    """
    Category of audit to run.

    Attributes:
        SECURITY: Auth, permissions, SQL injection, XSS, CSRF, secrets exposure.
        PERFORMANCE: N+1 queries, missing indexes, cache usage, async opportunities.
        SCALABILITY: Connection pooling, task offloading, pagination, rate limiting.
        BUNDLE_SIZE: Unused modules, tree-shaking opportunities, lazy loading.
        BEST_PRACTICES: Code organization, typing, documentation, testing coverage.
        ACCESSIBILITY: Frontend a11y (if using components/pages modules).
        MAINTAINABILITY: Complexity metrics, dependency health, tech debt.
        ALL: Run all audit categories.
    """

    SECURITY = "security"
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    BUNDLE_SIZE = "bundle_size"
    BEST_PRACTICES = "best_practices"
    ACCESSIBILITY = "accessibility"
    MAINTAINABILITY = "maintainability"
    ALL = "all"


class AuditFinding(BaseModel):
    """
    A single finding from an audit.

    Attributes:
        id: Unique identifier for this finding type (e.g., "SEC001").
        severity: How severe is this finding.
        category: Which audit category found this.
        message: Human-readable description of the issue.
        file: Path to the file containing the issue.
        line: Line number where the issue was found.
        column: Column number where the issue starts.
        code: The problematic code snippet.
        suggestion: Suggested fix or improvement.
        fix_command: Optional command to auto-fix this issue.
        documentation_url: Link to relevant documentation.
        tags: Additional tags for filtering (e.g., "owasp-top-10").
    """

    id: str = Field(..., description="Unique identifier for this finding type")
    severity: AuditSeverity = Field(..., description="Severity level")
    category: AuditCategory = Field(..., description="Audit category")
    message: str = Field(..., description="Human-readable description")
    file: str | None = Field(None, description="File path")
    line: int | None = Field(None, description="Line number")
    column: int | None = Field(None, description="Column number")
    code: str | None = Field(None, description="Problematic code snippet")
    suggestion: str | None = Field(None, description="Suggested fix")
    fix_command: str | None = Field(None, description="Auto-fix command")
    documentation_url: str | None = Field(None, description="Documentation link")
    tags: list[str] = Field(default_factory=list, description="Additional tags")

    def to_sarif(self) -> dict[str, Any]:
        """
        Convert this finding to SARIF format for GitHub Code Scanning.

        Returns:
            dict: SARIF-formatted result object.
        """
        result: dict[str, Any] = {
            "ruleId": self.id,
            "level": self._sarif_level(),
            "message": {"text": self.message},
        }

        if self.file:
            location: dict[str, Any] = {
                "physicalLocation": {
                    "artifactLocation": {"uri": self.file},
                }
            }
            if self.line:
                location["physicalLocation"]["region"] = {
                    "startLine": self.line,
                    "startColumn": self.column or 1,
                }
            result["locations"] = [location]

        if self.suggestion:
            result["fixes"] = [
                {
                    "description": {"text": self.suggestion},
                }
            ]

        return result

    def _sarif_level(self) -> str:
        """Map severity to SARIF level."""
        mapping = {
            AuditSeverity.CRITICAL: "error",
            AuditSeverity.HIGH: "error",
            AuditSeverity.MEDIUM: "warning",
            AuditSeverity.LOW: "note",
            AuditSeverity.INFO: "note",
        }
        return mapping.get(self.severity, "note")


class AuditResult(BaseModel):
    """
    Result from a single auditor.

    Attributes:
        auditor_name: Name of the auditor that produced this result.
        category: Category of audit performed.
        findings: List of findings discovered.
        duration_ms: Time taken to run the audit in milliseconds.
        files_scanned: Number of files scanned.
        error: Error message if the audit failed.
    """

    auditor_name: str = Field(..., description="Name of the auditor")
    category: AuditCategory = Field(..., description="Audit category")
    findings: list[AuditFinding] = Field(default_factory=list)
    duration_ms: float = Field(0.0, description="Duration in milliseconds")
    files_scanned: int = Field(0, description="Number of files scanned")
    error: str | None = Field(None, description="Error message if failed")

    @property
    def is_success(self) -> bool:
        """Check if audit completed without errors."""
        return self.error is None

    @property
    def critical_count(self) -> int:
        """Count of critical findings."""
        return sum(1 for f in self.findings if f.severity == AuditSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high severity findings."""
        return sum(1 for f in self.findings if f.severity == AuditSeverity.HIGH)


class AuditReport(BaseModel):
    """
    Complete audit report aggregating all results.

    Attributes:
        results: Results from each auditor.
        level: Strictness level used.
        started_at: When the audit started.
        completed_at: When the audit finished.
        total_files: Total files scanned across all auditors.
        project_path: Path to the project that was audited.
        django_matt_version: Version of django-matt used.
    """

    results: list[AuditResult] = Field(default_factory=list)
    level: AuditLevel = Field(AuditLevel.STANDARD)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(None)
    total_files: int = Field(0)
    project_path: str | None = Field(None)
    django_matt_version: str | None = Field(None)

    @property
    def all_findings(self) -> list[AuditFinding]:
        """Get all findings from all auditors."""
        findings = []
        for result in self.results:
            findings.extend(result.findings)
        return findings

    @property
    def critical_findings(self) -> list[AuditFinding]:
        """Get only critical findings."""
        return [f for f in self.all_findings if f.severity == AuditSeverity.CRITICAL]

    @property
    def passed(self) -> bool:
        """
        Check if the audit passed (no critical issues).

        For PARANOID level, also fails on high severity issues.
        """
        if any(f.severity == AuditSeverity.CRITICAL for f in self.all_findings):
            return False
        if self.level == AuditLevel.PARANOID:
            return not any(f.severity == AuditSeverity.HIGH for f in self.all_findings)
        return True

    @property
    def exit_code(self) -> int:
        """
        Get appropriate exit code for CI.

        Returns:
            0: Passed
            1: Failed (critical issues found)
            2: Errors during audit
        """
        if any(not r.is_success for r in self.results):
            return 2
        return 0 if self.passed else 1

    def filter_by_severity(self, min_severity: AuditSeverity) -> list[AuditFinding]:
        """
        Filter findings by minimum severity.

        Args:
            min_severity: Minimum severity to include.

        Returns:
            List of findings at or above the specified severity.
        """
        severity_order = [
            AuditSeverity.CRITICAL,
            AuditSeverity.HIGH,
            AuditSeverity.MEDIUM,
            AuditSeverity.LOW,
            AuditSeverity.INFO,
        ]
        min_index = severity_order.index(min_severity)
        allowed = set(severity_order[: min_index + 1])
        return [f for f in self.all_findings if f.severity in allowed]

    def to_sarif(self) -> dict[str, Any]:
        """
        Convert entire report to SARIF format.

        Returns:
            dict: Complete SARIF report for GitHub Code Scanning.
        """
        results = []
        rules = {}

        for finding in self.all_findings:
            results.append(finding.to_sarif())
            if finding.id not in rules:
                rules[finding.id] = {
                    "id": finding.id,
                    "name": finding.id,
                    "shortDescription": {"text": finding.message[:100]},
                    "defaultConfiguration": {
                        "level": finding._sarif_level(),
                    },
                }

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "django-matt-audit",
                            "version": self.django_matt_version or "unknown",
                            "rules": list(rules.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }

    def to_markdown(self) -> str:
        """
        Convert report to markdown format.

        Returns:
            str: Markdown-formatted audit report.
        """
        lines = [
            "# Audit Report",
            "",
            f"**Level:** {self.level.value}",
            f"**Status:** {'PASSED' if self.passed else 'FAILED'}",
            f"**Total Findings:** {len(self.all_findings)}",
            "",
        ]

        # Summary by severity
        lines.append("## Summary by Severity")
        lines.append("")
        for severity in AuditSeverity:
            count = sum(1 for f in self.all_findings if f.severity == severity)
            if count > 0:
                emoji = {
                    AuditSeverity.CRITICAL: "🔴",
                    AuditSeverity.HIGH: "🟠",
                    AuditSeverity.MEDIUM: "🟡",
                    AuditSeverity.LOW: "🔵",
                    AuditSeverity.INFO: "⚪",
                }.get(severity, "")
                lines.append(f"- {emoji} **{severity.value.upper()}:** {count}")
        lines.append("")

        # Findings by category
        lines.append("## Findings")
        lines.append("")

        for category in AuditCategory:
            if category == AuditCategory.ALL:
                continue
            category_findings = [f for f in self.all_findings if f.category == category]
            if not category_findings:
                continue

            lines.append(f"### {category.value.replace('_', ' ').title()}")
            lines.append("")

            for finding in sorted(category_findings, key=lambda f: f.severity.value):
                severity_badge = {
                    AuditSeverity.CRITICAL: "🔴 CRITICAL",
                    AuditSeverity.HIGH: "🟠 HIGH",
                    AuditSeverity.MEDIUM: "🟡 MEDIUM",
                    AuditSeverity.LOW: "🔵 LOW",
                    AuditSeverity.INFO: "⚪ INFO",
                }.get(finding.severity, finding.severity.value)

                lines.append(f"#### [{finding.id}] {severity_badge}")
                lines.append("")
                lines.append(finding.message)
                lines.append("")

                if finding.file:
                    location = finding.file
                    if finding.line:
                        location += f":{finding.line}"
                    lines.append(f"**Location:** `{location}`")
                    lines.append("")

                if finding.code:
                    lines.append("```python")
                    lines.append(finding.code)
                    lines.append("```")
                    lines.append("")

                if finding.suggestion:
                    lines.append(f"**Suggestion:** {finding.suggestion}")
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)


@dataclass
class AuditConfig:
    """
    Configuration for running audits.

    Attributes:
        level: Strictness level.
        categories: Categories to audit.
        exclude_patterns: File patterns to exclude.
        include_patterns: File patterns to include.
        max_findings: Maximum findings per category (0 = unlimited).
        fail_fast: Stop on first critical finding.
        diff_base: Only audit files changed since this git ref.
        project_path: Path to the project to audit.
    """

    level: AuditLevel = AuditLevel.STANDARD
    categories: list[AuditCategory] = field(default_factory=lambda: [AuditCategory.ALL])
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "**/migrations/**",
            "**/__pycache__/**",
            "**/tests/**",
            "**/.venv/**",
            "**/venv/**",
            "**/.env/**",
            "**/node_modules/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/.tox/**",
            "**/.nox/**",
        ]
    )
    include_patterns: list[str] = field(default_factory=lambda: ["**/*.py"])
    max_findings: int = 0
    fail_fast: bool = False
    diff_base: str | None = None
    project_path: Path | None = None


class BaseAuditor(ABC):
    """
    Base class for all auditors.

    Subclass this to create custom auditors for specific audit categories.

    Example:
        >>> class MySecurityAuditor(BaseAuditor):
        ...     name = "my-security"
        ...     category = AuditCategory.SECURITY
        ...
        ...     def audit(self, config: AuditConfig) -> AuditResult:
        ...         findings = []
        ...         for file in self.iter_files(config):
        ...             findings.extend(self._check_file(file))
        ...         return AuditResult(
        ...             auditor_name=self.name,
        ...             category=self.category,
        ...             findings=findings,
        ...         )
    """

    name: str = "base"
    category: AuditCategory = AuditCategory.ALL
    description: str = "Base auditor"

    def __init__(self) -> None:
        """Initialize the auditor."""
        self._start_time: float = 0.0

    @abstractmethod
    def audit(self, config: AuditConfig) -> AuditResult:
        """
        Run the audit and return results.

        Args:
            config: Audit configuration.

        Returns:
            AuditResult with findings.
        """
        ...

    def iter_files(self, config: AuditConfig) -> Iterator[Path]:
        """
        Iterate over files to audit based on config patterns.

        Args:
            config: Audit configuration with include/exclude patterns.

        Yields:
            Path objects for each file to audit.
        """
        project_path = config.project_path or Path.cwd()

        for pattern in config.include_patterns:
            for file_path in project_path.glob(pattern):
                if not file_path.is_file():
                    continue

                # Check exclude patterns
                excluded = False
                for exclude in config.exclude_patterns:
                    if file_path.match(exclude):
                        excluded = True
                        break

                if not excluded:
                    yield file_path

    def parse_python_file(self, file_path: Path) -> ast.Module | None:
        """
        Parse a Python file into an AST.

        Args:
            file_path: Path to the Python file.

        Returns:
            AST module or None if parsing failed.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            return ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse %s: %s", file_path, e)
            return None

    def should_skip_for_level(self, severity: AuditSeverity, level: AuditLevel) -> bool:
        """
        Check if a finding should be skipped based on audit level.

        Args:
            severity: Severity of the finding.
            level: Current audit level.

        Returns:
            True if the finding should be skipped.
        """
        if level == AuditLevel.RELAXED:
            return severity not in (AuditSeverity.CRITICAL,)
        if level == AuditLevel.STANDARD:
            return severity not in (AuditSeverity.CRITICAL, AuditSeverity.HIGH)
        return False  # STRICT and PARANOID include all


# Registry of available auditors
_auditor_registry: dict[str, type[BaseAuditor]] = {}


def register_auditor(auditor_class: type[BaseAuditor]) -> type[BaseAuditor]:
    """
    Register an auditor class.

    Args:
        auditor_class: The auditor class to register.

    Returns:
        The same class (allows use as decorator).

    Example:
        >>> @register_auditor
        ... class MyAuditor(BaseAuditor):
        ...     name = "my-auditor"
        ...     category = AuditCategory.SECURITY
    """
    _auditor_registry[auditor_class.name] = auditor_class
    return auditor_class


def get_auditor(name: str) -> type[BaseAuditor] | None:
    """
    Get an auditor class by name.

    Args:
        name: Name of the auditor.

    Returns:
        Auditor class or None if not found.
    """
    return _auditor_registry.get(name)


def list_auditors() -> list[type[BaseAuditor]]:
    """
    List all registered auditors.

    Returns:
        List of auditor classes.
    """
    return list(_auditor_registry.values())


def _load_builtin_auditors() -> None:
    """Load all built-in auditors from the auditors subpackage."""
    try:
        from django_matt.audits import auditors

        for _, module_name, _ in pkgutil.iter_modules(auditors.__path__):
            try:
                importlib.import_module(f"django_matt.audits.auditors.{module_name}")
            except ImportError as e:
                logger.debug("Failed to load auditor %s: %s", module_name, e)
    except ImportError:
        pass


def run_audit(
    category: str | AuditCategory = AuditCategory.ALL,
    *,
    level: AuditLevel = AuditLevel.STANDARD,
    config: AuditConfig | None = None,
    project_path: Path | str | None = None,
) -> AuditReport:
    """
    Run an audit on the project.

    Args:
        category: Category to audit (or "all" for all categories).
        level: Strictness level.
        config: Optional full configuration (overrides other args).
        project_path: Path to the project to audit.

    Returns:
        AuditReport with all findings.

    Example:
        >>> results = run_audit("security", level=AuditLevel.STRICT)
        >>> for finding in results.critical_findings:
        ...     print(f"[{finding.id}] {finding.file}:{finding.line}")
    """
    import time

    # Load built-in auditors
    _load_builtin_auditors()

    # Parse category
    if isinstance(category, str):
        try:
            category = AuditCategory(category.lower())
        except ValueError:
            raise ValueError(
                f"Unknown audit category: {category}. Available: {[c.value for c in AuditCategory]}"
            ) from None

    # Build config
    if config is None:
        config = AuditConfig(
            level=level,
            categories=[category],
            project_path=Path(project_path) if project_path else None,
        )

    # Determine which auditors to run
    if AuditCategory.ALL in config.categories:
        auditors_to_run = list(_auditor_registry.values())
    else:
        auditors_to_run = [
            auditor
            for auditor in _auditor_registry.values()
            if auditor.category in config.categories
        ]

    # Create report
    report = AuditReport(
        level=config.level,
        project_path=str(config.project_path) if config.project_path else None,
    )

    # Try to get django-matt version
    try:
        from django_matt import __version__

        report.django_matt_version = __version__
    except ImportError:
        pass

    # Run each auditor
    total_files = set()
    for auditor_class in auditors_to_run:
        auditor = auditor_class()
        start_time = time.perf_counter()

        try:
            result = auditor.audit(config)
            result.duration_ms = (time.perf_counter() - start_time) * 1000
            report.results.append(result)
            total_files.update(f.file for f in result.findings if f.file)
        except Exception as e:
            logger.exception("Auditor %s failed", auditor.name)
            report.results.append(
                AuditResult(
                    auditor_name=auditor.name,
                    category=auditor.category,
                    error=str(e),
                )
            )

        # Fail fast if configured
        if config.fail_fast and result.critical_count > 0:
            break

    report.total_files = len(total_files)
    report.completed_at = datetime.now(UTC)

    return report
