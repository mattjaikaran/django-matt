# file-length-max: 250
"""
Bundle size auditor for detecting unused modules and tree-shaking opportunities.

Wraps the existing BundleAnalyzer to produce standard AuditFindings
integrated with the audit framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..bundle import BundleAnalyzer
from ..framework import (
    AuditCategory,
    AuditConfig,
    AuditFinding,
    AuditResult,
    AuditSeverity,
    BaseAuditor,
    register_auditor,
)

if TYPE_CHECKING:
    pass


@register_auditor
class BundleSizeAuditor(BaseAuditor):
    """
    Auditor for django-matt bundle size and import cost.

    Detects unused modules, import-time costs, and provides
    tree-shaking / slim-mode recommendations.
    """

    name = "bundle_size"
    category = AuditCategory.BUNDLE_SIZE
    description = "Detect unused modules and bundle bloat"

    # Thresholds
    UNUSED_KB_WARN = 100  # flag when total unused exceeds this
    SINGLE_MODULE_KB_WARN = 50  # flag individual modules above this
    LARGE_MODULE_KB = 100  # modules above this get special attention

    def audit(self, config: AuditConfig) -> AuditResult:
        """Run bundle size audit on the project."""
        project_path = config.project_path or Path.cwd()
        findings: list[AuditFinding] = []

        try:
            analyzer = BundleAnalyzer()
            result = analyzer.analyze(project_path, include_import_time=False)
        except Exception as e:
            return AuditResult(
                auditor_name=self.name,
                category=self.category,
                error=str(e),
            )

        # Total unused size
        if result.unused_size_kb > self.UNUSED_KB_WARN:
            severity = AuditSeverity.MEDIUM
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="BUND001",
                        severity=severity,
                        category=self.category,
                        message=f"Unused django-matt modules total ~{result.unused_size_kb:.0f}KB — consider slim mode",
                        suggestion=(
                            f"{len(result.unused_modules)} unused modules found. "
                            "Use MattAPI(mode='slim') or add MATT_DISABLED_MODULES "
                            "to settings to trim bundle."
                        ),
                        fix_command="matt audit fix --rule BUND001",
                        documentation_url="https://django-matt.dev/slim-mode/",
                        tags=["bundle", "unused", "slim"],
                    )
                )

        # Per-module findings for large unused modules
        for module in result.unused_modules:
            size_kb = analyzer.MODULE_SIZES.get(module, 30)
            if size_kb > self.SINGLE_MODULE_KB_WARN:
                severity = (
                    AuditSeverity.HIGH if size_kb > self.LARGE_MODULE_KB else AuditSeverity.MEDIUM
                )
                if self.should_skip_for_level(severity, config.level):
                    continue

                findings.append(
                    AuditFinding(
                        id="BUND002",
                        severity=severity,
                        category=self.category,
                        message=f"Unused module '{module}' ({size_kb:.0f}KB) — add to MATT_DISABLED_MODULES",
                        suggestion=(
                            f"Add '{module}' to MATT_DISABLED_MODULES or remove "
                            f"from INSTALLED_APPS. Saves ~{size_kb:.0f}KB."
                        ),
                        fix_command=f"matt audit fix --rule BUND002 --module {module}",
                        documentation_url="https://django-matt.dev/slim-mode/",
                        tags=["bundle", module, "unused"],
                    )
                )

        # Many unused modules -> slim mode recommendation
        if len(result.unused_modules) > 5:
            severity = AuditSeverity.LOW
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="BUND003",
                        severity=severity,
                        category=self.category,
                        message=f"{len(result.unused_modules)} unused modules — enable slim mode for automatic trimming",
                        suggestion=(
                            "Use MattAPI(mode='slim') to auto-disable unused modules. "
                            "Run 'matt audit diff --category bundle_size' to preview."
                        ),
                        fix_command="matt audit fix --rule BUND003",
                        documentation_url="https://django-matt.dev/slim-mode/",
                        tags=["bundle", "slim"],
                    )
                )

        # Import time check
        if result.import_time_ms > 500:
            severity = AuditSeverity.MEDIUM
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="BUND004",
                        severity=severity,
                        category=self.category,
                        message=f"High import time ({result.import_time_ms:.0f}ms) — consider lazy loading",
                        suggestion=(
                            "Use lazy module loading: MATT_LAZY_LOAD=True. "
                            "Modules are loaded on first use instead of at startup."
                        ),
                        fix_command="matt audit fix --rule BUND004",
                        documentation_url="https://django-matt.dev/slim-mode/",
                        tags=["bundle", "import-time", "startup"],
                    )
                )

        return AuditResult(
            auditor_name=self.name,
            category=self.category,
            findings=findings,
            files_scanned=1,
        )
