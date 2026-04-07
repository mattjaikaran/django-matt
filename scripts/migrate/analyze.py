#!/usr/bin/env python3
"""
Analyze an existing Django/FastAPI project and generate a migration report.

Scans for DRF serializers, viewsets, routers; Django Ninja routers/schemas;
FastAPI routers/depends. Outputs a structured migration plan.

Usage:
    uv run python scripts/migrate/analyze.py /path/to/project
    uv run python scripts/migrate/analyze.py /path/to/project --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileAnalysis:
    path: str
    framework: str = ""
    models: list[str] = field(default_factory=list)
    serializers: list[str] = field(default_factory=list)
    schemas: list[str] = field(default_factory=list)
    viewsets: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    routers: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    auth_patterns: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ProjectAnalysis:
    root: str
    framework: str = "unknown"
    files: list[FileAnalysis] = field(default_factory=list)
    total_models: int = 0
    total_serializers: int = 0
    total_schemas: int = 0
    total_viewsets: int = 0
    total_views: int = 0
    total_routers: int = 0
    total_permissions: int = 0
    auth_patterns: set[str] = field(default_factory=set)
    migration_notes: list[str] = field(default_factory=list)


# --- Import detection ---

DRF_IMPORTS = {
    "rest_framework",
    "rest_framework.serializers",
    "rest_framework.viewsets",
    "rest_framework.views",
    "rest_framework.routers",
    "rest_framework.permissions",
    "rest_framework.decorators",
    "rest_framework.response",
    "rest_framework.generics",
    "rest_framework.mixins",
    "rest_framework.filters",
    "rest_framework.pagination",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "drf_yasg",
}

NINJA_IMPORTS = {
    "ninja",
    "ninja.router",
    "ninja.schema",
    "ninja.security",
    "ninja.pagination",
    "ninja_extra",
    "ninja_crud",
    "ninja_jwt",
}

FASTAPI_IMPORTS = {
    "fastapi",
    "fastapi.routing",
    "fastapi.security",
    "fastapi.middleware",
    "fastapi.responses",
    "starlette",
    "sqlalchemy",
    "sqlmodel",
}

# --- Base class detection ---

DRF_BASES = {
    "ModelSerializer",
    "Serializer",
    "HyperlinkedModelSerializer",
    "ListSerializer",
    "ModelViewSet",
    "ViewSet",
    "GenericViewSet",
    "APIView",
    "GenericAPIView",
    "ListAPIView",
    "CreateAPIView",
    "RetrieveAPIView",
    "UpdateAPIView",
    "DestroyAPIView",
    "ListCreateAPIView",
    "RetrieveUpdateAPIView",
    "RetrieveDestroyAPIView",
    "RetrieveUpdateDestroyAPIView",
    "BasePermission",
    "IsAuthenticated",
    "IsAdminUser",
    "DefaultRouter",
    "SimpleRouter",
    "UserRateThrottle",
    "AnonRateThrottle",
    "PageNumberPagination",
    "LimitOffsetPagination",
    "CursorPagination",
}

NINJA_BASES = {
    "NinjaAPI",
    "Router",
    "Schema",
    "ModelSchema",
    "ControllerBase",
    "HttpBearer",
    "APIController",
}

FASTAPI_BASES = {
    "FastAPI",
    "APIRouter",
    "BaseModel",
    "Depends",
    "HTTPException",
    "BackgroundTasks",
}

DJANGO_MODEL_BASES = {"Model", "AbstractUser", "AbstractBaseUser"}


def detect_imports(tree: ast.Module) -> set[str]:
    """Extract all import module names from an AST."""
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
                modules.add(node.module)
    return modules


def detect_imported_names(tree: ast.Module) -> set[str]:
    """Extract all imported names (the 'from X import Y' Y part)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def get_base_names(node: ast.ClassDef) -> list[str]:
    """Get base class names from a class definition."""
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
        elif isinstance(base, ast.Subscript):
            if isinstance(base.value, ast.Name):
                bases.append(base.value.id)
            elif isinstance(base.value, ast.Attribute):
                bases.append(base.value.attr)
    return bases


