# file-length-max: 500
"""
Management command to validate API endpoints for common issues.

Performs comprehensive validation:
- Missing permissions on endpoints
- Missing auth decorators on non-public endpoints
- Missing request schema on POST/PUT/PATCH endpoints
- Missing return type annotations
- Missing docstrings
- Sync ORM calls in async views

Usage:
    python manage.py validate_api                    # Validate all endpoints
    python manage.py validate_api --prefix /api/     # Filter by prefix
    python manage.py validate_api --strict           # Treat warnings as errors
    python manage.py validate_api --json             # JSON output for CI
"""

import inspect

from django.urls import URLPattern, URLResolver, get_resolver

import orjson

from django_matt.cli import MattCommand


class ValidationIssue:
    """A validation issue found on an endpoint."""

    def __init__(self, endpoint: str, severity: str, code: str, message: str, suggestion: str = ""):
        self.endpoint = endpoint
        self.severity = severity  # error, warning, info
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


class Command(MattCommand):
    """Validate API endpoints for common issues."""

    help = "Validate API routes for missing permissions, schemas, auth, and async safety."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--prefix",
            default="/api/",
            help="URL prefix to scan (default: /api/).",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors (exit code 1).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON for CI integration.",
        )

    def handle(self, *args, **options):
        prefix = options["prefix"]
        strict = options["strict"]
        output_json = options.get("json", False)

        issues: list[ValidationIssue] = []
        endpoint_count = 0

        resolver = get_resolver()
        patterns = self._collect_patterns(resolver, "")

        for url, name, callback in patterns:
            if not url.startswith(prefix.lstrip("/")):
                continue

            endpoint_count += 1
            endpoint_label = f"/{url} ({name or 'unnamed'})"

            # Check 1: Missing permission_classes
            issues.extend(self._check_permissions(callback, endpoint_label))

            # Check 2: Missing auth decorators
            issues.extend(self._check_auth(callback, endpoint_label))

            # Check 3: Missing request schema on write endpoints
            issues.extend(self._check_request_schema(callback, endpoint_label))

            # Check 4: Missing return type annotations
            issues.extend(self._check_return_type(callback, endpoint_label))

            # Check 5: Missing docstrings
            issues.extend(self._check_docstring(callback, endpoint_label))

            # Check 6: Sync ORM in async views
            issues.extend(self._check_async_safety(callback, endpoint_label))

        # Output results
        if output_json:
            self._output_json(issues, endpoint_count, prefix)
        else:
            self._output_rich(issues, endpoint_count, prefix, strict)

        if strict and any(i.severity in ("error", "warning") for i in issues):
            raise SystemExit(1)

    def _collect_patterns(self, resolver, prefix):
        """Recursively collect all URL patterns."""
        results = []
        for pattern in resolver.url_patterns:
            if isinstance(pattern, URLResolver):
                new_prefix = prefix + str(pattern.pattern)
                results.extend(self._collect_patterns(pattern, new_prefix))
            elif isinstance(pattern, URLPattern):
                url = prefix + str(pattern.pattern)
                results.append((url, pattern.name, pattern.callback))
        return results

    def _get_view_class(self, callback):
        """Extract the view class from a callback."""
        view_cls = getattr(callback, "view_class", None)
        if view_cls is None:
            view_cls = getattr(callback, "cls", None)
        return view_cls

    def _get_http_methods(self, callback) -> list[str]:
        """Detect HTTP methods for a callback."""
        if hasattr(callback, "actions"):
            return [m.upper() for m in callback.actions.keys()]
        view_cls = self._get_view_class(callback)
        if view_cls:
            methods = []
            for method in ["get", "post", "put", "patch", "delete"]:
                if hasattr(view_cls, method):
                    methods.append(method.upper())
            return methods or ["GET"]
        return ["GET"]

    def _check_permissions(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for missing permission_classes on ViewSets/Views."""
        issues = []
        view_cls = self._get_view_class(callback)

        if view_cls:
            perms = getattr(view_cls, "permission_classes", None)
            if not perms:
                issues.append(
                    ValidationIssue(
                        endpoint=endpoint,
                        severity="warning",
                        code="missing-permissions",
                        message="No permission_classes set",
                        suggestion="Add permission_classes = [IsAuthenticated] or [AllowAny]",
                    )
                )
        return issues

    def _check_auth(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for missing auth decorators on non-public endpoints."""
        issues = []

        # Check if it has any auth decorator
        has_auth = False
        current = callback
        while current:
            if getattr(current, "_auth_required", False):
                has_auth = True
                break
            if getattr(current, "_auth_optional", False):
                has_auth = True
                break

            view_cls = self._get_view_class(current)
            if view_cls:
                perms = getattr(view_cls, "permission_classes", None)
                if perms:
                    has_auth = True
                    break

            wrapped = getattr(current, "__wrapped__", None)
            if wrapped is current or wrapped is None:
                break
            current = wrapped

        if not has_auth:
            issues.append(
                ValidationIssue(
                    endpoint=endpoint,
                    severity="info",
                    code="no-auth",
                    message="No authentication decorator or permission class",
                    suggestion="Add @jwt_required or permission_classes if not a public endpoint",
                )
            )
        return issues

    def _check_request_schema(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for missing request schema on write endpoints."""
        issues = []
        methods = self._get_http_methods(callback)
        write_methods = {"POST", "PUT", "PATCH"}

        if not write_methods.intersection(methods):
            return issues

        # Check if the view function has a Pydantic schema parameter
        view_func = callback
        view_cls = self._get_view_class(callback)
        if view_cls:
            # Check individual method handlers
            for method_name in ["post", "put", "patch", "create", "update", "partial_update"]:
                method = getattr(view_cls, method_name, None)
                if method:
                    view_func = method
                    break

        try:
            sig = inspect.signature(view_func)
            has_schema = False
            for param in sig.parameters.values():
                if param.name in ("self", "request", "pk", "args", "kwargs", "format"):
                    continue
                if param.annotation != inspect.Parameter.empty:
                    anno = param.annotation
                    if hasattr(anno, "model_fields"):  # Pydantic model
                        has_schema = True
                        break

            if not has_schema:
                issues.append(
                    ValidationIssue(
                        endpoint=endpoint,
                        severity="info",
                        code="missing-request-schema",
                        message=f"Write endpoint ({', '.join(write_methods.intersection(methods))}) "
                        f"has no Pydantic request schema",
                        suggestion="Add a Pydantic schema parameter for request validation",
                    )
                )
        except (ValueError, TypeError):
            pass

        return issues

    def _check_return_type(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for missing return type annotations."""
        issues = []
        view_func = callback

        # Unwrap to get the actual function
        while hasattr(view_func, "__wrapped__"):
            wrapped = view_func.__wrapped__
            if wrapped is view_func:
                break
            view_func = wrapped

        try:
            sig = inspect.signature(view_func)
            if sig.return_annotation == inspect.Signature.empty:
                issues.append(
                    ValidationIssue(
                        endpoint=endpoint,
                        severity="info",
                        code="missing-return-type",
                        message="No return type annotation",
                        suggestion="Add a return type annotation (e.g., -> JsonResponse)",
                    )
                )
        except (ValueError, TypeError):
            pass

        return issues

    def _check_docstring(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for missing docstrings."""
        issues = []
        view_func = callback

        # Unwrap
        while hasattr(view_func, "__wrapped__"):
            wrapped = view_func.__wrapped__
            if wrapped is view_func:
                break
            view_func = wrapped

        doc = inspect.getdoc(view_func)
        if not doc:
            view_cls = self._get_view_class(callback)
            if view_cls:
                doc = inspect.getdoc(view_cls)

        if not doc:
            issues.append(
                ValidationIssue(
                    endpoint=endpoint,
                    severity="info",
                    code="missing-docstring",
                    message="No docstring (used for OpenAPI description)",
                    suggestion="Add a docstring to generate API documentation",
                )
            )
        return issues

    def _check_async_safety(self, callback, endpoint: str) -> list[ValidationIssue]:
        """Check for sync ORM calls in async views."""
        issues = []
        view_func = callback

        while hasattr(view_func, "__wrapped__"):
            wrapped = view_func.__wrapped__
            if wrapped is view_func:
                break
            view_func = wrapped

        if not inspect.iscoroutinefunction(view_func):
            return issues

        # Check source code for sync ORM calls
        try:
            source = inspect.getsource(view_func)
            sync_calls = [
                (".get(", ".aget("),
                (".filter(", ".afilter("),
                (".create(", ".acreate("),
                (".save(", ".asave("),
                (".delete(", ".adelete("),
                (".update(", ".aupdate("),
                (".all()", ".aall()"),
                (".first()", ".afirst()"),
                (".exists()", ".aexists()"),
                (".count()", ".acount()"),
            ]

            for sync_call, async_call in sync_calls:
                if sync_call in source and async_call not in source:
                    issues.append(
                        ValidationIssue(
                            endpoint=endpoint,
                            severity="error",
                            code="sync-orm-in-async",
                            message=f"Sync ORM call `{sync_call.strip('(')}` in async view",
                            suggestion=f"Use `{async_call.strip('(')}`"
                            f" or wrap with sync_to_async()",
                        )
                    )
                    break  # One warning per endpoint is enough
        except (OSError, TypeError):
            pass

        return issues

    def _output_json(self, issues: list[ValidationIssue], endpoint_count: int, prefix: str):
        """Output results as JSON."""
        result = {
            "endpoint_count": endpoint_count,
            "prefix": prefix,
            "issue_count": len(issues),
            "errors": len([i for i in issues if i.severity == "error"]),
            "warnings": len([i for i in issues if i.severity == "warning"]),
            "info": len([i for i in issues if i.severity == "info"]),
            "issues": [i.to_dict() for i in issues],
        }
        self.stdout.write(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

    def _output_rich(
        self,
        issues: list[ValidationIssue],
        endpoint_count: int,
        prefix: str,
        strict: bool,
    ):
        """Output results with rich formatting."""
        self.console.banner()
        self.header("API Validation", f"Scanning endpoints under {prefix}")

        if not issues:
            self.console.box_success(
                f"All {endpoint_count} endpoints passed validation!",
                title="Validation Results",
            )
            return

        # Group by severity
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        infos = [i for i in issues if i.severity == "info"]

        # Display errors first
        if errors:
            self.console.newline()
            self.console.section("Errors")
            for issue in errors:
                self.console.error(f"{issue.endpoint}")
                self.console.print(f"    [red]{issue.message}[/]")
                if issue.suggestion:
                    self.console.print(f"    [dim]Fix: {issue.suggestion}[/]")

        if warnings:
            self.console.newline()
            self.console.section("Warnings")
            for issue in warnings:
                self.console.warning(f"{issue.endpoint}")
                self.console.print(f"    [yellow]{issue.message}[/]")
                if issue.suggestion:
                    self.console.print(f"    [dim]Fix: {issue.suggestion}[/]")

        if infos:
            self.console.newline()
            self.console.section("Suggestions")
            for issue in infos:
                self.console.info(f"{issue.endpoint}")
                self.console.print(f"    [dim]{issue.message}[/]")

        # Summary
        self.console.newline()
        summary_parts = []
        if errors:
            summary_parts.append(f"{len(errors)} error(s)")
        if warnings:
            summary_parts.append(f"{len(warnings)} warning(s)")
        if infos:
            summary_parts.append(f"{len(infos)} suggestion(s)")

        msg = f"Scanned {endpoint_count} endpoints: {', '.join(summary_parts)}"

        if errors:
            self.console.box_error(msg, title="Validation Results")
        elif warnings:
            self.console.box_warning(msg, title="Validation Results")
        else:
            self.console.box_success(msg, title="Validation Results")
