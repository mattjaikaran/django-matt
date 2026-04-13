"""AST-based modularity and coupling analyzer.

Detects over-coupled modules, star imports, circular import risks,
god modules, deep import paths, mixed abstraction levels, and missing __all__.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity


class ModularityAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects modularity and coupling issues via AST inspection."""

    name = "modularity"
    description = "Checks import hygiene, module cohesion, coupling depth, and public API clarity"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()

        imports = self._collect_imports(tree)
        top_level_defs = self._collect_top_level_defs(tree)

        self._check_too_many_imports(imports)
        self._check_star_imports(tree)
        self._check_circular_import_risk(tree)
        self._check_god_module(top_level_defs)
        self._check_deep_import_paths(imports)
        self._check_mixed_abstraction_levels(tree)
        self._check_missing_dunder_all(tree, top_level_defs)

        return self._findings

    # ── Helpers ───────────────────────────────────────────────────────────

    def _collect_imports(self, tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
        """Collect all top-level import statements."""
        return [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]

    def _collect_top_level_defs(self, tree: ast.Module) -> list[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
        """Collect top-level class and function definitions."""
        return [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    # ── MOD001: Too many imports ─────────────────────────────────────────

    def _check_too_many_imports(self, imports: list[ast.Import | ast.ImportFrom]) -> None:
        count = len(imports)
        if count > 15:
            self._add_finding(Finding(
                rule_id="MOD001",
                message=f"File has {count} import statements (max 15)",
                severity=Severity.WARNING,
                category=Category.MODULARITY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Module may have too many responsibilities, consider splitting",
                metadata={"import_count": count},
            ))

    # ── MOD002: Star imports ─────────────────────────────────────────────

    def _check_star_imports(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names:
                for alias in node.names:
                    if alias.name == "*":
                        module = node.module or ""
                        self._add_finding(Finding(
                            rule_id="MOD002",
                            message=f"Star import from '{module}'",
                            severity=Severity.WARNING,
                            category=Category.MODULARITY,
                            location=Location(
                                file=str(self._file_path),
                                line=node.lineno,
                            ),
                            suggestion="Import specific names instead of using wildcard imports",
                        ))

    # ── MOD003: Circular import risk ─────────────────────────────────────

    def _check_circular_import_risk(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)) and child is not node:
                    self._add_finding(Finding(
                        rule_id="MOD003",
                        message=f"Import inside function '{node.name}' (possible circular import workaround)",
                        severity=Severity.HINT,
                        category=Category.MODULARITY,
                        location=Location(
                            file=str(self._file_path),
                            line=child.lineno,
                            function=node.name,
                        ),
                        suggestion="Refactor module dependencies to avoid circular imports",
                    ))

    # ── MOD004: God module ───────────────────────────────────────────────

    def _check_god_module(self, top_level_defs: list[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]) -> None:
        count = len(top_level_defs)
        if count > 10:
            self._add_finding(Finding(
                rule_id="MOD004",
                message=f"File has {count} top-level definitions (max 10)",
                severity=Severity.WARNING,
                category=Category.MODULARITY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Split into focused modules with fewer definitions each",
                metadata={"definitions": count},
            ))

    # ── MOD005: Deep import path ─────────────────────────────────────────

    def _check_deep_import_paths(self, imports: list[ast.Import | ast.ImportFrom]) -> None:
        for node in imports:
            if isinstance(node, ast.ImportFrom) and node.module:
                depth = node.module.count(".") + 1
                if depth > 4:
                    self._add_finding(Finding(
                        rule_id="MOD005",
                        message=f"Import from deeply nested module '{node.module}' ({depth} levels)",
                        severity=Severity.HINT,
                        category=Category.MODULARITY,
                        location=Location(
                            file=str(self._file_path),
                            line=node.lineno,
                        ),
                        suggestion="Consider re-exporting from a shorter path",
                    ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    depth = alias.name.count(".") + 1
                    if depth > 4:
                        self._add_finding(Finding(
                            rule_id="MOD005",
                            message=f"Import from deeply nested module '{alias.name}' ({depth} levels)",
                            severity=Severity.HINT,
                            category=Category.MODULARITY,
                            location=Location(
                                file=str(self._file_path),
                                line=node.lineno,
                            ),
                            suggestion="Consider re-exporting from a shorter path",
                        ))

    # ── MOD006: Mixed abstraction levels ─────────────────────────────────

    def _check_mixed_abstraction_levels(self, tree: ast.Module) -> None:
        has_complex_class = False
        has_standalone_function = False

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                method_count = sum(
                    1 for child in ast.iter_child_nodes(node)
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                if method_count >= 5:
                    has_complex_class = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_standalone_function = True

        if has_complex_class and has_standalone_function:
            self._add_finding(Finding(
                rule_id="MOD006",
                message="File mixes high-level classes (5+ methods) with standalone utility functions",
                severity=Severity.HINT,
                category=Category.MODULARITY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Separate abstractions into different modules",
            ))

    # ── MOD007: Missing __all__ ──────────────────────────────────────────

    def _check_missing_dunder_all(
        self,
        tree: ast.Module,
        top_level_defs: list[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        # Skip __init__.py files
        if self._file_path.name == "__init__.py":
            return

        # Check if __all__ is already defined
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        return

        # Count public names (no leading underscore)
        public_names = [
            d for d in top_level_defs
            if not d.name.startswith("_")
        ]

        if len(public_names) >= 3:
            self._add_finding(Finding(
                rule_id="MOD007",
                message=f"Module has {len(public_names)} public definitions but no __all__",
                severity=Severity.INFO,
                category=Category.MODULARITY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Define __all__ to clarify the module's public API",
            ))
