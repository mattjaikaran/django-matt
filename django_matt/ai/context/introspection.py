"""
Enhanced Django project introspection for AI context generation.

Provides deep introspection including:
- API endpoints with methods and permissions
- Pydantic schemas with field types
- Django models with relationships
- Authentication requirements per endpoint
- Example request/response payloads
- Test patterns used in the project
"""

import importlib
import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings

import orjson


class AuthRequirement(str, Enum):
    """Authentication requirements for endpoints."""

    NONE = "none"
    JWT_REQUIRED = "jwt_required"
    JWT_OPTIONAL = "jwt_optional"
    API_KEY = "api_key"
    SESSION = "session"
    PERMISSION_REQUIRED = "permission_required"
    ROLE_REQUIRED = "role_required"
    UNKNOWN = "unknown"


@dataclass
class ExamplePayload:
    """Example request/response payload for an endpoint."""

    request_body: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    query_params: dict[str, str] | None = None
    path_params: dict[str, str] | None = None
    headers: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "request_body": self.request_body,
            "response_body": self.response_body,
            "query_params": self.query_params,
            "path_params": self.path_params,
            "headers": self.headers,
        }


@dataclass
class SchemaFieldInfo:
    """Information about a Pydantic schema field."""

    name: str
    field_type: str
    required: bool = True
    default: Any = None
    description: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)
    example: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": self.field_type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
            "constraints": self.constraints,
            "example": self.example,
        }


@dataclass
class PydanticSchemaInfo:
    """Information about a Pydantic schema."""

    name: str
    module: str
    fields: list[SchemaFieldInfo] = field(default_factory=list)
    docstring: str = ""
    base_classes: list[str] = field(default_factory=list)
    is_model_schema: bool = False
    django_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "module": self.module,
            "fields": [f.to_dict() for f in self.fields],
            "docstring": self.docstring,
            "base_classes": self.base_classes,
            "is_model_schema": self.is_model_schema,
            "django_model": self.django_model,
        }


@dataclass
class EndpointInfo:
    """Detailed information about an API endpoint."""

    path: str
    method: str
    name: str | None = None
    view_name: str = ""
    view_module: str = ""
    auth_requirement: AuthRequirement = AuthRequirement.UNKNOWN
    permissions: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    request_schema: str | None = None
    response_schema: str | None = None
    docstring: str = ""
    tags: list[str] = field(default_factory=list)
    example: ExamplePayload | None = None
    deprecated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "path": self.path,
            "method": self.method,
            "name": self.name,
            "view_name": self.view_name,
            "view_module": self.view_module,
            "auth_requirement": self.auth_requirement.value,
            "permissions": self.permissions,
            "roles": self.roles,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "docstring": self.docstring,
            "tags": self.tags,
            "example": self.example.to_dict() if self.example else None,
            "deprecated": self.deprecated,
        }


@dataclass
class TestPatternInfo:
    """Information about test patterns in the project."""

    framework: str  # pytest, unittest
    fixture_files: list[str] = field(default_factory=list)
    factory_files: list[str] = field(default_factory=list)
    common_patterns: list[str] = field(default_factory=list)
    example_tests: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "framework": self.framework,
            "fixture_files": self.fixture_files,
            "factory_files": self.factory_files,
            "common_patterns": self.common_patterns,
            "example_tests": self.example_tests,
        }


@dataclass
class EnhancedProjectInfo:
    """Enhanced project information with deep introspection."""

    name: str
    root_path: str
    python_version: str
    django_version: str
    settings_module: str = ""
    endpoints: list[EndpointInfo] = field(default_factory=list)
    schemas: list[PydanticSchemaInfo] = field(default_factory=list)
    models: list[dict[str, Any]] = field(default_factory=list)
    test_patterns: TestPatternInfo | None = None
    middleware: list[str] = field(default_factory=list)
    installed_apps: list[str] = field(default_factory=list)
    databases: dict[str, str] = field(default_factory=dict)
    code_examples: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "root_path": self.root_path,
            "python_version": self.python_version,
            "django_version": self.django_version,
            "settings_module": self.settings_module,
            "endpoints": [e.to_dict() for e in self.endpoints],
            "schemas": [s.to_dict() for s in self.schemas],
            "models": self.models,
            "test_patterns": self.test_patterns.to_dict() if self.test_patterns else None,
            "middleware": self.middleware,
            "installed_apps": self.installed_apps,
            "databases": self.databases,
            "code_examples": self.code_examples,
        }


