# file-length-max: 1250
"""
Django Matt migration wizard command.

Helps migrate from Django REST Framework, Django Ninja, Django Ninja Extra,
or FastAPI to django-matt.
Uses the codemod engine for AST-based automated source transformations.

Usage:
    python manage.py matt_migrate_from --source drf               # Detect DRF code
    python manage.py matt_migrate_from --source ninja             # Detect Django Ninja code
    python manage.py matt_migrate_from --source ninja-extra       # Detect Django Ninja Extra code
    python manage.py matt_migrate_from --source fastapi           # Detect FastAPI code
    python manage.py matt_migrate_from --source drf --app myapp   # Migrate specific app
    python manage.py matt_migrate_from --source drf --dry-run     # Preview changes
    python manage.py matt_migrate_from --source drf --generate    # Generate migration files
    python manage.py matt_migrate_from --directory ./myproject --diff  # Show diffs
    python manage.py matt_migrate_from --framework auto --directory .  # Auto-detect & transform
"""

import ast
import re
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings

import orjson

from django_matt.cli import GeneratorCommand
from django_matt.codemods.engine import CodemodEngine


class Command(GeneratorCommand):
    """Migration wizard for DRF, Django Ninja, or FastAPI to django-matt."""

    help = "Migrate from DRF, Django Ninja, Django Ninja Extra, or FastAPI to django-matt"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--source",
            "-s",
            choices=["drf", "ninja", "ninja-extra", "auto"],
            default="auto",
            help="Source framework to migrate from (default: auto-detect)",
        )
        parser.add_argument(
            "--framework",
            choices=["drf", "ninja", "ninja-extra", "fastapi", "auto"],
            default=None,
            help="Framework for codemod engine (drf, ninja, ninja-extra, fastapi, auto)",
        )
        parser.add_argument(
            "--app",
            "-a",
            help="Limit migration to specific app",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output analysis as JSON",
        )
        parser.add_argument(
            "--generate",
            "-g",
            action="store_true",
            help="Generate migration files",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Output directory for generated files",
        )
        parser.add_argument(
            "--directory",
            default=None,
            help="Process entire directory tree with codemod engine",
        )
        parser.add_argument(
            "--diff",
            action="store_true",
            default=False,
            help="Show unified diff of proposed changes",
        )

    def handle(self, *args, **options):
        # New codemod engine path
        directory = options.get("directory")
        framework = options.get("framework")
        show_diff = options.get("diff", False)

        if directory or framework:
            return self._handle_codemod_engine(directory, framework, show_diff, options)

        source = options.get("source", "auto")
        app_filter = options.get("app")
        output_json = options.get("json", False)
        generate = options.get("generate", False)
        output_dir = options.get("output_dir")

        # Auto-detect source framework
        if source == "auto":
            source = self._detect_framework()
            if not source:
                self.error(
                    "Could not detect source framework. Specify --source drf, "
                    "--source ninja, or --source ninja-extra"
                )
                return None

        # Analyze codebase
        if source == "drf":
            analysis = self._analyze_drf(app_filter)
        elif source == "ninja-extra":
            analysis = self._analyze_ninja_extra(app_filter)
        else:
            analysis = self._analyze_ninja(app_filter)

        # Output
        if output_json:
            self.stdout.write(
                orjson.dumps(analysis, default=str, option=orjson.OPT_INDENT_2).decode()
            )
        else:
            self._display_analysis(analysis, source)

            if generate and analysis.get("items"):
                self._generate_migration_files(analysis, output_dir)

    def _detect_framework(self) -> str | None:
        """Auto-detect the source framework."""
        installed_apps = settings.INSTALLED_APPS

        # Check installed apps
        if "rest_framework" in installed_apps:
            return "drf"
        if "ninja_extra" in installed_apps:
            return "ninja-extra"
        if "ninja" in installed_apps:
            return "ninja"

        # Check requirements/dependencies
        try:
            import rest_framework

            return "drf"
        except ImportError:
            pass

        try:
            import ninja_extra

            return "ninja-extra"
        except ImportError:
            pass

        try:
            import ninja

            return "ninja"
        except ImportError:
            pass

        # Search for imports in code
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        for py_file in base_dir.glob("**/*.py"):
            if "__pycache__" in str(py_file) or "migrations" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                detected = self._detect_framework_from_source(content)
                if detected:
                    return detected
            except Exception:
                pass

        return None

    def _detect_framework_from_source(self, content: str) -> str | None:
        """Detect the source framework from a source file's text."""
        if "from rest_framework" in content or "import rest_framework" in content:
            return "drf"
        if "from ninja_extra" in content or "import ninja_extra" in content:
            return "ninja-extra"
        if "from ninja" in content or "import ninja" in content:
            return "ninja"
        return None

    def _analyze_drf(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze DRF code for migration."""
        analysis = {
            "framework": "drf",
            "items": [],
            "serializers": [],
            "viewsets": [],
            "views": [],
            "routers": [],
            "suggestions": [],
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

            # Analyze serializers
            for pattern in ["serializers.py", "serializers/*.py"]:
                for file_path in app_path.glob(pattern):
                    if file_path.name.startswith("_"):
                        continue
                    serializers = self._analyze_drf_serializers(
                        file_path, app_config.label, base_dir
                    )
                    analysis["serializers"].extend(serializers)
                    analysis["items"].extend(serializers)

            # Analyze views and viewsets
            for pattern in ["views.py", "views/*.py", "viewsets.py"]:
                for file_path in app_path.glob(pattern):
                    if file_path.name.startswith("_"):
                        continue
                    views = self._analyze_drf_views(file_path, app_config.label, base_dir)
                    analysis["views"].extend(views)
                    analysis["items"].extend(views)

            # Analyze routers
            for pattern in ["urls.py", "routers.py"]:
                for file_path in app_path.glob(pattern):
                    routers = self._analyze_drf_routers(file_path, app_config.label, base_dir)
                    analysis["routers"].extend(routers)

        # Generate migration suggestions
        analysis["suggestions"] = self._generate_drf_suggestions(analysis)

        return analysis

    def _analyze_drf_serializers(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Analyze DRF serializers in a file."""
        serializers = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [getattr(base, "id", getattr(base, "attr", "")) for base in node.bases]

                    is_serializer = any("Serializer" in b for b in bases)

                    if is_serializer:
                        # Analyze serializer structure
                        fields = []
                        meta_model = None
                        meta_fields = None

                        for item in node.body:
                            # Field definitions
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        fields.append(
                                            {
                                                "name": target.id,
                                                "type": self._get_serializer_field_type(item.value),
                                            }
                                        )

                            # Meta class
                            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                                for meta_item in item.body:
                                    if isinstance(meta_item, ast.Assign):
                                        for target in meta_item.targets:
                                            if isinstance(target, ast.Name):
                                                if target.id == "model":
                                                    meta_model = self._get_value_str(
                                                        meta_item.value
                                                    )
                                                elif target.id == "fields":
                                                    meta_fields = self._get_value_str(
                                                        meta_item.value
                                                    )

                        serializers.append(
                            {
                                "type": "serializer",
                                "name": node.name,
                                "app": app_label,
                                "file": str(file_path.relative_to(base_dir)),
                                "line": node.lineno,
                                "bases": bases,
                                "fields": fields,
                                "meta_model": meta_model,
                                "meta_fields": meta_fields,
                                "migration": {
                                    "target": "schema",
                                    "new_name": node.name.replace("Serializer", "Schema"),
                                },
                            }
                        )

        except Exception:
            pass

        return serializers

    def _analyze_drf_views(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Analyze DRF views and viewsets in a file."""
        views = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [getattr(base, "id", getattr(base, "attr", "")) for base in node.bases]

                    is_viewset = any("ViewSet" in b for b in bases)
                    is_view = any("View" in b or "Mixin" in b for b in bases)

                    if is_viewset or is_view:
                        # Analyze view structure
                        queryset = None
                        serializer_class = None
                        permission_classes = []
                        methods = []

                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        if target.id == "queryset":
                                            queryset = self._get_value_str(item.value)
                                        elif target.id == "serializer_class":
                                            serializer_class = self._get_value_str(item.value)
                                        elif target.id == "permission_classes":
                                            permission_classes = self._get_list_values(item.value)

                            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if not item.name.startswith("_"):
                                    methods.append(item.name)

                        view_type = "viewset" if is_viewset else "view"
                        new_name = node.name
                        if "ViewSet" in node.name:
                            new_name = node.name.replace("ViewSet", "Controller")
                        elif "View" in node.name and "API" not in node.name:
                            new_name = node.name.replace("View", "Controller")

                        views.append(
                            {
                                "type": view_type,
                                "name": node.name,
                                "app": app_label,
                                "file": str(file_path.relative_to(base_dir)),
                                "line": node.lineno,
                                "bases": bases,
                                "queryset": queryset,
                                "serializer_class": serializer_class,
                                "permission_classes": permission_classes,
                                "methods": methods,
                                "migration": {
                                    "target": "controller",
                                    "new_name": new_name,
                                },
                            }
                        )

        except Exception:
            pass

        return views

    def _analyze_drf_routers(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Analyze DRF router registrations."""
        routers = []

        try:
            content = file_path.read_text()

            # Find router.register calls
            register_pattern = r"router\.register\(['\"]([^'\"]+)['\"],\s*(\w+)"
            for match in re.finditer(register_pattern, content):
                routers.append(
                    {
                        "prefix": match.group(1),
                        "viewset": match.group(2),
                        "file": str(file_path.relative_to(base_dir)),
                    }
                )

        except Exception:
            pass

        return routers

    def _analyze_ninja(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze Django Ninja code for migration."""
        analysis = {
            "framework": "ninja",
            "items": [],
            "schemas": [],
            "routers": [],
            "api_instances": [],
            "suggestions": [],
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

            # Analyze schemas
            for pattern in ["schemas.py", "schemas/*.py"]:
                for file_path in app_path.glob(pattern):
                    schemas = self._analyze_ninja_schemas(file_path, app_config.label, base_dir)
                    analysis["schemas"].extend(schemas)
                    analysis["items"].extend(schemas)

            # Analyze API routers
            for pattern in ["api.py", "api/*.py", "views.py", "routers.py"]:
                for file_path in app_path.glob(pattern):
                    routers = self._analyze_ninja_routers(file_path, app_config.label, base_dir)
                    analysis["routers"].extend(routers)
                    analysis["items"].extend(routers)

        # Generate migration suggestions
        analysis["suggestions"] = self._generate_ninja_suggestions(analysis)

        return analysis

    def _analyze_ninja_schemas(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Analyze Django Ninja schemas."""
        schemas = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [getattr(base, "id", getattr(base, "attr", "")) for base in node.bases]

                    is_schema = any(b in ("Schema", "ModelSchema") for b in bases)

                    if is_schema:
                        schemas.append(
                            {
                                "type": "schema",
                                "name": node.name,
                                "app": app_label,
                                "file": str(file_path.relative_to(base_dir)),
                                "line": node.lineno,
                                "bases": bases,
                                "migration": {
                                    "target": "schema",
                                    "new_name": node.name,
                                    "changes": [
                                        "Import from django_matt.core.schema instead of ninja"
                                    ],
                                },
                            }
                        )

        except Exception:
            pass

        return schemas

    def _analyze_ninja_routers(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Analyze Django Ninja routers and API endpoints."""
        routers = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            # Find router/api definitions
            for node in ast.walk(tree):
                # Check for Router or NinjaAPI instantiation
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                            func = node.value.func
                            func_name = getattr(func, "id", getattr(func, "attr", ""))
                            if func_name in ("Router", "NinjaAPI"):
                                routers.append(
                                    {
                                        "type": "router",
                                        "name": target.id,
                                        "file": str(file_path.relative_to(base_dir)),
                                        "line": node.lineno,
                                        "migration": {
                                            "target": "MattAPI"
                                            if func_name == "NinjaAPI"
                                            else "router",
                                            "changes": [
                                                f"Replace {func_name} with django_matt equivalent"
                                            ],
                                        },
                                    }
                                )

            # Find decorated endpoint functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        # Check for @api.get, @router.post, etc.
                        if isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Attribute):
                                method = decorator.func.attr
                                if method in ("get", "post", "put", "patch", "delete"):
                                    routers.append(
                                        {
                                            "type": "endpoint",
                                            "name": node.name,
                                            "method": method.upper(),
                                            "file": str(file_path.relative_to(base_dir)),
                                            "line": node.lineno,
                                            "migration": {
                                                "target": "controller_method",
                                                "changes": [
                                                    "Move to controller class or use @api decorator"
                                                ],
                                            },
                                        }
                                    )

        except Exception:
            pass

        return routers

    def _analyze_ninja_extra(self, app_filter: str | None = None) -> dict[str, Any]:
        """Analyze Django Ninja Extra code for migration."""
        from django_matt.migrate.ninja_extra import analyze_ninja_extra

        return analyze_ninja_extra(app_filter)

    def _get_serializer_field_type(self, value) -> str:
        """Get the type of a serializer field."""
        if isinstance(value, ast.Call):
            if isinstance(value.func, ast.Attribute):
                return value.func.attr
            if isinstance(value.func, ast.Name):
                return value.func.id
        return "unknown"

    def _get_value_str(self, value) -> str:
        """Convert an AST value node to a string."""
        if isinstance(value, ast.Constant):
            return str(value.value)
        if isinstance(value, ast.Name):
            return value.id
        if isinstance(value, ast.Attribute):
            return f"{self._get_value_str(value.value)}.{value.attr}"
        if isinstance(value, ast.Call):
            return f"{self._get_value_str(value.func)}(...)"
        if isinstance(value, ast.List):
            return "[...]"
        if isinstance(value, ast.Tuple):
            return "(...)"
        return "..."

    def _get_list_values(self, value) -> list[str]:
        """Get values from a list AST node."""
        if isinstance(value, ast.List):
            return [self._get_value_str(elt) for elt in value.elts]
        return []

    def _generate_drf_suggestions(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate migration suggestions for DRF."""
        suggestions = []

        if analysis["serializers"]:
            suggestions.append(
                {
                    "title": "Convert Serializers to Pydantic Schemas",
                    "description": f"Found {len(analysis['serializers'])} serializers to convert",
                    "priority": "high",
                    "steps": [
                        "Create schema files with Pydantic BaseModel classes",
                        "Replace rest_framework imports with pydantic imports",
                        "Convert field definitions to Pydantic type annotations",
                        "Move validation logic to Pydantic validators",
                    ],
                }
            )

        if analysis["views"]:
            viewsets = [v for v in analysis["views"] if v["type"] == "viewset"]
            views = [v for v in analysis["views"] if v["type"] == "view"]

            if viewsets:
                suggestions.append(
                    {
                        "title": "Convert ViewSets to Controllers",
                        "description": f"Found {len(viewsets)} viewsets to convert",
                        "priority": "high",
                        "steps": [
                            "Create controller classes extending APIController",
                            "Replace @action decorators with @get, @post, etc.",
                            "Update queryset handling to use async methods",
                            "Update serializer_class to use Pydantic schemas",
                        ],
                    }
                )

            if views:
                suggestions.append(
                    {
                        "title": "Convert API Views",
                        "description": f"Found {len(views)} views to convert",
                        "priority": "medium",
                        "steps": [
                            "Convert class-based views to controller methods",
                            "Replace response classes with FastJsonResponse",
                            "Update authentication decorators",
                        ],
                    }
                )

        suggestions.append(
            {
                "title": "Update URL Configuration",
                "description": "Replace DRF routers with django-matt API registration",
                "priority": "medium",
                "steps": [
                    "Create MattAPI instance",
                    "Register controllers using api.register_controller()",
                    "Update urlpatterns to use api.urls",
                ],
            }
        )

        return suggestions

    def _generate_ninja_suggestions(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate migration suggestions for Django Ninja."""
        suggestions = []

        suggestions.append(
            {
                "title": "Update Import Statements",
                "description": "Replace ninja imports with django_matt imports",
                "priority": "high",
                "steps": [
                    "Replace 'from ninja import ...' with 'from django_matt import ...'",
                    "Replace 'from ninja.schema import Schema' with 'from django_matt.core.schema import Schema'",
                    "Update NinjaAPI to MattAPI",
                ],
            }
        )

        if analysis["schemas"]:
            suggestions.append(
                {
                    "title": "Update Schemas",
                    "description": f"Found {len(analysis['schemas'])} schemas",
                    "priority": "low",
                    "steps": [
                        "Schemas are mostly compatible - just update imports",
                        "Check for ninja-specific features that may need adjustment",
                    ],
                }
            )

        if analysis["routers"]:
            suggestions.append(
                {
                    "title": "Convert to Controller Pattern",
                    "description": "Consider using class-based controllers for better organization",
                    "priority": "medium",
                    "steps": [
                        "Group related endpoints into controller classes",
                        "Use APIController base class",
                        "Move function-based views to controller methods",
                    ],
                }
            )

        return suggestions

    def _generate_ninja_extra_suggestions(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate migration suggestions for Django Ninja Extra."""
        from django_matt.migrate.ninja_extra import generate_ninja_extra_suggestions

        return generate_ninja_extra_suggestions(analysis)


    def _display_analysis(self, analysis: dict[str, Any], source: str):
        """Display migration analysis."""
        self.console.banner()
        framework_name = (
            "Django REST Framework"
            if source == "drf"
            else "Django Ninja Extra"
            if source == "ninja-extra"
            else "Django Ninja"
        )
        self.header(f"Migration Analysis: {framework_name}", "Code to migrate to django-matt")

        items = analysis.get("items", [])
        if not items:
            self.info("No items found to migrate")
            return

        # Summary
        self.section("Summary")
        summary_data = []

        if analysis.get("serializers"):
            summary_data.append(
                {"Item Type": "Serializers", "Count": str(len(analysis["serializers"]))}
            )

        if analysis.get("views"):
            viewsets = [v for v in analysis["views"] if v["type"] == "viewset"]
            views = [v for v in analysis["views"] if v["type"] == "view"]
            if viewsets:
                summary_data.append({"Item Type": "ViewSets", "Count": str(len(viewsets))})
            if views:
                summary_data.append({"Item Type": "Views", "Count": str(len(views))})

        if analysis.get("schemas"):
            summary_data.append({"Item Type": "Schemas", "Count": str(len(analysis["schemas"]))})

        if analysis.get("routers"):
            summary_data.append(
                {"Item Type": "Routers/Endpoints", "Count": str(len(analysis["routers"]))}
            )

        if analysis.get("controllers"):
            summary_data.append(
                {"Item Type": "Controllers", "Count": str(len(analysis["controllers"]))}
            )

        if analysis.get("endpoints"):
            summary_data.append(
                {"Item Type": "Endpoints", "Count": str(len(analysis["endpoints"]))}
            )

        if analysis.get("registrations"):
            summary_data.append(
                {"Item Type": "Registrations", "Count": str(len(analysis["registrations"]))}
            )

        if analysis.get("api_instances"):
            summary_data.append(
                {"Item Type": "API Instances", "Count": str(len(analysis["api_instances"]))}
            )

        self.table(summary_data)

        # Items to migrate
        if source == "drf":
            if analysis.get("serializers"):
                self.section("Serializers to Convert")
                for s in analysis["serializers"][:10]:
                    migration = s.get("migration", {})
                    self.console.print(
                        f"  [yellow]{s['name']}[/] -> [green]{migration.get('new_name', s['name'])}[/]"
                    )
                    self.console.print(f"    [dim]{s['file']}:{s['line']}[/]")
                    if s.get("meta_model"):
                        self.console.print(f"    [dim]Model: {s['meta_model']}[/]")

            if analysis.get("views"):
                self.section("Views/ViewSets to Convert")
                for v in analysis["views"][:10]:
                    migration = v.get("migration", {})
                    self.console.print(
                        f"  [yellow]{v['name']}[/] -> [green]{migration.get('new_name', v['name'])}[/]"
                    )
                    self.console.print(f"    [dim]{v['file']}:{v['line']}[/]")
                    if v.get("methods"):
                        self.console.print(f"    [dim]Methods: {', '.join(v['methods'][:5])}[/]")

        elif source == "ninja-extra":
            if analysis.get("schemas"):
                self.section("Schemas")
                for s in analysis["schemas"][:10]:
                    self.console.print(f"  [cyan]{s['name']}[/]")
                    self.console.print(f"    [dim]{s['file']}:{s['line']}[/]")

            if analysis.get("controllers"):
                self.section("Controllers to Convert")
                for c in analysis["controllers"][:10]:
                    prefix = f" {c['prefix']!r}" if c.get("prefix") else ""
                    self.console.print(f"  [yellow]{c['name']}[/] -> [green]APIController[/]")
                    self.console.print(f"    [dim]{c['file']}:{c['line']} (prefix{prefix})[/]")
                    if c.get("permissions"):
                        self.console.print(
                            f"    [dim]Permissions: {', '.join(c['permissions'])}[/]"
                        )
                    for ep in c.get("endpoints", [])[:5]:
                        self.console.print(
                            f"      [cyan]{ep['method']}[/] {ep['path'] or ep['name']}"
                        )

            if analysis.get("registrations"):
                self.section("Controller Registration")
                for r in analysis["registrations"][:10]:
                    self.console.print("  [yellow]register_controllers[/] -> register_controller")
                    self.console.print(f"    [dim]{r['file']}:{r['line']}[/]")

        else:
            if analysis.get("schemas"):
                self.section("Schemas")
                for s in analysis["schemas"][:10]:
                    self.console.print(f"  [cyan]{s['name']}[/]")
                    self.console.print(f"    [dim]{s['file']}:{s['line']}[/]")

            if analysis.get("routers"):
                self.section("Routers/Endpoints")
                for r in analysis["routers"][:10]:
                    if r["type"] == "endpoint":
                        self.console.print(f"  [cyan]{r['method']}[/] {r['name']}")
                    else:
                        self.console.print(f"  [cyan]{r['name']}[/] ({r['type']})")
                    self.console.print(f"    [dim]{r['file']}:{r['line']}[/]")

        # Suggestions
        if analysis.get("suggestions"):
            self.section("Migration Steps")
            for i, suggestion in enumerate(analysis["suggestions"], 1):
                priority_color = {
                    "high": "red",
                    "medium": "yellow",
                    "low": "green",
                }.get(suggestion.get("priority", "medium"), "white")

                self.console.print(
                    f"\n[bold]{i}. {suggestion['title']}[/] "
                    f"[{priority_color}]({suggestion.get('priority', 'medium')} priority)[/]"
                )
                self.console.print(f"   [dim]{suggestion['description']}[/]")

                for step in suggestion.get("steps", []):
                    self.console.print(f"      - {step}")

        self.console.newline()
        self.info("Run with --generate to create migration files")
        self.info("Run with --json for machine-readable output")

    def _generate_migration_files(self, analysis: dict[str, Any], output_dir: str | None):
        """Generate migration helper files."""
        self.section("Generating Migration Files")

        output_path = Path(output_dir) if output_dir else Path.cwd() / "matt_migration"
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate schema conversions
        if analysis.get("serializers"):
            content = self._generate_schema_template(analysis["serializers"])
            self.write_file(output_path / "schemas.py", content)

        # Generate controller conversions
        views = analysis.get("views", [])
        if views:
            content = self._generate_controller_template(views)
            self.write_file(output_path / "controllers.py", content)

        # Generate ninja-extra controller conversions
        controllers = analysis.get("controllers", [])
        if controllers:
            content = self._generate_ninja_extra_controller_template(controllers)
            self.write_file(output_path / "controllers.py", content)

        # Generate migration guide
        content = self._generate_migration_guide(analysis)
        self.write_file(output_path / "MIGRATION_GUIDE.md", content)

        self.show_summary()
        self.next_steps(
            [
                f"Review generated files in {output_path}",
                "Copy and adapt schema definitions",
                "Copy and adapt controller definitions",
                "Update URL configuration",
                "Run tests to verify migration",
            ]
        )

    def _generate_schema_template(self, serializers: list[dict[str, Any]]) -> str:
        """Generate Pydantic schema template from serializers."""
        lines = [
            '"""',
            "Pydantic schemas converted from DRF serializers.",
            "",
            "Review and adapt these schemas for your needs.",
            '"""',
            "",
            "from datetime import datetime",
            "from typing import Optional, List",
            "",
            "from pydantic import BaseModel, Field",
            "",
            "",
        ]

        for s in serializers:
            name = s.get("migration", {}).get("new_name", s["name"])
            original = s["name"]

            lines.append(f"class {name}(BaseModel):")
            lines.append(f'    """Converted from {original}."""')
            lines.append("")

            # Add fields
            for field in s.get("fields", []):
                field_type = self._convert_drf_field_type(field.get("type", "unknown"))
                lines.append(f"    {field['name']}: {field_type}")

            # Add model reference if available
            if s.get("meta_model"):
                lines.append("")
                lines.append("    class Config:")
                lines.append("        from_attributes = True")
                lines.append(f"        # Original model: {s['meta_model']}")

            lines.append("")
            lines.append("")

        return "\n".join(lines)

    def _convert_drf_field_type(self, drf_type: str) -> str:
        """Convert DRF field type to Pydantic type."""
        type_map = {
            "CharField": "str",
            "TextField": "str",
            "IntegerField": "int",
            "FloatField": "float",
            "DecimalField": "float",
            "BooleanField": "bool",
            "DateField": "date",
            "DateTimeField": "datetime",
            "EmailField": "str",
            "URLField": "str",
            "UUIDField": "str",
            "PrimaryKeyRelatedField": "int",
            "SlugRelatedField": "str",
            "SerializerMethodField": "Any",
            "ListField": "list",
            "DictField": "dict",
        }
        return type_map.get(drf_type, "Any")

    def _generate_controller_template(self, views: list[dict[str, Any]]) -> str:
        """Generate controller template from views/viewsets."""
        lines = [
            '"""',
            "Controllers converted from DRF views/viewsets.",
            "",
            "Review and adapt these controllers for your needs.",
            '"""',
            "",
            "from django.http import Http404",
            "",
            "from django_matt.core.controller import APIController, CRUDController",
            "from django_matt.core.router import get, post, put, patch, delete",
            "from django_matt.permissions import IsAuthenticated",
            "",
            "# Import your models and schemas here",
            "# from .models import YourModel",
            "# from .schemas import YourSchema",
            "",
            "",
        ]

        for v in views:
            name = v.get("migration", {}).get("new_name", v["name"])
            original = v["name"]
            is_viewset = v.get("type") == "viewset"

            if is_viewset:
                lines.append(f"class {name}(CRUDController):")
            else:
                lines.append(f"class {name}(APIController):")

            lines.append(f'    """Converted from {original}."""')
            lines.append("")

            # Add prefix if viewset had a queryset
            if v.get("queryset"):
                lines.append(f"    # Original queryset: {v['queryset']}")
            if v.get("serializer_class"):
                lines.append(f"    # Original serializer: {v['serializer_class']}")

            # Add permissions
            if v.get("permission_classes"):
                perms = ", ".join(v["permission_classes"])
                lines.append(f"    # Original permissions: [{perms}]")
                lines.append("    permission_classes = [IsAuthenticated]")

            lines.append("")

            # Add method stubs
            for method in v.get("methods", [])[:5]:
                if method.startswith("_"):
                    continue
                lines.append("    # @get('/')  # or @post, @put, @delete")
                lines.append(f"    # async def {method}(self, request):")
                lines.append(f'    #     """Original method: {method}"""')
                lines.append("    #     pass")
                lines.append("")

            lines.append("")

        return "\n".join(lines)

    def _generate_ninja_extra_controller_template(
        self, controllers: list[dict[str, Any]]
    ) -> str:
        """Generate APIController templates from ninja-extra ControllerBase classes."""
        from django_matt.migrate.ninja_extra import generate_ninja_extra_controller_template

        return generate_ninja_extra_controller_template(controllers)


    def _generate_migration_guide(self, analysis: dict[str, Any]) -> str:
        """Generate a markdown migration guide."""
        framework = analysis.get("framework", "unknown")
        framework_name = {
            "drf": "Django REST Framework",
            "ninja-extra": "Django Ninja Extra",
            "fastapi": "FastAPI",
        }.get(framework, "Django Ninja")

        md = f"""# Migration Guide: {framework_name} to django-matt

This guide was auto-generated to help you migrate your codebase.

## Overview

"""
        if analysis.get("serializers"):
            md += f"- **{len(analysis['serializers'])}** serializers to convert\n"
        if analysis.get("views"):
            md += f"- **{len(analysis['views'])}** views/viewsets to convert\n"
        if analysis.get("controllers"):
            md += f"- **{len(analysis['controllers'])}** controllers to convert\n"
        if analysis.get("endpoints"):
            md += f"- **{len(analysis['endpoints'])}** endpoints to convert\n"
        if analysis.get("schemas"):
            md += f"- **{len(analysis['schemas'])}** schemas (minor changes needed)\n"

        md += """
## Step-by-Step Migration

"""
        for i, suggestion in enumerate(analysis.get("suggestions", []), 1):
            md += f"### {i}. {suggestion['title']}\n\n"
            md += f"{suggestion['description']}\n\n"
            for step in suggestion.get("steps", []):
                md += f"- {step}\n"
            md += "\n"

        md += """
## Common Patterns

### Serializer to Schema

**Before (DRF):**
```python
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
```

**After (django-matt):**
```python
from pydantic import BaseModel

class UserSchema(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True
```

### ViewSet to Controller

**Before (DRF):**
```python
from rest_framework import viewsets

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
```

**After (django-matt):**
```python
from django_matt.core.controller import CRUDController
from django_matt.core.router import get, post

class UserController(CRUDController):
    model = User
    schema = UserSchema

    @get('/')
    async def list_users(self, request):
        users = await User.objects.all()
        return [UserSchema.model_validate(u) for u in users]
```

## Resources

- [django-matt Documentation](https://github.com/mattjaikaran/django-matt)
- [Pydantic Documentation](https://docs.pydantic.dev/)

"""
        return md

    def _handle_codemod_engine(
        self,
        directory: str | None,
        framework: str | None,
        show_diff: bool,
        options: dict[str, Any],
    ) -> None:
        """Run the codemod engine on a directory or the project root."""
        engine = CodemodEngine()
        dry_run = options.get("dry_run", True)
        output_json = options.get("json", False)

        target_dir = (
            Path(directory) if directory else Path(getattr(settings, "BASE_DIR", Path.cwd()))
        )

        if framework == "auto":
            framework = engine.detect_framework_directory(target_dir)
            if framework:
                self.info(f"Auto-detected framework: {framework}")
            else:
                self.error("Could not auto-detect framework")
                return

        if show_diff:
            # Show diffs for all files
            for py_file in sorted(target_dir.rglob("*.py")):
                if engine._should_skip(py_file):
                    continue
                try:
                    source = py_file.read_text()
                    diff_text = engine.diff(source, str(py_file), framework)
                    if diff_text:
                        self.stdout.write(diff_text)
                except Exception:
                    continue
            return

        def on_progress(file_path: str, result: Any) -> None:
            confidence_pct = f"{result.confidence:.0%}"
            self.stdout.write(f"  [{confidence_pct}] {file_path} ({len(result.changes)} changes)")

        results = engine.run_directory(
            target_dir,
            framework=framework,
            dry_run=dry_run,
            progress_callback=on_progress,
        )

        if output_json:
            data = {
                path: {
                    "changes": r.changes,
                    "warnings": r.warnings,
                    "confidence": r.confidence,
                }
                for path, r in results.items()
            }
            self.stdout.write(orjson.dumps(data, default=str, option=orjson.OPT_INDENT_2).decode())
        else:
            report = engine.generate_report(results)
            self.stdout.write(report)

            if dry_run:
                self.info("Dry run -- no files were modified. Remove --dry-run to apply changes.")
