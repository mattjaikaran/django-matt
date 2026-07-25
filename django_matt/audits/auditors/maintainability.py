# file-length-max: 500
"""
Maintainability auditor for code health and technical debt.

Checks for:
- Code complexity (cyclomatic, cognitive)
- Dependency health
- Code duplication indicators
- Deprecated patterns
- Tech debt markers
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

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
class MaintainabilityAuditor(BaseAuditor):
    """
    Auditor for code maintainability and technical debt.

    Detects issues that affect long-term code health:
    - High cyclomatic complexity
    - Deep nesting
    - TODO/FIXME/HACK comments
    - Deprecated patterns
    - Dead code indicators
    """

    name = "maintainability"
    category = AuditCategory.MAINTAINABILITY
    description = "Detect maintainability issues and technical debt"

    # Patterns that indicate tech debt
    TECH_DEBT_PATTERNS: list[tuple[str, re.Pattern, AuditSeverity, str]] = [
        (
            "MAINT001",
            re.compile(r"#\s*TODO:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.INFO,
            "TODO comment found",
        ),
        (
            "MAINT002",
            re.compile(r"#\s*FIXME:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.MEDIUM,
            "FIXME comment found",
        ),
        (
            "MAINT003",
            re.compile(r"#\s*HACK:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.MEDIUM,
            "HACK comment found",
        ),
        (
            "MAINT004",
            re.compile(r"#\s*XXX:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.MEDIUM,
            "XXX marker found",
        ),
        (
            "MAINT005",
            re.compile(r"#\s*TEMP:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.HIGH,
            "TEMP/temporary code marker found",
        ),
        (
            "MAINT006",
            re.compile(r"#\s*DEPRECATED:?\s*(.{0,100})", re.IGNORECASE),
            AuditSeverity.MEDIUM,
            "DEPRECATED marker found",
        ),
    ]

    # Deprecated patterns
    DEPRECATED_PATTERNS: list[tuple[str, re.Pattern, str, str]] = [
        (
            "MAINT010",
            re.compile(r"from\s+django\.conf\.urls\s+import\s+url\b"),
            "django.conf.urls.url() is deprecated",
            "Use django.urls.path() or re_path() instead",
        ),
        (
            "MAINT011",
            re.compile(r"\.render_to_response\s*\("),
            "render_to_response() is deprecated",
            "Use render() instead",
        ),
        (
            "MAINT012",
            re.compile(r"from\s+django\.utils\.encoding\s+import\s+smart_text\b"),
            "smart_text is deprecated in Django 4.0+",
            "Use smart_str instead",
        ),
        (
            "MAINT013",
            re.compile(r"from\s+django\.utils\.encoding\s+import\s+force_text\b"),
            "force_text is deprecated in Django 4.0+",
            "Use force_str instead",
        ),
        (
            "MAINT014",
            re.compile(r"\.ugettext\b"),
            "ugettext is deprecated in Django 4.0+",
            "Use gettext instead",
        ),
        (
            "MAINT015",
            re.compile(r"\.ugettext_lazy\b"),
            "ugettext_lazy is deprecated in Django 4.0+",
            "Use gettext_lazy instead",
        ),
    ]

    def audit(self, config: AuditConfig) -> AuditResult:
        """
        Run maintainability audit on the project.

        Args:
            config: Audit configuration.

        Returns:
            AuditResult with maintainability findings.
        """
        findings: list[AuditFinding] = []
        files_scanned = 0

        for file_path in self.iter_files(config):
            files_scanned += 1
            file_findings = self._audit_file(file_path, config)
            findings.extend(file_findings)

            if config.max_findings > 0 and len(findings) >= config.max_findings:
                break

        return AuditResult(
            auditor_name=self.name,
            category=self.category,
            findings=findings,
            files_scanned=files_scanned,
        )

    def _audit_file(self, file_path: Path, config: AuditConfig) -> list[AuditFinding]:
        """
        Audit a single file for maintainability issues.

        Args:
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings for this file.
        """
        findings: list[AuditFinding] = []
        rel_path = str(file_path)

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return findings

        lines = content.split("\n")

        # Check for tech debt markers in comments
        for line_num, line in enumerate(lines, 1):
            for finding_id, pattern, severity, message in self.TECH_DEBT_PATTERNS:
                match = pattern.search(line)
                if match:
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    detail = match.group(1).strip() if match.groups() else ""
                    findings.append(
                        AuditFinding(
                            id=finding_id,
                            severity=severity,
                            category=self.category,
                            message=f"{message}: {detail}" if detail else message,
                            file=rel_path,
                            line=line_num,
                            code=line.strip()[:100],
                            suggestion="Address this technical debt item",
                            tags=["tech-debt", "comment"],
                        )
                    )

        # Check for deprecated patterns
        for line_num, line in enumerate(lines, 1):
            for finding_id, pattern, message, suggestion in self.DEPRECATED_PATTERNS:
                if pattern.search(line):
                    severity = AuditSeverity.MEDIUM
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id=finding_id,
                            severity=severity,
                            category=self.category,
                            message=message,
                            file=rel_path,
                            line=line_num,
                            code=line.strip()[:100],
                            suggestion=suggestion,
                            tags=["deprecated", "migration"],
                        )
                    )

        # AST-based complexity analysis
        tree = self.parse_python_file(file_path)
        if tree:
            findings.extend(self._check_complexity(tree, rel_path, config))
            findings.extend(self._check_nesting_depth(tree, rel_path, config))
            findings.extend(self._check_dead_code(tree, rel_path, config))

        return findings

    def _check_complexity(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check cyclomatic complexity of functions.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                complexity = self._calculate_complexity(node)

                if complexity > 15:
                    severity = AuditSeverity.HIGH
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id="MAINT020",
                            severity=severity,
                            category=self.category,
                            message=f"Function '{node.name}' has high cyclomatic complexity ({complexity})",
                            file=file_path,
                            line=node.lineno,
                            suggestion="Refactor to reduce complexity. Consider extracting methods or using early returns.",
                            tags=["complexity", "refactoring"],
                        )
                    )
                elif complexity > 10:
                    severity = AuditSeverity.MEDIUM
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="MAINT021",
                                severity=severity,
                                category=self.category,
                                message=f"Function '{node.name}' has moderate complexity ({complexity})",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Consider simplifying this function",
                                tags=["complexity"],
                            )
                        )

        return findings

    def _check_nesting_depth(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check for deeply nested code.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                max_depth = self._calculate_max_nesting(node)

                if max_depth > 5:
                    severity = AuditSeverity.HIGH
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id="MAINT030",
                            severity=severity,
                            category=self.category,
                            message=f"Function '{node.name}' has deep nesting ({max_depth} levels)",
                            file=file_path,
                            line=node.lineno,
                            suggestion="Use early returns, extract methods, or restructure logic to reduce nesting",
                            tags=["complexity", "nesting"],
                        )
                    )
                elif max_depth > 3:
                    severity = AuditSeverity.MEDIUM
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="MAINT031",
                                severity=severity,
                                category=self.category,
                                message=f"Function '{node.name}' has moderate nesting ({max_depth} levels)",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Consider flattening nested structures",
                                tags=["complexity", "nesting"],
                            )
                        )

        return findings

    def _check_dead_code(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check for potential dead code indicators.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            # Check for unreachable code after return/raise
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Return | ast.Raise):
                        if i < len(node.body) - 1:
                            next_stmt = node.body[i + 1]
                            severity = AuditSeverity.MEDIUM
                            if not self.should_skip_for_level(severity, config.level):
                                findings.append(
                                    AuditFinding(
                                        id="MAINT040",
                                        severity=severity,
                                        category=self.category,
                                        message="Unreachable code after return/raise statement",
                                        file=file_path,
                                        line=next_stmt.lineno,
                                        suggestion="Remove unreachable code",
                                        tags=["dead-code"],
                                    )
                                )
                            break

            # Check for pass statements in non-empty bodies
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                if len(node.body) > 1:
                    for stmt in node.body:
                        if isinstance(stmt, ast.Pass):
                            severity = AuditSeverity.LOW
                            if not self.should_skip_for_level(severity, config.level):
                                findings.append(
                                    AuditFinding(
                                        id="MAINT041",
                                        severity=severity,
                                        category=self.category,
                                        message="Unnecessary pass statement",
                                        file=file_path,
                                        line=stmt.lineno,
                                        suggestion="Remove unnecessary pass statement",
                                        tags=["dead-code", "cleanup"],
                                    )
                                )

        return findings

    def _calculate_complexity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """
        Calculate cyclomatic complexity of a function.

        Simplified calculation based on decision points.

        Args:
            node: Function AST node.

        Returns:
            Complexity score.
        """
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, ast.If | ast.While | ast.For | ast.AsyncFor) or isinstance(
                child, ast.ExceptHandler
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
                if child.ifs:
                    complexity += len(child.ifs)
            elif isinstance(child, ast.Match):
                complexity += len(child.cases)

        return complexity

    def _calculate_max_nesting(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """
        Calculate maximum nesting depth in a function.

        Args:
            node: Function AST node.

        Returns:
            Maximum nesting depth.
        """

        def _get_depth(node: ast.AST, current_depth: int) -> int:
            max_depth = current_depth

            nesting_nodes = (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.With,
                ast.AsyncWith,
                ast.Try,
                ast.Match,
            )

            for child in ast.iter_child_nodes(node):
                if isinstance(child, nesting_nodes):
                    child_depth = _get_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = _get_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)

            return max_depth

        return _get_depth(node, 0)
