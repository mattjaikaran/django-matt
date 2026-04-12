"""
Django Matt codebase analysis command.

Analyzes the project structure and provides insights about:
- Model counts and relationships
- Views, schemas, and permissions
- Missing tests
- Unused schemas
- N+1 query patterns

Usage:
    python manage.py matt_analyze                    # Full analysis
    python manage.py matt_analyze --section models   # Analyze only models
    python manage.py matt_analyze --json             # Output as JSON
    python manage.py matt_analyze --verbose          # Include detailed info
"""

import ast
import re
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db.models import ForeignKey

import orjson

from django_matt.cli import MattCommand


class Command(MattCommand):
    """Analyze codebase structure and detect potential issues."""

    help = "Analyze codebase: models, views, schemas, permissions, and detect issues"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--section",
            "-s",
            choices=["models", "views", "schemas", "permissions", "tests", "queries", "all"],
            default="all",
            help="Section to analyze (default: all)",
        )
        parser.add_argument(
            "--app",
            "-a",
            help="Limit analysis to specific app",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information",
        )

    def handle(self, *args, **options):
        output_json = options.get("json", False)
        section = options.get("section", "all")
        app_filter = options.get("app")
        verbose = options.get("verbose", False)

        # Gather analysis data
        analysis = {}

        if section in ("all", "models"):
            analysis["models"] = self._analyze_models(app_filter)

        if section in ("all", "views"):
            analysis["views"] = self._analyze_views(app_filter)

        if section in ("all", "schemas"):
            analysis["schemas"] = self._analyze_schemas(app_filter)

        if section in ("all", "permissions"):
            analysis["permissions"] = self._analyze_permissions(app_filter)

        if section in ("all", "tests"):
            analysis["tests"] = self._analyze_tests(app_filter)

        if section in ("all", "queries"):
            analysis["queries"] = self._analyze_query_patterns(app_filter)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        # Output results
        if output_json:
            self.stdout.write(orjson.dumps(analysis, default=str, option=orjson.OPT_INDENT_2).decode())
        else:
            self._display_analysis(analysis, verbose)

    def _analyze_models(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze Django models."""
        models_data = {
            "total": 0,
            "by_app": {},
            "relationships": [],
            "issues": [],
        }

        for model in apps.get_models():
            app_label = model._meta.app_label

            # Skip Django internal apps
            if app_label.startswith("django.") or app_label in (
                "contenttypes",
                "sessions",
                "admin",
                "auth",
            ):
                continue

            if app_filter and app_label != app_filter:
                continue

            if app_label not in models_data["by_app"]:
                models_data["by_app"][app_label] = []

            meta = model._meta
            model_info = {
                "name": model.__name__,
                "table": meta.db_table,
                "fields": len(meta.fields),
                "foreign_keys": [],
                "many_to_many": [],
                "has_created_at": False,
                "has_updated_at": False,
                "has_str_method": hasattr(model, "__str__") and model.__str__ is not object.__str__,
            }

            # Analyze fields
            for field in meta.fields:
                if isinstance(field, ForeignKey):
                    model_info["foreign_keys"].append(
                        {
                            "name": field.name,
                            "to": field.related_model.__name__,
                        }
                    )
                    models_data["relationships"].append(
                        {
                            "from": model.__name__,
                            "to": field.related_model.__name__,
                            "type": "ForeignKey",
                            "field": field.name,
                        }
                    )
                if field.name in ("created_at", "created", "date_created"):
                    model_info["has_created_at"] = True
                if field.name in ("updated_at", "modified", "date_modified"):
                    model_info["has_updated_at"] = True

            # M2M fields
            for field in meta.many_to_many:
                model_info["many_to_many"].append(
                    {
                        "name": field.name,
                        "to": field.related_model.__name__,
                    }
                )
                models_data["relationships"].append(
                    {
                        "from": model.__name__,
                        "to": field.related_model.__name__,
                        "type": "ManyToMany",
                        "field": field.name,
                    }
                )

            # Check for issues
            if not model_info["has_str_method"]:
                models_data["issues"].append(
                    {
                        "model": f"{app_label}.{model.__name__}",
                        "issue": "Missing __str__ method",
                        "severity": "low",
                    }
                )

            models_data["by_app"][app_label].append(model_info)
            models_data["total"] += 1

        return models_data

    def _analyze_views(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze views and controllers."""
        views_data = {
            "total": 0,
            "controllers": [],
            "function_views": [],
            "class_views": [],
            "by_app": {},
        }

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            app_views = {"controllers": [], "views": []}

            # Look for controllers.py or controllers/ directory
            for pattern in ["controllers.py", "controllers/*.py", "views.py", "views/*.py"]:
                for file_path in app_path.glob(pattern):
                    if file_path.name.startswith("_"):
                        continue

                    try:
                        content = file_path.read_text()
                        tree = ast.parse(content)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                # Check if it's a controller or view
                                bases = [
                                    getattr(base, "id", getattr(base, "attr", ""))
                                    for base in node.bases
                                ]

                                is_controller = any(
                                    "Controller" in b or "ViewSet" in b for b in bases
                                )
                                is_view = any("View" in b for b in bases)

                                if is_controller:
                                    methods = [
                                        n.name
                                        for n in ast.walk(node)
                                        if isinstance(n, ast.FunctionDef)
                                        and not n.name.startswith("_")
                                    ]
                                    views_data["controllers"].append(
                                        {
                                            "name": node.name,
                                            "app": app_config.label,
                                            "file": str(file_path.relative_to(base_dir)),
                                            "methods": methods,
                                        }
                                    )
                                    app_views["controllers"].append(node.name)
                                    views_data["total"] += 1
                                elif is_view:
                                    views_data["class_views"].append(
                                        {
                                            "name": node.name,
                                            "app": app_config.label,
                                            "file": str(file_path.relative_to(base_dir)),
                                        }
                                    )
                                    app_views["views"].append(node.name)
                                    views_data["total"] += 1

                            elif isinstance(node, ast.FunctionDef):
                                # Check for view decorators
                                decorators = [
                                    getattr(d, "id", getattr(d, "attr", ""))
                                    for d in node.decorator_list
                                ]
                                if any(
                                    d in ("get", "post", "put", "delete", "patch", "api_view")
                                    for d in decorators
                                ):
                                    views_data["function_views"].append(
                                        {
                                            "name": node.name,
                                            "app": app_config.label,
                                            "file": str(file_path.relative_to(base_dir)),
                                        }
                                    )
                                    views_data["total"] += 1

                    except Exception:
                        pass  # Skip files that can't be parsed

            if app_views["controllers"] or app_views["views"]:
                views_data["by_app"][app_config.label] = app_views

        return views_data

    def _analyze_schemas(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze Pydantic schemas."""
        schemas_data = {
            "total": 0,
            "schemas": [],
            "unused": [],
            "by_app": {},
        }

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            app_schemas = []

            # Look for schemas.py or schemas/ directory
            for pattern in ["schemas.py", "schemas/*.py"]:
                for file_path in app_path.glob(pattern):
                    if file_path.name.startswith("_"):
                        continue

                    try:
                        content = file_path.read_text()
                        tree = ast.parse(content)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                bases = [
                                    getattr(base, "id", getattr(base, "attr", ""))
                                    for base in node.bases
                                ]

                                is_schema = any(
                                    b in ("BaseModel", "Schema", "ModelSchema") for b in bases
                                )

                                if is_schema:
                                    # Count fields
                                    fields = []
                                    for item in node.body:
                                        if isinstance(item, ast.AnnAssign) and isinstance(
                                            item.target, ast.Name
                                        ):
                                            fields.append(item.target.id)

                                    schema_info = {
                                        "name": node.name,
                                        "app": app_config.label,
                                        "file": str(file_path.relative_to(base_dir)),
                                        "fields": fields,
                                        "field_count": len(fields),
                                    }
                                    schemas_data["schemas"].append(schema_info)
                                    app_schemas.append(node.name)
                                    schemas_data["total"] += 1

                    except Exception:
                        pass

            if app_schemas:
                schemas_data["by_app"][app_config.label] = app_schemas

        # Find potentially unused schemas
        all_schema_names = {s["name"] for s in schemas_data["schemas"]}
        used_schemas = set()

        # Search for schema usage in controllers/views
        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue

            app_path = Path(app_config.path)
            for py_file in app_path.glob("**/*.py"):
                if "schemas" in py_file.name:
                    continue
                try:
                    content = py_file.read_text()
                    for schema_name in all_schema_names:
                        if schema_name in content:
                            used_schemas.add(schema_name)
                except Exception:
                    pass

        schemas_data["unused"] = list(all_schema_names - used_schemas)

        return schemas_data

    def _analyze_permissions(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze permission classes and usage."""
        permissions_data = {
            "custom_permissions": [],
            "permission_usage": {},
            "unprotected_views": [],
        }

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        known_permissions = {
            "IsAuthenticated",
            "AllowAny",
            "IsAdmin",
            "IsAdminUser",
            "IsOwner",
            "HasRole",
            "DjangoModelPermissions",
        }

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            # Look for custom permissions
            for pattern in ["permissions.py", "permissions/*.py"]:
                for file_path in app_path.glob(pattern):
                    try:
                        content = file_path.read_text()
                        tree = ast.parse(content)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                bases = [
                                    getattr(base, "id", getattr(base, "attr", ""))
                                    for base in node.bases
                                ]
                                if any("Permission" in b for b in bases):
                                    permissions_data["custom_permissions"].append(
                                        {
                                            "name": node.name,
                                            "app": app_config.label,
                                            "file": str(file_path.relative_to(base_dir)),
                                        }
                                    )
                    except Exception:
                        pass

            # Analyze permission usage in controllers
            for pattern in ["controllers.py", "controllers/*.py", "views.py"]:
                for file_path in app_path.glob(pattern):
                    try:
                        content = file_path.read_text()

                        # Find permission_classes assignments
                        for match in re.finditer(
                            r"permission_classes\s*=\s*\[(.*?)\]", content, re.DOTALL
                        ):
                            perms = re.findall(r"\b(\w+)\b", match.group(1))
                            for perm in perms:
                                if perm not in permissions_data["permission_usage"]:
                                    permissions_data["permission_usage"][perm] = 0
                                permissions_data["permission_usage"][perm] += 1

                    except Exception:
                        pass

        return permissions_data

    def _analyze_tests(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze test coverage."""
        tests_data = {
            "total_test_files": 0,
            "total_test_classes": 0,
            "total_test_methods": 0,
            "by_app": {},
            "missing_tests": [],
        }

        models_with_tests = set()
        controllers_with_tests = set()

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            app_tests = {
                "files": 0,
                "classes": 0,
                "methods": 0,
            }

            # Look for test files
            for pattern in ["test*.py", "tests.py", "tests/*.py", "tests/**/test*.py"]:
                for file_path in app_path.glob(pattern):
                    if "__pycache__" in str(file_path):
                        continue

                    app_tests["files"] += 1
                    tests_data["total_test_files"] += 1

                    try:
                        content = file_path.read_text()
                        tree = ast.parse(content)

                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                if node.name.startswith("Test"):
                                    app_tests["classes"] += 1
                                    tests_data["total_test_classes"] += 1

                                    # Track what's being tested
                                    tested_name = node.name.replace("Test", "")
                                    models_with_tests.add(tested_name)
                                    controllers_with_tests.add(tested_name)
                                    controllers_with_tests.add(f"{tested_name}Controller")

                            elif isinstance(node, ast.FunctionDef):
                                if node.name.startswith("test_"):
                                    app_tests["methods"] += 1
                                    tests_data["total_test_methods"] += 1

                    except Exception:
                        pass

            if app_tests["files"] > 0:
                tests_data["by_app"][app_config.label] = app_tests

        # Find models/controllers without tests
        for model in apps.get_models():
            app_label = model._meta.app_label
            if app_label.startswith("django.") or app_label in (
                "contenttypes",
                "sessions",
                "admin",
                "auth",
            ):
                continue
            if app_filter and app_label != app_filter:
                continue

            if model.__name__ not in models_with_tests:
                tests_data["missing_tests"].append(
                    {
                        "type": "model",
                        "name": f"{app_label}.{model.__name__}",
                    }
                )

        return tests_data

    def _analyze_query_patterns(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze code for potential N+1 query patterns."""
        queries_data = {
            "potential_n_plus_1": [],
            "missing_select_related": [],
            "loop_queries": [],
        }

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            for py_file in app_path.glob("**/*.py"):
                if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()

                    # Pattern 1: Loop with FK access
                    # for item in queryset: item.fk_field.something
                    for_pattern = r"for\s+(\w+)\s+in\s+.*?:\s*\n(?:.*?\n)*?.*?\1\.(\w+)\."
                    for match in re.finditer(for_pattern, content):
                        queries_data["loop_queries"].append(
                            {
                                "file": str(py_file.relative_to(base_dir)),
                                "pattern": f"Loop variable '{match.group(1)}' accessing '{match.group(2)}'",
                                "suggestion": f"Consider using select_related('{match.group(2)}')",
                            }
                        )

                    # Pattern 2: .all() without select_related followed by FK access
                    all_pattern = r"\.all\(\)(?!.*select_related)"
                    if re.search(all_pattern, content):
                        # Check if there's FK access later
                        if re.search(r"\.\w+_set\.", content) or re.search(
                            r"\.related_name\.", content
                        ):
                            queries_data["missing_select_related"].append(
                                {
                                    "file": str(py_file.relative_to(base_dir)),
                                    "suggestion": "Consider adding select_related() or prefetch_related()",
                                }
                            )

                except Exception:
                    pass

        return queries_data

    def _generate_summary(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate analysis summary."""
        summary = {
            "total_models": analysis.get("models", {}).get("total", 0),
            "total_views": analysis.get("views", {}).get("total", 0),
            "total_schemas": analysis.get("schemas", {}).get("total", 0),
            "total_tests": analysis.get("tests", {}).get("total_test_methods", 0),
            "issues": [],
        }

        # Collect issues
        if analysis.get("models", {}).get("issues"):
            summary["issues"].extend(analysis["models"]["issues"])

        if analysis.get("schemas", {}).get("unused"):
            for schema in analysis["schemas"]["unused"]:
                summary["issues"].append(
                    {
                        "type": "unused_schema",
                        "name": schema,
                        "severity": "low",
                    }
                )

        if analysis.get("tests", {}).get("missing_tests"):
            for item in analysis["tests"]["missing_tests"][:5]:  # Limit to 5
                summary["issues"].append(
                    {
                        "type": "missing_test",
                        "name": item["name"],
                        "severity": "medium",
                    }
                )

        if analysis.get("queries", {}).get("loop_queries"):
            for item in analysis["queries"]["loop_queries"][:5]:
                summary["issues"].append(
                    {
                        "type": "potential_n_plus_1",
                        "file": item["file"],
                        "severity": "high",
                    }
                )

        # Health score (simple calculation)
        score = 100
        for issue in summary["issues"]:
            if issue.get("severity") == "high":
                score -= 10
            elif issue.get("severity") == "medium":
                score -= 5
            else:
                score -= 2
        summary["health_score"] = max(0, score)

        return summary

    def _display_analysis(self, analysis: dict[str, Any], verbose: bool = False):
        """Display analysis results in a formatted way."""
        self.console.banner()
        self.header("Codebase Analysis", "Project structure and health check")

        # Summary section
        summary = analysis.get("summary", {})

        self.section("Overview")
        overview_data = [
            {"Metric": "Models", "Count": str(summary.get("total_models", 0))},
            {"Metric": "Views/Controllers", "Count": str(summary.get("total_views", 0))},
            {"Metric": "Schemas", "Count": str(summary.get("total_schemas", 0))},
            {"Metric": "Test Methods", "Count": str(summary.get("total_tests", 0))},
        ]
        self.table(overview_data)

        # Health Score
        health_score = summary.get("health_score", 100)
        if health_score >= 80:
            self.console.box_success(f"Health Score: {health_score}/100", title="Project Health")
        elif health_score >= 50:
            self.console.box_warning(f"Health Score: {health_score}/100", title="Project Health")
        else:
            self.console.box_error(f"Health Score: {health_score}/100", title="Project Health")

        # Models section
        if "models" in analysis and analysis["models"]["by_app"]:
            self.section("Models by App")
            for app, models in analysis["models"]["by_app"].items():
                self.console.print(f"\n[bold cyan]{app}[/] ({len(models)} models)")
                if verbose:
                    model_data = [
                        {
                            "Model": m["name"],
                            "Fields": str(m["fields"]),
                            "FKs": str(len(m["foreign_keys"])),
                            "M2M": str(len(m["many_to_many"])),
                        }
                        for m in models
                    ]
                    self.table(model_data)

        # Controllers section
        if "views" in analysis and analysis["views"]["controllers"]:
            self.section("Controllers")
            ctrl_data = [
                {
                    "Controller": c["name"],
                    "App": c["app"],
                    "Methods": str(len(c.get("methods", []))),
                }
                for c in analysis["views"]["controllers"]
            ]
            self.table(ctrl_data)

        # Schemas section
        if "schemas" in analysis:
            self.section("Schemas")
            self.console.print(f"Total: {analysis['schemas']['total']} schemas")

            if analysis["schemas"]["unused"]:
                self.console.newline()
                self.warning(f"Potentially unused schemas: {len(analysis['schemas']['unused'])}")
                for schema in analysis["schemas"]["unused"][:5]:
                    self.console.list_item(schema, style="yellow")

        # Tests section
        if "tests" in analysis:
            self.section("Test Coverage")
            tests = analysis["tests"]
            test_data = [
                {"Metric": "Test Files", "Count": str(tests["total_test_files"])},
                {"Metric": "Test Classes", "Count": str(tests["total_test_classes"])},
                {"Metric": "Test Methods", "Count": str(tests["total_test_methods"])},
            ]
            self.table(test_data)

            if tests["missing_tests"]:
                self.console.newline()
                self.warning(f"Missing tests for: {len(tests['missing_tests'])} items")
                for item in tests["missing_tests"][:5]:
                    self.console.list_item(f"{item['type']}: {item['name']}", style="yellow")

        # Query patterns section
        if "queries" in analysis:
            queries = analysis["queries"]
            if queries["loop_queries"] or queries["missing_select_related"]:
                self.section("Query Optimization Opportunities")

                if queries["loop_queries"]:
                    self.warning(f"Potential N+1 patterns: {len(queries['loop_queries'])}")
                    for item in queries["loop_queries"][:3]:
                        self.console.list_item(
                            f"{item['file']}: {item['suggestion']}", style="yellow"
                        )

        # Issues section
        issues = summary.get("issues", [])
        if issues:
            self.section("Issues Found")
            high_issues = [i for i in issues if i.get("severity") == "high"]
            medium_issues = [i for i in issues if i.get("severity") == "medium"]
            low_issues = [i for i in issues if i.get("severity") == "low"]

            if high_issues:
                self.console.print(f"\n[red]High Priority ({len(high_issues)}):[/]")
                for issue in high_issues[:5]:
                    self.console.list_item(
                        f"{issue.get('type', 'issue')}: {issue.get('name', issue.get('file', 'unknown'))}",
                        style="red",
                    )

            if medium_issues:
                self.console.print(f"\n[yellow]Medium Priority ({len(medium_issues)}):[/]")
                for issue in medium_issues[:5]:
                    self.console.list_item(
                        f"{issue.get('type', 'issue')}: {issue.get('name', 'unknown')}",
                        style="yellow",
                    )

            if low_issues and verbose:
                self.console.print(f"\n[dim]Low Priority ({len(low_issues)}):[/]")
                for issue in low_issues[:5]:
                    self.console.list_item(
                        f"{issue.get('type', 'issue')}: {issue.get('name', 'unknown')}",
                        style="dim",
                    )

        self.console.newline()
        self.console.muted(
            "Run with --verbose for more details or --json for machine-readable output"
        )