def analyze_file(filepath: Path) -> FileAnalysis | None:
    """Analyze a single Python file."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return None

    analysis = FileAnalysis(path=str(filepath))
    imports = detect_imports(tree)
    imported_names = detect_imported_names(tree)

    # Detect framework
    if imports & DRF_IMPORTS:
        analysis.framework = "drf"
    elif imports & NINJA_IMPORTS:
        analysis.framework = "ninja"
    elif imports & FASTAPI_IMPORTS:
        analysis.framework = "fastapi"

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = get_base_names(node)

            # Models
            if any(b in DJANGO_MODEL_BASES for b in bases):
                analysis.models.append(node.name)

            # DRF serializers
            if any(b in ("ModelSerializer", "Serializer", "HyperlinkedModelSerializer", "ListSerializer") for b in bases):
                analysis.serializers.append(node.name)

            # DRF viewsets
            if any(b in ("ModelViewSet", "ViewSet", "GenericViewSet", "ReadOnlyModelViewSet") for b in bases):
                analysis.viewsets.append(node.name)

            # DRF generic views
            if any(b in (
                "APIView", "GenericAPIView", "ListAPIView", "CreateAPIView",
                "RetrieveAPIView", "UpdateAPIView", "DestroyAPIView",
                "ListCreateAPIView", "RetrieveUpdateAPIView",
                "RetrieveDestroyAPIView", "RetrieveUpdateDestroyAPIView",
            ) for b in bases):
                analysis.views.append(node.name)

            # DRF permissions
            if any(b in ("BasePermission", "IsAuthenticated", "IsAdminUser") for b in bases):
                analysis.permissions.append(node.name)

            # DRF pagination
            if any(b in ("PageNumberPagination", "LimitOffsetPagination", "CursorPagination") for b in bases):
                analysis.filters.append(f"pagination:{node.name}")

            # DRF filters
            if any(b in ("FilterSet", "BaseFilterBackend") for b in bases):
                analysis.filters.append(f"filter:{node.name}")

            # Ninja schemas
            if analysis.framework == "ninja" and any(b in ("Schema", "ModelSchema") for b in bases):
                analysis.schemas.append(node.name)

            # Ninja controllers
            if any(b in ("ControllerBase",) for b in bases):
                analysis.views.append(node.name)

            # FastAPI BaseModel schemas
            if analysis.framework == "fastapi" and "BaseModel" in bases:
                analysis.schemas.append(node.name)

            # SQLAlchemy models
            if any(b in ("Base", "DeclarativeBase") for b in bases):
                analysis.models.append(node.name)

        # Detect function-based views / route registrations
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                dec_name = ""
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute):
                        dec_name = decorator.func.attr
                    elif isinstance(decorator.func, ast.Name):
                        dec_name = decorator.func.id
                elif isinstance(decorator, ast.Attribute):
                    dec_name = decorator.attr
                elif isinstance(decorator, ast.Name):
                    dec_name = decorator.id

                if dec_name in ("api_view", "action"):
                    analysis.views.append(node.name)
                if dec_name in ("get", "post", "put", "patch", "delete"):
                    analysis.views.append(node.name)

        # Detect router registrations
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        name = ""
                        if isinstance(func, ast.Name):
                            name = func.id
                        elif isinstance(func, ast.Attribute):
                            name = func.attr
                        if name in ("DefaultRouter", "SimpleRouter", "Router", "NinjaAPI", "FastAPI", "APIRouter"):
                            analysis.routers.append(target.id)

    # Detect auth patterns
    if "rest_framework_simplejwt" in imports or "ninja_jwt" in imports:
        analysis.auth_patterns.append("jwt")
    if "rest_framework.authentication" in imports:
        analysis.auth_patterns.append("token_auth")
    if "oauth2_provider" in imports:
        analysis.auth_patterns.append("oauth2")
    if "allauth" in imports or "dj_rest_auth" in imports:
        analysis.auth_patterns.append("allauth")
    if "HttpBearer" in imported_names:
        analysis.auth_patterns.append("bearer")
    if "oauth2_scheme" in imported_names or "OAuth2PasswordBearer" in imported_names:
        analysis.auth_patterns.append("oauth2")

    # Detect Depends usage (FastAPI DI)
    if "Depends" in imported_names:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "Depends":
                    if node.args and isinstance(node.args[0], ast.Name):
                        analysis.dependencies.append(node.args[0].id)

    return analysis


def analyze_project(root: Path) -> ProjectAnalysis:
    """Analyze an entire project directory."""
    project = ProjectAnalysis(root=str(root))

    # Find all Python files (skip common non-project directories)
    skip_dirs = {
        ".venv", "venv", "env", ".env", "node_modules", "__pycache__",
        ".git", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
        ".eggs", "*.egg-info", "migrations",
    }

    py_files = []
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if not parts & skip_dirs:
            py_files.append(p)

    # Analyze each file
    framework_votes: dict[str, int] = {"drf": 0, "ninja": 0, "fastapi": 0}

    for filepath in sorted(py_files):
        analysis = analyze_file(filepath)
        if analysis is None:
            continue

        # Only include files with relevant content
        has_content = (
            analysis.models
            or analysis.serializers
            or analysis.schemas
            or analysis.viewsets
            or analysis.views
            or analysis.routers
            or analysis.permissions
            or analysis.auth_patterns
            or analysis.filters
            or analysis.dependencies
        )

        if not has_content:
            continue

        # Make path relative
        try:
            analysis.path = str(filepath.relative_to(root))
        except ValueError:
            pass

        project.files.append(analysis)

        if analysis.framework:
            framework_votes[analysis.framework] += 1

        project.total_models += len(analysis.models)
        project.total_serializers += len(analysis.serializers)
        project.total_schemas += len(analysis.schemas)
        project.total_viewsets += len(analysis.viewsets)
        project.total_views += len(analysis.views)
        project.total_routers += len(analysis.routers)
        project.total_permissions += len(analysis.permissions)
        project.auth_patterns.update(analysis.auth_patterns)

    # Determine primary framework
    if framework_votes["drf"] > 0:
        project.framework = "drf"
    elif framework_votes["ninja"] > 0:
        project.framework = "ninja"
    elif framework_votes["fastapi"] > 0:
        project.framework = "fastapi"
    else:
        project.framework = "django"

    # Generate migration notes
    project.migration_notes = generate_notes(project)

    return project


def generate_notes(project: ProjectAnalysis) -> list[str]:
    """Generate migration advice based on analysis."""
    notes = []

    if project.framework == "drf":
        notes.append("Framework: Django REST Framework")
        notes.append(f"  {project.total_serializers} serializer(s) -> ModelSchema conversions")
        notes.append(f"  {project.total_viewsets} viewset(s) -> Controller or APIViewSet conversions")
        notes.append(f"  {project.total_views} view(s) -> controller method conversions")
        if project.total_permissions > 0:
            notes.append(f"  {project.total_permissions} custom permission(s) -> BasePermission subclasses")
        notes.append("")
        notes.append("Recommended approach:")
        notes.append("  1. Convert serializers to ModelSchema (schemas.py)")
        notes.append("  2. Create service layer from viewset logic (services.py)")
        notes.append("  3. Convert viewsets to thin controllers (controllers.py)")
        notes.append("  4. Map permissions to django-matt equivalents")
        notes.append("  5. Use llm-prompt-drf.md for complex conversions")

    elif project.framework == "ninja":
        notes.append("Framework: Django Ninja")
        notes.append(f"  {project.total_schemas} schema(s) -> ModelSchema conversions (mostly compatible)")
        notes.append(f"  {project.total_views} view(s)/controller(s) -> Controller conversions")
        notes.append("")
        notes.append("Recommended approach:")
        notes.append("  1. Schemas: change class Meta -> class Config, fields -> include")
        notes.append("  2. NinjaAPI() -> MattAPI()")
        notes.append("  3. Router -> APIRouter or controller")
        notes.append("  4. Extract business logic to services")
        notes.append("  5. Use llm-prompt-ninja.md for complex conversions")

    elif project.framework == "fastapi":
        notes.append("Framework: FastAPI")
        notes.append(f"  {project.total_models} SQLAlchemy model(s) -> Django model conversions")
        notes.append(f"  {project.total_schemas} Pydantic schema(s) -> mostly reusable")
        notes.append(f"  {project.total_views} route(s) -> controller method conversions")
        if project.dependencies:
            dep_names = set()
            for f in project.files:
                dep_names.update(f.dependencies)
            notes.append(f"  {len(dep_names)} Depends() dependency(ies) -> service/DI conversions")
        notes.append("")
        notes.append("Recommended approach:")
        notes.append("  1. Convert SQLAlchemy models to Django models")
        notes.append("  2. Run makemigrations + migrate")
        notes.append("  3. Reuse Pydantic schemas or convert to ModelSchema")
        notes.append("  4. Replace Depends(get_db) with service layer")
        notes.append("  5. Convert route functions to controller methods")
        notes.append("  6. Use llm-prompt-fastapi.md for complex conversions")

    else:
        notes.append("Framework: Plain Django (no API framework detected)")
        notes.append(f"  {project.total_models} model(s)")
        notes.append(f"  {project.total_views} view(s) -> controller conversions")
        notes.append("")
        notes.append("Recommended approach:")
        notes.append("  1. Create ModelSchema for each model")
        notes.append("  2. Create service layer")
        notes.append("  3. Create controllers")
        notes.append("  4. Use llm-prompt-universal.md for conversions")

    if "jwt" in project.auth_patterns:
        notes.append("")
        notes.append("Auth: JWT detected -> use django-matt built-in JWT (@jwt_required)")
    if "oauth2" in project.auth_patterns:
        notes.append("Auth: OAuth2 detected -> use django_matt.auth.oauth module")
    if "allauth" in project.auth_patterns:
        notes.append("Auth: allauth detected -> can keep allauth or migrate to django-matt auth")

    return notes


def format_text(project: ProjectAnalysis) -> str:
    """Format analysis as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("django-matt Migration Analysis")
    lines.append("=" * 60)
    lines.append(f"Project: {project.root}")
    lines.append(f"Detected framework: {project.framework}")
    lines.append("")
    lines.append("--- Summary ---")
    lines.append(f"Models:       {project.total_models}")
    lines.append(f"Serializers:  {project.total_serializers}")
    lines.append(f"Schemas:      {project.total_schemas}")
    lines.append(f"ViewSets:     {project.total_viewsets}")
    lines.append(f"Views:        {project.total_views}")
    lines.append(f"Routers:      {project.total_routers}")
    lines.append(f"Permissions:  {project.total_permissions}")
    lines.append(f"Auth:         {', '.join(sorted(project.auth_patterns)) or 'none detected'}")
    lines.append("")

    if project.files:
        lines.append("--- File Details ---")
        for f in project.files:
            items = []
            if f.models:
                items.append(f"models: {', '.join(f.models)}")
            if f.serializers:
                items.append(f"serializers: {', '.join(f.serializers)}")
            if f.schemas:
                items.append(f"schemas: {', '.join(f.schemas)}")
            if f.viewsets:
                items.append(f"viewsets: {', '.join(f.viewsets)}")
            if f.views:
                items.append(f"views: {', '.join(f.views)}")
            if f.routers:
                items.append(f"routers: {', '.join(f.routers)}")
            if f.permissions:
                items.append(f"permissions: {', '.join(f.permissions)}")
            if f.auth_patterns:
                items.append(f"auth: {', '.join(f.auth_patterns)}")
            if f.filters:
                items.append(f"filters: {', '.join(f.filters)}")
            if items:
                lines.append(f"\n  {f.path}")
                for item in items:
                    lines.append(f"    {item}")
        lines.append("")

    lines.append("--- Migration Plan ---")
    for note in project.migration_notes:
        lines.append(note)

    lines.append("")
    return "\n".join(lines)


