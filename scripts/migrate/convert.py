#!/usr/bin/env python3
"""
Best-effort mechanical converter for migrating to django-matt.

Generates stub files from DRF serializers, viewsets, Ninja schemas, and
FastAPI routes. NOT a complete migration -- meant as a starting point.

Usage:
    uv run python scripts/migrate/convert.py /path/to/app --framework drf
    uv run python scripts/migrate/convert.py /path/to/app --framework drf --output ./migrated
    uv run python scripts/migrate/convert.py /path/to/app --framework ninja
    uv run python scripts/migrate/convert.py /path/to/app --framework fastapi
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SerializerInfo:
    name: str
    model: str | None = None
    fields: list[str] | str | None = None
    exclude: list[str] | None = None
    read_only_fields: list[str] | None = None
    validators: list[str] = field(default_factory=list)
    extra_fields: list[str] = field(default_factory=list)


@dataclass
class ViewSetInfo:
    name: str
    model: str | None = None
    serializer: str | None = None
    permission_classes: list[str] = field(default_factory=list)
    filter_fields: list[str] = field(default_factory=list)
    search_fields: list[str] = field(default_factory=list)
    ordering_fields: list[str] = field(default_factory=list)
    ordering: str | None = None
    actions: list[str] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)
    base_class: str = "ModelViewSet"


@dataclass
class RouteInfo:
    name: str
    method: str
    path: str
    has_body: bool = False
    body_type: str | None = None
    response_type: str | None = None
    is_async: bool = False


def extract_string_value(node: ast.expr) -> str | None:
    """Extract a string value from an AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_list_strings(node: ast.expr) -> list[str] | None:
    """Extract a list of strings from an AST node."""
    if isinstance(node, ast.List):
        result = []
        for elt in node.elts:
            s = extract_string_value(elt)
            if s:
                result.append(s)
        return result
    return None


