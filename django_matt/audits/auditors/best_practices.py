"""
Best practices auditor for code quality and standards.

Checks for:
- Missing type hints
- Missing docstrings
- Code organization issues
- Testing coverage gaps
- Documentation standards
"""

from __future__ import annotations

import ast
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
class BestPracticesAuditor(BaseAuditor):
    """
    Auditor for code quality and best practices.

    Detects violations of coding standards including:
    - Public functions/methods missing docstrings
    - Functions missing type hints
    - Classes missing docstrings
    - Overly complex functions
    - Code organization issues
    """

    name = "best_practices"
    category = AuditCategory.BEST_PRACTICES
    description = "Detect violations of coding standards and best practices"

    def audit(self, config: AuditConfig) -> AuditResult:
        """
        Run best practices audit on the project.

        Args:
            config: Audit configuration.

        Returns:
            AuditResult with best practices findings.
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
        Audit a single file for best practices.

        Args:
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings for this file.
        """
        findings: list[AuditFinding] = []
        rel_path = str(file_path)

        tree = self.parse_python_file(file_path)
        if not tree:
            return findings

        # Check functions and methods
        findings.extend(self._check_functions(tree, rel_path, config))

        # Check classes
        findings.extend(self._check_classes(tree, rel_path, config))

        # Check module-level docstring
        findings.extend(self._check_module_docstring(tree, rel_path, config))

        return findings

    def _check_functions(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check functions and methods for best practices.

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
                # Skip private/dunder methods
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue

                # Check for missing docstring on public functions
                if not self._has_docstring(node):
                    # Only flag public functions
                    if not node.name.startswith("_"):
                        severity = AuditSeverity.MEDIUM
                        if self.should_skip_for_level(severity, config.level):
                            continue

                        findings.append(
                            AuditFinding(
                                id="BP001",
                                severity=severity,
                                category=self.category,
                                message=f"Public function '{node.name}' is missing a docstring",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Add a docstring describing the function's purpose, args, and return value",
                                tags=["documentation", "docstring"],
                            )
                        )

                # Check for missing return type hint
                if node.returns is None and not node.name.startswith("__"):
                    severity = AuditSeverity.LOW
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="BP002",
                                severity=severity,
                                category=self.category,
                                message=f"Function '{node.name}' is missing return type annotation",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Add return type annotation (e.g., -> None, -> str, -> dict[str, Any])",
                                tags=["typing", "type-hints"],
                            )
                        )

                # Check for parameters missing type hints
                missing_hints = self._get_missing_param_hints(node)
                if missing_hints and not node.name.startswith("__"):
                    severity = AuditSeverity.LOW
                    if not self.should_skip_for_level(severity, config.level):
                        params = ", ".join(missing_hints[:3])
                        if len(missing_hints) > 3:
                            params += f" (and {len(missing_hints) - 3} more)"

                        findings.append(
                            AuditFinding(
                                id="BP003",
                                severity=severity,
                                category=self.category,
                                message=f"Function '{node.name}' has parameters without type hints: {params}",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Add type annotations to all parameters",
                                tags=["typing", "type-hints"],
                            )
                        )

                # Check function complexity (simple heuristic: line count)
                func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                if func_lines > 50:
                    severity = AuditSeverity.INFO
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="BP004",
                                severity=severity,
                                category=self.category,
                                message=f"Function '{node.name}' is {func_lines} lines long",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Consider breaking into smaller functions (aim for <30 lines)",
                                tags=["complexity", "refactoring"],
                            )
                        )

        return findings

    def _check_classes(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check classes for best practices.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Skip private classes
                if node.name.startswith("_"):
                    continue

                # Check for missing class docstring
                if not self._has_docstring(node):
                    severity = AuditSeverity.MEDIUM
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="BP010",
                                severity=severity,
                                category=self.category,
                                message=f"Class '{node.name}' is missing a docstring",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Add a docstring describing the class's purpose and usage",
                                tags=["documentation", "docstring"],
                            )
                        )

                # Check for overly large classes
                class_lines = node.end_lineno - node.lineno if node.end_lineno else 0
                if class_lines > 300:
                    severity = AuditSeverity.INFO
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="BP011",
                                severity=severity,
                                category=self.category,
                                message=f"Class '{node.name}' is {class_lines} lines long",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Consider splitting into smaller, focused classes",
                                tags=["complexity", "refactoring"],
                            )
                        )

                # Check method count
                method_count = sum(
                    1 for n in node.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                )
                if method_count > 20:
                    severity = AuditSeverity.INFO
                    if not self.should_skip_for_level(severity, config.level):
                        findings.append(
                            AuditFinding(
                                id="BP012",
                                severity=severity,
                                category=self.category,
                                message=f"Class '{node.name}' has {method_count} methods",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Consider using composition or mixins to reduce class size",
                                tags=["complexity", "refactoring"],
                            )
                        )

        return findings

    def _check_module_docstring(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check for module-level docstring.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        # Skip __init__.py files (often empty or just imports)
        if file_path.endswith("__init__.py"):
            return findings

        if not ast.get_docstring(tree):
            severity = AuditSeverity.LOW
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="BP020",
                        severity=severity,
                        category=self.category,
                        message="Module is missing a docstring",
                        file=file_path,
                        line=1,
                        suggestion='Add a module docstring at the top: """Description of module."""',
                        tags=["documentation", "docstring"],
                    )
                )

        return findings

    def _has_docstring(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
        """Check if a function or class has a docstring."""
        return ast.get_docstring(node) is not None

    def _get_missing_param_hints(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Get list of parameters missing type hints."""
        missing = []
        for arg in node.args.args:
            # Skip self and cls
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                missing.append(arg.arg)

        # Also check *args and **kwargs
        if node.args.vararg and node.args.vararg.annotation is None:
            missing.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg and node.args.kwarg.annotation is None:
            missing.append(f"**{node.args.kwarg.arg}")

        return missing