def format_json(project: ProjectAnalysis) -> str:
    """Format analysis as JSON."""
    data = {
        "root": project.root,
        "framework": project.framework,
        "summary": {
            "models": project.total_models,
            "serializers": project.total_serializers,
            "schemas": project.total_schemas,
            "viewsets": project.total_viewsets,
            "views": project.total_views,
            "routers": project.total_routers,
            "permissions": project.total_permissions,
            "auth_patterns": sorted(project.auth_patterns),
        },
        "files": [],
        "migration_notes": project.migration_notes,
    }

    for f in project.files:
        file_data: dict[str, object] = {"path": f.path}
        if f.framework:
            file_data["framework"] = f.framework
        if f.models:
            file_data["models"] = f.models
        if f.serializers:
            file_data["serializers"] = f.serializers
        if f.schemas:
            file_data["schemas"] = f.schemas
        if f.viewsets:
            file_data["viewsets"] = f.viewsets
        if f.views:
            file_data["views"] = f.views
        if f.routers:
            file_data["routers"] = f.routers
        if f.permissions:
            file_data["permissions"] = f.permissions
        if f.auth_patterns:
            file_data["auth_patterns"] = f.auth_patterns
        if f.filters:
            file_data["filters"] = f.filters
        if f.dependencies:
            file_data["dependencies"] = f.dependencies
        data["files"].append(file_data)

    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a project for migration to django-matt"
    )
    parser.add_argument("path", help="Path to the project root")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    project = analyze_project(root)

    if args.format == "json":
        print(format_json(project))
    else:
        print(format_text(project))


if __name__ == "__main__":
    main()
