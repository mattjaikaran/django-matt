# file-length-max: 500
"""AST-based performance anti-pattern analyzer.

Detects common performance pitfalls: ORM queries in loops, blocking I/O in
async functions, unnecessary conversions, mutable defaults, and more.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity

_ORM_METHODS = frozenset({"filter", "get", "all", "values", "count", "exists"})
_QUERYSET_SUFFIXES = ("_qs", "_queryset")
_BLOCKING_FUNCS: dict[str | None, frozenset[str]] = {
    None: frozenset({"open"}),
    "time": frozenset({"sleep"}),
    "requests": frozenset({"get", "post", "put", "patch", "delete", "head", "options", "request"}),
    "urllib": frozenset({"urlopen"}),
    "urllib.request": frozenset({"urlopen"}),
    "subprocess": frozenset({"run", "call", "check_output", "check_call"}),
    "os": frozenset({"system"}),
}


class PerformanceAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects performance anti-patterns via AST inspection."""

    name = "performance"
    description = (
        "Detects ORM queries in loops, blocking I/O in async, mutable defaults, "
        "unnecessary conversions, and queryset re-evaluation"
    )

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self._in_async = False
        self._loop_depth = 0
        self._current_function: str | None = None
        self._current_class: str | None = None
        # Track queryset assignments: name -> list of line numbers where used
        self._qs_assignments: dict[str, int] = {}
        self._qs_usage_counts: dict[str, list[int]] = defaultdict(list)
        # Track string += targets in loops
        self._string_concat_targets: set[str] = set()

        self.visit(tree)

        # PERF005 — check for queryset re-evaluation after full walk
        self._check_queryset_reevaluation()

        return self._findings

    # ------------------------------------------------------------------
    # Visitor overrides
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._check_len_on_queryset(node)
        self._check_list_conversion_in_loop(node)
        self._check_blocking_io_in_async(node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_string_concat_in_loop(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._track_queryset_assignment(node)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        self._track_queryset_usage(node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # Track usage of queryset variables in expressions
        if isinstance(node.ctx, ast.Load) and node.id in self._qs_assignments:
            self._qs_usage_counts[node.id].append(node.lineno)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_location(self, lineno: int) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            function=self._current_function,
            class_name=self._current_class,
        )

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        prev_func = self._current_function
        prev_async = self._in_async
        self._current_function = node.name
        self._in_async = is_async

        self._check_mutable_default(node)
        self.generic_visit(node)

        self._current_function = prev_func
        self._in_async = prev_async

    def _visit_loop(self, node: ast.For | ast.While) -> None:
        self._loop_depth += 1
        for child in node.body:
            self._check_orm_in_loop(child)
            self.visit(child)
        for child in node.orelse:
            self.visit(child)
        self._loop_depth -= 1

    # ------------------------------------------------------------------
    # PERF001 — QuerySet in loop
    # ------------------------------------------------------------------

    def _check_orm_in_loop(self, node: ast.AST) -> None:
        """Detect ORM calls directly in a loop body (recursively)."""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if self._is_orm_call(node.value):
                self._add_finding(
                    Finding(
                        rule_id="PERF001",
                        message="ORM query inside loop body",
                        severity=Severity.WARNING,
                        category=Category.PERFORMANCE,
                        location=self._make_location(node.lineno),
                        suggestion="Prefetch data before the loop or use select_related/prefetch_related",
                        context=self._get_source_line(node.lineno),
                    )
                )
                return
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call) and self._is_orm_call(node.value):
                self._add_finding(
                    Finding(
                        rule_id="PERF001",
                        message="ORM query inside loop body",
                        severity=Severity.WARNING,
                        category=Category.PERFORMANCE,
                        location=self._make_location(node.lineno),
                        suggestion="Prefetch data before the loop or use select_related/prefetch_related",
                        context=self._get_source_line(node.lineno),
                    )
                )
                return
        # Check if statements and other compound bodies inside the loop
        if isinstance(node, ast.If):
            for child in node.body + node.orelse:
                self._check_orm_in_loop(child)
        elif isinstance(node, ast.With):
            for child in node.body:
                self._check_orm_in_loop(child)

    def _is_orm_call(self, node: ast.Call) -> bool:
        """Check whether a Call node looks like a Django ORM method call."""
        if isinstance(node.func, ast.Attribute) and node.func.attr in _ORM_METHODS:
            return True
        return False

    # ------------------------------------------------------------------
    # PERF002 — len() on QuerySet
    # ------------------------------------------------------------------

    def _check_len_on_queryset(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Name) and node.func.id == "len"):
            return
        if len(node.args) != 1:
            return

        arg = node.args[0]
        is_qs = False

        # Variable ending in _qs or _queryset
        if isinstance(arg, ast.Name) and any(arg.id.endswith(s) for s in _QUERYSET_SUFFIXES):
            is_qs = True
        # Result of .filter() or .all()
        elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr in ("filter", "all"):
                is_qs = True

        if is_qs:
            self._add_finding(
                Finding(
                    rule_id="PERF002",
                    message="len() called on QuerySet — loads all objects into memory",
                    severity=Severity.HINT,
                    category=Category.PERFORMANCE,
                    location=self._make_location(node.lineno),
                    suggestion="Use .count() to avoid loading all objects",
                    context=self._get_source_line(node.lineno),
                )
            )

    # ------------------------------------------------------------------
    # PERF003 — Blocking I/O in async
    # ------------------------------------------------------------------

    def _check_blocking_io_in_async(self, node: ast.Call) -> None:
        if not self._in_async:
            return

        func_name: str | None = None
        module: str | None = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            module = None
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            # Resolve module from the value chain
            module = self._resolve_dotted_name(node.func.value)

        if func_name is None:
            return

        # Check builtins (module=None)
        if module is None and func_name in _BLOCKING_FUNCS.get(None, frozenset()):
            self._emit_blocking_io(node)
            return

        # Check module-qualified calls
        if module is not None:
            for mod_prefix, funcs in _BLOCKING_FUNCS.items():
                if mod_prefix is None:
                    continue
                if module == mod_prefix or module.endswith(f".{mod_prefix}"):
                    if func_name in funcs:
                        self._emit_blocking_io(node)
                        return

    def _resolve_dotted_name(self, node: ast.expr) -> str | None:
        """Resolve a chain of Attribute/Name nodes to a dotted string."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._resolve_dotted_name(node.value)
            if parent is not None:
                return f"{parent}.{node.attr}"
        return None

    def _emit_blocking_io(self, node: ast.Call) -> None:
        self._add_finding(
            Finding(
                rule_id="PERF003",
                message="Blocking I/O call in async function",
                severity=Severity.ERROR,
                category=Category.PERFORMANCE,
                location=self._make_location(node.lineno),
                suggestion=(
                    "Use async alternatives: aiofiles for file I/O, asyncio.sleep, "
                    "httpx for HTTP, asyncio.subprocess for subprocesses"
                ),
                context=self._get_source_line(node.lineno),
            )
        )

    # ------------------------------------------------------------------
    # PERF004 — Unnecessary list() conversion
    # ------------------------------------------------------------------

    def _check_list_conversion_in_loop(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Name) and node.func.id == "list"):
            return
        if len(node.args) != 1:
            return

        # Only flag if the list() call is the iterable of a for-loop
        # We detect this by checking if the parent is a For node's iter.
        # Since we don't have parent tracking, check if we're inside a for
        # and the node is the iter. This is handled during for-loop visit.
        # Instead, flag list(qs) where qs looks like a queryset.
        arg = node.args[0]
        is_qs = False
        if isinstance(arg, ast.Name) and any(arg.id.endswith(s) for s in _QUERYSET_SUFFIXES):
            is_qs = True
        elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
            if arg.func.attr in _ORM_METHODS:
                is_qs = True

        if is_qs and self._loop_depth > 0:
            self._add_finding(
                Finding(
                    rule_id="PERF004",
                    message="Unnecessary list() conversion of QuerySet inside loop",
                    severity=Severity.HINT,
                    category=Category.PERFORMANCE,
                    location=self._make_location(node.lineno),
                    suggestion="Iterate directly over the QuerySet instead of converting to list",
                    context=self._get_source_line(node.lineno),
                )
            )

    # ------------------------------------------------------------------
    # PERF005 — QuerySet re-evaluation
    # ------------------------------------------------------------------

    def _track_queryset_assignment(self, node: ast.Assign) -> None:
        """Track assignments like `qs = Model.objects.filter(...)`."""
        if not isinstance(node.value, ast.Call):
            return
        if not isinstance(node.value.func, ast.Attribute):
            return
        if node.value.func.attr not in ("filter", "all"):
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._qs_assignments[target.id] = node.lineno

    def _track_queryset_usage(self, node: ast.Expr) -> None:
        """Track standalone expression usages of queryset variables."""
        # Handled by visit_Name for all Name loads

    def _check_queryset_reevaluation(self) -> None:
        """Emit PERF005 for queryset variables used in 2+ separate expressions."""
        for name, usages in self._qs_usage_counts.items():
            if name not in self._qs_assignments:
                continue
            # Deduplicate to unique lines (same line doesn't count as re-eval)
            unique_lines = set(usages)
            # Exclude the assignment line itself
            unique_lines.discard(self._qs_assignments[name])
            if len(unique_lines) >= 2:
                self._add_finding(
                    Finding(
                        rule_id="PERF005",
                        message=f"QuerySet '{name}' evaluated multiple times without caching",
                        severity=Severity.HINT,
                        category=Category.PERFORMANCE,
                        location=self._make_location(self._qs_assignments[name]),
                        suggestion="Evaluate once with list() or use queryset caching to avoid repeated DB hits",
                        context=self._get_source_line(self._qs_assignments[name]),
                    )
                )

    # ------------------------------------------------------------------
    # PERF006 — String concatenation in loop
    # ------------------------------------------------------------------

    def _check_string_concat_in_loop(self, node: ast.AugAssign) -> None:
        if self._loop_depth == 0:
            return
        if not isinstance(node.op, ast.Add):
            return
        if not isinstance(node.target, ast.Name):
            return

        # Heuristic: if the value being added is a string literal or f-string,
        # or the target name suggests string usage (e.g. contains "str", "text", "html", "msg")
        is_string_concat = False

        if isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            if (
                isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
            ) or isinstance(node.value, ast.JoinedStr):
                is_string_concat = True

        # Also check for common string variable name patterns
        target_name = node.target.id.lower()
        string_hints = (
            "html",
            "text",
            "msg",
            "message",
            "output",
            "result",
            "body",
            "content",
            "xml",
            "csv",
            "sql",
        )
        if any(hint in target_name for hint in string_hints):
            is_string_concat = True

        if is_string_concat:
            self._add_finding(
                Finding(
                    rule_id="PERF006",
                    message="String concatenation with += inside loop",
                    severity=Severity.HINT,
                    category=Category.PERFORMANCE,
                    location=self._make_location(node.lineno),
                    suggestion="Collect parts in a list and use ''.join() after the loop",
                    context=self._get_source_line(node.lineno),
                )
            )

    # ------------------------------------------------------------------
    # PERF007 — Mutable default argument
    # ------------------------------------------------------------------

    def _check_mutable_default(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if self._is_mutable_literal(default):
                self._add_finding(
                    Finding(
                        rule_id="PERF007",
                        message=f"Mutable default argument in '{node.name}'",
                        severity=Severity.WARNING,
                        category=Category.PERFORMANCE,
                        location=self._make_location(default.lineno),
                        suggestion="Use None as default and initialize inside the function: if arg is None: arg = []",
                        context=self._get_source_line(node.lineno),
                    )
                )

    def _is_mutable_literal(self, node: ast.expr) -> bool:
        """Check if a node is a mutable literal: [], {}, set()."""
        if isinstance(node, ast.List):
            return True
        if isinstance(node, ast.Dict):
            return True
        if isinstance(node, ast.Set):
            return True
        # set() / list() / dict() calls with no args
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("list", "dict", "set") and not node.args and not node.keywords:
                return True
        return False
