"""AST-based N+1 query detector.

Detects loops that access related model fields without select_related/prefetch_related,
queryset.all() inside loops, and related field traversals in comprehensions.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Category, Finding, Location, Severity

# ORM calls that typically indicate queryset evaluation
_QUERYSET_METHODS: frozenset[str] = frozenset(
    {
        "filter",
        "get",
        "all",
        "exclude",
        "values",
        "values_list",
        "count",
        "exists",
        "first",
        "last",
        "create",
        "update",
        "aggregate",
        "annotate",
    }
)

# Methods that prefetch/optimize related lookups
_PREFETCH_METHODS: frozenset[str] = frozenset(
    {
        "select_related",
        "prefetch_related",
    }
)


class NPlusOneAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects N+1 query patterns via AST inspection."""

    name = "n_plus_one"
    description = "Detects N+1 query patterns: related field access in loops, .all() in loops"

    def __init__(self, config: ReviewConfig) -> None:
        super().__init__(config)
        self._current_function: str | None = None
        self._current_class: str | None = None

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self._current_function = None
        self._current_class = None
        self._prefetched_vars: set[str] = set()
        self.visit(tree)
        return self._findings

    def _make_location(self, lineno: int) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            function=self._current_function,
            class_name=self._current_class,
        )

    # -- Visitors ----------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        prev = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = prev

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variables assigned from querysets with select_related/prefetch_related."""
        if self._iterable_has_prefetch(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._prefetched_vars.add(target.id)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._check_loop(node)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._check_loop(node)
        self.generic_visit(node)

    # -- Checks ------------------------------------------------------------

    def _check_loop(self, node: ast.For | ast.AsyncFor) -> None:
        """Check a for loop for N+1 patterns."""
        loop_var = self._extract_loop_var(node.target)
        if loop_var is None:
            return

        # Check if the iterable has select_related/prefetch_related
        has_prefetch = self._iterable_has_prefetch(node.iter)

        # Also check if the iterable is a variable previously assigned with prefetch
        if not has_prefetch and isinstance(node.iter, ast.Name):
            if node.iter.id in self._prefetched_vars:
                has_prefetch = True

        if not has_prefetch:
            self._check_related_access_in_body(node.body, loop_var, node.lineno)
            self._check_orm_calls_in_body(node.body)

    def _extract_loop_var(self, target: ast.expr) -> str | None:
        """Extract the loop variable name from a for target."""
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Tuple) and target.elts:
            # Take the first element of tuple unpacking
            if isinstance(target.elts[0], ast.Name):
                return target.elts[0].id
        return None

    def _iterable_has_prefetch(self, node: ast.expr) -> bool:
        """Check if the loop iterable includes select_related/prefetch_related."""
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr in _PREFETCH_METHODS:
                return True
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr in _PREFETCH_METHODS:
                    return True
        return False

    def _check_related_access_in_body(
        self,
        body: list[ast.stmt],
        loop_var: str,
        loop_lineno: int,
    ) -> None:
        """NP001: Detect loop_var.related_field access patterns in loop body."""
        reported_attrs: set[str] = set()

        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if not isinstance(child, ast.Attribute):
                continue
            # Pattern: loop_var.related_field (chained attribute access)
            if isinstance(child.value, ast.Name) and child.value.id == loop_var:
                attr = child.attr
                # Skip common non-relation attrs
                if attr.startswith("_") or attr in {
                    "pk",
                    "id",
                    "name",
                    "title",
                    "email",
                    "is_active",
                    "created_at",
                    "updated_at",
                    "status",
                    "type",
                    "slug",
                    "description",
                    "content",
                    "value",
                    "key",
                    "data",
                }:
                    continue
                if attr in reported_attrs:
                    continue
                reported_attrs.add(attr)

                self._add_finding(
                    Finding(
                        rule_id="NP001",
                        message=f"Potential N+1: '{loop_var}.{attr}' accessed inside loop (line {child.lineno})",
                        severity=Severity.WARNING,
                        category=Category.N_PLUS_ONE,
                        location=self._make_location(child.lineno),
                        suggestion=f"Add .select_related('{attr}') or .prefetch_related('{attr}') to the queryset",
                        context=self._get_source_line(child.lineno).strip(),
                    )
                )

            # Pattern: loop_var.related.subfield (deeper traversal)
            if (
                isinstance(child.value, ast.Attribute)
                and isinstance(child.value.value, ast.Name)
                and child.value.value.id == loop_var
            ):
                related = child.value.attr
                subfield = child.attr
                key = f"{related}.{subfield}"
                if key in reported_attrs:
                    continue
                # Skip common non-relation first-level attrs
                if related.startswith("_") or related in {
                    "pk",
                    "id",
                    "name",
                    "title",
                    "email",
                }:
                    continue
                reported_attrs.add(key)
                self._add_finding(
                    Finding(
                        rule_id="NP001",
                        message=f"Potential N+1: '{loop_var}.{related}.{subfield}' accessed inside loop",
                        severity=Severity.WARNING,
                        category=Category.N_PLUS_ONE,
                        location=self._make_location(child.lineno),
                        suggestion=f"Add .select_related('{related}') to the queryset",
                        context=self._get_source_line(child.lineno).strip(),
                    )
                )

    def _check_orm_calls_in_body(self, body: list[ast.stmt]) -> None:
        """NP002: Detect ORM queryset calls inside loop body."""
        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute):
                continue
            method = child.func.attr
            if method not in _QUERYSET_METHODS:
                continue
            # Check if it's an .objects.method() or chained queryset call
            value = child.func.value
            if isinstance(value, ast.Attribute) and value.attr == "objects":
                self._add_finding(
                    Finding(
                        rule_id="NP002",
                        message=f"ORM .objects.{method}() called inside loop body",
                        severity=Severity.WARNING,
                        category=Category.N_PLUS_ONE,
                        location=self._make_location(child.lineno),
                        suggestion="Move the query before the loop or use bulk operations",
                        context=self._get_source_line(child.lineno).strip(),
                    )
                )
                return  # One finding per loop body
