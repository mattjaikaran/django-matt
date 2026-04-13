"""Fix suggestion engine — pattern-matched suggestions for common errors."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Callable

from django_matt.errors.structured import StructuredError


@dataclass
class SuggestionPattern:
    """A pattern that matches an exception and produces suggestions."""

    exception_types: tuple[type[Exception], ...]
    message_pattern: re.Pattern[str] | None
    suggestions: list[str]
    related_settings: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    docs_url: str | None = None
    code: str | None = None
    detail: str | None = None
    priority: int = 0

    def matches(self, exc: Exception) -> bool:
        if not isinstance(exc, self.exception_types):
            return False
        if self.message_pattern is not None:
            return bool(self.message_pattern.search(str(exc)))
        return True


class SuggestionEngine:
    """Registry of error patterns mapped to fix suggestions.

    Supports both built-in patterns and custom registrations.
    Patterns are evaluated in priority order (higher first), and the
    first match wins.
    """

    def __init__(self) -> None:
        self._patterns: list[SuggestionPattern] = []
        self._custom_matchers: list[Callable[[Exception], StructuredError | None]] = []
        self._register_builtins()

    def register(
        self,
        exception_types: type[Exception] | tuple[type[Exception], ...],
        *,
        message_pattern: str | None = None,
        suggestions: list[str],
        related_settings: list[str] | None = None,
        search_terms: list[str] | None = None,
        docs_url: str | None = None,
        code: str | None = None,
        detail: str | None = None,
        priority: int = 0,
    ) -> None:
        """Register a new suggestion pattern."""
        if isinstance(exception_types, type):
            exception_types = (exception_types,)
        pattern = SuggestionPattern(
            exception_types=exception_types,
            message_pattern=re.compile(message_pattern) if message_pattern else None,
            suggestions=suggestions,
            related_settings=related_settings or [],
            search_terms=search_terms or [],
            docs_url=docs_url,
            code=code,
            detail=detail,
            priority=priority,
        )
        self._patterns.append(pattern)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)

    def register_matcher(
        self, matcher: Callable[[Exception], StructuredError | None]
    ) -> None:
        """Register a custom matcher function.

        The function receives an exception and returns a ``StructuredError``
        if it can handle it, or ``None`` to pass to the next matcher.
        """
        self._custom_matchers.append(matcher)

    def get_suggestions(self, exc: Exception) -> StructuredError:
        """Produce a ``StructuredError`` for the given exception.

        Tries custom matchers first, then pattern registry, then falls
        back to a generic error.
        """
        # custom matchers first
        for matcher in self._custom_matchers:
            result = matcher(exc)
            if result is not None:
                return result

        # pattern registry
        for pattern in self._patterns:
            if pattern.matches(exc):
                return StructuredError(
                    code=pattern.code or _exc_to_code(exc),
                    message=str(exc) or exc.__class__.__name__,
                    status_code=_exc_to_status(exc),
                    detail=pattern.detail,
                    fix_suggestions=pattern.suggestions,
                    docs_url=pattern.docs_url,
                    related_settings=pattern.related_settings,
                    search_terms=pattern.search_terms,
                    exception_type=exc.__class__.__qualname__,
                )

        # fallback
        return StructuredError(
            code=_exc_to_code(exc),
            message=str(exc) or exc.__class__.__name__,
            status_code=_exc_to_status(exc),
            fix_suggestions=["Review the error message and traceback for more information."],
            exception_type=exc.__class__.__qualname__,
        )

    # ------------------------------------------------------------------
    # Built-in patterns
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register all built-in suggestion patterns."""

        # --- Django ImproperlyConfigured ---
        self.register(
            _lazy_type("django.core.exceptions", "ImproperlyConfigured"),
            suggestions=[
                "Check INSTALLED_APPS for missing or misspelled app names.",
                "Verify MIDDLEWARE ordering — authentication middleware must come before permission middleware.",
                "Ensure all required settings are defined (check settings.py or environment variables).",
            ],
            related_settings=["INSTALLED_APPS", "MIDDLEWARE", "DATABASES"],
            search_terms=["django ImproperlyConfigured", "django settings misconfiguration"],
            code="IMPROPERLY_CONFIGURED",
            detail="Django detected a configuration error. This usually means a required setting is missing or an app/middleware is not installed correctly.",
            priority=10,
        )

        # --- Database OperationalError ---
        self.register(
            _lazy_type("django.db", "OperationalError"),
            suggestions=[
                "Check that the database server is running and accepting connections.",
                "Verify DATABASES settings (HOST, PORT, NAME, USER, PASSWORD).",
                "Run `python manage.py migrate` to apply pending migrations.",
                "If using connection pooling, check pool size and timeout settings.",
            ],
            related_settings=["DATABASES", "CONN_MAX_AGE", "CONN_HEALTH_CHECKS"],
            search_terms=["django OperationalError database", "database connection refused"],
            code="DATABASE_ERROR",
            detail="A database operation failed. This could be a connection issue, missing table, or query error.",
            priority=10,
        )

        # --- Pydantic ValidationError ---
        self.register(
            _lazy_type("pydantic", "ValidationError"),
            suggestions=[
                "Check that the request body matches the expected schema.",
                "Verify field types — e.g., string where int expected, missing required fields.",
                "Run GET on the endpoint to see the expected schema shape.",
            ],
            search_terms=["pydantic validation error", "request body validation"],
            code="VALIDATION_ERROR",
            detail="The request data did not pass schema validation. Check the context for field-level errors.",
            priority=10,
        )

        # --- PermissionDenied ---
        self.register(
            _lazy_type("django.core.exceptions", "PermissionDenied"),
            suggestions=[
                "Ensure the user is authenticated before accessing this resource.",
                "Check that the user has the required role or permission.",
                "Verify permission_classes on the controller/view.",
            ],
            related_settings=["MATT_AUTH", "AUTHENTICATION_BACKENDS"],
            search_terms=["django permission denied", "403 forbidden"],
            code="PERMISSION_DENIED",
            detail="The current user does not have permission to perform this action.",
            priority=10,
        )

        # --- AuthenticationFailed (django-matt) ---
        self.register(
            _lazy_type("django_matt.core.errors", "AuthenticationAPIError"),
            suggestions=[
                "Check that the JWT token is not expired (decode at jwt.io).",
                "Verify the Authorization header format: 'Bearer <token>'.",
                "Ensure the signing algorithm matches MATT_AUTH['ALGORITHM'].",
                "Check that the token was issued by this server (verify SECRET_KEY).",
            ],
            related_settings=["MATT_AUTH", "SECRET_KEY"],
            search_terms=["JWT token expired", "authentication failed", "401 unauthorized"],
            code="AUTH_FAILED",
            detail="Authentication credentials were missing, expired, or invalid.",
            priority=10,
        )

        # --- ModuleNotFoundError ---
        self.register(
            ModuleNotFoundError,
            suggestions=[
                "Install the missing package with `uv add <package>`.",
                "Check for typos in the import path.",
                "Verify the package is listed in pyproject.toml dependencies.",
            ],
            search_terms=["python ModuleNotFoundError", "missing package"],
            code="MODULE_NOT_FOUND",
            detail="A required Python module could not be imported.",
            priority=10,
        )

        # --- ImportError ---
        self.register(
            ImportError,
            suggestions=[
                "Verify the import path is correct.",
                "Check that the package version supports the imported symbol.",
                "Install or upgrade the package with `uv add <package>`.",
            ],
            search_terms=["python ImportError", "cannot import name"],
            code="IMPORT_ERROR",
            priority=5,
        )

        # --- AttributeError on model (fuzzy match) ---
        self.register_matcher(_attribute_error_matcher)

        # --- KeyError ---
        self.register(
            KeyError,
            suggestions=[
                "Use .get(key, default) instead of direct dict access to handle missing keys.",
                "Check that the expected key exists in the data before accessing it.",
            ],
            search_terms=["python KeyError", "missing dictionary key"],
            code="KEY_ERROR",
            priority=5,
        )

        # --- TypeError ---
        self.register(
            TypeError,
            suggestions=[
                "Check argument types — a function received an unexpected type.",
                "Verify that async functions are awaited and sync functions are not.",
            ],
            search_terms=["python TypeError", "wrong argument type"],
            code="TYPE_ERROR",
            priority=5,
        )

        # --- NotImplementedError ---
        self.register(
            NotImplementedError,
            suggestions=[
                "This method or feature needs to be implemented.",
                "Check if there is an alternative method or a newer API version.",
            ],
            search_terms=["python NotImplementedError"],
            code="NOT_IMPLEMENTED",
            priority=5,
        )

        # --- ConnectionError ---
        self.register(
            ConnectionError,
            suggestions=[
                "Verify the target service is running and reachable.",
                "Check network configuration, firewalls, and DNS resolution.",
                "Increase connection timeout if the service is slow to respond.",
            ],
            search_terms=["python ConnectionError", "connection refused"],
            code="CONNECTION_ERROR",
            priority=5,
        )

        # --- TimeoutError ---
        self.register(
            TimeoutError,
            suggestions=[
                "Increase the timeout value for this operation.",
                "Check if the target service is overloaded or unresponsive.",
                "Consider adding retry logic with exponential backoff.",
            ],
            search_terms=["python TimeoutError", "request timeout"],
            code="TIMEOUT_ERROR",
            priority=5,
        )