def extract_name(node: ast.expr) -> str | None:
    """Extract a name from a Name or Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


# --- DRF Extraction ---


def extract_drf_serializers(tree: ast.Module) -> list[SerializerInfo]:
    """Extract DRF serializer definitions from AST."""
    serializers = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        bases = [extract_name(b) for b in node.bases]
        if not any(
            b in ("ModelSerializer", "Serializer", "HyperlinkedModelSerializer")
            for b in bases
            if b
        ):
            continue

        info = SerializerInfo(name=node.name)

        # Parse Meta class
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            tname = extract_name(target)
                            if tname == "model":
                                info.model = extract_name(meta_item.value)
                            elif tname == "fields":
                                if isinstance(meta_item.value, ast.Constant) and meta_item.value.value == "__all__":
                                    info.fields = "__all__"
                                else:
                                    info.fields = extract_list_strings(meta_item.value)
                            elif tname == "exclude":
                                info.exclude = extract_list_strings(meta_item.value)
                            elif tname == "read_only_fields":
                                info.read_only_fields = extract_list_strings(meta_item.value)

            # Detect validate_* methods
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name.startswith("validate_"):
                    field_name = item.name[len("validate_"):]
                    info.validators.append(field_name)
                elif item.name == "validate":
                    info.validators.append("__root__")

            # Detect extra field declarations
            if isinstance(item, ast.Assign):
                for target in meta_item.targets if isinstance(item, ast.Assign) else []:
                    pass
                for target in item.targets:
                    tname = extract_name(target)
                    if tname and not tname.startswith("_"):
                        info.extra_fields.append(tname)

        serializers.append(info)

    return serializers


def extract_drf_viewsets(tree: ast.Module) -> list[ViewSetInfo]:
    """Extract DRF viewset definitions from AST."""
    viewsets = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        bases = [extract_name(b) for b in node.bases]
        base_names = [b for b in bases if b]

        viewset_bases = {
            "ModelViewSet", "ViewSet", "GenericViewSet", "ReadOnlyModelViewSet",
            "APIView", "GenericAPIView", "ListAPIView", "CreateAPIView",
            "RetrieveAPIView", "UpdateAPIView", "DestroyAPIView",
            "ListCreateAPIView", "RetrieveUpdateAPIView",
            "RetrieveUpdateDestroyAPIView",
        }

        if not any(b in viewset_bases for b in base_names):
            continue

        info = ViewSetInfo(name=node.name)
        info.base_class = next((b for b in base_names if b in viewset_bases), "ModelViewSet")
        info.mixins = [b for b in base_names if b not in viewset_bases]

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    tname = extract_name(target)
                    if tname == "queryset":
                        # Try to extract model from queryset
                        if isinstance(item.value, ast.Call):
                            if isinstance(item.value.func, ast.Attribute):
                                if isinstance(item.value.func.value, ast.Attribute):
                                    info.model = extract_name(item.value.func.value.value)
                    elif tname == "serializer_class":
                        info.serializer = extract_name(item.value)
                    elif tname == "permission_classes":
                        if isinstance(item.value, ast.List):
                            info.permission_classes = [extract_name(e) for e in item.value.elts if extract_name(e)]
                    elif tname == "filterset_fields":
                        info.filter_fields = extract_list_strings(item.value) or []
                    elif tname == "search_fields":
                        info.search_fields = extract_list_strings(item.value) or []
                    elif tname == "ordering_fields":
                        info.ordering_fields = extract_list_strings(item.value) or []
                    elif tname == "ordering":
                        info.ordering = extract_string_value(item.value)

            # Detect @action methods
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in item.decorator_list:
                    if isinstance(dec, ast.Call) and extract_name(dec.func) == "action":
                        info.actions.append(item.name)

        viewsets.append(info)

    return viewsets


# --- Generators ---


def generate_schema_from_serializer(s: SerializerInfo) -> str:
    """Generate ModelSchema code from a DRF serializer."""
    lines = []

    # Response schema
    schema_name = s.name.replace("Serializer", "Schema")
    lines.append(f"class {schema_name}(ModelSchema):")

    if s.model:
        lines.append("    class Config:")
        lines.append(f"        model = {s.model}")
        if s.fields == "__all__":
            lines.append("        include = '__all__'")
        elif s.fields:
            fields_str = ", ".join(f"'{f}'" for f in s.fields)
            lines.append(f"        include = [{fields_str}]")
        if s.exclude:
            exclude_str = ", ".join(f"'{f}'" for f in s.exclude)
            lines.append(f"        exclude = [{exclude_str}]")
    else:
        lines.append("    pass")

    # Add validators
    for field_name in s.validators:
        if field_name == "__root__":
            continue
        lines.append("")
        lines.append(f"    @model_validator('{field_name}')")
        lines.append(f"    def validate_{field_name}(cls, v):")
        lines.append(f"        # TODO: migrate validation logic from {s.name}.validate_{field_name}")
        lines.append("        return v")

    lines.append("")

    # Create schema (excludes read-only fields)
    if s.read_only_fields and s.fields and s.fields != "__all__":
        create_name = schema_name.replace("Schema", "CreateSchema")
        writable = [f for f in s.fields if f not in s.read_only_fields]
        fields_str = ", ".join(f"'{f}'" for f in writable)
        lines.append(f"class {create_name}(ModelSchema):")
        lines.append("    class Config:")
        lines.append(f"        model = {s.model}")
        lines.append(f"        include = [{fields_str}]")
        lines.append("")

        # Update schema (all optional)
        update_name = schema_name.replace("Schema", "UpdateSchema")
        lines.append(f"class {update_name}(ModelSchema):")
        lines.append("    class Config:")
        lines.append(f"        model = {s.model}")
        lines.append(f"        include = [{fields_str}]")
        lines.append("        optional = '__all__'")
        lines.append("")

    return "\n".join(lines)


def generate_service_from_viewset(vs: ViewSetInfo) -> str:
    """Generate a CRUDService stub from a DRF viewset."""
    model = vs.model or "YourModel"
    service_name = vs.name.replace("ViewSet", "Service")

    lines = [
        f'class {service_name}(CRUDService["{model}"]):',
        f"    model = {model}",
        "",
        "    def get_queryset(self):",
        "        return super().get_queryset()",
    ]

    for action in vs.actions:
        lines.append("")
        lines.append(f"    async def {action}(self, pk, user=None):")
        lines.append(f"        # TODO: migrate logic from {vs.name}.{action}")
        lines.append("        instance = await self.get(pk)")
        lines.append("        return instance")

    lines.append("")
    return "\n".join(lines)


def generate_controller_from_viewset(vs: ViewSetInfo) -> str:
    """Generate a Controller stub from a DRF viewset."""
    model = vs.model or "YourModel"
    controller_name = vs.name.replace("ViewSet", "Controller")
    service_name = vs.name.replace("ViewSet", "Service")
    schema_name = (vs.serializer or "").replace("Serializer", "Schema") or f"{model}Schema"
    create_schema = schema_name.replace("Schema", "CreateSchema")
    update_schema = schema_name.replace("Schema", "UpdateSchema")

    prefix = "/" + model.lower() + "s"

    lines = [
        f'@api.controller("{prefix}", tags=["{model}s"])',
        f"class {controller_name}(APIController):",
    ]

    # Permission classes
    perm_map = {
        "IsAuthenticated": "IsAuthenticated",
        "IsAdminUser": "IsAdmin",
        "AllowAny": "AllowAny",
        "IsAuthenticatedOrReadOnly": "IsAuthenticatedOrReadOnly",
    }
    if vs.permission_classes:
        mapped = [perm_map.get(p, p) for p in vs.permission_classes]
        lines.append(f"    permission_classes = [{', '.join(mapped)}]")

    lines.append("")
    lines.append("    def __init__(self):")
    lines.append(f"        self.service = {service_name}()")
    lines.append("        super().__init__()")

    # CRUD methods based on base class
    crud_ops = set()
    if vs.base_class in ("ModelViewSet", "ListCreateAPIView", "ListAPIView"):
        crud_ops.add("list")
    if vs.base_class in ("ModelViewSet", "ListCreateAPIView", "CreateAPIView"):
        crud_ops.add("create")
    if vs.base_class in ("ModelViewSet", "RetrieveAPIView", "RetrieveUpdateAPIView", "RetrieveDestroyAPIView", "RetrieveUpdateDestroyAPIView", "ReadOnlyModelViewSet"):
        crud_ops.add("retrieve")
    if vs.base_class in ("ModelViewSet", "UpdateAPIView", "RetrieveUpdateAPIView", "RetrieveUpdateDestroyAPIView"):
        crud_ops.add("update")
    if vs.base_class in ("ModelViewSet", "DestroyAPIView", "RetrieveDestroyAPIView", "RetrieveUpdateDestroyAPIView"):
        crud_ops.add("delete")
    if vs.base_class == "ReadOnlyModelViewSet":
        crud_ops.add("list")

    if "list" in crud_ops:
        lines.append("")
        lines.append('    @get("/")')
        lines.append(f"    async def list_{model.lower()}s(self, request):")
        lines.append("        page = int(request.GET.get('page', 1))")
        lines.append("        items, total = await self.service.list(page=page)")
        lines.append("        return {")
        lines.append(f'            "items": [{schema_name}.from_orm_fast(i).model_dump() for i in items],')
        lines.append('            "total": total,')
        lines.append("        }")

    if "create" in crud_ops:
        lines.append("")
        lines.append('    @post("/")')
        lines.append(f"    async def create_{model.lower()}(self, request, data: {create_schema}):")
        lines.append("        instance = await self.service.create(data.model_dump(), user=request.user)")
        lines.append(f"        return {schema_name}.from_orm(instance).model_dump()")

    if "retrieve" in crud_ops:
        lines.append("")
        lines.append('    @get("/{id}")')
        lines.append(f"    async def get_{model.lower()}(self, request, id: int):")
        lines.append("        instance = await self.service.get(id)")
        lines.append(f"        return {schema_name}.from_orm(instance).model_dump()")

    if "update" in crud_ops:
        lines.append("")
        lines.append('    @put("/{id}")')
        lines.append(f"    async def update_{model.lower()}(self, request, id: int, data: {update_schema}):")
        lines.append("        instance = await self.service.update(id, data.model_dump(), user=request.user)")
        lines.append(f"        return {schema_name}.from_orm(instance).model_dump()")

    if "delete" in crud_ops:
        lines.append("")
        lines.append('    @delete("/{id}")')
        lines.append(f"    async def delete_{model.lower()}(self, request, id: int):")
        lines.append("        await self.service.delete(id)")
        lines.append('        return {"deleted": True}')

    for action in vs.actions:
        lines.append("")
        lines.append(f'    @post("/{{id}}/{action}")')
        lines.append(f"    async def {action}(self, request, id: int):")
        lines.append(f"        instance = await self.service.{action}(id, user=request.user)")
        lines.append(f"        return {schema_name}.from_orm(instance).model_dump()")

    lines.append("")
    return "\n".join(lines)


def generate_viewset_from_viewset(vs: ViewSetInfo) -> str:
    """Generate an APIViewSet stub (declarative CRUD) from a DRF viewset."""
    model = vs.model or "YourModel"
    schema_name = (vs.serializer or "").replace("Serializer", "Schema") or f"{model}Schema"
    create_schema = schema_name.replace("Schema", "CreateSchema")
    update_schema = schema_name.replace("Schema", "UpdateSchema")

    lines = [
        f"class {vs.name.replace('ViewSet', '')}ViewSet(APIViewSet):",
        f"    model = {model}",
        f'    prefix = "{model.lower()}s"',
        f'    tags = ["{model}s"]',
        f"    default_response_schema = {schema_name}",
        f"    default_request_schema = {create_schema}",
    ]

    if vs.filter_fields:
        ff = ", ".join(f"'{f}'" for f in vs.filter_fields)
        lines.append(f"    filter_fields = [{ff}]")
    if vs.search_fields:
        sf = ", ".join(f"'{f}'" for f in vs.search_fields)
        lines.append(f"    search_fields = [{sf}]")
    if vs.ordering_fields:
        of = ", ".join(f"'{f}'" for f in vs.ordering_fields)
        lines.append(f"    ordering_fields = [{of}]")
    if vs.ordering:
        lines.append(f"    ordering = '{vs.ordering}'")

    lines.append("")
    lines.append("    list = ListView(pagination=True, page_size=20)")
    lines.append("    create = CreateView()")
    lines.append("    read = ReadView()")
    lines.append(f"    update = UpdateView(request_schema={update_schema})")
    lines.append("    delete = DeleteView()")

    lines.append("")
    return "\n".join(lines)


# --- Main conversion ---


def convert_drf(app_path: Path) -> dict[str, str]:
    """Convert DRF files to django-matt stubs."""
    outputs: dict[str, str] = {}

    all_serializers: list[SerializerInfo] = []
    all_viewsets: list[ViewSetInfo] = []

    for py_file in sorted(app_path.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        all_serializers.extend(extract_drf_serializers(tree))
        all_viewsets.extend(extract_drf_viewsets(tree))

    # Generate schemas.py
    if all_serializers:
        schema_lines = [
            "from django_matt.core.schema import ModelSchema, model_validator",
            "",
            "# TODO: import your Django models here",
            "",
            "",
        ]
        for s in all_serializers:
            schema_lines.append(generate_schema_from_serializer(s))

        outputs["schemas.py"] = "\n".join(schema_lines)

    # Generate services.py
    if all_viewsets:
        service_lines = [
            "from django_matt.services.base import CRUDService",
            "",
            "# TODO: import your Django models here",
            "",
            "",
        ]
        for vs in all_viewsets:
            service_lines.append(generate_service_from_viewset(vs))

        outputs["services.py"] = "\n".join(service_lines)

    # Generate controllers.py
    if all_viewsets:
        controller_lines = [
            "from django_matt.core.controller import APIController",
            "from django_matt.core.router import get, post, put, patch, delete",
            "from django_matt.permissions.common import IsAuthenticated, IsAdmin, AllowAny",
            "",
            "# TODO: import your schemas and services",
            "# from .schemas import ...",
            "# from .services import ...",
            "",
            "# TODO: replace 'api' with your MattAPI instance",
            "# from myproject.api import api",
            "",
            "",
        ]
        for vs in all_viewsets:
            controller_lines.append(generate_controller_from_viewset(vs))

        outputs["controllers.py"] = "\n".join(controller_lines)

    # Generate viewsets.py (alternative declarative approach)
    if all_viewsets:
        viewset_lines = [
            "from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView",
            "",
            "# TODO: import your Django models and schemas",
            "",
            "",
        ]
        for vs in all_viewsets:
            viewset_lines.append(generate_viewset_from_viewset(vs))

        outputs["viewsets.py"] = "\n".join(viewset_lines)

    return outputs


def convert_ninja(app_path: Path) -> dict[str, str]:
    """Convert Django Ninja files to django-matt stubs."""
    outputs: dict[str, str] = {}

    for py_file in sorted(app_path.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
        except (UnicodeDecodeError, OSError):
            continue

        # Simple text replacements for Ninja -> django-matt
        converted = source
        converted = re.sub(r"from ninja import", "from django_matt.core.schema import ModelSchema\nfrom django_matt.core.router import", converted)
        converted = re.sub(r"from ninja\.schema import", "from django_matt.core.schema import", converted)
        converted = converted.replace("NinjaAPI(", "MattAPI(")
        converted = converted.replace("class Meta:", "class Config:")
        converted = re.sub(r"(\s+)fields\s*=", r"\1include =", converted)
        converted = re.sub(r"(\s+)fields_optional\s*=", r"\1optional =", converted)

        if converted != source:
            rel_path = py_file.relative_to(app_path)
            outputs[str(rel_path)] = (
                "# AUTO-CONVERTED from Django Ninja -- review and fix\n"
                + converted
            )

    return outputs


def convert_fastapi(app_path: Path) -> dict[str, str]:
    """Convert FastAPI files to django-matt stubs."""
    outputs: dict[str, str] = {}

    notes = [
        "# FastAPI -> django-matt conversion notes:",
        "#",
        "# 1. SQLAlchemy models must be manually converted to Django models",
        "# 2. Pydantic schemas are largely compatible -- keep or convert to ModelSchema",
        "# 3. Depends(get_db) is removed -- Django ORM handles connections",
        "# 4. Route functions -> controller methods with 'request' as first param",
        "# 5. Use the LLM prompt (llm-prompt-fastapi.md) for complex conversions",
        "#",
    ]

    for py_file in sorted(app_path.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
        except (UnicodeDecodeError, OSError):
            continue

        if "fastapi" not in source.lower() and "sqlalchemy" not in source.lower():
            continue

        converted = source
        converted = re.sub(r"from fastapi import.*\n", "from django_matt.core.controller import APIController\nfrom django_matt.core.router import get, post, put, patch, delete\n", converted)
        converted = re.sub(r"from fastapi.routing import.*\n", "", converted)
        converted = re.sub(r"db:\s*Session\s*=\s*Depends\(get_db\),?\s*", "", converted)
        converted = re.sub(r"current_user:\s*\w+\s*=\s*Depends\(get_current_user\),?\s*", "", converted)

        if converted != source:
            rel_path = py_file.relative_to(app_path)
            outputs[str(rel_path)] = "\n".join(notes) + "\n\n" + converted

    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="Convert existing API code to django-matt stubs"
    )
    parser.add_argument("path", help="Path to the app directory")
    parser.add_argument(
        "--framework",
        choices=["drf", "ninja", "fastapi"],
        required=True,
        help="Source framework",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output directory (default: stdout)",
    )
    args = parser.parse_args()

    app_path = Path(args.path).resolve()
    if not app_path.is_dir():
        print(f"Error: {app_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    converters = {
        "drf": convert_drf,
        "ninja": convert_ninja,
        "fastapi": convert_fastapi,
    }

    outputs = converters[args.framework](app_path)

    if not outputs:
        print(f"No {args.framework} code found in {app_path}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in outputs.items():
            out_file = out_dir / filename
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content)
            print(f"  wrote {out_file}")
        print(f"\nGenerated {len(outputs)} file(s) in {out_dir}")
    else:
        for filename, content in outputs.items():
            print(f"\n{'=' * 60}")
            print(f"# {filename}")
            print(f"{'=' * 60}")
            print(content)


if __name__ == "__main__":
    main()
