# file-length-max: 450
"""
FastAPI codemods.

AST-based transformations for migrating FastAPI code to django-matt.
"""

from __future__ import annotations

import ast

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.patterns import (
    add_import,
    remove_response_wrapper,
    rewrite_imports,
    transform_decorators,
)


class FastAPIAppToMattAPI(Codemod):
    """Convert FastAPI() to MattAPI() and APIRouter() to APIController."""

    name = "fastapi-app-to-matt-api"
    source_framework = "fastapi"
    description = "Convert FastAPI/APIRouter to MattAPI/APIController"

    def detect(self, source: str, filename: str) -> bool:
        return "fastapi" in source.lower() and ("FastAPI" in source or "APIRouter" in source)

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite imports
        changes.extend(
            rewrite_imports(
                tree,
                "fastapi",
                "django_matt",
                {
                    "FastAPI": "MattAPI",
                    "APIRouter": "APIRouter",
                    "Depends": "Depends",
                    "HTTPException": "APIError",
                    "Query": "Query",
                    "Path": "Path",
                    "Body": "Body",
                    "Header": "Header",
                },
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "fastapi.responses",
                "django.http",
                {"JSONResponse": "JsonResponse"},
            )
        )

        # Rename FastAPI() instantiations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "FastAPI":
                    if isinstance(node.func, ast.Name):
                        node.func.id = "MattAPI"
                    elif isinstance(node.func, ast.Attribute):
                        node.func.attr = "MattAPI"
                    changes.append("Replaced FastAPI() -> MattAPI()")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.9,
        )


class FastAPIRouterToController(Codemod):
    """Convert FastAPI @app.get/post functions to controller method patterns."""

    name = "fastapi-router-to-controller"
    source_framework = "fastapi"
    description = "Convert FastAPI route decorators to django-matt patterns"

    def detect(self, source: str, filename: str) -> bool:
        return ("@app." in source or "@router." in source) and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Transform @app.get/post/etc -> @api.get/post/etc
                changes.extend(transform_decorators(node, "app", "api"))
                changes.extend(transform_decorators(node, "router", "api"))

                # Unwrap JSONResponse / Response
                changes.extend(remove_response_wrapper(node))

        if changes:
            add_import(tree, "django_matt.core.router", ["get", "post", "put", "patch", "delete"])
            warnings.append("Consider grouping endpoint functions into APIController classes")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.8,
        )


class FastAPIDependsToMattDI(Codemod):
    """Convert FastAPI Depends() to django-matt DI system."""

    name = "fastapi-depends-to-matt-di"
    source_framework = "fastapi"
    description = "Convert FastAPI Depends() to django-matt dependency injection"

    def detect(self, source: str, filename: str) -> bool:
        return "Depends" in source and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite Depends import
        changes.extend(
            rewrite_imports(
                tree,
                "fastapi",
                "django_matt.di",
                {"Depends": "Depends"},
            )
        )

        # Find Depends() usage in function signatures and flag for review
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    # Check if default is Depends(...)
                    defaults = node.args.defaults
                    kw_defaults = node.args.kw_defaults
                    for default in defaults + kw_defaults:
                        if default and isinstance(default, ast.Call):
                            func_name = ""
                            if isinstance(default.func, ast.Name):
                                func_name = default.func.id
                            elif isinstance(default.func, ast.Attribute):
                                func_name = default.func.attr
                            if func_name == "Depends":
                                warnings.append(
                                    f"Depends() in {node.name}() -- django-matt uses "
                                    "Depends() from django_matt.di with similar syntax"
                                )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.75,
        )


class FastAPIBaseModelToSchema(Codemod):
    """Convert FastAPI/Pydantic BaseModel usage to django-matt Schema."""

    name = "fastapi-basemodel-to-schema"
    source_framework = "fastapi"
    description = "Convert Pydantic BaseModel to django-matt Schema (optional)"

    def detect(self, source: str, filename: str) -> bool:
        return "BaseModel" in source and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Only transform if file also uses FastAPI -- don't touch standalone Pydantic
        has_fastapi = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "fastapi" in node.module:
                has_fastapi = True
                break

        if not has_fastapi:
            return CodemodResult(transformed=source, confidence=0.0)

        warnings.append(
            "Pydantic BaseModel is fully compatible with django-matt -- "
            "optionally inherit from django_matt.core.schema.Schema for "
            "from_orm() and model_dump_response() support"
        )
        changes.append("Flagged BaseModel classes for optional Schema migration")

        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.5,
        )


