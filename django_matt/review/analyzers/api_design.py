"""AST-based API design checker.

Detects inconsistent URL patterns, missing pagination on list endpoints,
missing authentication on mutation endpoints, overly broad serialization,
and missing error response annotations.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import BaseAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity

_ROUTE_DECORATORS: frozenset[str] = frozenset({
    "get", "post", "put", "patch", "delete", "head", "options",
})

_MUTATION_METHODS: frozenset[str] = frozenset({
    "post", "put", "patch", "delete",
})

_AUTH_DECORATORS: frozenset[str] = frozenset({
    "jwt_required", "jwt_optional", "login_required",
    "permission_required", "requires_role", "requires_permission",
    "authenticated", "IsAuthenticated",
})

_PAGINATION_INDICATORS: frozenset[str] = frozenset({
    "paginate", "pagination", "paginator", "page_size",
    "limit", "offset", "cursor", "PageNumberPagination",
    "LimitOffsetPagination", "CursorPagination",
    "paginate_queryset",
})


class APIDesignAnalyzer(BaseAnalyzer):
    """Analyzer that detects API design issues via AST inspection."""

    name = "api_design"
    description = "Checks URL consistency, missing pagination, missing auth on mutations, broad serialization"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()

        endpoints = self._collect_endpoints(tree)
        class_info = self._collect_class_info(tree)

        self._check_url_consistency(endpoints, findings)
        self._check_missing_pagination(endpoints, class_info, findings)
        self._check_missing_auth_on_mutations(endpoints, class_info, findings)
        self._check_broad_serialization(tree, findings)
        self._check_missing_error_responses(endpoints, findings)

        return findings

    def _make_location(
        self,
        lineno: int,
        function: str | None = None,
        class_name: str | None = None,
    ) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            function=function,
            class_name=class_name,
        )

    def _get_source_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self._source_lines):
            return self._source_lines[lineno - 1]
        return ""

    # -- Endpoint collection -----------------------------------------------

    def _collect_endpoints(self, tree: ast.Module) -> list[dict[str, object]]:
        """Collect all route-decorated functions with their metadata."""
        endpoints: list[dict[str, object]] = []

        # Walk with parent tracking to know enclosing class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for dec in item.decorator_list:
                        route_info = self._parse_route_decorator(dec)
                        if route_info is None:
                            continue
                        method, path = route_info
                        has_auth = self._function_has_auth(item)
                        endpoints.append({
                            "node": item,
                            "method": method,
                            "path": path,
                            "has_auth": has_auth,
                            "name": item.name,
                            "lineno": item.lineno,
                            "class_name": node.name,
                        })

            # Also collect module-level route functions (no enclosing class)
            if isinstance(node, ast.Module):
                for item in node.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for dec in item.decorator_list:
                        route_info = self._parse_route_decorator(dec)
                        if route_info is None:
                            continue
                        method, path = route_info
                        has_auth = self._function_has_auth(item)
                        endpoints.append({
                            "node": item,
                            "method": method,
                            "path": path,
                            "has_auth": has_auth,
                            "name": item.name,
                            "lineno": item.lineno,
                            "class_name": None,
                        })

        return endpoints

    def _parse_route_decorator(self, dec: ast.expr) -> tuple[str, str | None] | None:
        """Parse @api.get("/path") or @get("/path") style decorators."""
        call_node: ast.Call | None = None
        attr_name: str | None = None

        if isinstance(dec, ast.Call):
            call_node = dec
            if isinstance(dec.func, ast.Attribute):
                attr_name = dec.func.attr
            elif isinstance(dec.func, ast.Name):
                attr_name = dec.func.id
        elif isinstance(dec, ast.Attribute):
            attr_name = dec.attr

        if attr_name not in _ROUTE_DECORATORS:
            return None

        path: str | None = None
        if call_node and call_node.args:
            first_arg = call_node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                path = first_arg.value

        return (attr_name, path)

    def _function_has_auth(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function has authentication decorators."""
        for dec in node.decorator_list:
            name = self._get_decorator_name(dec)
            if name in _AUTH_DECORATORS:
                return True
        return False

    def _collect_class_info(self, tree: ast.Module) -> dict[str, dict[str, object]]:
        """Collect class-level auth and pagination info."""
        info: dict[str, dict[str, object]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_auth = False
            has_pagination = False
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id in ("permission_classes", "authentication_classes"):
                                has_auth = True
                            if target.id in ("pagination_class", "paginator_class"):
                                has_pagination = True
            # Check class decorators for auth
            for dec in node.decorator_list:
                name = self._get_decorator_name(dec)
                if name in _AUTH_DECORATORS:
                    has_auth = True
            info[node.name] = {"has_auth": has_auth, "has_pagination": has_pagination}
        return info

    # -- Checks ------------------------------------------------------------

    def _check_url_consistency(
        self,
        endpoints: list[dict[str, object]],
        findings: list[Finding],
    ) -> None:
        """API001: Check for inconsistent URL naming patterns."""
        paths = [ep["path"] for ep in endpoints if ep["path"] is not None]
        if len(paths) < 2:
            return

        # Check for mixed trailing slashes
        has_trailing = sum(1 for p in paths if isinstance(p, str) and p.endswith("/"))
        has_no_trailing = len(paths) - has_trailing

        if has_trailing > 0 and has_no_trailing > 0:
            finding = Finding(
                rule_id="API001",
                message=f"Inconsistent trailing slashes: {has_trailing} paths with, {has_no_trailing} without",
                severity=Severity.HINT,
                category=Category.API_DESIGN,
                location=self._make_location(1),
                suggestion="Standardize URL patterns — use trailing slashes consistently",
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

        # Check for mixed casing (kebab-case vs snake_case vs camelCase)
        has_kebab = any(isinstance(p, str) and "-" in p for p in paths)
        has_snake = any(isinstance(p, str) and "_" in p for p in paths)
        if has_kebab and has_snake:
            finding = Finding(
                rule_id="API001",
                message="Mixed URL casing: both kebab-case and snake_case found",
                severity=Severity.HINT,
                category=Category.API_DESIGN,
                location=self._make_location(1),
                suggestion="Standardize URL patterns — prefer kebab-case for URLs",
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

    def _check_missing_pagination(
        self,
        endpoints: list[dict[str, object]],
        class_info: dict[str, dict[str, object]],
        findings: list[Finding],
    ) -> None:
        """API002: Check for list endpoints without pagination."""
        for ep in endpoints:
            if ep["method"] != "get":
                continue
            node = ep["node"]
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            name = str(ep["name"])

            # Heuristic: function name suggests a list endpoint
            is_list = (
                name.startswith("list")
                or name.startswith("get_all")
                or name.endswith("_list")
                or name == "index"
            )

            # Check for return of .all() or .filter() without slicing
            if not is_list:
                is_list = self._returns_queryset(node)

            if not is_list:
                continue

            # Check if pagination is applied
            has_pagination = self._function_has_pagination(node)

            # Check class-level pagination (scoped to enclosing class)
            if not has_pagination:
                enclosing_class = ep.get("class_name")
                if enclosing_class and enclosing_class in class_info:
                    has_pagination = bool(class_info[enclosing_class].get("has_pagination"))

            if not has_pagination:
                finding = Finding(
                    rule_id="API002",
                    message=f"List endpoint '{name}' has no pagination",
                    severity=Severity.WARNING,
                    category=Category.API_DESIGN,
                    location=self._make_location(node.lineno, function=name),
                    suggestion="Add pagination to prevent unbounded result sets",
                    context=self._get_source_line(node.lineno).strip(),
                )
                if self.config.should_report_finding(finding.rule_id, finding.severity):
                    findings.append(finding)

    def _check_missing_auth_on_mutations(
        self,
        endpoints: list[dict[str, object]],
        class_info: dict[str, dict[str, object]],
        findings: list[Finding],
    ) -> None:
        """API003: Check for mutation endpoints without authentication."""
        for ep in endpoints:
            method = ep["method"]
            if method not in _MUTATION_METHODS:
                continue
            if ep["has_auth"]:
                continue

            # Check if enclosing class has auth (scoped to the actual parent class)
            node = ep["node"]
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            has_class_auth = False
            enclosing_class = ep.get("class_name")
            if enclosing_class and enclosing_class in class_info:
                has_class_auth = bool(class_info[enclosing_class].get("has_auth"))

            if has_class_auth:
                continue

            name = str(ep["name"])
            finding = Finding(
                rule_id="API003",
                message=f"Mutation endpoint '{name}' ({method.upper()}) has no authentication",
                severity=Severity.WARNING,
                category=Category.API_DESIGN,
                location=self._make_location(node.lineno, function=name),
                suggestion="Add @jwt_required or permission_classes to protect mutation endpoints",
                context=self._get_source_line(node.lineno).strip(),
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

    def _check_broad_serialization(self, tree: ast.Module, findings: list[Finding]) -> None:
        """API004: Detect '__all__' in Meta.fields of serializer/schema classes."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name != "Meta":
                continue
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                for target in item.targets:
                    if not isinstance(target, ast.Name) or target.id != "fields":
                        continue
                    if isinstance(item.value, ast.Constant) and item.value.value == "__all__":
                        finding = Finding(
                            rule_id="API004",
                            message="Meta.fields = '__all__' exposes all model fields",
                            severity=Severity.WARNING,
                            category=Category.API_DESIGN,
                            location=self._make_location(item.lineno),
                            suggestion="Explicitly list fields to prevent accidental exposure of sensitive data",
                            context=self._get_source_line(item.lineno).strip(),
                        )
                        if self.config.should_report_finding(finding.rule_id, finding.severity):
                            findings.append(finding)

    def _check_missing_error_responses(
        self,
        endpoints: list[dict[str, object]],
        findings: list[Finding],
    ) -> None:
        """API005: Check for mutation endpoints without error response annotations."""
        for ep in endpoints:
            if ep["method"] not in _MUTATION_METHODS:
                continue
            node = ep["node"]
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))

            # Check return annotation for error/response types
            if node.returns is None:
                name = str(ep["name"])
                finding = Finding(
                    rule_id="API005",
                    message=f"Mutation endpoint '{name}' has no return type annotation",
                    severity=Severity.HINT,
                    category=Category.API_DESIGN,
                    location=self._make_location(node.lineno, function=name),
                    suggestion="Add return type annotation including error response types",
                )
                if self.config.should_report_finding(finding.rule_id, finding.severity):
                    findings.append(finding)

    # -- Helpers -----------------------------------------------------------

    def _returns_queryset(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function body returns .all() or .filter() result."""
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                for inner in ast.walk(child.value):
                    if isinstance(inner, ast.Attribute) and inner.attr in ("all", "filter"):
                        return True
        return False

    def _function_has_pagination(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function uses pagination."""
        source_segment = ast.dump(node)
        for indicator in _PAGINATION_INDICATORS:
            if indicator in source_segment:
                return True
        return False

    def _get_decorator_name(self, dec: ast.expr) -> str | None:
        """Extract decorator name from various forms."""
        if isinstance(dec, ast.Name):
            return dec.id
        if isinstance(dec, ast.Attribute):
            return dec.attr
        if isinstance(dec, ast.Call):
            return self._get_decorator_name(dec.func)
        return None
