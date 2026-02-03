"""
Django Matt schema listing command.

Lists all Pydantic schemas with details about fields, validators, and inheritance.

Usage:
    python manage.py matt_schemas                    # List all schemas
    python manage.py matt_schemas --app myapp        # Filter by app
    python manage.py matt_schemas --unused           # Show only unused schemas
    python manage.py matt_schemas --verbose          # Show field details
    python manage.py matt_schemas --json             # Output as JSON
"""

import ast
import json
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings

from django_matt.cli import MattCommand


class Command(MattCommand):
    """List all Pydantic schemas with detailed information."""

    help = "List all Pydantic schemas with fields, validators, and inheritance"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--app",
            "-a",
            help="Filter by app name",
        )
        parser.add_argument(
            "--unused",
            action="store_true",
            help="Show only potentially unused schemas",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show field details and validators",
        )
        parser.add_argument(
            "--filter",
            "-f",
            help="Filter schemas by name pattern",
        )

    def handle(self, *args, **options):
        output_json = options.get("json", False)
        app_filter = options.get("app")
        show_unused = options.get("unused", False)
        verbose = options.get("verbose", False)
        name_filter = options.get("filter")

        # Collect all schemas
        schemas = self._collect_schemas(app_filter)

        # Find unused schemas
        used_schemas = self._find_used_schemas()
        for schema in schemas:
            schema["is_used"] = schema["name"] in used_schemas

        # Apply filters
        if show_unused:
            schemas = [s for s in schemas if not s["is_used"]]

        if name_filter:
            name_filter_lower = name_filter.lower()
            schemas = [s for s in schemas if name_filter_lower in s["name"].lower()]

        # Output in requested format
        if output_json:
            self.stdout.write(json.dumps(schemas, indent=2, default=str))
        else:
            self._display_schemas(schemas, verbose)

    def _collect_schemas(self, app_filter: str | None = None) -> list[dict[str, Any]]:
        """Collect all Pydantic schemas from the project."""
        schemas = []
        base_dir = Path(settings.BASE_DIR)

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue
            if app_filter and app_config.label != app_filter:
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            # Look for schema files
            for pattern in ["schemas.py", "schemas/*.py", "schema.py", "*_schemas.py"]:
                for file_path in app_path.glob(pattern):
                    if file_path.name.startswith("_"):
                        continue

                    try:
                        file_schemas = self._parse_schema_file(file_path, app_config.label, base_dir)
                        schemas.extend(file_schemas)
                    except Exception as e:
                        self.warning(f"Error parsing {file_path}: {e}")

        return schemas

    def _parse_schema_file(
        self, file_path: Path, app_label: str, base_dir: Path
    ) -> list[dict[str, Any]]:
        """Parse a Python file and extract Pydantic schema definitions."""
        schemas = []

        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except Exception:
            return schemas

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                schema_info = self._extract_schema_info(node, file_path, app_label, base_dir, content)
                if schema_info:
                    schemas.append(schema_info)

        return schemas

    def _extract_schema_info(
        self,
        node: ast.ClassDef,
        file_path: Path,
        app_label: str,
        base_dir: Path,
        content: str,
    ) -> dict[str, Any] | None:
        """Extract information from a class definition if it's a Pydantic schema."""
        # Check if this is a Pydantic schema
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        schema_bases = {"BaseModel", "Schema", "ModelSchema", "GenericModel"}
        is_schema = any(b in schema_bases for b in base_names)

        # Also check for schemas that inherit from other schemas
        if not is_schema and base_names:
            # If it ends with "Schema" or "Model", assume it's a schema
            is_schema = any(
                b.endswith("Schema") or b.endswith("Base") or b.endswith("Create") or b.endswith("Update")
                for b in base_names
            )

        if not is_schema:
            return None

        # Extract fields
        fields = []
        validators = []
        config_options = {}

        for item in node.body:
            # Field annotations
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_info = self._extract_field_info(item)
                if field_info:
                    fields.append(field_info)

            # Validators
            elif isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    decorator_name = ""
                    if isinstance(decorator, ast.Name):
                        decorator_name = decorator.id
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            decorator_name = decorator.func.id
                        elif isinstance(decorator.func, ast.Attribute):
                            decorator_name = decorator.func.attr

                    if decorator_name in ("validator", "field_validator", "model_validator", "root_validator"):
                        validators.append(
                            {
                                "name": item.name,
                                "type": decorator_name,
                            }
                        )

            # Config class
            elif isinstance(item, ast.ClassDef) and item.name == "Config":
                config_options = self._extract_config_options(item)

        # Get docstring
        docstring = ast.get_docstring(node) or ""

        # Determine schema type
        schema_type = "base"
        name_lower = node.name.lower()
        if "create" in name_lower:
            schema_type = "create"
        elif "update" in name_lower:
            schema_type = "update"
        elif "response" in name_lower or "out" in name_lower:
            schema_type = "response"
        elif "list" in name_lower:
            schema_type = "list"
        elif "filter" in name_lower:
            schema_type = "filter"

        return {
            "name": node.name,
            "app": app_label,
            "file": str(file_path.relative_to(base_dir)),
            "line": node.lineno,
            "bases": base_names,
            "fields": fields,
            "field_count": len(fields),
            "validators": validators,
            "validator_count": len(validators),
            "config": config_options,
            "docstring": docstring[:100] if docstring else "",
            "schema_type": schema_type,
        }

    def _extract_field_info(self, node: ast.AnnAssign) -> dict[str, Any] | None:
        """Extract field information from an annotated assignment."""
        if not isinstance(node.target, ast.Name):
            return None

        field_name = node.target.id

        # Skip private fields
        if field_name.startswith("_"):
            return None

        # Get type annotation
        type_str = self._get_annotation_str(node.annotation)

        # Check for Field() or default value
        required = True
        default = None
        has_field = False

        if node.value:
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name):
                    func_name = node.value.func.id
                    if func_name == "Field":
                        has_field = True
                        # Check for default argument
                        for keyword in node.value.keywords:
                            if keyword.arg == "default":
                                required = False
                                default = self._get_value_str(keyword.value)
                            elif keyword.arg == "default_factory":
                                required = False
                                default = "factory"
                        # Check positional args
                        if node.value.args:
                            first_arg = node.value.args[0]
                            if isinstance(first_arg, ast.Constant):
                                if first_arg.value is not ...:
                                    required = False
                                    default = str(first_arg.value)
            elif isinstance(node.value, ast.Constant):
                required = False
                default = str(node.value.value)
            elif isinstance(node.value, ast.Name):
                if node.value.id == "None":
                    required = False
                    default = "None"

        # Check for Optional type
        if "Optional" in type_str or "| None" in type_str:
            required = False

        return {
            "name": field_name,
            "type": type_str,
            "required": required,
            "default": default,
            "has_field": has_field,
        }

    def _get_annotation_str(self, annotation) -> str:
        """Convert an AST annotation node to a string."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Subscript):
            base = self._get_annotation_str(annotation.value)
            if isinstance(annotation.slice, ast.Tuple):
                args = ", ".join(self._get_annotation_str(e) for e in annotation.slice.elts)
            else:
                args = self._get_annotation_str(annotation.slice)
            return f"{base}[{args}]"
        elif isinstance(annotation, ast.Attribute):
            return f"{self._get_annotation_str(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.BinOp):
            if isinstance(annotation.op, ast.BitOr):
                left = self._get_annotation_str(annotation.left)
                right = self._get_annotation_str(annotation.right)
                return f"{left} | {right}"
        elif isinstance(annotation, ast.Tuple):
            return ", ".join(self._get_annotation_str(e) for e in annotation.elts)
        return "Any"

    def _get_value_str(self, value) -> str:
        """Convert an AST value node to a string."""
        if isinstance(value, ast.Constant):
            return str(value.value)
        elif isinstance(value, ast.Name):
            return value.id
        elif isinstance(value, ast.List):
            return "[]"
        elif isinstance(value, ast.Dict):
            return "{}"
        return "..."

    def _extract_config_options(self, config_node: ast.ClassDef) -> dict[str, Any]:
        """Extract options from a Config class."""
        options = {}
        for item in config_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        options[target.id] = self._get_value_str(item.value)
        return options

    def _find_used_schemas(self) -> set[str]:
        """Find schemas that are referenced in other files."""
        used = set()
        base_dir = Path(settings.BASE_DIR)

        for app_config in apps.get_app_configs():
            if app_config.name.startswith("django."):
                continue

            app_path = Path(app_config.path)
            if not app_path.exists():
                continue

            for py_file in app_path.glob("**/*.py"):
                # Skip schema files themselves
                if "schema" in py_file.name.lower():
                    continue
                if "__pycache__" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()

                    # Look for schema imports and usages
                    # Import patterns
                    import_matches = list(
                        __import__("re").finditer(r"from\s+[\w.]+schemas?\s+import\s+([^#\n]+)", content)
                    )
                    for match in import_matches:
                        imports = match.group(1)
                        # Extract schema names
                        names = __import__("re").findall(r"\b(\w+Schema|\w+Base|\w+Create|\w+Update)\b", imports)
                        used.update(names)

                    # Type hint usages
                    type_matches = __import__("re").findall(r"[:\s](\w+Schema|\w+Base)\b", content)
                    used.update(type_matches)

                    # Response model usages
                    response_matches = __import__("re").findall(r"response_model\s*=\s*(\w+)", content)
                    used.update(response_matches)

                except Exception:
                    pass

        return used

    def _display_schemas(self, schemas: list[dict[str, Any]], verbose: bool):
        """Display schemas in a formatted table."""
        self.console.banner()
        self.header("Pydantic Schemas", f"Found {len(schemas)} schemas")

        if not schemas:
            self.warning("No schemas found")
            return

        # Group by app
        by_app = {}
        for schema in schemas:
            app = schema.get("app", "unknown")
            if app not in by_app:
                by_app[app] = []
            by_app[app].append(schema)

        for app, app_schemas in sorted(by_app.items()):
            self.section(f"{app} ({len(app_schemas)} schemas)")

            if verbose:
                for schema in app_schemas:
                    self._display_schema_detail(schema)
            else:
                table_data = []
                for s in app_schemas:
                    status = "" if s.get("is_used", True) else "[yellow](unused)[/]"
                    table_data.append(
                        {
                            "Name": f"{s['name']} {status}",
                            "Type": s.get("schema_type", "base"),
                            "Fields": str(s["field_count"]),
                            "Validators": str(s["validator_count"]),
                            "Bases": ", ".join(s.get("bases", [])),
                        }
                    )
                self.table(table_data)

        # Summary
        self.console.newline()
        total_fields = sum(s["field_count"] for s in schemas)
        total_validators = sum(s["validator_count"] for s in schemas)
        unused_count = len([s for s in schemas if not s.get("is_used", True)])

        summary_data = [
            {"Metric": "Total Schemas", "Value": str(len(schemas))},
            {"Metric": "Total Fields", "Value": str(total_fields)},
            {"Metric": "Total Validators", "Value": str(total_validators)},
            {"Metric": "Potentially Unused", "Value": str(unused_count)},
        ]
        self.table(summary_data)

        if unused_count > 0:
            self.console.newline()
            self.warning(
                f"{unused_count} schemas appear unused. "
                "Run with --unused to see only those schemas."
            )

    def _display_schema_detail(self, schema: dict[str, Any]):
        """Display detailed information about a schema."""
        status = "" if schema.get("is_used", True) else " [yellow](potentially unused)[/]"
        self.console.print(f"\n[bold cyan]{schema['name']}[/]{status}")
        self.console.print(f"[dim]  File: {schema['file']}:{schema['line']}[/]")

        if schema.get("docstring"):
            self.console.print(f"[dim]  {schema['docstring']}[/]")

        if schema.get("bases"):
            self.console.print(f"  [dim]Inherits:[/] {', '.join(schema['bases'])}")

        # Fields
        if schema.get("fields"):
            self.console.print("\n  [bold]Fields:[/]")
            for field in schema["fields"]:
                required = "[red]*[/]" if field["required"] else ""
                default = f" = {field['default']}" if field.get("default") else ""
                self.console.print(
                    f"    {required}{field['name']}: [cyan]{field['type']}[/]{default}"
                )

        # Validators
        if schema.get("validators"):
            self.console.print("\n  [bold]Validators:[/]")
            for validator in schema["validators"]:
                self.console.print(
                    f"    @{validator['type']} {validator['name']}"
                )

        # Config
        if schema.get("config"):
            self.console.print("\n  [bold]Config:[/]")
            for key, value in schema["config"].items():
                self.console.print(f"    {key} = {value}")
