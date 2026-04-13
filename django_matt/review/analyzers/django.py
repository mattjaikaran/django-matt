"""Django best-practices AST analyzer — detects ORM misuse, fat views, and security risks."""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity

_SYNC_ORM_METHODS: frozenset[str] = frozenset({
    "get", "filter", "all", "save", "delete", "create", "update",
    "count", "exists", "first", "last", "aggregate", "values", "values_list",
})

_VIEW_BASE_KEYWORDS: frozenset[str] = frozenset({
    "Controller", "ViewSet", "View", "APIView",
})

_ROUTE_DECORATOR_NAMES: frozenset[str] = frozenset({
    "get", "post", "put", "patch", "delete", "head", "options", "trace",
})


def _is_async_def(node: ast.AST) -> bool:
    return isinstance(node, ast.AsyncFunctionDef)


def _function_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return (node.end_lineno or node.lineno) - node.lineno + 1


def _has_route_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            dec = dec.func  # type: ignore[assignment]
        if isinstance(dec, ast.Attribute) and dec.attr in _ROUTE_DECORATOR_NAMES:
            return True
        if isinstance(dec, ast.Name) and dec.id in _ROUTE_DECORATOR_NAMES:
            return True
    return False


def _has_auth_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    auth_names = {"jwt_required", "jwt_optional", "requires_role", "requires_permission",
                  "login_required", "permission_required"}
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            dec = dec.func  # type: ignore[assignment]
        if isinstance(dec, ast.Name) and dec.id in auth_names:
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in auth_names:
            return True
    return False


def _is_view_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.args.args and node.args.args[0].arg == "request":
        return True
    return _has_route_decorator(node)


def _is_view_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = ""
        if isinstance(base, ast.Name):
            name = base.id
        elif isinstance(base, ast.Attribute):
            name = base.attr
        for kw in _VIEW_BASE_KEYWORDS:
            if kw in name:
                return True
    # Check if any method has a route decorator
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_route_decorator(item):
                return True
    return False


def _class_has_auth(node: ast.ClassDef) -> bool:
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "permission_classes", "authentication_classes",
                }:
                    return True
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_auth_decorator(item):
                return True
    # Check class decorators
    for dec in node.decorator_list:
        func = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(func, ast.Name) and func.id in {
            "jwt_required", "requires_role", "requires_permission",
        }:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {
            "jwt_required", "requires_role", "requires_permission",
        }:
            return True
    return False


def _node_contains_orm_call(node: ast.AST) -> bool:
    """Check if any sub-expression contains an ORM-like call."""
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            if child.attr in {"objects", "filter", "get", "all", "create", "update"}:
                return True
    return False