def _attribute_error_matcher(exc: Exception) -> StructuredError | None:
    """Match AttributeError and suggest similar attribute names via fuzzy matching."""
    if not isinstance(exc, AttributeError):
        return None

    msg = str(exc)
    suggestions = [
        "Verify the attribute name is spelled correctly.",
        "Check that the object is the expected type (not None).",
    ]
    search_terms = ["python AttributeError", "object has no attribute"]

    # Try to extract object type and attribute from the message
    # Pattern: "'Foo' object has no attribute 'bar'"
    match = re.search(r"'(\w+)' object has no attribute '(\w+)'", msg)
    if match:
        obj_type_name = match.group(1)
        attr_name = match.group(2)

        # Try to find the actual type and suggest close matches
        close = _find_close_attributes(obj_type_name, attr_name)
        if close:
            suggestions.insert(0, f"Did you mean one of: {', '.join(close)}?")
            search_terms.append(f"{obj_type_name} attributes")

    return StructuredError(
        code="ATTRIBUTE_ERROR",
        message=msg,
        status_code=500,
        detail="An attribute access failed. The object may be the wrong type or the attribute name is misspelled.",
        fix_suggestions=suggestions,
        search_terms=search_terms,
        exception_type="AttributeError",
    )


def _find_close_attributes(type_name: str, attr_name: str) -> list[str]:
    """Find similar attribute names on a type using difflib."""
    # Try to find the class in Django models first
    try:
        from django.apps import apps

        for model in apps.get_models():
            if model.__name__ == type_name:
                field_names = [f.name for f in model._meta.get_fields()]
                return difflib.get_close_matches(attr_name, field_names, n=3, cutoff=0.5)
    except Exception:
        pass

    # Try builtins / common types
    try:
        import builtins

        cls = getattr(builtins, type_name, None)
        if cls is not None:
            attrs = [a for a in dir(cls) if not a.startswith("_")]
            return difflib.get_close_matches(attr_name, attrs, n=3, cutoff=0.5)
    except Exception:
        pass

    return []


