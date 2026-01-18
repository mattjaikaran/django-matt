"""
Django project introspection for AI context generation.

Extracts information about models, views, URLs, and settings
to help AI assistants understand the project structure.
"""

import importlib
import inspect
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from django.apps import apps
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver


@dataclass
class FieldInfo:
    """Information about a model field."""
    name: str
    field_type: str
    nullable: bool = False
    blank: bool = False
    unique: bool = False
    primary_key: bool = False
    default: Optional[str] = None
    choices: Optional[List[tuple]] = None
    related_model: Optional[str] = None
    help_text: str = ""


@dataclass
class ModelInfo:
    """Information about a Django model."""
    name: str
    app_label: str
    module: str
    table_name: str
    fields: List[FieldInfo] = field(default_factory=list)
    meta_options: Dict[str, Any] = field(default_factory=dict)
    docstring: str = ""
    is_abstract: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.app_label}.{self.name}"


@dataclass
class ViewInfo:
    """Information about a view."""
    name: str
    module: str
    view_type: str  # function, class, viewset
    methods: List[str] = field(default_factory=list)
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)


@dataclass
class URLInfo:
    """Information about a URL pattern."""
    pattern: str
    name: Optional[str]
    view_name: str
    methods: List[str] = field(default_factory=list)
    namespace: Optional[str] = None


@dataclass
class AppInfo:
    """Information about a Django app."""
    name: str
    label: str
    path: str
    models: List[ModelInfo] = field(default_factory=list)
    views: List[ViewInfo] = field(default_factory=list)
    urls: List[URLInfo] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """Complete project information."""
    name: str
    root_path: str
    python_version: str
    django_version: str
    apps: List[AppInfo] = field(default_factory=list)
    settings_module: str = ""
    installed_packages: List[str] = field(default_factory=list)
    middleware: List[str] = field(default_factory=list)
    databases: Dict[str, str] = field(default_factory=dict)