def _is_fstring_or_format(node: ast.AST) -> bool:
    """Check if a node is an f-string or .format() call."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return True
    return False


def _count_chained_calls(node: ast.Call) -> int:
    """Count depth of chained method calls like .filter().annotate().aggregate()."""
    count = 1
    current = node.func
    while isinstance(current, ast.Attribute):
        if isinstance(current.value, ast.Call):
            count += 1
            current = current.value.func
        else:
            break
    return count


class DjangoBestPracticesAnalyzer(ASTVisitorAnalyzer):
    """AST-based Django best practices analyzer."""

    name: str = "django"
    description: str = "Detects Django anti-patterns: sync ORM in async, N+1, fat views, raw SQL, missing auth"

    def __init__(self, config: object) -> None:
        super().__init__(config)  # type: ignore[arg-type]
        self._async_context: list[str] = []
        self._class_context: list[ast.ClassDef] = []
        self._view_context: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self._in_loop_depth: int = 0

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._async_context = []
        self._class_context = []
        self._view_context = []
        self._in_loop_depth = 0
        return super().analyze_file(file_path, tree, source)

    def _location(
        self,
        lineno: int,
        end_lineno: int | None = None,
        function: str | None = None,
        class_name: str | None = None,
    ) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            end_line=end_lineno,
            function=function or (self._async_context[-1] if self._async_context else None),
            class_name=class_name or (self._class_context[-1].name if self._class_context else None),
        )

    # ── DJ001: Sync ORM in async context ─────────────────────────────

    def _check_sync_orm_in_async(self, node: ast.Call) -> None:
        if not self._async_context:
            return
        func = node.func
        if not isinstance(func, ast.Attribute):
            return
        method_name = func.attr
        if method_name in _SYNC_ORM_METHODS:
            self._add_finding(Finding(
                rule_id="DJ001",
                message=f"Sync ORM method .{method_name}() called inside async function '{self._async_context[-1]}'",
                severity=Severity.ERROR,
                category=Category.DJANGO,
                location=self._location(node.lineno),
                suggestion=f"Use .a{method_name}() or wrap with sync_to_async()",
                context=self._get_source_line(node.lineno).strip(),
            ))

    # ── DJ002: N+1 query pattern ─────────────────────────────────────

    def _check_n_plus_one(self, node: ast.For) -> None:
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, ast.Attribute) and child.attr in {
                "objects", "filter", "get", "all",
            }:
                self._add_finding(Finding(
                    rule_id="DJ002",
                    message="Potential N+1 query: ORM access inside loop",
                    severity=Severity.WARNING,
                    category=Category.PERFORMANCE,
                    location=self._location(child.lineno),
                    suggestion="Use select_related() or prefetch_related() before the loop",
                    context=self._get_source_line(child.lineno).strip(),
                ))
                return  # one finding per loop

    # ── DJ003: Fat view ──────────────────────────────────────────────

    def _check_fat_view(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_view = _is_view_function(node)
        if not is_view and self._class_context:
            if _is_view_class(self._class_context[-1]):
                is_view = True
        if not is_view:
            return
        line_count = _function_line_count(node)
        if line_count > 50:
            self._add_finding(Finding(
                rule_id="DJ003",
                message=f"View '{node.name}' is {line_count} lines — consider extracting to service layer",
                severity=Severity.WARNING,
                category=Category.COMPLEXITY,
                location=self._location(node.lineno, node.end_lineno, function=node.name),
                suggestion="Extract business logic to a service layer; keep views thin",
            ))

    # ── DJ004: Raw SQL usage ─────────────────────────────────────────

    def _check_raw_sql(self, node: ast.Call) -> None:
        func = node.func
        if not isinstance(func, ast.Attribute):
            return
        method_name = func.attr

        if method_name in {"raw", "extra"}:
            # Check if arguments contain f-strings or .format()
            has_injection_risk = any(
                _is_fstring_or_format(arg) for arg in node.args
            )
            if has_injection_risk:
                self._add_finding(Finding(
                    rule_id="DJ004",
                    message=f"SQL injection risk: .{method_name}() with string interpolation",
                    severity=Severity.ERROR,
                    category=Category.SECURITY,
                    location=self._location(node.lineno),
                    suggestion="Use parameterized queries: .raw('SELECT ... WHERE id = %s', [id])",
                    context=self._get_source_line(node.lineno).strip(),
                ))
            else:
                self._add_finding(Finding(
                    rule_id="DJ004",
                    message=f"Raw SQL via .{method_name}() — prefer ORM when possible",
                    severity=Severity.WARNING,
                    category=Category.DJANGO,
                    location=self._location(node.lineno),
                    suggestion="Use Django ORM or ensure parameterized queries",
                    context=self._get_source_line(node.lineno).strip(),
                ))

        if method_name == "execute":
            # cursor.execute() with f-string/format
            if node.args and _is_fstring_or_format(node.args[0]):
                self._add_finding(Finding(
                    rule_id="DJ004",
                    message="SQL injection risk: cursor.execute() with string interpolation",
                    severity=Severity.ERROR,
                    category=Category.SECURITY,
                    location=self._location(node.lineno),
                    suggestion="Use parameterized queries: cursor.execute('SELECT ... WHERE id = %s', [id])",
                    context=self._get_source_line(node.lineno).strip(),
                ))

    # ── DJ005: Missing auth on view class ────────────────────────────

    def _check_missing_auth(self, node: ast.ClassDef) -> None:
        if not _is_view_class(node):
            return
        if _class_has_auth(node):
            return
        self._add_finding(Finding(
            rule_id="DJ005",
            message=f"Class '{node.name}' has no permission_classes or auth decorators",
            severity=Severity.HINT,
            category=Category.SECURITY,
            location=self._location(node.lineno, class_name=node.name),
            suggestion="Add permission_classes = [IsAuthenticated] or apply auth decorators",
        ))

    # ── DJ006: Business logic in view ────────────────────────────────

    def _check_business_logic_in_view(self, node: ast.Call) -> None:
        if not self._view_context:
            return
        func = node.func
        if not isinstance(func, ast.Attribute):
            return

        # .objects.create() pattern
        if func.attr == "create" and isinstance(func.value, ast.Attribute):
            if func.value.attr == "objects":
                self._add_finding(Finding(
                    rule_id="DJ006",
                    message=f"Direct .objects.create() in view '{self._view_context[-1].name}'",
                    severity=Severity.HINT,
                    category=Category.MODULARITY,
                    location=self._location(node.lineno),
                    suggestion="Extract model creation to a service or repository layer",
                    context=self._get_source_line(node.lineno).strip(),
                ))
                return

        # 3+ chained ORM calls
        chain_depth = _count_chained_calls(node)
        if chain_depth >= 3:
            self._add_finding(Finding(
                rule_id="DJ006",
                message=f"Complex query chain ({chain_depth} calls) in view '{self._view_context[-1].name}'",
                severity=Severity.HINT,
                category=Category.MODULARITY,
                location=self._location(node.lineno),
                suggestion="Extract complex queries to a service or repository layer",
                context=self._get_source_line(node.lineno).strip(),
            ))

    # ── DJ007: Unbounded queryset ────────────────────────────────────

    def _check_unbounded_queryset(self, node: ast.Call) -> None:
        if not self._view_context:
            return
        func = node.func
        if not isinstance(func, ast.Attribute):
            return
        if func.attr not in {"all", "filter"}:
            return

        # Walk up to see if the result is sliced, paginated, or iterated
        # We check the parent context — if it's a standalone expression or
        # assignment without slicing, flag it
        # Since AST doesn't have parent refs, we check if this call is
        # wrapped in a Subscript (slice) at the call site via visit_Assign/visit_Expr
        # For simplicity, flag .all()/.filter() in view context and
        # skip if the call is inside a chained call (likely paginated/sliced elsewhere)
        parent_attr = None
        if isinstance(func.value, ast.Call) and isinstance(func.value.func, ast.Attribute):
            parent_attr = func.value.func.attr

        # Skip if it's part of a deeper chain (likely has pagination/slicing downstream)
        if parent_attr in {"select_related", "prefetch_related", "order_by", "only", "defer"}:
            return

        self._add_finding(Finding(
            rule_id="DJ007",
            message=f"Potentially unbounded .{func.attr}() in view '{self._view_context[-1].name}'",
            severity=Severity.WARNING,
            category=Category.PERFORMANCE,
            location=self._location(node.lineno),
            suggestion="Add pagination, slicing [:N], or .iterator() to limit results",
            context=self._get_source_line(node.lineno).strip(),
        ))

    # ── AST visitors ─────────────────────────────────────────────────

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._async_context.append(node.name)
        is_view = _is_view_function(node) or (
            self._class_context and _is_view_class(self._class_context[-1])
        )
        if is_view:
            self._view_context.append(node)
        self._check_fat_view(node)
        self.generic_visit(node)
        self._async_context.pop()
        if is_view:
            self._view_context.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        is_view = _is_view_function(node) or (
            self._class_context and _is_view_class(self._class_context[-1])
        )
        if is_view:
            self._view_context.append(node)
        self._check_fat_view(node)
        self.generic_visit(node)
        if is_view:
            self._view_context.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_context.append(node)
        self._check_missing_auth(node)
        self.generic_visit(node)
        self._class_context.pop()

    def visit_For(self, node: ast.For) -> None:
        self._check_n_plus_one(node)
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._check_n_plus_one(node)
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        self._check_sync_orm_in_async(node)
        self._check_raw_sql(node)
        self._check_business_logic_in_view(node)
        self._check_unbounded_queryset(node)
        self.generic_visit(node)