def _lazy_type(module_path: str, name: str) -> type[Exception]:
    """Import an exception type lazily, falling back to Exception."""
    try:
        from importlib import import_module

        mod = import_module(module_path)
        return getattr(mod, name)
    except (ImportError, AttributeError):
        return Exception


def _exc_to_code(exc: Exception) -> str:
    """Derive a machine-readable code from an exception class name."""
    name = exc.__class__.__name__
    # CamelCase → UPPER_SNAKE
    code = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    code = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", code)
    return code.upper()


def _exc_to_status(exc: Exception) -> int:
    """Derive an HTTP status code from an exception."""
    if hasattr(exc, "status_code"):
        return exc.status_code

    from pydantic import ValidationError

    status_map: list[tuple[type[Exception], int]] = [
        (ValidationError, 422),
        (PermissionError, 403),
        (FileNotFoundError, 404),
        (NotImplementedError, 501),
        (KeyError, 400),
        (TimeoutError, 504),
    ]
    for exc_type, status in status_map:
        if isinstance(exc, exc_type):
            return status

    # Django-specific
    try:
        from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

        if isinstance(exc, ObjectDoesNotExist):
            return 404
        if isinstance(exc, PermissionDenied):
            return 403
    except ImportError:
        pass

    return 500


# Module-level singleton
default_engine = SuggestionEngine()
