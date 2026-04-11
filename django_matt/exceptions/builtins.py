from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse

import orjson

from django_matt.exceptions.filters import ExceptionFilter


def _json_response(data: dict[str, Any], status: int, headers: dict[str, str] | None = None) -> HttpResponse:
    body = orjson.dumps(data)
    response = HttpResponse(body, content_type="application/json", status=status)
    if headers:
        for k, v in headers.items():
            response[k] = v
    return response


class ValidationExceptionFilter(ExceptionFilter):
    order: int = 10

    @property
    def exception_types(self) -> tuple[type[Exception], ...]:  # type: ignore[override]
        from pydantic import ValidationError

        return (ValidationError,)

    def can_handle(self, exc: Exception) -> bool:
        from pydantic import ValidationError

        return isinstance(exc, ValidationError)

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        from pydantic import ValidationError

        assert isinstance(exc, ValidationError)
        errors = exc.errors()
        extra = [
            {
                "message": e.get("msg", str(e)),
                "key": e.get("loc", ("unknown",))[-1] if isinstance(e.get("loc"), (list, tuple)) else "unknown",
                "source": "body",
            }
            for e in errors
        ]
        return _json_response(
            {
                "status": 422,
                "detail": "Validation error",
                "code": "validation_error",
                "hint": "Check the request body against the expected schema. "
                "Run GET on this endpoint to see the required fields.",
                "extra": extra,
            },
            status=422,
        )


class NotFoundExceptionFilter(ExceptionFilter):
    exception_types = ()
    order: int = 10

    def can_handle(self, exc: Exception) -> bool:
        from django.core.exceptions import ObjectDoesNotExist

        return isinstance(exc, ObjectDoesNotExist)

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        detail = str(exc) or "Not found"
        return _json_response(
            {
                "status": 404,
                "detail": detail,
                "code": "not_found",
                "hint": "Check that the resource ID is correct and that the resource has not been deleted.",
                "extra": None,
            },
            status=404,
        )


class PermissionExceptionFilter(ExceptionFilter):
    exception_types = ()
    order: int = 10

    def can_handle(self, exc: Exception) -> bool:
        from django.core.exceptions import PermissionDenied

        return isinstance(exc, (PermissionDenied, PermissionError))

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        detail = str(exc) or "Permission denied"
        return _json_response(
            {
                "status": 403,
                "detail": detail,
                "code": "permission_denied",
                "hint": "Ensure the authenticated user has the required role or permission for this action.",
                "extra": None,
            },
            status=403,
        )


class DatabaseExceptionFilter(ExceptionFilter):
    exception_types = ()
    order: int = 20

    def can_handle(self, exc: Exception) -> bool:
        from django.db import IntegrityError

        return isinstance(exc, IntegrityError)

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        return _json_response(
            {
                "status": 409,
                "detail": "Database conflict",
                "code": "integrity_error",
                "hint": "A uniqueness or foreign-key constraint was violated. "
                "Check for duplicate values or ensure referenced resources exist.",
                "extra": None,
            },
            status=409,
        )


class ThrottleExceptionFilter(ExceptionFilter):
    exception_types = ()
    order: int = 5

    def can_handle(self, exc: Exception) -> bool:
        from django_matt.core.errors import RateLimitAPIError

        return isinstance(exc, RateLimitAPIError)

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        from django_matt.core.errors import RateLimitAPIError

        assert isinstance(exc, RateLimitAPIError)
        retry_after = exc.context.get("retry_after")
        headers: dict[str, str] = {}
        hint = "Too many requests."
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
            hint = f"Rate limited. Retry after {retry_after} seconds."
        return _json_response(
            {
                "status": 429,
                "detail": str(exc),
                "code": "rate_limited",
                "hint": hint,
                "extra": None,
            },
            status=429,
            headers=headers,
        )
