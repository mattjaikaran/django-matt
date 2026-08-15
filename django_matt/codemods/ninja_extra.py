"""
Django Ninja Extra codemods.

AST-based transformations for migrating django-ninja-extra code to django-matt.

Covers the patterns that distinguish ninja-extra from plain Django Ninja:
ControllerBase classes, the api_controller decorator, route decorators,
register_controllers, Inject-based DI, and ninja_extra permission imports.
"""

from __future__ import annotations

import ast
import copy

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.patterns import (
    add_import,
    has_base_class,
    remove_import,
    rewrite_imports,
    transform_decorators,
)

# Names from ninja_extra modules that have direct django-matt equivalents.
_NINJA_EXTRA_PERMISSIONS = {
    "AllowAny": "AllowAny",
    "IsAdminUser": "IsAdmin",
    "IsAuthenticated": "IsAuthenticated",
    "IsAuthenticatedOrReadOnly": "IsAuthenticatedOrReadOnly",
}

# Names imported from the bare ninja_extra module that map to django-matt.
_NINJA_EXTRA_API_NAMES = {
    "NinjaExtraAPI": "DjangoMattAPI",
}


class NinjaExtraImportsToMatt(Codemod):
    """Rewrite ninja_extra imports to their django-matt equivalents."""

    name = "ninja-extra-imports-to-matt"
    source_framework = "ninja-extra"
    description = "Convert ninja_extra imports to django-matt imports"

    def detect(self, source: str, filename: str) -> bool:
        return "ninja_extra" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Submodule imports map cleanly onto django-matt modules.
        changes.extend(
            rewrite_imports(
                tree,
                "ninja_extra.permissions",
                "django_matt.permissions",
                _NINJA_EXTRA_PERMISSIONS,
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "ninja_extra.pagination",
                "django_matt.pagination",
                {"paginate": "paginate"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "ninja_extra.throttling",
                "django_matt.throttling",
                {"throttle": "throttle"},
            )
        )

        # Bare `from ninja_extra import ...`: move mapped names to django_matt,
        # keep unmapped names (api_controller, ControllerBase, route, Inject)
        # in place until the controller codemod consumes them.
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.module == "ninja_extra"):
                continue
            mapped = [a for a in node.names if a.name in _NINJA_EXTRA_API_NAMES]
            unmapped = [a for a in node.names if a.name not in _NINJA_EXTRA_API_NAMES]
            for alias in mapped:
                alias.name = _NINJA_EXTRA_API_NAMES[alias.name]
            if mapped and not unmapped:
                node.module = "django_matt"
                changes.append("Moved NinjaExtraAPI import to django_matt")
            elif mapped and unmapped:
                idx = tree.body.index(node)
                moved = ast.ImportFrom(
                    module="django_matt",
                    names=mapped,
                    level=0,
                )
                tree.body.insert(idx + 1, moved)
                node.names = unmapped
                changes.append("Split ninja_extra import: mapped names moved to django_matt")

        # Rename NinjaExtraAPI() call sites to DjangoMattAPI()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name == "NinjaExtraAPI":
                if isinstance(node.func, ast.Name):
                    node.func.id = "DjangoMattAPI"
                elif isinstance(node.func, ast.Attribute):
                    node.func.attr = "DjangoMattAPI"
                changes.append("Replaced NinjaExtraAPI() -> DjangoMattAPI()")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.9,
        )


class NinjaExtraControllerToMattController(Codemod):
    """Convert api_controller + ControllerBase classes into APIController classes."""

    name = "ninja-extra-controller-to-matt-controller"
    source_framework = "ninja-extra"
    description = "Convert @api_controller ControllerBase classes to APIController"

    def detect(self, source: str, filename: str) -> bool:
        return "ControllerBase" in source or "api_controller" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            is_controller = has_base_class(node, "ControllerBase") or has_base_class(
                node, "AsyncControllerBase"
            )
            controller_decorator = None
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                    if dec.func.id == "api_controller":
                        controller_decorator = dec
                        is_controller = True

            if not is_controller:
                continue

            # Swap the base class to APIController
            for base in node.bases:
                base_name = getattr(base, "id", getattr(base, "attr", ""))
                if base_name in ("ControllerBase", "AsyncControllerBase"):
                    if isinstance(base, ast.Name):
                        base.id = "APIController"
                    elif isinstance(base, ast.Attribute):
                        base.attr = "APIController"
                    changes.append(
                        f"Replaced {base_name} base with APIController on {node.name}"
                    )

            # Extract prefix, tags, and permissions from the api_controller decorator
            if controller_decorator is not None:
                prefix = None
                if controller_decorator.args:
                    arg = controller_decorator.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        prefix = arg.value
                tags = None
                for kw in controller_decorator.keywords:
                    if kw.arg == "permissions":
                        perm_attr = ast.Assign(
                            targets=[ast.Name(id="permission_classes")],
                            value=copy.deepcopy(kw.value),
                        )
                        node.body.insert(0, perm_attr)
                        changes.append(
                            f"Moved api_controller permissions to permission_classes on {node.name}"
                        )
                    elif kw.arg == "tags":
                        tags = copy.deepcopy(kw.value)
                node.decorator_list.remove(controller_decorator)
                if prefix is not None:
                    prefix_attr = ast.Assign(
                        targets=[ast.Name(id="prefix")],
                        value=ast.Constant(value=prefix),
                    )
                    node.body.insert(0, prefix_attr)
                    changes.append(f"Set prefix = {prefix!r} on {node.name}")
                if tags is not None:
                    tags_attr = ast.Assign(
                        targets=[ast.Name(id="tags")],
                        value=tags,
                    )
                    node.body.insert(1, tags_attr)
                    changes.append(f"Set tags on {node.name}")

            # Convert @route.<method> to @api.<method>
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    changes.extend(transform_decorators(method, "route", "api"))

            # Flag Inject-based DI for manual conversion
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    src = ast.get_source_segment(source, method) or ""
                    if "Inject" in src:
                        warnings.append(
                            f"{node.name}.{method.name}: replace Inject() parameters "
                            "with the django_matt.di @inject decorator"
                        )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        # Fix imports: ensure APIController and api are imported
        add_import(tree, "django_matt", ["APIController", "api"])
        changes.append("Added 'from django_matt import APIController, api'")

        # Remove ninja_extra-only names that no longer exist after conversion
        removed = remove_import(
            tree,
            "ninja_extra",
            ["api_controller", "ControllerBase", "AsyncControllerBase", "route"],
        )
        if removed:
            changes.append("Removed ninja_extra-only imports (api_controller, ControllerBase, route)")

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.8,
        )


class NinjaExtraRegisterToMatt(Codemod):
    """Convert register_controllers calls to register_controller."""

    name = "ninja-extra-register-to-matt"
    source_framework = "ninja-extra"
    description = "Convert api.register_controllers() to register_controller()"

    def detect(self, source: str, filename: str) -> bool:
        return "register_controllers" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "register_controllers":
                    node.func.attr = "register_controller"
                    if len(node.args) > 1:
                        warnings.append(
                            "register_controllers() received multiple controllers; "
                            "call register_controller() once per controller"
                        )
                    changes.append("Replaced register_controllers() -> register_controller()")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.95,
        )


class NinjaExtraCodemods:
    """Collection of all Django Ninja Extra codemods."""

    @staticmethod
    def all() -> list[Codemod]:
        return [
            NinjaExtraImportsToMatt(),
            NinjaExtraControllerToMattController(),
            NinjaExtraRegisterToMatt(),
        ]