class EnhancedIntrospector:
    """
    Enhanced Django project introspector.

    Provides deep introspection including:
    - All API endpoints with methods and permissions
    - All Pydantic schemas with field types
    - All Django models with relationships
    - Authentication requirements per endpoint
    - Example request/response for each endpoint
    - Test patterns used in the project

    Usage:
        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Access endpoints
        for endpoint in info.endpoints:
            print(f"{endpoint.method} {endpoint.path} - {endpoint.auth_requirement}")

        # Access schemas
        for schema in info.schemas:
            print(f"{schema.name}: {[f.name for f in schema.fields]}")
    """

    def __init__(
        self,
        include_third_party: bool = False,
        exclude_apps: list[str] | None = None,
        include_examples: bool = True,
    ):
        """
        Initialize enhanced introspector.

        Args:
            include_third_party: Include third-party apps
            exclude_apps: Apps to exclude from introspection
            include_examples: Include code examples from codebase
        """
        self.include_third_party = include_third_party
        self.exclude_apps = set(exclude_apps or [])
        self.include_examples = include_examples
        self._project_root = self._find_project_root()
        self._auth_decorators = {
            "jwt_required": AuthRequirement.JWT_REQUIRED,
            "jwt_optional": AuthRequirement.JWT_OPTIONAL,
            "api_key_required": AuthRequirement.API_KEY,
            "login_required": AuthRequirement.SESSION,
            "permission_required": AuthRequirement.PERMISSION_REQUIRED,
            "requires_permission": AuthRequirement.PERMISSION_REQUIRED,
            "requires_role": AuthRequirement.ROLE_REQUIRED,
            "authenticated": AuthRequirement.JWT_REQUIRED,
        }

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        import os

        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if settings_module:
            try:
                module = importlib.import_module(settings_module)
                if hasattr(module, "__file__") and module.__file__:
                    return Path(module.__file__).parent.parent
            except ImportError:
                pass
        return Path.cwd()

    def _is_project_app(self, app_config) -> bool:
        """Check if an app is part of the project."""
        if self.include_third_party:
            return True

        app_path = Path(app_config.path)
        try:
            app_path.relative_to(self._project_root)
            return True
        except ValueError:
            return False

    def introspect(self) -> EnhancedProjectInfo:
        """Perform full enhanced project introspection."""
        import sys

        import django

        info = EnhancedProjectInfo(
            name=self._project_root.name,
            root_path=str(self._project_root),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            django_version=django.__version__,
            settings_module=getattr(settings, "SETTINGS_MODULE", ""),
            middleware=list(getattr(settings, "MIDDLEWARE", [])),
            installed_apps=list(getattr(settings, "INSTALLED_APPS", [])),
            databases={
                name: conf.get("ENGINE", "").split(".")[-1]
                for name, conf in getattr(settings, "DATABASES", {}).items()
            },
        )

        # Introspect endpoints
        info.endpoints = self._introspect_endpoints()

        # Introspect Pydantic schemas
        info.schemas = self._introspect_schemas()

        # Introspect Django models
        info.models = self._introspect_models()

        # Introspect test patterns
        info.test_patterns = self._introspect_test_patterns()

        # Extract code examples
        if self.include_examples:
            info.code_examples = self._extract_code_examples()

        return info

    def _introspect_endpoints(self) -> list[EndpointInfo]:
        """Introspect all API endpoints."""
        endpoints = []

        # Try to find MattAPI instances and controllers
        endpoints.extend(self._find_matt_api_endpoints())

        # Also check URL patterns
        endpoints.extend(self._find_url_pattern_endpoints())

        # Deduplicate by path+method
        seen = set()
        unique_endpoints = []
        for ep in endpoints:
            key = f"{ep.method}:{ep.path}"
            if key not in seen:
                seen.add(key)
                unique_endpoints.append(ep)

        return unique_endpoints

    def _find_matt_api_endpoints(self) -> list[EndpointInfo]:
        """Find endpoints from MattAPI instances and controllers."""
        endpoints = []

        for app_config in apps.get_app_configs():
            if app_config.label in self.exclude_apps:
                continue
            if not self._is_project_app(app_config):
                continue

            # Look for controllers
            try:
                controllers_module = importlib.import_module(f"{app_config.name}.controllers")
                endpoints.extend(self._extract_controller_endpoints(controllers_module))
            except ImportError:
                pass

            # Look for api.py
            try:
                api_module = importlib.import_module(f"{app_config.name}.api")
                endpoints.extend(self._extract_api_endpoints(api_module))
            except ImportError:
                pass

            # Look for views with decorators
            try:
                views_module = importlib.import_module(f"{app_config.name}.views")
                endpoints.extend(self._extract_view_endpoints(views_module))
            except ImportError:
                pass

        return endpoints

    def _extract_controller_endpoints(self, module) -> list[EndpointInfo]:
        """Extract endpoints from controller classes."""
        endpoints = []

        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it's a controller
            if not hasattr(obj, "prefix"):
                continue

            controller_prefix = getattr(obj, "prefix", "")
            controller_tags = getattr(obj, "tags", [])

            for method_name, method in inspect.getmembers(obj, inspect.isfunction):
                if method_name.startswith("_"):
                    continue

                route_info = getattr(method, "_route_info", None)
                if not route_info:
                    continue

                http_method = route_info.get("method", "GET")
                path_suffix = route_info.get("path", method_name)

                # Build full path
                full_path = f"/{controller_prefix}/{path_suffix}".replace("//", "/")

                # Detect auth requirements
                auth_req, permissions, roles = self._detect_auth_requirements(method)

                # Get request/response schemas
                request_schema, response_schema = self._extract_schemas_from_method(method)

                # Generate example
                example = self._generate_example_payload(method, request_schema)

                endpoints.append(
                    EndpointInfo(
                        path=full_path,
                        method=http_method,
                        name=route_info.get("name", method_name),
                        view_name=method_name,
                        view_module=module.__name__,
                        auth_requirement=auth_req,
                        permissions=permissions,
                        roles=roles,
                        request_schema=request_schema,
                        response_schema=response_schema,
                        docstring=inspect.getdoc(method) or "",
                        tags=controller_tags,
                        example=example,
                    )
                )

        return endpoints

    def _extract_api_endpoints(self, module) -> list[EndpointInfo]:
        """Extract endpoints from api.py module."""
        endpoints = []

        for name, obj in inspect.getmembers(module):
            # Check for decorated functions
            if inspect.isfunction(obj):
                route_info = getattr(obj, "_route_info", None)
                if route_info:
                    http_method = route_info.get("method", "GET")
                    path = route_info.get("path", f"/{name}")

                    auth_req, permissions, roles = self._detect_auth_requirements(obj)
                    request_schema, response_schema = self._extract_schemas_from_method(obj)

                    endpoints.append(
                        EndpointInfo(
                            path=path,
                            method=http_method,
                            name=name,
                            view_name=name,
                            view_module=module.__name__,
                            auth_requirement=auth_req,
                            permissions=permissions,
                            roles=roles,
                            request_schema=request_schema,
                            response_schema=response_schema,
                            docstring=inspect.getdoc(obj) or "",
                        )
                    )

        return endpoints

    def _extract_view_endpoints(self, module) -> list[EndpointInfo]:
        """Extract endpoints from views with route decorators."""
        endpoints = []

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                route_info = getattr(obj, "_route_info", None)
                if route_info:
                    http_method = route_info.get("method", "GET")
                    path = route_info.get("path", f"/{name}")

                    auth_req, permissions, roles = self._detect_auth_requirements(obj)

                    endpoints.append(
                        EndpointInfo(
                            path=path,
                            method=http_method,
                            name=name,
                            view_name=name,
                            view_module=module.__name__,
                            auth_requirement=auth_req,
                            permissions=permissions,
                            roles=roles,
                            docstring=inspect.getdoc(obj) or "",
                        )
                    )

        return endpoints

    def _find_url_pattern_endpoints(self) -> list[EndpointInfo]:
        """Find endpoints from Django URL patterns."""
        from django.urls import URLPattern, URLResolver, get_resolver

        endpoints = []

        def extract_urls(patterns, prefix=""):
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    new_prefix = prefix + str(pattern.pattern)
                    extract_urls(pattern.url_patterns, new_prefix)
                elif isinstance(pattern, URLPattern):
                    callback = pattern.callback
                    if callback:
                        full_path = "/" + prefix + str(pattern.pattern)
                        full_path = re.sub(r"<(\w+):(\w+)>", r"{\2}", full_path)
                        full_path = re.sub(r"<(\w+)>", r"{\1}", full_path)

                        # Detect HTTP methods from view
                        methods = self._detect_view_methods(callback)

                        for method in methods:
                            auth_req, permissions, roles = self._detect_auth_requirements(callback)
                            endpoints.append(
                                EndpointInfo(
                                    path=full_path,
                                    method=method,
                                    name=pattern.name,
                                    view_name=getattr(callback, "__name__", str(callback)),
                                    view_module=getattr(callback, "__module__", ""),
                                    auth_requirement=auth_req,
                                    permissions=permissions,
                                    roles=roles,
                                    docstring=inspect.getdoc(callback) or "",
                                )
                            )

        try:
            resolver = get_resolver()
            extract_urls(resolver.url_patterns)
        except Exception:
            pass

        return endpoints

    def _detect_view_methods(self, view) -> list[str]:
        """Detect HTTP methods supported by a view."""
        if hasattr(view, "http_method_names"):
            return [m.upper() for m in view.http_method_names if m != "options"]

        # Check for class-based view
        if hasattr(view, "cls"):
            cls = view.cls
            methods = []
            for method in ["get", "post", "put", "patch", "delete", "head"]:
                if hasattr(cls, method):
                    methods.append(method.upper())
            return methods or ["GET"]

        # Check for route info
        route_info = getattr(view, "_route_info", None)
        if route_info:
            return [route_info.get("method", "GET")]

        return ["GET"]

    def _detect_auth_requirements(self, func) -> tuple[AuthRequirement, list[str], list[str]]:
        """Detect authentication requirements from decorators."""
        auth_req = AuthRequirement.NONE
        permissions = []
        roles = []

        # Check wrapper chain for decorators
        current = func
        while current:
            # Check function name and qualname for decorator hints
            func_name = getattr(current, "__name__", "")
            qualname = getattr(current, "__qualname__", "")

            # Check for _auth_required attribute (from our decorators)
            if getattr(current, "_auth_required", False):
                auth_req = AuthRequirement.JWT_REQUIRED

            if getattr(current, "_auth_optional", False):
                auth_req = AuthRequirement.JWT_OPTIONAL

            # Check for permission_classes
            permission_classes = getattr(current, "permission_classes", None)
            if permission_classes:
                for perm_class in permission_classes:
                    perm_name = (
                        perm_class.__name__ if hasattr(perm_class, "__name__") else str(perm_class)
                    )
                    permissions.append(perm_name)
                    if "Authenticated" in perm_name:
                        auth_req = AuthRequirement.JWT_REQUIRED

            # Check wrapper
            wrapped = getattr(current, "__wrapped__", None)
            if wrapped is current:
                break
            current = wrapped

        return auth_req, permissions, roles

    def _extract_schemas_from_method(self, method) -> tuple[str | None, str | None]:
        """Extract request and response schema names from method."""
        request_schema = None
        response_schema = None

        try:
            hints = inspect.signature(method)
            for param in hints.parameters.values():
                if param.annotation != inspect.Parameter.empty:
                    anno = param.annotation
                    if hasattr(anno, "__name__"):
                        # Skip common types
                        if anno.__name__ not in ("HttpRequest", "Request", "str", "int", "dict"):
                            request_schema = anno.__name__

            # Check return annotation
            if hints.return_annotation != inspect.Signature.empty:
                anno = hints.return_annotation
                if hasattr(anno, "__name__"):
                    if anno.__name__ not in ("JsonResponse", "Response", "dict", "None"):
                        response_schema = anno.__name__
        except (ValueError, TypeError):
            pass

        return request_schema, response_schema

    def _generate_example_payload(self, method, schema_name: str | None) -> ExamplePayload | None:
        """Generate example payload for an endpoint."""
        if not schema_name:
            return None

        example = ExamplePayload()

        # Try to find the schema class and generate example
        try:
            hints = inspect.signature(method)
            for param in hints.parameters.values():
                if param.annotation != inspect.Parameter.empty:
                    anno = param.annotation
                    if hasattr(anno, "model_json_schema"):
                        # It's a Pydantic model
                        schema = anno.model_json_schema()
                        example.request_body = self._schema_to_example(schema)
                        break
        except Exception:
            pass

        return example

    def _schema_to_example(self, schema: dict) -> dict[str, Any]:
        """Convert JSON schema to example values."""
        example = {}
        properties = schema.get("properties", {})

        type_examples = {
            "string": "example_string",
            "integer": 123,
            "number": 123.45,
            "boolean": True,
            "array": [],
            "object": {},
        }

        for name, prop in properties.items():
            prop_type = prop.get("type", "string")
            if "example" in prop:
                example[name] = prop["example"]
            elif "default" in prop:
                example[name] = prop["default"]
            else:
                # Use format hints
                fmt = prop.get("format", "")
                if fmt == "email":
                    example[name] = "user@example.com"
                elif fmt == "date-time":
                    example[name] = "2024-01-01T00:00:00Z"
                elif fmt == "uuid":
                    example[name] = "550e8400-e29b-41d4-a716-446655440000"
                elif fmt == "uri":
                    example[name] = "https://example.com"
                else:
                    example[name] = type_examples.get(prop_type, "example")

        return example

    def _introspect_schemas(self) -> list[PydanticSchemaInfo]:
        """Introspect all Pydantic schemas in the project."""
        schemas = []

        for app_config in apps.get_app_configs():
            if app_config.label in self.exclude_apps:
                continue
            if not self._is_project_app(app_config):
                continue

            # Look for schemas.py
            for module_name in ["schemas", "schema", "models"]:
                try:
                    module = importlib.import_module(f"{app_config.name}.{module_name}")
                    schemas.extend(self._extract_pydantic_schemas(module))
                except ImportError:
                    pass

        return schemas

    def _extract_pydantic_schemas(self, module) -> list[PydanticSchemaInfo]:
        """Extract Pydantic schemas from a module."""
        from pydantic import BaseModel

        schemas = []

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseModel):
                continue
            if obj is BaseModel:
                continue
            if obj.__module__ != module.__name__:
                continue

            schema_info = PydanticSchemaInfo(
                name=name,
                module=module.__name__,
                docstring=inspect.getdoc(obj) or "",
                base_classes=[b.__name__ for b in obj.__bases__ if b is not BaseModel],
            )

            # Check if it's a ModelSchema
            if hasattr(obj, "Config"):
                config = obj.Config
                if hasattr(config, "model"):
                    schema_info.is_model_schema = True
                    model = config.model
                    schema_info.django_model = f"{model._meta.app_label}.{model.__name__}"

            # Extract fields
            try:
                for field_name, field_info in obj.model_fields.items():
                    field_type = str(field_info.annotation) if field_info.annotation else "Any"
                    # Clean up type string
                    field_type = re.sub(r"<class '([^']+)'>", r"\1", field_type)
                    field_type = re.sub(r"typing\.([A-Za-z]+)", r"\1", field_type)

                    schema_field = SchemaFieldInfo(
                        name=field_name,
                        field_type=field_type,
                        required=field_info.is_required(),
                        default=field_info.default if not field_info.is_required() else None,
                        description=field_info.description or "",
                    )

                    # Extract constraints
                    if field_info.metadata:
                        for meta in field_info.metadata:
                            if hasattr(meta, "min_length"):
                                schema_field.constraints["min_length"] = meta.min_length
                            if hasattr(meta, "max_length"):
                                schema_field.constraints["max_length"] = meta.max_length
                            if hasattr(meta, "ge"):
                                schema_field.constraints["ge"] = meta.ge
                            if hasattr(meta, "le"):
                                schema_field.constraints["le"] = meta.le

                    schema_info.fields.append(schema_field)
            except Exception:
                pass

            schemas.append(schema_info)

        return schemas

    def _introspect_models(self) -> list[dict[str, Any]]:
        """Introspect all Django models."""
        models_info = []

        for app_config in apps.get_app_configs():
            if app_config.label in self.exclude_apps:
                continue
            if not self._is_project_app(app_config):
                continue

            for model in app_config.get_models():
                meta = model._meta
                model_info = {
                    "name": model.__name__,
                    "app_label": meta.app_label,
                    "table_name": meta.db_table,
                    "docstring": inspect.getdoc(model) or "",
                    "fields": [],
                    "relationships": [],
                }

                for field in meta.get_fields():
                    if hasattr(field, "get_internal_type"):
                        field_data = {
                            "name": field.name,
                            "type": field.get_internal_type(),
                            "nullable": getattr(field, "null", False),
                            "blank": getattr(field, "blank", False),
                            "unique": getattr(field, "unique", False),
                            "primary_key": getattr(field, "primary_key", False),
                        }

                        # Add relationship info
                        if hasattr(field, "related_model") and field.related_model:
                            rel_model = field.related_model
                            field_data["related_to"] = (
                                f"{rel_model._meta.app_label}.{rel_model.__name__}"
                            )
                            model_info["relationships"].append(
                                {
                                    "field": field.name,
                                    "type": field.get_internal_type(),
                                    "to": field_data["related_to"],
                                }
                            )

                        model_info["fields"].append(field_data)

                models_info.append(model_info)

        return models_info

    def _introspect_test_patterns(self) -> TestPatternInfo:
        """Introspect test patterns in the project."""
        test_info = TestPatternInfo(framework="pytest")

        # Find test files
        test_dir = self._project_root / "tests"
        if test_dir.exists():
            for test_file in test_dir.glob("**/*.py"):
                if test_file.name.startswith("test_"):
                    # Check for fixtures
                    content = test_file.read_text()
                    if "@pytest.fixture" in content:
                        test_info.fixture_files.append(
                            str(test_file.relative_to(self._project_root))
                        )

                    # Check for factories
                    if "Factory" in content:
                        test_info.factory_files.append(
                            str(test_file.relative_to(self._project_root))
                        )

        # Check for conftest.py
        conftest = self._project_root / "tests" / "conftest.py"
        if conftest.exists():
            test_info.fixture_files.insert(0, "tests/conftest.py")

        # Detect common patterns
        patterns = []
        if (self._project_root / "pytest.ini").exists():
            patterns.append("pytest.ini configuration")
        if (self._project_root / "pyproject.toml").exists():
            toml_content = (self._project_root / "pyproject.toml").read_text()
            if "[tool.pytest" in toml_content:
                patterns.append("pytest in pyproject.toml")
        test_info.common_patterns = patterns

        return test_info

    def _extract_code_examples(self) -> dict[str, list[dict[str, str]]]:
        """Extract code examples from the codebase."""
        examples: dict[str, list[dict[str, str]]] = {
            "controllers": [],
            "views": [],
            "schemas": [],
            "models": [],
            "tests": [],
        }

        for app_config in apps.get_app_configs():
            if app_config.label in self.exclude_apps:
                continue
            if not self._is_project_app(app_config):
                continue

            app_path = Path(app_config.path)

            # Extract controller examples
            controllers_file = app_path / "controllers.py"
            if controllers_file.exists():
                examples["controllers"].extend(
                    self._extract_examples_from_file(controllers_file, "class.*Controller")
                )

            # Extract view examples
            views_file = app_path / "views.py"
            if views_file.exists():
                examples["views"].extend(
                    self._extract_examples_from_file(views_file, "@(get|post|put|patch|delete)")
                )

            # Extract schema examples
            schemas_file = app_path / "schemas.py"
            if schemas_file.exists():
                examples["schemas"].extend(
                    self._extract_examples_from_file(
                        schemas_file, "class.*Schema|class.*Request|class.*Response"
                    )
                )

        # Limit examples
        for key in examples:
            examples[key] = examples[key][:3]

        return examples

    def _extract_examples_from_file(self, file_path: Path, pattern: str) -> list[dict[str, str]]:
        """Extract code examples matching a pattern from a file."""
        examples = []

        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    # Extract the block (class or function)
                    start = i
                    end = i + 1

                    # Find the end of the block
                    indent = len(line) - len(line.lstrip())
                    for j in range(i + 1, min(i + 50, len(lines))):
                        if lines[j].strip() and not lines[j].startswith(" " * (indent + 1)):
                            if not lines[j].startswith(" " * indent + " "):
                                break
                        end = j + 1

                    # Limit to 30 lines
                    end = min(end, start + 30)

                    example_code = "\n".join(lines[start:end])
                    examples.append(
                        {
                            "file": str(file_path),
                            "line": start + 1,
                            "code": example_code,
                        }
                    )

                    if len(examples) >= 3:
                        break
        except Exception:
            pass

        return examples

    def to_json(self) -> str:
        """Export introspection data as JSON."""
        info = self.introspect()
        return orjson.dumps(info.to_dict(), default=str, option=orjson.OPT_INDENT_2).decode()


__all__ = [
    "AuthRequirement",
    "EndpointInfo",
    "EnhancedIntrospector",
    "EnhancedProjectInfo",
    "ExamplePayload",
    "PydanticSchemaInfo",
    "SchemaFieldInfo",
    "TestPatternInfo",
]
