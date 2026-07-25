# file-length-max: 700
"""
DRF (Django REST Framework) codemods.

AST-based transformations for migrating DRF code to django-matt.
"""

from __future__ import annotations

import ast
from typing import Any

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.patterns import (
    add_import,
    remove_import,
    remove_response_wrapper,
    rename_all_references,
    rewrite_imports,
    swap_base_classes,
)


class DRFSerializerToSchema(Codemod):
    """Convert DRF ModelSerializer/Serializer to Pydantic ModelSchema/BaseModel."""

    name = "drf-serializer-to-schema"
    source_framework = "drf"
    description = "Convert DRF serializers to Pydantic schemas"

    # DRF field -> Pydantic type annotation string
    FIELD_MAP: dict[str, str] = {
        "CharField": "str",
        "TextField": "str",
        "EmailField": "str",
        "URLField": "str",
        "SlugField": "str",
        "UUIDField": "str",
        "IPAddressField": "str",
        "FilePathField": "str",
        "IntegerField": "int",
        "FloatField": "float",
        "DecimalField": "Decimal",
        "BooleanField": "bool",
        "NullBooleanField": "bool | None",
        "DateField": "date",
        "DateTimeField": "datetime",
        "TimeField": "time",
        "DurationField": "timedelta",
        "ListField": "list",
        "DictField": "dict",
        "JSONField": "Any",
        "PrimaryKeyRelatedField": "int",
        "SlugRelatedField": "str",
        "HyperlinkedRelatedField": "str",
        "SerializerMethodField": "Any",
        "HiddenField": "Any",
        "ReadOnlyField": "Any",
        "FileField": "str",
        "ImageField": "str",
    }

    def detect(self, source: str, filename: str) -> bool:
        return "rest_framework" in source and "Serializer" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []
        confidence = 1.0

        # Rewrite imports
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.serializers",
                "django_matt.core.schema",
                {"ModelSerializer": "ModelSchema", "Serializer": "Schema"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework",
                "django_matt.core.schema",
                {"serializers": "schema"},
            )
        )

        # Transform class definitions
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            swapped = swap_base_classes(node, "ModelSerializer", "ModelSchema")
            if not swapped:
                swapped = swap_base_classes(node, "Serializer", "Schema")
            if not swapped:
                # Check for serializers.ModelSerializer / serializers.Serializer
                swapped = swap_base_classes(node, "serializers.ModelSerializer", "ModelSchema")
                if not swapped:
                    swapped = swap_base_classes(node, "serializers.Serializer", "Schema")

            if not swapped:
                continue

            old_name = node.name
            if "Serializer" in node.name:
                node.name = node.name.replace("Serializer", "Schema")
                rename_all_references(tree, old_name, node.name)
                changes.append(f"Renamed {old_name} -> {node.name}")

            # Transform Meta class
            self._transform_meta(node, changes, warnings)

            # Transform field definitions
            self._transform_fields(node, changes, warnings)

            # Handle validate_* methods -> field_validator
            self._transform_validators(node, changes, warnings)

            # Remove serializer-specific methods
            self._remove_drf_methods(node, changes)

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=confidence,
        )

    def _transform_meta(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
        warnings: list[str],
    ) -> None:
        """Transform DRF Meta class to django-matt Config-compatible Meta."""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                # Rename 'fields' to 'include' if it's a list
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                if target.id == "fields":
                                    target.id = "include"
                                    changes.append("Renamed Meta.fields -> Meta.include")
                                elif target.id == "read_only_fields":
                                    warnings.append(
                                        "read_only_fields needs manual review -- "
                                        "use computed fields or exclude from create schema"
                                    )
                                elif target.id == "extra_kwargs":
                                    warnings.append(
                                        "extra_kwargs needs manual review -- "
                                        "use Pydantic Field() annotations"
                                    )

    def _transform_fields(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
        warnings: list[str],
    ) -> None:
        """Transform DRF field definitions to Pydantic annotations."""
        new_body: list[ast.stmt] = []
        annotations: dict[str, ast.expr] = {}

        for item in class_node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target = item.targets[0]
                if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                    field_type = self._get_call_name(item.value)
                    pydantic_type = self.FIELD_MAP.get(field_type)

                    if pydantic_type:
                        # Check for required=False or allow_null=True
                        is_optional = self._is_optional_field(item.value)
                        type_str = f"{pydantic_type} | None" if is_optional else pydantic_type

                        # Create annotation
                        ann = ast.AnnAssign(
                            target=ast.Name(id=target.id, ctx=ast.Store()),
                            annotation=ast.Name(id=type_str, ctx=ast.Load()),
                            value=ast.Constant(value=None) if is_optional else None,
                            simple=1,
                        )
                        new_body.append(ann)
                        changes.append(f"Converted field {target.id}: {field_type} -> {type_str}")
                        continue

            new_body.append(item)

        class_node.body = new_body if new_body else [ast.Pass()]

    def _transform_validators(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
        warnings: list[str],
    ) -> None:
        """Transform DRF validate_<field> methods to Pydantic field_validators."""
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("validate_"):
                field_name = item.name[len("validate_") :]
                if field_name and field_name != "":
                    warnings.append(
                        f"validate_{field_name}() needs manual conversion to "
                        f"@field_validator('{field_name}')"
                    )

    def _remove_drf_methods(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
    ) -> None:
        """Remove DRF-specific methods that don't apply to Pydantic."""
        drf_methods = {"create", "update", "to_representation", "to_internal_value"}
        to_remove = []
        for i, item in enumerate(class_node.body):
            if isinstance(item, ast.FunctionDef) and item.name in drf_methods:
                to_remove.append(i)
                changes.append(f"Removed DRF method {item.name}() -- needs manual migration")

        for idx in reversed(to_remove):
            class_node.body.pop(idx)

    def _get_call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def _is_optional_field(self, call: ast.Call) -> bool:
        for kw in call.keywords:
            if (
                kw.arg == "required"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is False
            ):
                return True
            if (
                kw.arg == "allow_null"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
            if (
                kw.arg == "allow_blank"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
        return False


class DRFViewSetToController(Codemod):
    """Convert DRF ViewSet/ModelViewSet to APIController/CRUDController."""

    name = "drf-viewset-to-controller"
    source_framework = "drf"
    description = "Convert DRF ViewSets to django-matt controllers"

    def detect(self, source: str, filename: str) -> bool:
        return "rest_framework" in source and ("ViewSet" in source or "APIView" in source)

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []
        confidence = 1.0

        # Rewrite imports
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.viewsets",
                "django_matt.core.controller",
                {"ModelViewSet": "CRUDController", "ViewSet": "APIController"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.views",
                "django_matt.core.controller",
                {"APIView": "APIController"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.generics",
                "django_matt.core.controller",
                {
                    "GenericAPIView": "APIController",
                    "ListAPIView": "APIController",
                    "CreateAPIView": "APIController",
                    "RetrieveAPIView": "APIController",
                    "UpdateAPIView": "APIController",
                    "DestroyAPIView": "APIController",
                    "ListCreateAPIView": "APIController",
                    "RetrieveUpdateAPIView": "APIController",
                    "RetrieveUpdateDestroyAPIView": "APIController",
                    "RetrieveDestroyAPIView": "APIController",
                },
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.decorators",
                "django_matt.core.router",
                {"api_view": "get", "action": "get"},
            )
        )
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.response",
                "django_matt.core.controller",
                {},
            )
        )
        remove_import(tree, "rest_framework.response")
        changes.extend(
            rewrite_imports(
                tree,
                "rest_framework.permissions",
                "django_matt.permissions",
                {"IsAuthenticated": "IsAuthenticated", "IsAdminUser": "IsAdmin"},
            )
        )

        add_import(tree, "django_matt.core.router", ["get", "post", "put", "patch", "delete"])

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Swap base classes
            swapped = False
            for old, new in [
                ("ModelViewSet", "CRUDController"),
                ("ViewSet", "APIController"),
                ("APIView", "APIController"),
                ("GenericAPIView", "APIController"),
                ("ListAPIView", "APIController"),
                ("CreateAPIView", "APIController"),
                ("RetrieveAPIView", "APIController"),
                ("UpdateAPIView", "APIController"),
                ("DestroyAPIView", "APIController"),
                ("ListCreateAPIView", "APIController"),
                ("RetrieveUpdateDestroyAPIView", "APIController"),
            ]:
                if swap_base_classes(node, old, new):
                    changes.append(f"Swapped base {old} -> {new}")
                    swapped = True
                    break

            if not swapped:
                continue

            # Rename class
            old_name = node.name
            if "ViewSet" in node.name:
                node.name = node.name.replace("ViewSet", "Controller")
                rename_all_references(tree, old_name, node.name)
                changes.append(f"Renamed {old_name} -> {node.name}")
            elif node.name.endswith("View") and "Controller" not in node.name:
                node.name = node.name.replace("View", "Controller")
                rename_all_references(tree, old_name, node.name)
                changes.append(f"Renamed {old_name} -> {node.name}")

            # Transform serializer_class -> schema
            self._transform_class_attrs(node, changes)

            # Transform methods
            self._transform_methods(node, changes, warnings)

            # Transform @action decorators
            self._transform_actions(node, changes)

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=confidence,
        )

    def _transform_class_attrs(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
    ) -> None:
        for item in class_node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target = item.targets[0]
                if isinstance(target, ast.Name):
                    if target.id == "serializer_class":
                        target.id = "schema"
                        changes.append("Renamed serializer_class -> schema")
                    elif target.id == "queryset":
                        # Convert queryset = Model.objects.all() to model = Model
                        if isinstance(item.value, ast.Call):
                            func = item.value.func
                            if isinstance(func, ast.Attribute) and func.attr == "all":
                                if (
                                    isinstance(func.value, ast.Attribute)
                                    and func.value.attr == "objects"
                                ):
                                    target.id = "model"
                                    item.value = func.value.value
                                    changes.append(
                                        "Converted queryset = Model.objects.all() -> model = Model"
                                    )

    def _transform_methods(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
        warnings: list[str],
    ) -> None:
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Unwrap Response()
                resp_changes = remove_response_wrapper(item)
                changes.extend(resp_changes)

                # Transform serializer.is_valid() patterns
                if item.name in ("create", "update", "partial_update"):
                    warnings.append(
                        f"{item.name}(): DRF serializer validation is automatic "
                        "with Pydantic -- review data handling"
                    )

    def _transform_actions(
        self,
        class_node: ast.ClassDef,
        changes: list[str],
    ) -> None:
        """Transform @action(detail=True, methods=['get']) -> @get('/{id}/name')."""
        for item in class_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            new_decorators = []
            for dec in item.decorator_list:
                if isinstance(dec, ast.Call) and self._is_action_decorator(dec):
                    detail = self._get_action_kwarg(dec, "detail")
                    methods = self._get_action_kwarg(dec, "methods")
                    url_path = self._get_action_kwarg(dec, "url_path")

                    http_method = "get"
                    if methods and isinstance(methods, list):
                        http_method = methods[0].lower()

                    path = url_path or item.name
                    if detail:
                        path = f"/{{id}}/{path}"
                    else:
                        path = f"/{path}"

                    # Create @api.get("/path") decorator
                    new_dec = ast.Call(
                        func=ast.Name(id=http_method, ctx=ast.Load()),
                        args=[ast.Constant(value=path)],
                        keywords=[],
                    )
                    new_decorators.append(new_dec)
                    changes.append(f"Transformed @action -> @{http_method}('{path}')")
                else:
                    new_decorators.append(dec)

            item.decorator_list = new_decorators

    def _is_action_decorator(self, call: ast.Call) -> bool:
        func = call.func
        if isinstance(func, ast.Name) and func.id == "action":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "action":
            return True
        return False

    def _get_action_kwarg(self, call: ast.Call, name: str) -> Any:
        for kw in call.keywords:
            if kw.arg == name:
                if isinstance(kw.value, ast.Constant):
                    return kw.value.value
                if isinstance(kw.value, ast.List):
                    return [
                        elt.value if isinstance(elt, ast.Constant) else "" for elt in kw.value.elts
                    ]
        return None


