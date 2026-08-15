"""
Django Ninja Extra migration analysis.

AST-based analysis of django-ninja-extra projects for the
`matt_migrate_from` command. Detects ControllerBase classes, api_controller
decorators, route endpoints, NinjaExtraAPI instances, register_controllers
calls, and Inject-based dependency injection.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings

_SCAN_PATTERNS = ["api.py", "api/*.py", "views.py", "routers.py", "controllers.py"]
_SCHEMA_PATTERNS = ["schemas.py", "schemas/*.py"]
_ROUTE_VERBS = ("get", "post", "put", "patch", "delete")
_CONTROLLER_BASES = ("ControllerBase", "AsyncControllerBase")
_SCHEMA_BASES = ("Schema", "ModelSchema", "SchemaModel")


def analyze_ninja_extra(app_filter: str | None = None) -> dict[str, Any]:
    """Analyze Django Ninja Extra code for migration."""
    analysis = {
        "framework": "ninja-extra",
        "items": [],
        "schemas": [],
        "controllers": [],
        "endpoints": [],
        "api_instances": [],
        "registrations": [],
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

        for pattern in _SCHEMA_PATTERNS:
            for file_path in app_path.glob(pattern):
                schemas = _analyze_schemas(file_path, app_config.label, base_dir)
                analysis["schemas"].extend(schemas)
                analysis["items"].extend(schemas)

        for pattern in _SCAN_PATTERNS:
            for file_path in app_path.glob(pattern):
                controllers, endpoints, api_instances, registrations = _analyze_controllers(
                    file_path, app_config.label, base_dir
                )
                analysis["controllers"].extend(controllers)
                analysis["endpoints"].extend(endpoints)
                analysis["api_instances"].extend(api_instances)
                analysis["registrations"].extend(registrations)
                analysis["items"].extend(controllers)
                analysis["items"].extend(endpoints)

    analysis["suggestions"] = generate_ninja_extra_suggestions(analysis)

    return analysis


def _analyze_schemas(
    file_path: Path, app_label: str, base_dir: Path
) -> list[dict[str, Any]]:
    """Analyze Django Ninja Extra schemas."""
    schemas: list[dict[str, Any]] = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [getattr(base, "id", getattr(base, "attr", "")) for base in node.bases]

            if not any(b in _SCHEMA_BASES for b in bases):
                continue

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


def _analyze_controllers(
    file_path: Path, app_label: str, base_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyze controllers, endpoints, and API wiring in a single file."""
    controllers: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    api_instances: list[dict[str, Any]] = []
    registrations: list[dict[str, Any]] = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content)
        rel = str(file_path.relative_to(base_dir))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if func_name == "NinjaExtraAPI":
                    api_instances.append(
                        {
                            "type": "api",
                            "name": func_name,
                            "file": rel,
                            "line": node.lineno,
                            "migration": {
                                "target": "MattAPI",
                                "changes": ["Replace NinjaExtraAPI with DjangoMattAPI"],
                            },
                        }
                    )

                if isinstance(node.func, ast.Attribute) and node.func.attr == "register_controllers":
                    registrations.append(
                        {
                            "type": "registration",
                            "name": "register_controllers",
                            "file": rel,
                            "line": node.lineno,
                            "migration": {
                                "target": "register_controller",
                                "changes": [
                                    "Replace register_controllers() with register_controller()"
                                ],
                            },
                        }
                    )

            if not isinstance(node, ast.ClassDef):
                continue

            bases = [getattr(b, "id", getattr(b, "attr", "")) for b in node.bases]
            is_controller = any(b in _CONTROLLER_BASES for b in bases)

            decorator_info = None
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                    if dec.func.id == "api_controller":
                        is_controller = True
                        decorator_info = _parse_api_controller_decorator(dec)

            if not is_controller:
                continue

            class_endpoints: list[dict[str, Any]] = []
            for method in node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in method.decorator_list:
                    if not (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                    ):
                        continue
                    verb = decorator.func.attr
                    if verb not in _ROUTE_VERBS:
                        continue
                    path = ""
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = str(decorator.args[0].value)
                    class_endpoints.append(
                        {
                            "type": "endpoint",
                            "name": method.name,
                            "method": verb.upper(),
                            "path": path,
                            "file": rel,
                            "line": method.lineno,
                            "controller": node.name,
                            "migration": {
                                "target": "controller_method",
                                "changes": ["Convert @route decorator to @api decorator"],
                            },
                        }
                    )

            endpoints.extend(class_endpoints)
            uses_inject = any(
                "Inject" in (ast.get_source_segment(content, m) or "")
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            controllers.append(
                {
                    "type": "controller",
                    "name": node.name,
                    "app": app_label,
                    "file": rel,
                    "line": node.lineno,
                    "bases": bases,
                    "prefix": decorator_info["prefix"] if decorator_info else None,
                    "tags": decorator_info["tags"] if decorator_info else None,
                    "permissions": decorator_info["permissions"] if decorator_info else [],
                    "endpoints": class_endpoints,
                    "inject": uses_inject,
                    "migration": {
                        "target": "APIController",
                        "changes": [
                            "Replace ControllerBase with APIController",
                            "Replace api_controller decorator with prefix attribute",
                        ],
                    },
                }
            )
    except Exception:
        pass

    return controllers, endpoints, api_instances, registrations


def _parse_api_controller_decorator(dec: ast.Call) -> dict[str, Any]:
    """Extract prefix, tags, and permissions from an api_controller decorator."""
    info: dict[str, Any] = {"prefix": None, "tags": None, "permissions": []}

    if dec.args and isinstance(dec.args[0], ast.Constant):
        info["prefix"] = dec.args[0].value

    for kw in dec.keywords:
        if kw.arg == "tags":
            if isinstance(kw.value, ast.List):
                info["tags"] = [_value_str(e) for e in kw.value.elts]
        elif kw.arg == "permissions":
            if isinstance(kw.value, ast.List):
                info["permissions"] = [_value_str(e) for e in kw.value.elts]
            elif isinstance(kw.value, ast.Name):
                info["permissions"] = [_value_str(kw.value)]

    return info


def _value_str(value: ast.expr) -> str:
    """Convert an AST value node to a string."""
    if isinstance(value, ast.Constant):
        return str(value.value)
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return f"{_value_str(value.value)}.{value.attr}"
    if isinstance(value, ast.Call):
        return f"{_value_str(value.func)}(...)"
    if isinstance(value, ast.List):
        return "[...]"
    if isinstance(value, ast.Tuple):
        return "(...)"
    return "..."


def generate_ninja_extra_suggestions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate migration suggestions for Django Ninja Extra."""
    suggestions: list[dict[str, Any]] = []

    suggestions.append(
        {
            "title": "Update Import Statements",
            "description": "Replace ninja_extra imports with django_matt imports",
            "priority": "high",
            "steps": [
                "Replace 'from ninja_extra import ...' with 'from django_matt import ...'",
                "Replace NinjaExtraAPI with DjangoMattAPI",
                "Replace 'from ninja_extra.permissions import ...' with "
                "'from django_matt.permissions import ...'",
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
                    "Check SchemaModel usage against django-matt ModelSchema",
                ],
            }
        )

    if analysis["controllers"]:
        suggestions.append(
            {
                "title": "Convert ControllerBase Classes",
                "description": (
                    f"Found {len(analysis['controllers'])} controller classes "
                    "using ControllerBase/api_controller"
                ),
                "priority": "high",
                "steps": [
                    "Replace ControllerBase with APIController",
                    "Move api_controller decorator arguments to class attributes",
                    "Convert @route.get/post decorators to @api.get/post",
                    "Move permissions to permission_classes",
                ],
            }
        )

    if analysis["registrations"]:
        suggestions.append(
            {
                "title": "Update Controller Registration",
                "description": "Replace register_controllers with register_controller",
                "priority": "medium",
                "steps": [
                    "Replace api.register_controllers(...) with api.register_controller(...)",
                    "Call register_controller once per controller class",
                ],
            }
        )

    inject_hits = [c["name"] for c in analysis["controllers"] if c.get("inject")]
    if inject_hits:
        suggestions.append(
            {
                "title": "Convert Inject-based Dependency Injection",
                "description": f"Controllers using Inject(): {', '.join(inject_hits)}",
                "priority": "medium",
                "steps": [
                    "Replace 'service: Service = Inject()' parameters with the "
                    "django_matt.di @inject decorator",
                    "See django_matt.di for injectable/provides/singleton APIs",
                ],
            }
        )

    return suggestions


def generate_ninja_extra_controller_template(
    controllers: list[dict[str, Any]],
) -> str:
    """Generate APIController templates from ninja-extra ControllerBase classes."""
    lines = [
        '"""',
        "Controllers converted from Django Ninja Extra ControllerBase classes.",
        "",
        "Review and adapt these controllers for your needs.",
        '"""',
        "",
        "from django_matt import APIController, api",
        "",
        "",
    ]

    for c in controllers:
        name = c["name"]
        lines.append(f"class {name}(APIController):")
        lines.append(f'    """Converted from {c["name"]}."""')
        lines.append("")

        prefix = c.get("prefix")
        if prefix:
            lines.append(f"    prefix = {prefix!r}")
        else:
            lines.append("    # TODO: set the prefix from the original api_controller decorator")

        if c.get("tags"):
            lines.append(f"    tags = {c['tags']!r}")

        if c.get("permissions"):
            lines.append(f"    permission_classes = [{', '.join(c['permissions'])}]")

        lines.append("")

        for ep in c.get("endpoints", []):
            method_name = ep["name"]
            verb = ep["method"].lower()
            path = ep["path"]
            lines.append(f"    @api.{verb}({path!r})")
            if method_name.startswith("_"):
                method_name = method_name.lstrip("_") or "handler"
            lines.append(f"    async def {method_name}(self, request):")
            lines.append(f'        """Converted from {c["name"]}.{ep["name"]}."""')
            lines.append("        raise NotImplementedError")
            lines.append("")

        lines.append("")

    return "\n".join(lines)
