# Backwards compat — import from core
from django_matt.core.errors import *  # noqa: F403
from django_matt.core.errors import (  # noqa: F401
    APIError,
    AuthenticationAPIError,
    ConfigurationError,
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    NotFoundAPIError,
    PermissionAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
    ValidationAPIError,
    ValidationErrorFormatter,
    _make_error_envelope,
    error_handler,
    handle_exceptions,
)