class DRFApiViewDecorator(Codemod):
    """Convert @api_view decorated functions to controller methods."""

    name = "drf-api-view-to-controller"
    source_framework = "drf"
    description = "Convert @api_view functions to controller methods"

    def detect(self, source: str, filename: str) -> bool:
        return "api_view" in source and "rest_framework" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Find @api_view decorated functions
        api_view_funcs: list[ast.FunctionDef] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if self._is_api_view(dec):
                        api_view_funcs.append(node)
                        methods = self._get_api_view_methods(dec)
                        # Replace @api_view with appropriate route decorator
                        method = methods[0].lower() if methods else "get"
                        new_dec = ast.Call(
                            func=ast.Name(id=method, ctx=ast.Load()),
                            args=[ast.Constant(value=f"/{node.name}")],
                            keywords=[],
                        )
                        node.decorator_list = [new_dec]
                        changes.append(
                            f"Converted @api_view({methods}) on {node.name} -> @{method}('/{node.name}')"
                        )
                        # Unwrap Response
                        changes.extend(remove_response_wrapper(node))

        if api_view_funcs:
            warnings.append("Converted functions should be moved into an APIController class")

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        # Rewrite imports
        remove_import(tree, "rest_framework.decorators", ["api_view"])
        remove_import(tree, "rest_framework.response", ["Response"])
        add_import(tree, "django_matt.core.router", ["get", "post", "put", "patch", "delete"])

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.8,
        )

    def _is_api_view(self, dec: ast.expr) -> bool:
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "api_view":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "api_view":
                return True
        return False

    def _get_api_view_methods(self, dec: ast.Call) -> list[str]:
        if dec.args and isinstance(dec.args[0], ast.List):
            return [
                elt.value.upper() if isinstance(elt, ast.Constant) else ""
                for elt in dec.args[0].elts
            ]
        return ["GET"]


