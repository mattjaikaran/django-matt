# file-length-max: 450
"""
Performance auditor for detecting common performance issues.

Checks for:
- N+1 query patterns
- Missing database indexes
- Inefficient queryset operations
- Blocking operations in async code
- Missing caching opportunities
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
class PerformanceAuditor(BaseAuditor):
    """
    Auditor for performance issues.

    Detects common performance problems including:
    - N+1 query patterns in loops
    - Missing select_related/prefetch_related
    - Inefficient queryset operations
    - Sync ORM calls in async functions
    - Missing pagination on list endpoints
    """

    name = "performance"
    category = AuditCategory.PERFORMANCE
    description = "Detect performance issues and optimization opportunities"

    # ORM methods that indicate potential N+1
    RELATED_ACCESS_PATTERNS = [
        re.compile(r"\.(\w+)_set\."),  # reverse relation
        re.compile(r"\.\w+\.objects\."),  # related model access
    ]

    # Sync ORM methods that shouldn't be called in async
    SYNC_ORM_METHODS = {
        "all",
        "filter",
        "exclude",
        "get",
        "first",
        "last",
        "create",
        "update",
        "delete",
        "save",
        "count",
        "exists",
        "aggregate",
        "annotate",
        "values",
        "values_list",
        "iterator",
        "bulk_create",
        "bulk_update",
        "get_or_create",
        "update_or_create",
    }

    # Methods that should use async variants
    ASYNC_ALTERNATIVES = {
        "get": "aget",
        "filter": "aiterator() or async for",
        "all": "aiterator() or async for",
        "first": "afirst",
        "last": "alast",
        "count": "acount",
        "exists": "aexists",
        "create": "acreate",
        "save": "asave",
        "delete": "adelete",
        "update": "aupdate",
        "bulk_create": "abulk_create",
        "bulk_update": "abulk_update",
        "get_or_create": "aget_or_create",
        "update_or_create": "aupdate_or_create",
        "aggregate": "aaggregate",
        "in_bulk": "ain_bulk",
        "contains": "acontains",
    }

    def audit(self, config: AuditConfig) -> AuditResult:
        """
        Run performance audit on the project.

        Args:
            config: Audit configuration.

        Returns:
            AuditResult with performance findings.
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
        Audit a single file for performance issues.

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

        # Check for N+1 patterns
        findings.extend(self._check_n_plus_one(tree, rel_path, config))

        # Check for sync ORM in async
        findings.extend(self._check_sync_in_async(tree, rel_path, config))

        # Check for missing pagination
        findings.extend(self._check_missing_pagination(tree, rel_path, config))

        # Check for inefficient patterns
        findings.extend(self._check_inefficient_patterns(tree, rel_path, config))

        return findings

    def _check_n_plus_one(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Detect potential N+1 query patterns.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            # Look for for loops
            if isinstance(node, ast.For | ast.AsyncFor):
                loop_body_src = ast.unparse(node) if hasattr(ast, "unparse") else ""

                # Check for queryset access in loop
                for pattern in self.RELATED_ACCESS_PATTERNS:
                    if pattern.search(loop_body_src):
                        severity = AuditSeverity.HIGH
                        if self.should_skip_for_level(severity, config.level):
                            continue

                        findings.append(
                            AuditFinding(
                                id="PERF001",
                                severity=severity,
                                category=self.category,
                                message="Potential N+1 query: related object accessed in loop",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Use select_related() or prefetch_related() before the loop",
                                tags=["n+1", "database"],
                            )
                        )
                        break

        return findings

    def _check_sync_in_async(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Detect sync ORM calls in async functions.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Walk the async function body
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        method_name = self._get_method_name(child)
                        if method_name in self.SYNC_ORM_METHODS:
                            # Check if it's a Django model method
                            if self._looks_like_orm_call(child):
                                severity = AuditSeverity.HIGH
                                if self.should_skip_for_level(severity, config.level):
                                    continue

                                alternative = self.ASYNC_ALTERNATIVES.get(
                                    method_name, f"a{method_name}"
                                )
                                findings.append(
                                    AuditFinding(
                                        id="PERF010",
                                        severity=severity,
                                        category=self.category,
                                        message=f"Sync ORM call '{method_name}()' in async function",
                                        file=file_path,
                                        line=child.lineno,
                                        suggestion=f"Use '{alternative}()' instead for async compatibility",
                                        tags=["async", "database", "blocking"],
                                    )
                                )

        return findings

    def _check_missing_pagination(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Detect list endpoints potentially missing pagination.

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
                # Check if this looks like a list endpoint
                if not self._is_list_endpoint(node):
                    continue

                # Check if pagination is used
                func_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                pagination_indicators = [
                    "paginate",
                    "page_size",
                    "limit",
                    "offset",
                    "cursor",
                    "Paginator",
                    "PageNumberPagination",
                    "LimitOffsetPagination",
                    "CursorPagination",
                ]

                has_pagination = any(ind in func_src for ind in pagination_indicators)

                if not has_pagination:
                    # Check for .all() without limit
                    if ".all()" in func_src or "objects.filter" in func_src:
                        severity = AuditSeverity.MEDIUM
                        if self.should_skip_for_level(severity, config.level):
                            continue

                        findings.append(
                            AuditFinding(
                                id="PERF020",
                                severity=severity,
                                category=self.category,
                                message=f"List endpoint '{node.name}' may be missing pagination",
                                file=file_path,
                                line=node.lineno,
                                suggestion="Add pagination to prevent loading unbounded data",
                                tags=["pagination", "scalability"],
                            )
                        )

        return findings

    def _check_inefficient_patterns(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Detect inefficient code patterns.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []
        src = ast.unparse(tree) if hasattr(ast, "unparse") else ""

        # Check for len(queryset) instead of count()
        if re.search(r"len\s*\(\s*\w+\.objects\.", src):
            severity = AuditSeverity.MEDIUM
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="PERF030",
                        severity=severity,
                        category=self.category,
                        message="Using len() on queryset instead of count()",
                        file=file_path,
                        suggestion="Use queryset.count() which runs a COUNT query instead of fetching all rows",
                        tags=["database", "queryset"],
                    )
                )

        # Check for list(queryset) when iterating
        if re.search(r"list\s*\(\s*\w+\.objects\.", src):
            severity = AuditSeverity.LOW
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="PERF031",
                        severity=severity,
                        category=self.category,
                        message="Converting queryset to list may load all data into memory",
                        file=file_path,
                        suggestion="Use iterator() for large querysets, or paginate results",
                        tags=["memory", "queryset"],
                    )
                )

        # Check for multiple .filter() calls that could be combined
        if src.count(".filter(") > 3:
            severity = AuditSeverity.INFO
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="PERF032",
                        severity=severity,
                        category=self.category,
                        message="Multiple chained filter() calls may be combinable",
                        file=file_path,
                        suggestion="Combine filters into a single call for better readability",
                        tags=["queryset", "readability"],
                    )
                )

        return findings

    def _get_method_name(self, call_node: ast.Call) -> str:
        """Get the method name from a Call node."""
        if isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return ""

    def _looks_like_orm_call(self, call_node: ast.Call) -> bool:
        """Check if a call looks like a Django ORM operation."""
        if isinstance(call_node.func, ast.Attribute):
            value = call_node.func.value
            # Check for Model.objects.method() pattern
            if isinstance(value, ast.Attribute) and value.attr == "objects":
                return True
            # Check for queryset.method() pattern
            if isinstance(value, ast.Name):
                return True
        return False

    def _is_list_endpoint(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function looks like a list endpoint."""
        # Check name patterns
        list_patterns = ["list", "get_all", "index", "search"]
        if any(p in node.name.lower() for p in list_patterns):
            return True

        # Check decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == "get":
                        # Check if path ends with /
                        for arg in decorator.args:
                            if isinstance(arg, ast.Constant) and str(arg.value).endswith("/"):
                                return True
        return False
