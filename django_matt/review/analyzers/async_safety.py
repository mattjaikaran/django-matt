"""AST-based async safety analyzer.

Detects sync ORM calls in async functions, missing await on coroutines,
time.sleep() in async context, and blocking I/O in async functions.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Category, Finding, Location, Severity

_SYNC_ORM_METHODS: frozenset[str] = frozenset(
    {
        "get",
        "filter",
        "save",
        "delete",
        "all",
        "count",
        "exists",
        "first",
        "last",
        "create",
        "update",
        "bulk_create",
        "bulk_update",
        "aggregate",
        "values",
        "values_list",
        "exclude",
        "annotate",
        "order_by",
        "distinct",
        "select_for_update",
    }
)

_BLOCKING_IO_CALLS: dict[str | None, frozenset[str]] = {
    None: frozenset({"open"}),
    "time": frozenset({"sleep"}),
    "requests": frozenset({"get", "post", "put", "patch", "delete", "head", "options", "request"}),
    "urllib": frozenset({"urlopen"}),
    "urllib.request": frozenset({"urlopen"}),
    "subprocess": frozenset({"run", "call", "check_output", "check_call", "Popen"}),
    "os": frozenset({"system", "popen"}),
}


class AsyncSafetyAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects async safety violations via AST inspection."""

    name = "async_safety"
    description = (
        "Detects sync ORM in async, missing await, time.sleep, blocking I/O in async context"
    )

    def __init__(self, config: ReviewConfig) -> None:
        super().__init__(config)
        self._async_stack: list[str] = []
        self._current_class: str | None = None

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self._async_stack = []
        self._current_class = None
        self.visit(tree)
        return self._findings

    def _make_location(self, lineno: int, function: str | None = None) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            function=function or (self._async_stack[-1] if self._async_stack else None),
            class_name=self._current_class,
        )

    # -- Visitors ----------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._async_stack.append(node.name)
        self.generic_visit(node)
        self._async_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Not async — clear the async context for nested sync functions
        prev_stack = self._async_stack
        self._async_stack = []
        self.generic_visit(node)
        self._async_stack = prev_stack

    def visit_Call(self, node: ast.Call) -> None:
        if self._async_stack:
            self._check_sync_orm(node)
            self._check_time_sleep(node)
            self._check_blocking_io(node)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        if self._async_stack and isinstance(node.value, ast.Call):
            self._check_missing_await(node.value)
        self.generic_visit(node)

    # -- Checks ------------------------------------------------------------

    def _check_sync_orm(self, node: ast.Call) -> None:
        """AS001: Detect sync ORM calls in async functions."""
        if not isinstance(node.func, ast.Attribute):
            return
        method_name = node.func.attr
        if method_name not in _SYNC_ORM_METHODS:
            return

        # Heuristic: the call target looks like an ORM call
        # e.g. Model.objects.get(), queryset.filter(), instance.save()
        # We check if the parent chain includes .objects or common ORM patterns
        if self._looks_like_orm_call(node):
            self._add_finding(
                Finding(
                    rule_id="AS001",
                    message=f"Sync ORM method .{method_name}() called in async function '{self._async_stack[-1]}'",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=self._make_location(node.lineno),
                    suggestion=f"Use .a{method_name}() or wrap with sync_to_async()",
                    context=self._get_source_line(node.lineno).strip(),
                )
            )

    def _looks_like_orm_call(self, node: ast.Call) -> bool:
        """Heuristic check if a method call looks like Django ORM usage."""
        func = node.func
        if not isinstance(func, ast.Attribute):
            return False

        method = func.attr

        # instance.save() / instance.delete()
        if method in ("save", "delete", "refresh_from_db"):
            return True

        # Check for .objects chain
        value = func.value
        if isinstance(value, ast.Attribute) and value.attr == "objects":
            return True

        # Chained calls: qs.filter().get(), etc.
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            parent_method = value.func.attr
            if parent_method in _SYNC_ORM_METHODS or parent_method == "objects":
                return True

        return False

    def _check_time_sleep(self, node: ast.Call) -> None:
        """AS002: Detect time.sleep() in async context."""
        dotted = self._get_dotted_name(node.func)
        if dotted == "time.sleep":
            self._add_finding(
                Finding(
                    rule_id="AS002",
                    message=f"time.sleep() called in async function '{self._async_stack[-1]}'",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=self._make_location(node.lineno),
                    suggestion="Use await asyncio.sleep() instead of time.sleep()",
                    context=self._get_source_line(node.lineno).strip(),
                )
            )

    def _check_blocking_io(self, node: ast.Call) -> None:
        """AS003: Detect blocking I/O calls in async context."""
        func_name: str | None = None
        module: str | None = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            module = None
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            module = self._resolve_module(node.func.value)

        if func_name is None:
            return

        # Check builtins (open)
        if module is None and func_name in _BLOCKING_IO_CALLS.get(None, frozenset()):
            self._emit_blocking_finding(node, f"{func_name}()")
            return

        # Check module-qualified calls
        if module is not None:
            for mod_prefix, funcs in _BLOCKING_IO_CALLS.items():
                if mod_prefix is None:
                    continue
                if module == mod_prefix or module.endswith(f".{mod_prefix}"):
                    if func_name in funcs:
                        self._emit_blocking_finding(node, f"{module}.{func_name}()")
                        return

    def _emit_blocking_finding(self, node: ast.Call, call_repr: str) -> None:
        self._add_finding(
            Finding(
                rule_id="AS003",
                message=f"Blocking I/O call {call_repr} in async function '{self._async_stack[-1]}'",
                severity=Severity.ERROR,
                category=Category.ASYNC_SAFETY,
                location=self._make_location(node.lineno),
                suggestion="Use async alternatives: aiofiles.open(), httpx, asyncio.subprocess",
                context=self._get_source_line(node.lineno).strip(),
            )
        )

    def _check_missing_await(self, node: ast.Call) -> None:
        """AS004: Detect calls to known async methods without await."""
        if not isinstance(node.func, ast.Attribute):
            return
        method = node.func.attr
        # Methods that start with 'a' and have a sync counterpart
        if method.startswith("a") and method[1:] in _SYNC_ORM_METHODS:
            # This is an async ORM call used as a bare expression (no await)
            # The parent visit_Expr already filtered to bare expressions
            self._add_finding(
                Finding(
                    rule_id="AS004",
                    message=f"Async ORM method .{method}() called without await in '{self._async_stack[-1]}'",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=self._make_location(node.lineno),
                    suggestion=f"Add 'await' before .{method}() call",
                    context=self._get_source_line(node.lineno).strip(),
                )
            )

    # -- Helpers -----------------------------------------------------------

    def _get_dotted_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_dotted_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return None

    def _resolve_module(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._resolve_module(node.value)
            if parent:
                return f"{parent}.{node.attr}"
        return None
