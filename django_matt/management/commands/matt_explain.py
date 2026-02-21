"""
Django Matt view explanation command.

Explains the request flow and configuration for a specific view or endpoint.

Usage:
    python manage.py matt_explain myapp.views.UserView
    python manage.py matt_explain /api/users/
    python manage.py matt_explain UserController
    python manage.py matt_explain --json myapp.views.UserView
"""

import ast
import inspect
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver

import orjson

from django_matt.cli import MattCommand


class Command(MattCommand):
    """Explain view chain: middleware, permissions, throttling, authentication."""

    help = "Explain the request flow for a view, including middleware and permissions"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "target",
            help="View to explain (path like /api/users/, module.path.ViewClass, or view name)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed source code analysis",
        )

    def handle(self, *args, **options):
        target = options.get("target")
        output_json = options.get("json", False)
        verbose = options.get("verbose", False)

        # Try to resolve the target
        view_info = self._resolve_target(target)

        if not view_info:
            self.error(f"Could not find view: {target}")
            return

        # Gather explanation data
        explanation = {
            "target": target,
            "view": view_info,
            "middleware_stack": self._get_middleware_stack(),
            "request_flow": self._trace_request_flow(view_info),
            "permissions": self._get_permissions(view_info),
            "authentication": self._get_authentication(view_info),
            "throttling": self._get_throttling(view_info),
            "caching": self._get_caching(view_info),
            "source_analysis": self._analyze_source(view_info) if verbose else None,
        }

        # Output
        if output_json:
            self.stdout.write(orjson.dumps(explanation, default=str, option=orjson.OPT_INDENT_2).decode())
        else:
            self._display_explanation(explanation, verbose)

    def _resolve_target(self, target: str) -> dict[str, Any] | None:
        """Resolve the target to a view."""
        # Try as URL path first
        if target.startswith("/"):
            return self._resolve_url_path(target)

        # Try as module path
        if "." in target:
            return self._resolve_module_path(target)

        # Try as view name
        return self._resolve_view_name(target)

    def _resolve_url_path(self, path: str) -> dict[str, Any] | None:
        """Resolve a URL path to a view."""
        try:
            from django.urls import resolve

            match = resolve(path)
            callback = match.func

            # Get view class if available
            view_class = getattr(callback, "view_class", None)
            view_name = (
                view_class.__name__ if view_class else getattr(callback, "__name__", str(callback))
            )
            view_module = (
                view_class.__module__ if view_class else getattr(callback, "__module__", "")
            )

            return {
                "path": path,
                "name": match.url_name or view_name,
                "view_name": view_name,
                "view_module": view_module,
                "view_class": view_class,
                "callback": callback,
                "kwargs": match.kwargs,
                "route": match.route,
            }
        except Exception:
            return None

    def _resolve_module_path(self, module_path: str) -> dict[str, Any] | None:
        """Resolve a module path to a view."""
        try:
            parts = module_path.rsplit(".", 1)
            if len(parts) != 2:
                return None

            module_name, class_name = parts
            module = __import__(module_name, fromlist=[class_name])
            view_class = getattr(module, class_name)

            # Find URL path for this view
            url_path = self._find_url_for_view(view_class)

            return {
                "path": url_path,
                "name": class_name,
                "view_name": class_name,
                "view_module": module_name,
                "view_class": view_class,
                "callback": None,
            }
        except Exception:
            return None

    def _resolve_view_name(self, name: str) -> dict[str, Any] | None:
        """Resolve a view by name search."""
        # Search all apps for matching view
        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue

            app_path = Path(app_config.path)

            for pattern in ["views.py", "views/*.py", "controllers.py", "controllers/*.py"]:
                for file_path in app_path.glob(pattern):
                    try:
                        content = file_path.read_text()
                        if f"class {name}" in content:
                            # Found it - parse the file
                            module_name = str(file_path).replace("/", ".").replace(".py", "")
                            module_name = module_name.split("site-packages/")[-1]

                            # Try to import
                            try:
                                module = __import__(module_name, fromlist=[name])
                                view_class = getattr(module, name, None)
                                if view_class:
                                    url_path = self._find_url_for_view(view_class)
                                    return {
                                        "path": url_path,
                                        "name": name,
                                        "view_name": name,
                                        "view_module": module_name,
                                        "view_class": view_class,
                                        "callback": None,
                                        "file": str(file_path),
                                    }
                            except Exception:
                                pass
                    except Exception:
                        pass

        return None

    def _find_url_for_view(self, view_class) -> str | None:
        """Find the URL path for a view class."""

        def search_patterns(patterns, prefix=""):
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    result = search_patterns(pattern.url_patterns, prefix + str(pattern.pattern))
                    if result:
                        return result
                elif isinstance(pattern, URLPattern):
                    callback = pattern.callback
                    callback_class = getattr(callback, "view_class", None)
                    if callback_class == view_class:
                        return "/" + (prefix + str(pattern.pattern)).strip("^$")
            return None

        resolver = get_resolver()
        return search_patterns(resolver.url_patterns)

    def _get_middleware_stack(self) -> list[dict[str, Any]]:
        """Get the middleware stack configuration."""
        middleware_info = []

        for middleware in settings.MIDDLEWARE:
            parts = middleware.rsplit(".", 1)
            name = parts[-1] if len(parts) > 1 else middleware
            module = parts[0] if len(parts) > 1 else ""

            # Categorize middleware
            category = "other"
            if "Auth" in name or "auth" in middleware.lower():
                category = "authentication"
            elif "Session" in name:
                category = "session"
            elif "CSRF" in name or "Csrf" in name:
                category = "security"
            elif "CORS" in name or "Cors" in name:
                category = "cors"
            elif "Cache" in name or "cache" in middleware.lower():
                category = "caching"
            elif "Throttle" in name or "throttle" in middleware.lower():
                category = "throttling"
            elif "Benchmark" in name or "Timing" in name:
                category = "performance"
            elif "Tenant" in name or "tenant" in middleware.lower():
                category = "multitenancy"

            middleware_info.append(
                {
                    "name": name,
                    "module": module,
                    "full_path": middleware,
                    "category": category,
                }
            )

        return middleware_info

    def _trace_request_flow(self, view_info: dict[str, Any]) -> list[dict[str, Any]]:
        """Trace the request flow for a view."""
        flow = []

        # 1. WSGI/ASGI entry
        flow.append(
            {
                "step": 1,
                "stage": "Entry",
                "component": "WSGI/ASGI Handler",
                "description": "Request enters Django",
            }
        )

        # 2. Middleware (request phase)
        flow.append(
            {
                "step": 2,
                "stage": "Middleware (Request)",
                "component": "Middleware Stack",
                "description": f"{len(settings.MIDDLEWARE)} middleware process request",
            }
        )

        # 3. URL Resolution
        flow.append(
            {
                "step": 3,
                "stage": "URL Resolution",
                "component": "URL Router",
                "description": f"Resolves to {view_info.get('view_name', 'view')}",
            }
        )

        # 4. View dispatch
        view_class = view_info.get("view_class")
        if view_class:
            # Check for authentication
            auth_classes = getattr(view_class, "authentication_classes", [])
            if auth_classes:
                flow.append(
                    {
                        "step": 4,
                        "stage": "Authentication",
                        "component": ", ".join(c.__name__ for c in auth_classes),
                        "description": "Authenticate request",
                    }
                )

            # Check for permissions
            perm_classes = getattr(view_class, "permission_classes", [])
            if perm_classes:
                flow.append(
                    {
                        "step": len(flow) + 1,
                        "stage": "Authorization",
                        "component": ", ".join(
                            c.__name__ if isinstance(c, type) else c.__class__.__name__
                            for c in perm_classes
                        ),
                        "description": "Check permissions",
                    }
                )

            # Check for throttling
            throttle_classes = getattr(view_class, "throttle_classes", [])
            if throttle_classes:
                flow.append(
                    {
                        "step": len(flow) + 1,
                        "stage": "Throttling",
                        "component": ", ".join(c.__name__ for c in throttle_classes),
                        "description": "Apply rate limits",
                    }
                )

        # View execution
        flow.append(
            {
                "step": len(flow) + 1,
                "stage": "View Execution",
                "component": view_info.get("view_name", "View"),
                "description": "Process request and generate response",
            }
        )

        # Middleware (response phase)
        flow.append(
            {
                "step": len(flow) + 1,
                "stage": "Middleware (Response)",
                "component": "Middleware Stack",
                "description": "Middleware process response (reverse order)",
            }
        )

        # Response
        flow.append(
            {
                "step": len(flow) + 1,
                "stage": "Response",
                "component": "WSGI/ASGI Handler",
                "description": "Send response to client",
            }
        )

        return flow

    def _get_permissions(self, view_info: dict[str, Any]) -> list[dict[str, Any]]:
        """Get permission information for a view."""
        permissions = []
        view_class = view_info.get("view_class")

        if view_class:
            # Class-level permissions
            perm_classes = getattr(view_class, "permission_classes", [])
            for perm in perm_classes:
                perm_class = perm if isinstance(perm, type) else perm.__class__
                permissions.append(
                    {
                        "name": perm_class.__name__,
                        "module": perm_class.__module__,
                        "docstring": perm_class.__doc__[:100] if perm_class.__doc__ else "",
                        "level": "class",
                    }
                )

            # Check for method-level permissions (decorators)
            for method_name in (
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "list",
                "create",
                "retrieve",
                "update",
                "destroy",
            ):
                method = getattr(view_class, method_name, None)
                if method:
                    # Check for permission decorators
                    if hasattr(method, "_permission_classes"):
                        for perm in method._permission_classes:
                            perm_class = perm if isinstance(perm, type) else perm.__class__
                            permissions.append(
                                {
                                    "name": perm_class.__name__,
                                    "module": perm_class.__module__,
                                    "level": "method",
                                    "method": method_name,
                                }
                            )

        return permissions

    def _get_authentication(self, view_info: dict[str, Any]) -> list[dict[str, Any]]:
        """Get authentication configuration for a view."""
        auth = []
        view_class = view_info.get("view_class")

        if view_class:
            auth_classes = getattr(view_class, "authentication_classes", [])
            for auth_class in auth_classes:
                auth.append(
                    {
                        "name": auth_class.__name__,
                        "module": auth_class.__module__,
                        "docstring": auth_class.__doc__[:100] if auth_class.__doc__ else "",
                    }
                )

        # Check for JWT decorators
        callback = view_info.get("callback")
        if callback:
            if hasattr(callback, "_jwt_required"):
                auth.append(
                    {
                        "name": "JWT Required",
                        "module": "django_matt.auth.jwt",
                        "docstring": "Requires valid JWT token",
                    }
                )
            if hasattr(callback, "_jwt_optional"):
                auth.append(
                    {
                        "name": "JWT Optional",
                        "module": "django_matt.auth.jwt",
                        "docstring": "JWT token optional",
                    }
                )

        return auth

    def _get_throttling(self, view_info: dict[str, Any]) -> list[dict[str, Any]]:
        """Get throttling configuration for a view."""
        throttles = []
        view_class = view_info.get("view_class")

        if view_class:
            throttle_classes = getattr(view_class, "throttle_classes", [])
            for throttle in throttle_classes:
                throttle_info = {
                    "name": throttle.__name__,
                    "module": throttle.__module__,
                }

                # Try to get rate info
                if hasattr(throttle, "rate"):
                    throttle_info["rate"] = throttle.rate
                elif hasattr(throttle, "THROTTLE_RATES"):
                    throttle_info["rates"] = throttle.THROTTLE_RATES

                throttles.append(throttle_info)

        return throttles

    def _get_caching(self, view_info: dict[str, Any]) -> dict[str, Any]:
        """Get caching configuration for a view."""
        caching = {
            "enabled": False,
            "decorators": [],
            "settings": {},
        }

        view_class = view_info.get("view_class")
        callback = view_info.get("callback")

        # Check for caching decorators
        for obj in (view_class, callback):
            if obj and hasattr(obj, "_cache_response"):
                caching["enabled"] = True
                caching["decorators"].append("cache_response")

            if obj and hasattr(obj, "_cache_timeout"):
                caching["enabled"] = True
                caching["settings"]["timeout"] = obj._cache_timeout

        # Check global cache settings
        caching["settings"]["default_timeout"] = getattr(settings, "DJANGO_MATT_CACHE_TIMEOUT", 300)

        return caching

    def _analyze_source(self, view_info: dict[str, Any]) -> dict[str, Any] | None:
        """Analyze the source code of a view."""
        view_class = view_info.get("view_class")
        if not view_class:
            return None

        analysis = {
            "methods": [],
            "decorators": [],
            "imports": [],
            "docstring": view_class.__doc__ or "",
        }

        try:
            source = inspect.getsource(view_class)
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    method_info = {
                        "name": node.name,
                        "async": False,
                        "decorators": [
                            getattr(d, "id", getattr(d, "attr", str(d)))
                            for d in node.decorator_list
                        ],
                        "docstring": ast.get_docstring(node) or "",
                    }
                    analysis["methods"].append(method_info)
                elif isinstance(node, ast.AsyncFunctionDef):
                    method_info = {
                        "name": node.name,
                        "async": True,
                        "decorators": [
                            getattr(d, "id", getattr(d, "attr", str(d)))
                            for d in node.decorator_list
                        ],
                        "docstring": ast.get_docstring(node) or "",
                    }
                    analysis["methods"].append(method_info)

            analysis["source_file"] = inspect.getfile(view_class)
            analysis["source_lines"] = len(source.splitlines())

        except Exception:
            pass

        return analysis

    def _display_explanation(self, explanation: dict[str, Any], verbose: bool):
        """Display the explanation in a formatted way."""
        self.console.banner()
        view_info = explanation["view"]
        self.header(
            f"View Explanation: {view_info.get('view_name', 'Unknown')}",
            view_info.get("path", ""),
        )

        # View Info
        self.section("View Information")
        info_data = [
            {"Property": "Name", "Value": view_info.get("view_name", "N/A")},
            {"Property": "Module", "Value": view_info.get("view_module", "N/A")},
            {"Property": "URL Path", "Value": view_info.get("path", "N/A")},
            {"Property": "URL Name", "Value": view_info.get("route", "N/A")},
        ]
        self.table(info_data)

        # Request Flow
        self.section("Request Flow")
        flow = explanation["request_flow"]
        for step in flow:
            stage = step["stage"]
            component = step["component"]
            desc = step["description"]
            self.console.print(f"  [cyan]{step['step']}.[/] [bold]{stage}[/] -> {component}")
            self.console.print(f"     [dim]{desc}[/]")

        # Middleware Stack
        self.section("Middleware Stack")
        middleware = explanation["middleware_stack"]
        for i, mw in enumerate(middleware, 1):
            category = mw.get("category", "other")
            color = {
                "authentication": "green",
                "security": "yellow",
                "caching": "blue",
                "performance": "cyan",
                "session": "magenta",
            }.get(category, "white")
            self.console.print(f"  {i}. [{color}]{mw['name']}[/] [dim]({category})[/]")

        # Authentication
        auth = explanation["authentication"]
        if auth:
            self.section("Authentication")
            for a in auth:
                self.console.print(f"  [green]{a['name']}[/]")
                if a.get("docstring"):
                    self.console.print(f"    [dim]{a['docstring']}[/]")

        # Permissions
        perms = explanation["permissions"]
        if perms:
            self.section("Permissions")
            for p in perms:
                level = f" [dim]({p['level']})[/]" if p.get("level") else ""
                self.console.print(f"  [yellow]{p['name']}{level}[/]")
                if p.get("docstring"):
                    self.console.print(f"    [dim]{p['docstring']}[/]")

        # Throttling
        throttles = explanation["throttling"]
        if throttles:
            self.section("Throttling / Rate Limits")
            for t in throttles:
                rate = t.get("rate", t.get("rates", "N/A"))
                self.console.print(f"  [red]{t['name']}[/]: {rate}")

        # Caching
        caching = explanation["caching"]
        if caching.get("enabled") or caching.get("decorators"):
            self.section("Caching")
            cache_data = [
                {"Setting": "Enabled", "Value": "Yes" if caching.get("enabled") else "No"},
                {
                    "Setting": "Default Timeout",
                    "Value": f"{caching['settings'].get('default_timeout', 300)}s",
                },
            ]
            if caching.get("decorators"):
                cache_data.append(
                    {"Setting": "Decorators", "Value": ", ".join(caching["decorators"])}
                )
            self.table(cache_data)

        # Source Analysis (verbose mode)
        if verbose and explanation.get("source_analysis"):
            analysis = explanation["source_analysis"]
            self.section("Source Analysis")

            if analysis.get("source_file"):
                self.console.print(f"  [dim]File: {analysis['source_file']}[/]")
                self.console.print(f"  [dim]Lines: {analysis.get('source_lines', 'N/A')}[/]")

            if analysis.get("methods"):
                self.console.print("\n  [bold]Methods:[/]")
                for method in analysis["methods"]:
                    async_tag = "[cyan]async[/] " if method.get("async") else ""
                    decorators = (
                        f" [dim](@{', @'.join(method['decorators'])})[/]"
                        if method.get("decorators")
                        else ""
                    )
                    self.console.print(f"    {async_tag}{method['name']}{decorators}")

        self.console.newline()
