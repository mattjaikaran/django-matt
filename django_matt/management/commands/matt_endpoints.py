"""
Django Matt endpoint listing command.

Lists all API endpoints with details about methods, paths, views, and permissions.

Usage:
    python manage.py matt_endpoints                       # List all endpoints
    python manage.py matt_endpoints --method GET          # Filter by HTTP method
    python manage.py matt_endpoints --filter /api/users   # Filter by path pattern
    python manage.py matt_endpoints --app myapp           # Filter by app
    python manage.py matt_endpoints --markdown            # Export as markdown
    python manage.py matt_endpoints --openapi             # Export as OpenAPI JSON
    python manage.py matt_endpoints --json                # Output as JSON
"""

import json
import re
from typing import Any

from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver

from django_matt.cli import MattCommand


class Command(MattCommand):
    """List all API endpoints with detailed information."""

    help = "List all API endpoints with methods, paths, views, and permissions"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--method",
            "-m",
            choices=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            help="Filter by HTTP method",
        )
        parser.add_argument(
            "--filter",
            "-f",
            help="Filter endpoints by path pattern (regex supported)",
        )
        parser.add_argument(
            "--app",
            "-a",
            help="Filter by app name",
        )
        parser.add_argument(
            "--markdown",
            action="store_true",
            help="Export as markdown documentation",
        )
        parser.add_argument(
            "--openapi",
            action="store_true",
            help="Export as OpenAPI JSON schema",
        )
        parser.add_argument(
            "--group-by",
            choices=["app", "method", "prefix"],
            help="Group endpoints by app, method, or URL prefix",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show additional details (permissions, throttling)",
        )

    def handle(self, *args, **options):
        output_json = options.get("json", False)
        method_filter = options.get("method")
        path_filter = options.get("filter")
        app_filter = options.get("app")
        markdown = options.get("markdown", False)
        openapi = options.get("openapi", False)
        group_by = options.get("group_by")
        verbose = options.get("verbose", False)

        # Collect all endpoints
        endpoints = self._collect_endpoints()

        # Apply filters
        if method_filter:
            endpoints = [e for e in endpoints if method_filter.upper() in e.get("methods", [])]

        if path_filter:
            try:
                pattern = re.compile(path_filter, re.IGNORECASE)
                endpoints = [e for e in endpoints if pattern.search(e.get("path", ""))]
            except re.error:
                # Fallback to simple string matching
                endpoints = [
                    e for e in endpoints if path_filter.lower() in e.get("path", "").lower()
                ]

        if app_filter:
            endpoints = [
                e for e in endpoints if e.get("app", "").lower() == app_filter.lower()
            ]

        # Output in requested format
        if openapi:
            self._output_openapi(endpoints)
        elif markdown:
            self._output_markdown(endpoints)
        elif output_json:
            self.stdout.write(json.dumps(endpoints, indent=2, default=str))
        else:
            self._display_endpoints(endpoints, group_by, verbose)

    def _collect_endpoints(self, resolver=None, prefix="", app_name=None) -> list[dict[str, Any]]:
        """Recursively collect all URL endpoints."""
        if resolver is None:
            resolver = get_resolver()

        endpoints = []

        for pattern in resolver.url_patterns:
            path = prefix + str(pattern.pattern).lstrip("^").rstrip("$")

            if isinstance(pattern, URLResolver):
                # Get app name from namespace or pattern
                namespace = pattern.namespace or app_name
                endpoints.extend(self._collect_endpoints(pattern, path, namespace))

            elif isinstance(pattern, URLPattern):
                endpoint_info = self._extract_endpoint_info(pattern, path, app_name)
                if endpoint_info:
                    endpoints.append(endpoint_info)

        return endpoints

    def _extract_endpoint_info(
        self, pattern: URLPattern, path: str, app_name: str | None
    ) -> dict[str, Any] | None:
        """Extract detailed information from a URL pattern."""
        callback = pattern.callback

        # Skip admin and static file handlers
        if "admin" in path or path.startswith("static/"):
            return None

        # Get view information
        view_name = ""
        view_class = None
        view_module = ""

        if hasattr(callback, "__name__"):
            view_name = callback.__name__
        elif hasattr(callback, "__class__"):
            view_name = callback.__class__.__name__

        if hasattr(callback, "view_class"):
            view_class = callback.view_class
            view_name = view_class.__name__
            view_module = view_class.__module__
        elif hasattr(callback, "__module__"):
            view_module = callback.__module__

        # Determine HTTP methods
        methods = self._get_methods(callback)

        # Get permissions
        permissions = self._get_permissions(callback)

        # Get docstring/description
        description = ""
        if callback.__doc__:
            description = callback.__doc__.strip().split("\n")[0]
        elif view_class and view_class.__doc__:
            description = view_class.__doc__.strip().split("\n")[0]

        # Determine app from module path
        app = app_name or ""
        if view_module:
            parts = view_module.split(".")
            if len(parts) > 0:
                app = parts[0]

        # Clean up path
        clean_path = "/" + path.strip("/") if path else "/"

        return {
            "path": clean_path,
            "name": pattern.name or view_name,
            "view": view_name,
            "module": view_module,
            "methods": methods,
            "permissions": permissions,
            "description": description,
            "app": app,
            "url_name": pattern.name or "",
        }

    def _get_methods(self, callback) -> list[str]:
        """Extract HTTP methods from a view callback."""
        methods = []

        # Check for explicitly defined methods
        if hasattr(callback, "actions"):
            methods = [m.upper() for m in callback.actions.keys()]
        elif hasattr(callback, "http_method_names"):
            methods = [m.upper() for m in callback.http_method_names if m != "options"]
        elif hasattr(callback, "view_class"):
            view_class = callback.view_class
            if hasattr(view_class, "http_method_names"):
                methods = [m.upper() for m in view_class.http_method_names if m != "options"]

        # Check for Django Ninja/Matt route decorators
        if hasattr(callback, "_route_methods"):
            methods = list(callback._route_methods)

        # Default to GET if no methods found
        if not methods:
            methods = ["GET"]

        # Filter out HEAD and OPTIONS for cleaner output
        methods = [m for m in methods if m not in ("HEAD", "OPTIONS", "TRACE")]

        return sorted(set(methods))

    def _get_permissions(self, callback) -> list[str]:
        """Extract permission classes from a view callback."""
        permissions = []

        # Check for permission_classes attribute
        if hasattr(callback, "permission_classes"):
            for perm in callback.permission_classes:
                if isinstance(perm, type):
                    permissions.append(perm.__name__)
                else:
                    permissions.append(perm.__class__.__name__)

        # Check view class
        if hasattr(callback, "view_class"):
            view_class = callback.view_class
            if hasattr(view_class, "permission_classes"):
                for perm in view_class.permission_classes:
                    if isinstance(perm, type):
                        permissions.append(perm.__name__)
                    else:
                        permissions.append(perm.__class__.__name__)

        return list(set(permissions))

    def _display_endpoints(
        self, endpoints: list[dict[str, Any]], group_by: str | None, verbose: bool
    ):
        """Display endpoints in a formatted table."""
        self.console.banner()
        self.header("API Endpoints", f"Found {len(endpoints)} endpoints")

        if not endpoints:
            self.warning("No endpoints found")
            return

        if group_by == "app":
            self._display_grouped_by_app(endpoints, verbose)
        elif group_by == "method":
            self._display_grouped_by_method(endpoints, verbose)
        elif group_by == "prefix":
            self._display_grouped_by_prefix(endpoints, verbose)
        else:
            self._display_flat(endpoints, verbose)

    def _display_flat(self, endpoints: list[dict[str, Any]], verbose: bool):
        """Display endpoints as a flat table."""
        if verbose:
            table_data = []
            for e in endpoints:
                table_data.append(
                    {
                        "Methods": ", ".join(e.get("methods", ["GET"])),
                        "Path": e.get("path", ""),
                        "Name": e.get("name", ""),
                        "Permissions": ", ".join(e.get("permissions", [])) or "-",
                        "App": e.get("app", ""),
                    }
                )
            self.table(table_data)
        else:
            table_data = []
            for e in endpoints:
                methods_str = ", ".join(e.get("methods", ["GET"]))
                table_data.append(
                    {
                        "Methods": methods_str,
                        "Path": e.get("path", ""),
                        "View": e.get("view", ""),
                    }
                )
            self.table(table_data)

    def _display_grouped_by_app(self, endpoints: list[dict[str, Any]], verbose: bool):
        """Display endpoints grouped by app."""
        by_app = {}
        for e in endpoints:
            app = e.get("app", "unknown")
            if app not in by_app:
                by_app[app] = []
            by_app[app].append(e)

        for app, app_endpoints in sorted(by_app.items()):
            self.section(f"{app} ({len(app_endpoints)} endpoints)")
            self._display_flat(app_endpoints, verbose)

    def _display_grouped_by_method(self, endpoints: list[dict[str, Any]], verbose: bool):
        """Display endpoints grouped by HTTP method."""
        by_method = {}
        for e in endpoints:
            for method in e.get("methods", ["GET"]):
                if method not in by_method:
                    by_method[method] = []
                by_method[method].append(e)

        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            if method in by_method:
                self.section(f"{method} ({len(by_method[method])} endpoints)")
                table_data = [
                    {
                        "Path": e.get("path", ""),
                        "View": e.get("view", ""),
                        "Permissions": ", ".join(e.get("permissions", [])) or "-",
                    }
                    for e in by_method[method]
                ]
                self.table(table_data)

    def _display_grouped_by_prefix(self, endpoints: list[dict[str, Any]], verbose: bool):
        """Display endpoints grouped by URL prefix."""
        by_prefix = {}
        for e in endpoints:
            path = e.get("path", "/")
            parts = path.strip("/").split("/")
            prefix = "/" + parts[0] if parts and parts[0] else "/"
            if prefix not in by_prefix:
                by_prefix[prefix] = []
            by_prefix[prefix].append(e)

        for prefix, prefix_endpoints in sorted(by_prefix.items()):
            self.section(f"{prefix}/* ({len(prefix_endpoints)} endpoints)")
            self._display_flat(prefix_endpoints, verbose)

    def _output_markdown(self, endpoints: list[dict[str, Any]]):
        """Output endpoints as markdown documentation."""
        md = "# API Endpoints\n\n"

        # Group by app for markdown
        by_app = {}
        for e in endpoints:
            app = e.get("app", "Other")
            if app not in by_app:
                by_app[app] = []
            by_app[app].append(e)

        for app, app_endpoints in sorted(by_app.items()):
            md += f"## {app.title()}\n\n"
            md += "| Method | Path | Description | Permissions |\n"
            md += "|--------|------|-------------|-------------|\n"

            for e in sorted(app_endpoints, key=lambda x: x.get("path", "")):
                methods = ", ".join(e.get("methods", ["GET"]))
                path = e.get("path", "")
                desc = e.get("description", "-") or "-"
                perms = ", ".join(e.get("permissions", [])) or "None"
                md += f"| `{methods}` | `{path}` | {desc} | {perms} |\n"

            md += "\n"

        self.stdout.write(md)

    def _output_openapi(self, endpoints: list[dict[str, Any]]):
        """Output endpoints as OpenAPI JSON schema."""
        openapi_spec = {
            "openapi": "3.0.3",
            "info": {
                "title": getattr(settings, "PROJECT_NAME", "API"),
                "version": "1.0.0",
                "description": "API Documentation",
            },
            "paths": {},
        }

        for e in endpoints:
            path = e.get("path", "/")
            # Convert Django URL params to OpenAPI format
            openapi_path = re.sub(r"<(\w+:)?(\w+)>", r"{\2}", path)
            openapi_path = re.sub(r"\{int:(\w+)\}", r"{\1}", openapi_path)

            if openapi_path not in openapi_spec["paths"]:
                openapi_spec["paths"][openapi_path] = {}

            for method in e.get("methods", ["GET"]):
                method_lower = method.lower()
                openapi_spec["paths"][openapi_path][method_lower] = {
                    "summary": e.get("description") or e.get("name", ""),
                    "operationId": f"{e.get('name', 'operation')}_{method_lower}",
                    "tags": [e.get("app", "default")],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                        }
                    },
                }

                # Add security if permissions are specified
                if e.get("permissions"):
                    openapi_spec["paths"][openapi_path][method_lower]["security"] = [
                        {"bearerAuth": []}
                    ]

        # Add security scheme
        if any(e.get("permissions") for e in endpoints):
            openapi_spec["components"] = {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    }
                }
            }

        self.stdout.write(json.dumps(openapi_spec, indent=2))