class ProjectIntrospector:
    """
    Introspects a Django project to extract structural information.

    Usage:
        introspector = ProjectIntrospector()
        project_info = introspector.introspect()
    """

    def __init__(
        self,
        include_third_party: bool = False,
        exclude_apps: Optional[List[str]] = None,
    ):
        """
        Initialize introspector.

        Args:
            include_third_party: Include third-party apps
            exclude_apps: Apps to exclude from introspection
        """
        self.include_third_party = include_third_party
        self.exclude_apps = set(exclude_apps or [])
        self._project_root = self._find_project_root()

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        # Start from settings module location
        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if settings_module:
            try:
                module = importlib.import_module(settings_module)
                if hasattr(module, "__file__") and module.__file__:
                    return Path(module.__file__).parent.parent
            except ImportError:
                pass

        # Fallback to current directory
        return Path.cwd()

    def _is_project_app(self, app_config) -> bool:
        """Check if an app is part of the project (not third-party)."""
        if self.include_third_party:
            return True

        app_path = Path(app_config.path)
        try:
            app_path.relative_to(self._project_root)
            return True
        except ValueError:
            return False

    def introspect(self) -> ProjectInfo:
        """Perform full project introspection."""
        import django
        import sys

        project_info = ProjectInfo(
            name=self._project_root.name,
            root_path=str(self._project_root),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            django_version=django.__version__,
            settings_module=os.environ.get("DJANGO_SETTINGS_MODULE", ""),
            middleware=list(getattr(settings, "MIDDLEWARE", [])),
            databases={
                name: conf.get("ENGINE", "").split(".")[-1]
                for name, conf in getattr(settings, "DATABASES", {}).items()
            },
        )

        # Introspect apps
        for app_config in apps.get_app_configs():
            if app_config.label in self.exclude_apps:
                continue

            if not self._is_project_app(app_config):
                continue

            app_info = self._introspect_app(app_config)
            project_info.apps.append(app_info)

        # Get installed packages
        project_info.installed_packages = self._get_installed_packages()

        return project_info

    def _introspect_app(self, app_config) -> AppInfo:
        """Introspect a single app."""
        app_info = AppInfo(
            name=app_config.name,
            label=app_config.label,
            path=app_config.path,
        )

        # Get models
        for model in app_config.get_models():
            model_info = self._introspect_model(model)
            app_info.models.append(model_info)

        # Get views
        app_info.views = self._introspect_views(app_config)

        # Get URLs
        app_info.urls = self._get_app_urls(app_config.label)

        return app_info

    def _introspect_model(self, model: Type) -> ModelInfo:
        """Introspect a Django model."""
        meta = model._meta

        model_info = ModelInfo(
            name=model.__name__,
            app_label=meta.app_label,
            module=model.__module__,
            table_name=meta.db_table,
            docstring=inspect.getdoc(model) or "",
            is_abstract=meta.abstract,
        )

        # Get fields
        for field in meta.get_fields():
            if hasattr(field, "get_internal_type"):
                field_info = FieldInfo(
                    name=field.name,
                    field_type=field.get_internal_type(),
                    nullable=getattr(field, "null", False),
                    blank=getattr(field, "blank", False),
                    unique=getattr(field, "unique", False),
                    primary_key=getattr(field, "primary_key", False),
                    help_text=str(getattr(field, "help_text", "")),
                )

                # Handle default
                if hasattr(field, "default") and field.default is not None:
                    if callable(field.default):
                        field_info.default = f"{field.default.__name__}()"
                    elif field.default != field.empty:
                        field_info.default = repr(field.default)

                # Handle choices
                if hasattr(field, "choices") and field.choices:
                    field_info.choices = list(field.choices)

                # Handle relations
                if hasattr(field, "related_model") and field.related_model:
                    field_info.related_model = f"{field.related_model._meta.app_label}.{field.related_model.__name__}"

                model_info.fields.append(field_info)

        # Get meta options
        for option in ["ordering", "unique_together", "indexes", "permissions"]:
            value = getattr(meta, option, None)
            if value:
                model_info.meta_options[option] = str(value)

        return model_info

    def _introspect_views(self, app_config) -> List[ViewInfo]:
        """Introspect views in an app."""
        views = []

        # Try to import views module
        try:
            views_module = importlib.import_module(f"{app_config.name}.views")
        except ImportError:
            return views

        for name, obj in inspect.getmembers(views_module):
            if name.startswith("_"):
                continue

            if inspect.isfunction(obj):
                view_info = ViewInfo(
                    name=name,
                    module=f"{app_config.name}.views",
                    view_type="function",
                    docstring=inspect.getdoc(obj) or "",
                )
                views.append(view_info)

            elif inspect.isclass(obj):
                # Check if it's a view class
                if hasattr(obj, "as_view") or hasattr(obj, "dispatch"):
                    methods = []
                    for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                        if hasattr(obj, method):
                            methods.append(method.upper())

                    view_info = ViewInfo(
                        name=name,
                        module=f"{app_config.name}.views",
                        view_type="class",
                        methods=methods,
                        docstring=inspect.getdoc(obj) or "",
                    )
                    views.append(view_info)

        return views

    def _get_app_urls(self, app_label: str) -> List[URLInfo]:
        """Get URLs for an app."""
        urls = []

        def extract_urls(patterns, namespace=None, prefix=""):
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    new_namespace = pattern.namespace or namespace
                    new_prefix = prefix + str(pattern.pattern)
                    extract_urls(pattern.url_patterns, new_namespace, new_prefix)
                elif isinstance(pattern, URLPattern):
                    # Check if this URL belongs to the app
                    callback = pattern.callback
                    if callback:
                        module = getattr(callback, "__module__", "")
                        if app_label in module or (hasattr(callback, "cls") and app_label in getattr(callback.cls, "__module__", "")):
                            url_info = URLInfo(
                                pattern=prefix + str(pattern.pattern),
                                name=pattern.name,
                                view_name=getattr(callback, "__name__", str(callback)),
                                namespace=namespace,
                            )
                            urls.append(url_info)

        try:
            resolver = get_resolver()
            extract_urls(resolver.url_patterns)
        except Exception:
            pass

        return urls

    def _get_installed_packages(self) -> List[str]:
        """Get list of installed packages."""
        packages = []

        try:
            import pkg_resources
            for dist in pkg_resources.working_set:
                packages.append(f"{dist.project_name}=={dist.version}")
        except ImportError:
            pass

        return sorted(packages)[:50]  # Limit to top 50


def get_project_structure(root_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a simple dictionary representation of project structure.

    Returns file tree with Python files highlighted.
    """
    root = Path(root_path) if root_path else Path.cwd()

    def scan_directory(path: Path, depth: int = 0, max_depth: int = 4) -> Dict[str, Any]:
        if depth > max_depth:
            return {}

        result = {}

        try:
            for item in sorted(path.iterdir()):
                # Skip common non-essential directories
                if item.name in {
                    "__pycache__", ".git", ".venv", "venv", "node_modules",
                    ".pytest_cache", ".mypy_cache", "htmlcov", "dist", "build",
                    ".eggs", "*.egg-info", ".tox", ".coverage",
                }:
                    continue

                if item.name.startswith(".") and item.name not in {".env.example"}:
                    continue

                if item.is_dir():
                    children = scan_directory(item, depth + 1, max_depth)
                    if children:  # Only include non-empty directories
                        result[item.name + "/"] = children
                elif item.suffix in {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}:
                    result[item.name] = None
        except PermissionError:
            pass

        return result

    return scan_directory(root)


__all__ = [
    "FieldInfo",
    "ModelInfo",
    "ViewInfo",
    "URLInfo",
    "AppInfo",
    "ProjectInfo",
    "ProjectIntrospector",
    "get_project_structure",
]
