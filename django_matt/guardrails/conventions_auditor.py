"""
Convention auditor — integrates ConventionChecker into the audits framework.

Registered under the name "conventions" in the BEST_PRACTICES category.
Wraps :class:`ConventionChecker` and converts its findings into the
framework's :class:`AuditFinding` objects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from django_matt.audits.framework import (
    AuditCategory,
    AuditConfig,
    AuditFinding,
    AuditLevel,
    AuditResult,
    AuditSeverity,
    BaseAuditor,
    register_auditor,
)
from django_matt.guardrails.conventions import (
    ConventionCategory,
    ConventionChecker,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("django_matt.guardrails.conventions_auditor")

# ── Directories ConventionChecker skips (mirrored for file counting) ──────────
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".tox",
        ".nox",
        "migrations",
        ".eggs",
    }
)

# ── Category → Finding ID prefix ─────────────────────────────────────────────
_CATEGORY_ID_PREFIX: dict[ConventionCategory, str] = {
    ConventionCategory.ERROR_HANDLING: "CONV-ERR",
    ConventionCategory.CONTROLLER_PATTERNS: "CONV-CTRL",
    ConventionCategory.SERVICE_LAYER: "CONV-SVC",
    ConventionCategory.TYPE_HINTS: "CONV-TYPE",
    ConventionCategory.DOCSTRINGS: "CONV-DOC",
    ConventionCategory.ORM_ACCESS: "CONV-ORM",
    ConventionCategory.IMPORT_STYLE: "CONV-IMP",
    ConventionCategory.SOFT_DELETE: "CONV-SOFT",
    ConventionCategory.QUERY_OPTIMIZATION: "CONV-QOPT",
    ConventionCategory.SCHEMA_USAGE: "CONV-SCH",
}

# ── Category → Human-readable suggestion ──────────────────────────────────────
_CATEGORY_SUGGESTIONS: dict[ConventionCategory, str] = {
    ConventionCategory.ERROR_HANDLING: (
        "Use ServiceError hierarchy consistently and avoid bare except clauses"
    ),
    ConventionCategory.CONTROLLER_PATTERNS: (
        "Use a consistent controller pattern (class-based or function-based, not both)"
    ),
    ConventionCategory.SERVICE_LAYER: (
        "Move business logic into service classes instead of placing it in controllers"
    ),
    ConventionCategory.TYPE_HINTS: (
        "Add type annotations to function signatures and class attributes"
    ),
    ConventionCategory.DOCSTRINGS: (
        "Add docstrings to all public functions and classes"
    ),
    ConventionCategory.ORM_ACCESS: (
        "Use the service layer instead of accessing ORM models directly in controllers"
    ),
    ConventionCategory.IMPORT_STYLE: (
        "Use absolute imports consistently across the project"
    ),
    ConventionCategory.SOFT_DELETE: (
        "Use SoftDeleteMixin on models when the project uses soft-delete elsewhere"
    ),
    ConventionCategory.QUERY_OPTIMIZATION: (
        "Add select_related or prefetch_related to querysets to avoid N+1 queries"
    ),
    ConventionCategory.SCHEMA_USAGE: (
        "Use Pydantic schemas consistently instead of returning plain dicts from controllers"
    ),
}


@register_auditor
class ConventionAuditor(BaseAuditor):
    """Auditor that checks project code against django-matt conventions.

    Wraps :class:`ConventionChecker` and maps its findings into the
    standard audits framework.  Respects ``AuditConfig.level``:

    - **STANDARD** — only reports deductions >= 3 (HIGH severity).
    - **STRICT**   — reports deductions >= 2 (MEDIUM+ severity).
    - **PARANOID** — reports all deductions (LOW+ severity).
    """

    name = "conventions"
    category = AuditCategory.BEST_PRACTICES
    description = "Check project against django-matt conventions and best practices"

    # ── Deduction → Severity mapping ──────────────────────────────────────

    @staticmethod
    def _deduction_to_severity(deduction: int) -> AuditSeverity:
        """Map a convention deduction (1-3) to an audit severity."""
        if deduction >= 3:
            return AuditSeverity.HIGH
        if deduction >= 2:
            return AuditSeverity.MEDIUM
        return AuditSeverity.LOW

    @staticmethod
    def _min_deduction_for_level(level: AuditLevel) -> int:
        """Return the minimum deduction to report at the given audit level.

        - STANDARD: >= 3 (HIGH only)
        - STRICT:   >= 2 (MEDIUM+)
        - PARANOID: >= 1 (everything)
        """
        if level == AuditLevel.STANDARD:
            return 3
        if level == AuditLevel.STRICT:
            return 2
        return 1  # PARANOID or RELAXED

    # ── Finding conversion ────────────────────────────────────────────────

    def _convert_finding(
        self,
        finding: "ConventionFinding",
        finding_index: int,
    ) -> AuditFinding:
        """Convert a single :class:`ConventionFinding` to an :class:`AuditFinding`.

        Args:
            finding: The convention finding to convert.
            finding_index: Zero-based index used to build a unique finding ID.

        Returns:
            An ``AuditFinding`` with severity, tags, and suggestion populated.
        """
        severity = self._deduction_to_severity(finding.deduction)
        category_tag = finding.category.value
        finding_id = f"{_CATEGORY_ID_PREFIX.get(finding.category, 'CONV')}-{finding_index + 1:04d}"

        return AuditFinding(
            id=finding_id,
            severity=severity,
            category=self.category,
            message=finding.message,
            file=finding.file,
            line=finding.line,
            column=None,
            code=None,
            suggestion=_CATEGORY_SUGGESTIONS.get(finding.category),
            fix_command=None,
            documentation_url=None,
            tags=["conventions", category_tag],
        )

    # ── File counting ─────────────────────────────────────────────────────

    @staticmethod
    def _count_python_files(project_path: Path) -> int:
        """Count scannable Python files under *project_path* excluding skip dirs."""
        count = 0
        for py_file in project_path.rglob("*.py"):
            if any(part in _SKIP_DIRS for part in py_file.parts):
                continue
            count += 1
        return count

    # ── Main audit entry point ────────────────────────────────────────────

    def audit(self, config: AuditConfig) -> AuditResult:
        """Run the convention audit.

        Args:
            config: Audit configuration controlling level, paths, and limits.

        Returns:
            ``AuditResult`` with convention findings converted to
            ``AuditFinding`` objects.
        """
        project_path = config.project_path or Path.cwd()

        # Determine minimum deduction threshold from audit level
        min_deduction = self._min_deduction_for_level(config.level)

        # Run the convention checker
        checker = ConventionChecker(project_path)
        report = checker.check()

        # Convert findings, respecting level thresholds and max_findings
        audit_findings: list[AuditFinding] = []
        for i, finding in enumerate(report.findings):
            if finding.deduction < min_deduction:
                continue

            audit_findings.append(self._convert_finding(finding, i))

            if config.max_findings > 0 and len(audit_findings) >= config.max_findings:
                logger.debug(
                    "Reached max_findings limit (%d) for conventions auditor",
                    config.max_findings,
                )
                break

        # Count scanned files for the report
        files_scanned = self._count_python_files(project_path)

        logger.info(
            "Convention audit complete: %d findings from %d files",
            len(audit_findings),
            files_scanned,
        )

        return AuditResult(
            auditor_name=self.name,
            category=self.category,
            findings=audit_findings,
            files_scanned=files_scanned,
        )
