from __future__ import annotations

from django_matt.exceptions.builtins import (
    DatabaseExceptionFilter,
    NotFoundExceptionFilter,
    PermissionExceptionFilter,
    ThrottleExceptionFilter,
    ValidationExceptionFilter,
)
from django_matt.exceptions.decorators import (
    catch,
    catch_all,
    exception_filter,
    register_global_filter,
)
from django_matt.exceptions.filters import (
    ExceptionFilter,
    ExceptionFilterChain,
    FunctionExceptionFilter,
)
from django_matt.exceptions.registry import (
    ExceptionFilterRegistry,
    default_registry,
)

__all__ = [
    "ExceptionFilter",
    "ExceptionFilterChain",
    "ExceptionFilterRegistry",
    "FunctionExceptionFilter",
    "catch",
    "catch_all",
    "default_registry",
    "exception_filter",
    "register_global_filter",
    # builtins
    "DatabaseExceptionFilter",
    "NotFoundExceptionFilter",
    "PermissionExceptionFilter",
    "ThrottleExceptionFilter",
    "ValidationExceptionFilter",
]
