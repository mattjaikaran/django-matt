"""
Django Ninja codemods.

AST-based transformations for migrating Django Ninja code to django-matt.
"""

from __future__ import annotations

import ast

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.patterns import (
    remove_response_wrapper,
    rename_all_references,
    rewrite_imports,
    transform_decorators,
)


class NinjaAPIToMattAPI(Codemod):
    """Convert NinjaAPI() to MattAPI() and Router() to APIController."""

    name = "ninja-api-to-matt-api"
    source_framework = "ninja"
    description = "Convert NinjaAPI/Router to MattAPI/APIController"

    def detect(self, source: str, filename: str) -> bool:
        return "ninja" in source and ("NinjaAPI" in source or "Router" in source)

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite imports
        changes.extend(
            rewrite_imports(
                tree,
                "ninja",
                "django_matt",
                {"NinjaAPI": "MattAPI", "Router": "APIRouter"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "ninja.router",
                "django_matt.core.router",
                {"Router": "APIRouter"},
            )
        )

        # Find and rename NinjaAPI() instantiations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "NinjaAPI":
                    if isinstance(node.func, ast.Name):
                        node.func.id = "MattAPI"
                    elif isinstance(node.func, ast.Attribute):
                        node.func.attr = "MattAPI"
                    changes.append("Replaced NinjaAPI() -> MattAPI()")

                elif func_name == "Router":
                    if isinstance(node.func, ast.Name):
                        node.func.id = "APIRouter"
                    elif isinstance(node.func, ast.Attribute):
                        node.func.attr = "APIRouter"
                    changes.append("Replaced Router() -> APIRouter()")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.95,
        )


class NinjaSchemaToMattSchema(Codemod):
    """Convert Ninja Schema imports to django-matt Schema."""

    name = "ninja-schema-to-matt-schema"
    source_framework = "ninja"
    description = "Convert Ninja Schema to django-matt Schema"

    def detect(self, source: str, filename: str) -> bool:
        return ("from ninja" in source or "import ninja" in source) and "Schema" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite Schema imports
        changes.extend(
            rewrite_imports(
                tree,
                "ninja",
                "django_matt.core.schema",
                {"Schema": "ModelSchema", "ModelSchema": "ModelSchema"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "ninja.schema",
                "django_matt.core.schema",
                {"Schema": "ModelSchema"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "ninja.orm",
                "django_matt.core.schema",
                {"create_schema": "create_schema_from_model"},
            )
        )

        # Rename create_schema() calls to create_schema_from_model()
        count = rename_all_references(tree, "create_schema", "create_schema_from_model")
        if count > 0:
            changes.append(f"Renamed {count} create_schema() -> create_schema_from_model()")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.95,
        )


class NinjaRouterToController(Codemod):
    """Convert Ninja router-decorated functions into APIController classes."""

    name = "ninja-router-to-controller"
    source_framework = "ninja"
    description = "Convert Ninja @router.get/post functions to controller methods"

    def detect(self, source: str, filename: str) -> bool:
        return "router" in source and ("@router." in source or "@api." in source)

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Find router-decorated functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dec_changes = transform_decorators(node, "router", "api")
                changes.extend(dec_changes)

                # Unwrap Response() if used
                changes.extend(remove_response_wrapper(node))

        if changes:
            warnings.append(
                "Consider grouping endpoint functions into APIController classes "
                "for better organization"
            )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.85,
        )


class NinjaExceptionHandlerToFilter(Codemod):
    """Convert Ninja @api.exception_handler to django-matt exception filters."""

    name = "ninja-exception-handler-to-filter"
    source_framework = "ninja"
    description = "Convert Ninja exception handlers to django-matt exception filters"

    def detect(self, source: str, filename: str) -> bool:
        return "exception_handler" in source and "ninja" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if dec.func.attr == "exception_handler":
                            warnings.append(
                                f"@api.exception_handler on {node.name}() -> "
                                "use django_matt.exceptions @catch decorator or ExceptionFilter"
                            )
                            changes.append(
                                f"Flagged {node.name}() for conversion to ExceptionFilter"
                            )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.6,
        )


class NinjaAuthToJWT(Codemod):
    """Convert Ninja HttpBearer auth to django-matt JWT auth."""

    name = "ninja-auth-to-jwt"
    source_framework = "ninja"
    description = "Convert Ninja HttpBearer to django-matt JWT"

    def detect(self, source: str, filename: str) -> bool:
        return "HttpBearer" in source and "ninja" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite auth imports
        changes.extend(
            rewrite_imports(
                tree,
                "ninja.security",
                "django_matt.auth",
                {"HttpBearer": "jwt_required"},
            )
        )

        # Find HttpBearer subclasses and flag them
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name == "HttpBearer":
                        warnings.append(
                            f"Class {node.name}(HttpBearer) -> replace with @jwt_required "
                            "decorator or IsAuthenticated permission class"
                        )
                        changes.append(f"Flagged {node.name} for JWT migration")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.7,
        )


class NinjaCodemods:
    """Collection of all Django Ninja codemods."""

    @staticmethod
    def all() -> list[Codemod]:
        return [
            NinjaAPIToMattAPI(),
            NinjaSchemaToMattSchema(),
            NinjaRouterToController(),
            NinjaExceptionHandlerToFilter(),
            NinjaAuthToJWT(),
        ]