class FastAPIHTTPExceptionToAPIError(Codemod):
    """Convert FastAPI HTTPException raises to django-matt APIError."""

    name = "fastapi-httpexception-to-apierror"
    source_framework = "fastapi"
    description = "Convert HTTPException to django-matt APIError"

    def detect(self, source: str, filename: str) -> bool:
        return "HTTPException" in source and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Rewrite import
        changes.extend(
            rewrite_imports(
                tree,
                "fastapi",
                "django_matt.core.errors",
                {"HTTPException": "APIError"},
            )
        )

        # Transform raise HTTPException(status_code=404, detail="...") ->
        # raise APIError("...", status_code=404)
        class ExceptionTransformer(ast.NodeTransformer):
            def visit_Raise(self, node: ast.Raise) -> ast.Raise:
                if node.exc and isinstance(node.exc, ast.Call):
                    func_name = ""
                    if isinstance(node.exc.func, ast.Name):
                        func_name = node.exc.func.id
                    elif isinstance(node.exc.func, ast.Attribute):
                        func_name = node.exc.func.attr

                    if func_name in ("HTTPException", "APIError"):
                        # Extract status_code and detail
                        status_code = None
                        detail = None
                        other_kwargs = []

                        for kw in node.exc.keywords:
                            if kw.arg == "status_code":
                                status_code = kw.value
                            elif kw.arg == "detail":
                                detail = kw.value
                            else:
                                other_kwargs.append(kw)

                        # Rebuild as APIError(message, status_code=...)
                        if isinstance(node.exc.func, ast.Name):
                            node.exc.func.id = "APIError"
                        elif isinstance(node.exc.func, ast.Attribute):
                            node.exc.func.attr = "APIError"

                        new_args = []
                        if detail:
                            new_args.append(detail)
                        new_kwargs = []
                        if status_code:
                            new_kwargs.append(ast.keyword(arg="status_code", value=status_code))
                        new_kwargs.extend(other_kwargs)

                        node.exc.args = new_args
                        node.exc.keywords = new_kwargs
                        changes.append("Transformed HTTPException -> APIError")

                return node

        ExceptionTransformer().visit(tree)

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.85,
        )


class FastAPILifecycleToHooks(Codemod):
    """Convert FastAPI @app.on_event to django-matt lifecycle hooks."""

    name = "fastapi-lifecycle-to-hooks"
    source_framework = "fastapi"
    description = "Convert FastAPI lifecycle events to django-matt hooks"

    def detect(self, source: str, filename: str) -> bool:
        return "on_event" in source and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if dec.func.attr == "on_event":
                            event_name = ""
                            if dec.args and isinstance(dec.args[0], ast.Constant):
                                event_name = dec.args[0].value
                            warnings.append(
                                f"@app.on_event('{event_name}') on {node.name}() -> "
                                "use Django AppConfig.ready() or django-matt modules lifecycle"
                            )
                            changes.append(f"Flagged {node.name}() lifecycle event for migration")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.5,
        )


class FastAPIBackgroundTasksToMatt(Codemod):
    """Convert FastAPI BackgroundTasks to django-matt tasks."""

    name = "fastapi-background-tasks"
    source_framework = "fastapi"
    description = "Convert FastAPI BackgroundTasks to django-matt tasks"

    def detect(self, source: str, filename: str) -> bool:
        return "BackgroundTasks" in source and "fastapi" in source.lower()

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        changes.extend(
            rewrite_imports(
                tree,
                "fastapi",
                "django_matt.tasks",
                {"BackgroundTasks": "BackgroundTasks"},
            )
        )

        warnings.append(
            "FastAPI BackgroundTasks -> django-matt tasks module. "
            "For production, use Celery/Dramatiq via django_matt.tasks"
        )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.6,
        )


class FastAPICodemods:
    """Collection of all FastAPI codemods."""

    @staticmethod
    def all() -> list[Codemod]:
        return [
            FastAPIAppToMattAPI(),
            FastAPIRouterToController(),
            FastAPIDependsToMattDI(),
            FastAPIBaseModelToSchema(),
            FastAPIHTTPExceptionToAPIError(),
            FastAPILifecycleToHooks(),
            FastAPIBackgroundTasksToMatt(),
        ]