class DRFRouterToRegistration(Codemod):
    """Convert DRF router.register() to api.register_controller()."""

    name = "drf-router-to-registration"
    source_framework = "drf"
    description = "Convert DRF router registrations to api.register_controller()"

    def detect(self, source: str, filename: str) -> bool:
        return ("DefaultRouter" in source or "SimpleRouter" in source) and "register" in source

    def transform(self, source: str, filename: str) -> CodemodResult:
        tree = self._parse(source)
        changes: list[str] = []
        warnings: list[str] = []

        # Find router = DefaultRouter() or SimpleRouter()
        router_var: str | None = None
        to_remove: list[int] = []

        for i, node in enumerate(tree.body):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                    func_name = ""
                    if isinstance(node.value.func, ast.Name):
                        func_name = node.value.func.id
                    elif isinstance(node.value.func, ast.Attribute):
                        func_name = node.value.func.attr
                    if func_name in ("DefaultRouter", "SimpleRouter"):
                        router_var = target.id
                        # Replace with DjangoMattAPI()
                        node.value.func = ast.Name(id="DjangoMattAPI", ctx=ast.Load())
                        node.value.args = []
                        node.value.keywords = []
                        target.id = "api"
                        changes.append(f"Replaced {func_name}() -> DjangoMattAPI()")

        # Transform router.register() calls
        if router_var:
            for i, node in enumerate(tree.body):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call = node.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == "register":
                        obj_name = ""
                        if isinstance(call.func.value, ast.Name):
                            obj_name = call.func.value.id
                        if obj_name == router_var and len(call.args) >= 2:
                            viewset_ref = call.args[1]
                            call.func = ast.Attribute(
                                value=ast.Name(id="api", ctx=ast.Load()),
                                attr="register_controller",
                                ctx=ast.Load(),
                            )
                            call.args = [viewset_ref]
                            call.keywords = []
                            viewset_name = ""
                            if isinstance(viewset_ref, ast.Name):
                                viewset_name = viewset_ref.id
                            changes.append(
                                f"Converted {router_var}.register(..., {viewset_name}) "
                                "-> api.register_controller(...)"
                            )

        if not changes:
            return CodemodResult(transformed=source, confidence=0.0)

        # Update imports
        remove_import(tree, "rest_framework.routers")
        add_import(tree, "django_matt", ["DjangoMattAPI"])

        ast.fix_missing_locations(tree)
        return CodemodResult(
            transformed=self._unparse(tree),
            changes=changes,
            warnings=warnings,
            confidence=0.85,
        )


class DRFCodemods:
    """Collection of all DRF codemods."""

    @staticmethod
    def all() -> list[Codemod]:
        return [
            DRFSerializerToSchema(),
            DRFViewSetToController(),
            DRFApiViewDecorator(),
            DRFRouterToRegistration(),
        ]
