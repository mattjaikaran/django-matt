"""
Django Matt CLI - Main entry point.

Usage:
    python manage.py matt info              # Show project info
    python manage.py matt doctor            # Check project health
    python manage.py matt routes            # List all API routes
    python manage.py matt models            # List all models
    python manage.py matt version           # Show version
    python manage.py matt new controller    # Scaffold a new controller
    python manage.py matt new schema        # Scaffold a new schema
    python manage.py matt new service       # Scaffold a new service
    python manage.py matt new test          # Scaffold a new test file
"""

import sys
from importlib import import_module
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver

from django_matt.cli import GeneratorCommand
from django_matt.cli.templates import (
    generate_controller_template,
    generate_schema_template,
    generate_service_template,
    generate_test_template,
)


class Command(GeneratorCommand):
    """Django Matt CLI - Project utilities and information."""

    help = "Django Matt CLI utilities (info, doctor, routes, models, version, new)"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

        # info
        info_parser = subparsers.add_parser("info", help="Show project information")
        info_parser.add_argument("--json", action="store_true", help="Output as JSON")

        # doctor
        doctor_parser = subparsers.add_parser("doctor", help="Check project health")
        doctor_parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")

        # routes
        routes_parser = subparsers.add_parser("routes", help="List all API routes")
        routes_parser.add_argument("--filter", "-f", help="Filter routes by pattern")
        routes_parser.add_argument("--method", "-m", help="Filter by HTTP method")

        # models
        models_parser = subparsers.add_parser("models", help="List all models")
        models_parser.add_argument("--app", "-a", help="Filter by app name")
        models_parser.add_argument("--fields", action="store_true", help="Show model fields")

        # version
        subparsers.add_parser("version", help="Show django-matt version")

        # new (scaffolding)
        new_parser = subparsers.add_parser("new", help="Scaffold new components")
        new_subparsers = new_parser.add_subparsers(
            dest="component", help="Component type to create"
        )

        # new controller
        ctrl_parser = new_subparsers.add_parser("controller", help="Create a new controller")
        ctrl_parser.add_argument("name", help="Controller name (e.g., User, Product)")
        ctrl_parser.add_argument("--app", "-a", help="Target app (default: current directory)")
        ctrl_parser.add_argument("--crud", action="store_true", help="Generate full CRUD endpoints")

        # new schema
        schema_parser = new_subparsers.add_parser("schema", help="Create a new schema")
        schema_parser.add_argument("name", help="Schema name (e.g., User, Product)")
        schema_parser.add_argument("--app", "-a", help="Target app (default: current directory)")

        # new service
        svc_parser = new_subparsers.add_parser("service", help="Create a new service")
        svc_parser.add_argument("name", help="Service name (e.g., User, Product)")
        svc_parser.add_argument("--app", "-a", help="Target app (default: current directory)")

        # new test
        test_parser = new_subparsers.add_parser("test", help="Create a new test file")
        test_parser.add_argument("name", help="Test name (e.g., User, Product)")
        test_parser.add_argument("--app", "-a", help="Target app (default: current directory)")
        test_parser.add_argument(
            "--type",
            "-t",
            choices=["controller", "service", "unit"],
            default="controller",
            help="Type of test to generate",
        )

    # Available subcommands for "did you mean" suggestions
    SUBCOMMANDS = ["info", "doctor", "routes", "models", "version", "new"]

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")

        if not subcommand:
            self.show_help()
            return

        handler = getattr(self, f"handle_{subcommand}", None)
        if handler:
            handler(options)
        else:
            # Try to suggest a similar command
            suggestion = self._suggest_command(subcommand)
            if suggestion:
                self.console.did_you_mean(subcommand, suggestion)
            else:
                self.error(f"Unknown subcommand: {subcommand}")

    def _suggest_command(self, input_cmd: str) -> str | None:
        """Suggest a similar command for typos."""
        best_match = None
        best_score = 0

        for cmd in self.SUBCOMMANDS:
            score = self._similarity(input_cmd.lower(), cmd.lower())
            if score > best_score and score > 0.5:
                best_score = score
                best_match = cmd

        return best_match

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0

        # Count matching characters in order
        matches = sum(1 for a, b in zip(s1, s2, strict=False) if a == b)
        max_len = max(len(s1), len(s2))

        return matches / max_len if max_len > 0 else 0.0

    def show_help(self):
        """Show main help with banner and grouped commands."""
        self.console.banner()
        self.console.print("[bold]Usage:[/] python manage.py matt <command>")
        self.console.newline()

        # Group commands by category
        self.console.command_group(
            "Project Commands",
            [
                ("info", "Show project information and statistics"),
                ("doctor", "Check project health and configuration"),
                ("version", "Show django-matt version"),
            ],
        )

        self.console.command_group(
            "Development Commands",
            [
                ("routes", "List all API routes"),
                ("models", "List all Django models"),
            ],
        )

        self.console.command_group(
            "Scaffolding Commands",
            [
                ("new controller", "Generate a new API controller"),
                ("new schema", "Generate Pydantic schemas"),
                ("new service", "Generate a service layer"),
                ("new test", "Generate test files"),
            ],
        )

        self.console.newline()
        self.console.muted("Run 'python manage.py matt <command> --help' for more info")

    # =========================================================================
    # Subcommand Handlers
    # =========================================================================

    def handle_info(self, options):
        """Show project information."""
        self.console.header("Project Information")

        # Gather info
        info = self._gather_project_info()

        if options.get("json"):
            import orjson

            self.console.print(orjson.dumps(info, option=orjson.OPT_INDENT_2).decode())
            return

        # Display info sections
        self.console.section("Environment")
        env_data = [
            {"Key": "Python", "Value": info["python_version"]},
            {"Key": "Django", "Value": info["django_version"]},
            {"Key": "django-matt", "Value": info["matt_version"]},
            {"Key": "Debug Mode", "Value": "Yes" if info["debug"] else "No"},
        ]
        self.console.table(env_data)

        self.console.section("Project Stats")
        stats_data = [
            {"Metric": "Installed Apps", "Count": str(info["app_count"])},
            {"Metric": "Models", "Count": str(info["model_count"])},
            {"Metric": "URL Patterns", "Count": str(info["url_count"])},
            {"Metric": "Middleware", "Count": str(info["middleware_count"])},
        ]
        self.console.table(stats_data)

        self.console.section("Database")
        for alias, db_info in info["databases"].items():
            self.console.print(f"  [cyan]{alias}:[/] {db_info['engine']} - {db_info['name']}")

    def handle_doctor(self, options):
        """Check project health."""
        self.console.header("Project Health Check")

        checks = []
        all_passed = True

        # Check 1: Django settings
        check = self._check_settings()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Check 2: Database connection
        check = self._check_database()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Check 3: Installed apps
        check = self._check_installed_apps()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Check 4: Security settings (in production)
        if not settings.DEBUG:
            check = self._check_security()
            checks.append(check)
            if not check["passed"]:
                all_passed = False

        # Check 5: Required dependencies
        check = self._check_dependencies()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Display results
        self.console.newline()
        for check in checks:
            if check["passed"]:
                self.console.success(check["name"])
            elif check["warning"]:
                self.console.warning(f"{check['name']}: {check['message']}")
            else:
                self.console.error(f"{check['name']}: {check['message']}")

        self.console.newline()
        if all_passed:
            self.console.box_success("All checks passed! Your project is healthy.")
        else:
            self.console.box_warning(
                "Some checks failed. Review the warnings above.",
                title="Health Check Complete",
            )

    def handle_routes(self, options):
        """List all API routes."""
        self.console.header("API Routes")

        routes = self._collect_routes()
        filter_pattern = options.get("filter")
        filter_method = options.get("method")

        # Apply filters
        if filter_pattern:
            routes = [r for r in routes if filter_pattern.lower() in r["path"].lower()]
        if filter_method:
            routes = [r for r in routes if filter_method.upper() in r["methods"]]

        if not routes:
            self.console.warning("No routes found")
            return

        # Group by app/prefix
        self.console.table(
            routes,
            columns=["Methods", "Path", "Name", "View"],
            title=f"Found {len(routes)} routes",
        )

    def handle_models(self, options):
        """List all models."""
        self.console.header("Django Models")

        app_filter = options.get("app")
        show_fields = options.get("fields", False)

        models_by_app = {}
        for model in apps.get_models():
            app_label = model._meta.app_label

            # Skip Django internal apps unless specifically requested
            if app_label in ("contenttypes", "sessions", "admin", "auth") and not app_filter:
                continue

            if app_filter and app_label != app_filter:
                continue

            if app_label not in models_by_app:
                models_by_app[app_label] = []

            model_info = {
                "name": model.__name__,
                "table": model._meta.db_table,
                "fields": [f.name for f in model._meta.fields],
            }
            models_by_app[app_label].append(model_info)

        if not models_by_app:
            self.console.warning("No models found")
            return

        for app_label, models in sorted(models_by_app.items()):
            self.console.section(f"{app_label}")

            if show_fields:
                # Show as tree with fields
                tree_data = {}
                for model in models:
                    tree_data[model["name"]] = dict.fromkeys(model["fields"])
                self.console.tree(tree_data, title=app_label)
            else:
                # Show as simple table
                table_data = [
                    {"Model": m["name"], "Table": m["table"], "Fields": len(m["fields"])}
                    for m in models
                ]
                self.console.table(table_data)

        total = sum(len(models) for models in models_by_app.values())
        self.console.newline()
        self.console.muted(f"Total: {total} models in {len(models_by_app)} apps")

    def handle_version(self, options):
        """Show version info."""
        try:
            from django_matt import __version__

            version = __version__
        except (ImportError, AttributeError):
            version = "0.1.0"

        self.console.banner()
        self.console.version_info(version)

    def handle_new(self, options):
        """Handle scaffolding new components."""
        component = options.get("component")

        if not component:
            self._show_new_help()
            return

        name = options.get("name")
        app = options.get("app")

        # Determine output directory
        if app:
            try:
                app_config = apps.get_app_config(app)
                output_dir = Path(app_config.path)
            except LookupError:
                self.error(f"App '{app}' not found", raise_error=True)
                return
        else:
            output_dir = Path.cwd()

        self.header(f"Create New {component.title()}", f"Name: {name}")

        # Generate component
        handler = getattr(self, f"_scaffold_{component}", None)
        if handler:
            handler(name, output_dir, options)
            self.show_summary()
        else:
            self.error(f"Unknown component type: {component}")

    def _show_new_help(self):
        """Show help for the new command."""
        self.console.header("Scaffold New Components")
        self.console.print("[bold]Usage:[/] python manage.py matt new <component> <name>")
        self.console.newline()

        components = [
            {"Component": "controller", "Description": "API controller with endpoints"},
            {"Component": "schema", "Description": "Pydantic schema for request/response"},
            {"Component": "service", "Description": "Service layer for business logic"},
            {"Component": "test", "Description": "Test file for testing components"},
        ]

        self.console.table(components, title="Available Components")
        self.console.newline()
        self.console.muted("Example: python manage.py matt new controller User --app myapp")

    def _scaffold_controller(self, name: str, output_dir: Path, options: dict):
        """Scaffold a new controller."""
        crud = options.get("crud", False)

        content = generate_controller_template(name, crud)
        filename = f"{name.lower()}_controller.py"

        self.write_file(output_dir / filename, content)

        self.next_steps(
            [
                "Register controller in your API:",
                f"  from .{name.lower()}_controller import {name}Controller",
                f"  api.register_controller({name}Controller)",
            ]
        )

    def _scaffold_schema(self, name: str, output_dir: Path, options: dict):
        """Scaffold a new schema."""
        content = generate_schema_template(name)
        filename = f"{name.lower()}_schemas.py"

        self.write_file(output_dir / filename, content)

        self.next_steps(
            [
                "Import schemas in your controller:",
                f"  from .{name.lower()}_schemas import {name}Schema, {name}CreateSchema",
            ]
        )

    def _scaffold_service(self, name: str, output_dir: Path, options: dict):
        """Scaffold a new service."""
        content = generate_service_template(name)
        filename = f"{name.lower()}_service.py"

        self.write_file(output_dir / filename, content)

        self.next_steps(
            [
                "Use the service in your controller:",
                f"  from .{name.lower()}_service import {name}Service",
                f"  self.service = {name}Service()",
            ]
        )

    def _scaffold_test(self, name: str, output_dir: Path, options: dict):
        """Scaffold a new test file."""
        test_type = options.get("type", "controller")
        content = generate_test_template(name, test_type)
        filename = f"test_{name.lower()}.py"

        # Put tests in tests directory if it exists
        tests_dir = output_dir / "tests"
        if tests_dir.exists():
            output_dir = tests_dir

        self.write_file(output_dir / filename, content)

        self.next_steps(
            [
                "Run tests with:",
                f"  pytest {output_dir / filename}",
            ]
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _gather_project_info(self) -> dict:
        """Gather project information."""
        import django

        try:
            from django_matt import __version__ as matt_version
        except (ImportError, AttributeError):
            matt_version = "0.1.0"

        # Count models
        model_count = len(list(apps.get_models()))

        # Count URLs
        url_count = len(self._collect_routes())

        # Database info
        databases = {}
        for alias in settings.DATABASES:
            db = settings.DATABASES[alias]
            databases[alias] = {
                "engine": db.get("ENGINE", "").split(".")[-1],
                "name": db.get("NAME", ""),
            }

        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "django_version": django.get_version(),
            "matt_version": matt_version,
            "debug": settings.DEBUG,
            "app_count": len(settings.INSTALLED_APPS),
            "model_count": model_count,
            "url_count": url_count,
            "middleware_count": len(settings.MIDDLEWARE),
            "databases": databases,
        }

    def _collect_routes(self, resolver=None, prefix="") -> list[dict]:
        """Recursively collect all URL routes."""
        if resolver is None:
            resolver = get_resolver()

        routes = []

        for pattern in resolver.url_patterns:
            path = prefix + str(pattern.pattern)

            if isinstance(pattern, URLResolver):
                # Recurse into included URLs
                routes.extend(self._collect_routes(pattern, path))
            elif isinstance(pattern, URLPattern):
                # Get view info
                callback = pattern.callback
                view_name = ""

                if hasattr(callback, "__name__"):
                    view_name = callback.__name__
                elif hasattr(callback, "__class__"):
                    view_name = callback.__class__.__name__

                # Try to get HTTP methods
                methods = "GET"
                if hasattr(callback, "actions"):
                    methods = ", ".join(callback.actions.keys()).upper()
                elif hasattr(callback, "http_method_names"):
                    methods = ", ".join(
                        m.upper() for m in callback.http_method_names if m != "options"
                    )

                routes.append(
                    {
                        "path": "/" + path.lstrip("^").rstrip("$"),
                        "name": pattern.name or "",
                        "view": view_name,
                        "Methods": methods,
                        "Path": "/" + path.lstrip("^").rstrip("$"),
                        "Name": pattern.name or "-",
                        "View": view_name or "-",
                    }
                )

        return routes

    def _check_settings(self) -> dict:
        """Check Django settings."""
        try:
            # Just accessing settings should work
            _ = settings.DEBUG
            return {"name": "Django settings", "passed": True, "warning": False, "message": ""}
        except Exception as e:
            return {
                "name": "Django settings",
                "passed": False,
                "warning": False,
                "message": str(e),
            }

    def _check_database(self) -> dict:
        """Check database connection."""
        from django.db import connection

        try:
            connection.ensure_connection()
            return {"name": "Database connection", "passed": True, "warning": False, "message": ""}
        except Exception as e:
            return {
                "name": "Database connection",
                "passed": False,
                "warning": True,
                "message": str(e),
            }

    def _check_installed_apps(self) -> dict:
        """Check that required apps are installed."""
        required = ["django.contrib.contenttypes"]
        missing = [app for app in required if app not in settings.INSTALLED_APPS]

        if missing:
            return {
                "name": "Required apps",
                "passed": False,
                "warning": True,
                "message": f"Missing: {', '.join(missing)}",
            }

        return {"name": "Required apps", "passed": True, "warning": False, "message": ""}

    def _check_security(self) -> dict:
        """Check security settings for production."""
        issues = []

        if not getattr(settings, "SECRET_KEY", None):
            issues.append("SECRET_KEY not set")
        if getattr(settings, "SECRET_KEY", "").startswith("django-insecure"):
            issues.append("Using insecure SECRET_KEY")
        if not getattr(settings, "ALLOWED_HOSTS", []):
            issues.append("ALLOWED_HOSTS is empty")

        if issues:
            return {
                "name": "Security settings",
                "passed": False,
                "warning": True,
                "message": "; ".join(issues),
            }

        return {"name": "Security settings", "passed": True, "warning": False, "message": ""}

    def _check_dependencies(self) -> dict:
        """Check required dependencies are installed."""
        required = ["django", "pydantic", "rich"]
        missing = []

        for pkg in required:
            try:
                import_module(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            return {
                "name": "Dependencies",
                "passed": False,
                "warning": False,
                "message": f"Missing: {', '.join(missing)}",
            }

        return {"name": "Dependencies", "passed": True, "warning": False, "message": ""}
