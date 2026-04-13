import datetime
import inspect
import json
import logging
import os
import sys
import traceback
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse

import orjson
from pydantic import ValidationError

logger = logging.getLogger("django_matt.errors")


class ErrorDetail:
    """
    Detailed error information with context.

    Supports two construction styles:

    Style A — core/errors style (status_code-aware):
        ErrorDetail(message, error_type, code, status_code, path, line_number, ...)

    Style B — utils/errors style (traceback-first):
        ErrorDetail(message, exception_type, traceback_str, file_path, line_number, ...)

    Both styles expose the full set of attributes so that either can be passed
    to either ``to_dict()`` implementation.
    """

    def __init__(
        self,
        message: str,
        # Style A fields
        error_type: str | None = None,
        code: str = "error",
        status_code: int = 500,
        path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
        traceback_str: str | None = None,
        code_snippet: list[str] | dict[int, str] | None = None,
        # Style B additional fields
        exception_type: str | None = None,
        file_path: str | None = None,
    ):
        self.message = message
        # Normalise: exception_type and error_type are the same concept
        self.error_type = error_type or exception_type or "UnknownError"
        self.exception_type = self.error_type  # alias for utils-style consumers
        self.code = code
        self.status_code = status_code
        # Track which construction style was used for serialisation.
        # utils/errors style: callers pass exception_type= or file_path=
        # core/errors style: callers pass error_type= or path=
        self._utils_style = exception_type is not None or file_path is not None
        # Normalise: path and file_path are the same concept
        self.path = path or file_path
        self.file_path = self.path  # alias for utils-style consumers
        self.line_number = line_number
        self.context = context or {}
        self.suggestion = suggestion
        self.traceback_str = traceback_str
        self.code_snippet = code_snippet
        self.timestamp = datetime.datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Style A serialisation (used by core/errors consumers)
    # ------------------------------------------------------------------

    def to_dict(
        self,
        include_traceback: bool = False,
        include_snippet: bool = False,
    ) -> dict[str, Any]:
        """Convert error details to a dictionary.

        Calling with no arguments produces the standard API envelope:
            {"status": ..., "detail": "...", "extra": null}
        """
        result: dict[str, Any] = {
            "message": self.message,
            "error_type": self.error_type,
            "code": self.code,
            "status_code": self.status_code,
            "timestamp": self.timestamp,
        }
        # utils/errors style: expose exception_type in output
        if self._utils_style:
            result["exception_type"] = self.error_type

        if self.path:
            if self._utils_style:
                # utils/errors style: location uses "file" key
                result["location"] = {"file": self.path, "line": self.line_number}
            else:
                # core/errors style: location uses "path" key
                result["location"] = {"path": self.path, "line": self.line_number}

        if self.context:
            result["context"] = self.context

        if self.suggestion:
            result["suggestion"] = self.suggestion

        if include_traceback and self.traceback_str:
            result["traceback"] = self.traceback_str

        if self.code_snippet:
            if include_snippet or self._utils_style:
                # utils style: always show snippet when present
                # core style: only show when include_snippet=True
                result["code_snippet"] = self.code_snippet

        return result

    def to_json(self, include_traceback: bool = False, include_snippet: bool = False) -> str:
        """Convert error details to JSON."""
        return orjson.dumps(
            self.to_dict(include_traceback=include_traceback, include_snippet=include_snippet),
            option=orjson.OPT_INDENT_2,
        ).decode()

    def to_response(
        self, include_traceback: bool = False, include_snippet: bool = False
    ) -> JsonResponse:
        """Convert error details to a JsonResponse."""
        return JsonResponse(
            self.to_dict(include_traceback=include_traceback, include_snippet=include_snippet),
            status=self.status_code,
        )


def _make_error_envelope(
    status: int,
    detail: str,
    extra: list[dict[str, Any]] | None = None,
    *,
    code: str | None = None,
    hint: str | None = None,
    docs_url: str | None = None,
) -> dict[str, Any]:
    """
    Build the standard API error envelope.

    Response body::

        {
            "status": 400,
            "detail": "message",
            "code": "validation_error",
            "hint": "Check the request body matches the schema.",
            "docs_url": "https://...",
            "extra": null
        }

    ``code`` is a stable, machine-readable error identifier (e.g.
    ``"not_found"``, ``"validation_error"``).  LLM agents and client
    code-generators can switch on this field instead of parsing
    ``detail`` strings.

    ``hint`` is a one-line, actionable suggestion aimed at developers
    and LLM agents — it tells the caller *what to do next* rather than
    just what went wrong.

    ``docs_url`` points to the relevant documentation page when
    available.
    """
    envelope: dict[str, Any] = {"status": status, "detail": detail}
    if code is not None:
        envelope["code"] = code
    if hint is not None:
        envelope["hint"] = hint
    if docs_url is not None:
        envelope["docs_url"] = docs_url
    envelope["extra"] = extra
    return envelope


class ErrorHandler:
    """
    Error handler for Django Matt framework.

    Supports both instance-based usage (core style) and static/class-method
    usage (utils style).
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

    # ------------------------------------------------------------------
    # Instance methods (core/errors style)
    # ------------------------------------------------------------------

    def capture_exception(self, exc: Exception, request: HttpRequest | None = None) -> ErrorDetail:
        """
        Capture an exception and create detailed error information.

        Args:
            exc: The exception to capture
            request: The HTTP request that caused the exception (optional)

        Returns:
            ErrorDetail object with rich error information
        """
        error_type = exc.__class__.__name__
        message = str(exc)
        status_code = self._get_status_code(exc)
        code = self._get_error_code(exc)

        # Get traceback information
        tb = traceback.extract_tb(sys.exc_info()[2])
        if tb:
            frame = tb[-1]  # Get the last frame (where the error occurred)
            path = frame.filename
            line_number = frame.lineno

            # Get code snippet if in debug mode
            code_snippet = None
            if self.debug:
                code_snippet = self._get_code_snippet(path, line_number)
        else:
            path = None
            line_number = None
            code_snippet = None

        # Format traceback
        traceback_str = None
        if self.debug:
            traceback_str = "".join(traceback.format_exception(type(exc), exc, sys.exc_info()[2]))

        # Build context
        context = {}
        if request:
            context["request"] = {
                "method": request.method,
                "path": request.path,
                "query_params": dict(request.GET.items()),
            }

            # Add body if it's a JSON request
            if request.content_type == "application/json" and request.body:
                try:
                    context["request"]["body"] = orjson.loads(request.body)
                except (orjson.JSONDecodeError, ValueError):
                    context["request"]["body"] = "Invalid JSON"

        # Generate suggestion
        suggestion = self._generate_suggestion(exc, error_type)

        # Create error detail
        error_detail = ErrorDetail(
            message=message,
            error_type=error_type,
            code=code,
            status_code=status_code,
            path=path,
            line_number=line_number,
            context=context,
            suggestion=suggestion,
            traceback_str=traceback_str,
            code_snippet=code_snippet,
        )

        # Log the error
        logger.error(
            f"Error: {error_type} - {message}",
            extra={"error_detail": error_detail.to_dict(include_traceback=True)},
        )

        return error_detail

    def _get_status_code(self, exc: Exception) -> int:
        """Get the appropriate HTTP status code for an exception."""
        if hasattr(exc, "status_code"):
            return exc.status_code

        # Map common exceptions to status codes
        if isinstance(exc, ValidationError):
            return 422  # Unprocessable Entity
        if isinstance(exc, PermissionError):
            return 403  # Forbidden
        if isinstance(exc, FileNotFoundError):
            return 404  # Not Found
        if (
            isinstance(exc, json.JSONDecodeError)
            or isinstance(exc, KeyError)
            or isinstance(exc, AttributeError)
        ):
            return 400  # Bad Request
        if isinstance(exc, NotImplementedError):
            return 501  # Not Implemented

        # Default to 500 Internal Server Error
        return 500

    def _get_error_code(self, exc: Exception) -> str:
        """Get a machine-readable error code for an exception."""
        if hasattr(exc, "code"):
            return exc.code

        # Generate a code based on the exception type
        return exc.__class__.__name__.lower()

    def _get_code_snippet(self, path: str, line_number: int, context_lines: int = 5) -> list[str]:
        """Get a code snippet around the error location."""
        try:
            if not os.path.exists(path):
                return None

            with open(path) as f:
                lines = f.readlines()

            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)

            return [f"{i + 1}: {lines[i].rstrip()}" for i in range(start_line, end_line)]
        except Exception:
            return None

    def _generate_suggestion(self, exc: Exception, error_type: str) -> str:
        """Generate a helpful suggestion for fixing the error."""
        if isinstance(exc, ValidationError):
            return "Check the request data against the schema requirements."
        if isinstance(exc, PermissionError):
            return "Ensure the user has the necessary permissions for this action."
        if isinstance(exc, FileNotFoundError):
            return (
                f"The file '{exc.filename}' could not be found. Check the path and file existence."
            )
        if isinstance(exc, json.JSONDecodeError):
            return "The JSON data is invalid. Check the syntax and structure."
        if isinstance(exc, KeyError):
            return f"The key '{exc.args[0]}' was not found in the dictionary."
        if isinstance(exc, AttributeError):
            return "Check that you're accessing a valid attribute on the object."
        if isinstance(exc, NotImplementedError):
            return "This feature is not yet implemented."

        # Default suggestion
        return "Review the error message and traceback for more information."

    # ------------------------------------------------------------------
    # Static / class methods (utils/errors style)
    # ------------------------------------------------------------------

    @staticmethod
    def get_code_snippet(
        file_path: str, line_number: int, context_lines: int = 3
    ) -> dict[int, str]:
        """Get a code snippet around the error location (returns line-keyed dict)."""
        if not os.path.exists(file_path):
            return {}

        try:
            with open(file_path) as f:
                lines = f.readlines()

            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)

            return {i + 1: lines[i].rstrip() for i in range(start_line, end_line)}
        except Exception:
            return {}

    @staticmethod
    def extract_error_location(tb_frame) -> tuple[str, int]:
        """Extract file path and line number from a traceback frame."""
        file_path = tb_frame.tb_frame.f_code.co_filename
        line_number = tb_frame.tb_lineno
        return file_path, line_number

    @staticmethod
    def generate_suggestion(exception: Exception, error_type: str) -> str | None:
        """Generate a helpful suggestion based on the exception type (utils style)."""
        if error_type == "ValidationError":
            return "Check the data structure against the schema requirements."
        if error_type == "TypeError":
            return "Verify the types of all arguments being passed."
        if error_type == "AttributeError":
            return "Ensure the object has the attribute you're trying to access."
        if error_type == "ImportError":
            return "Check that the module exists and is installed."
        if error_type == "KeyError":
            return "Verify the key exists in the dictionary before accessing it."
        if error_type == "IndexError":
            return "Ensure the index is within the bounds of the list."
        if error_type == "SyntaxError":
            return "Fix the syntax error in your code."
        if error_type == "NameError":
            return "Make sure the variable is defined before using it."
        if error_type == "FileNotFoundError":
            return "Verify the file path is correct and the file exists."
        if error_type == "PermissionError":
            return "Check file permissions or if you have the necessary access rights."
        if error_type == "ConnectionError":
            return "Verify network connectivity and that the service is running."
        if error_type == "ValueError":
            return "Check that the value is appropriate for the operation."
        if error_type == "ZeroDivisionError":
            return "Avoid dividing by zero; add a check before division."
        if error_type == "AssertionError":
            return "The assertion condition failed; check your assumptions."
        if error_type == "RuntimeError":
            return "A runtime error occurred; check the execution flow."
        if error_type == "NotImplementedError":
            return "This feature is not implemented yet; implement it or use an alternative."
        if error_type == "RecursionError":
            return "Your recursion is too deep; check for infinite recursion or use iteration."
        if error_type == "MemoryError":
            return "The operation is using too much memory; optimize memory usage."
        if error_type == "TimeoutError":
            return "The operation timed out; check for long-running operations or increase timeout."
        if error_type == "StopIteration":
            return "The iterator has no more items; check your iteration logic."
        return None

    @classmethod
    def capture_error(cls, exception: Exception) -> "ErrorDetail":
        """Capture and format error details from an exception (utils/errors style)."""
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # Get the traceback as a string
        traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # Get the error type
        error_type = exc_type.__name__ if exc_type else "Unknown"

        # Get the error message
        error_message = str(exc_value) if exc_value else "No error message"

        # Get the traceback frame for the error location
        tb_frame = exc_traceback
        while tb_frame and tb_frame.tb_next:
            tb_frame = tb_frame.tb_next

        file_path = None
        line_number = None
        code_snippet: dict[int, str] = {}

        if tb_frame:
            file_path, line_number = cls.extract_error_location(tb_frame)
            if file_path and line_number:
                code_snippet = cls.get_code_snippet(file_path, line_number)

        # Generate a suggestion
        suggestion = cls.generate_suggestion(exception, error_type)

        # Create context information
        context = {}

        # For validation errors, add more context
        if isinstance(exception, ValidationError):
            context["validation_errors"] = exception.errors()

        return ErrorDetail(
            message=error_message,
            exception_type=error_type,
            traceback_str=traceback_str,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
            context=context,
            suggestion=suggestion,
        )

    @classmethod
    def format_response(
        cls, exception: Exception, include_traceback: bool | None = None
    ) -> dict[str, Any]:
        """Format an exception into a detailed error response (utils/errors style)."""
        if include_traceback is None:
            include_traceback = getattr(settings, "DEBUG", False)

        error_detail = cls.capture_error(exception)
        return {"error": error_detail.to_dict(include_traceback=include_traceback)}

    @classmethod
    def json_response(
        cls,
        exception: Exception,
        status_code: int = 500,
        include_traceback: bool | None = None,
    ) -> JsonResponse:
        """Create a JSON response with detailed error information (utils/errors style)."""
        response_data = cls.format_response(exception, include_traceback)
        return JsonResponse(response_data, status=status_code)


class APIError(Exception):
    """
    Base class for API errors in Django Matt.

    This exception can be raised with custom status codes and error details.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "api_error",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.context = context or {}
        self.suggestion = suggestion
        super().__init__(message)

    def to_response(self) -> JsonResponse:
        """Render the standard error envelope as a JSON response."""
        is_debug = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
        extra = self.context if (is_debug and self.context) else None
        envelope = _make_error_envelope(
            self.status_code,
            self.message,
            extra,
            code=self.code,
            hint=self.suggestion,
        )
        return JsonResponse(envelope, status=self.status_code)


class ValidationAPIError(APIError):
    """Error raised when validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        errors: list[dict[str, Any]] | None = None,
        status_code: int = 422,
        code: str = "validation_error",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        self.errors = errors or []
        context = context or {}
        context["validation_errors"] = self.errors
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion or "Check the request data against the schema requirements.",
        )

    def to_response(self) -> JsonResponse:
        """Render with field-level ``extra`` list in the standard envelope."""
        extra: list[dict[str, Any]] | None = None
        if self.errors:
            extra = [
                {
                    "message": e.get("message", e.get("msg", str(e))),
                    "key": e.get("field", e.get("loc", ["unknown"])[-1] if isinstance(e.get("loc"), (list, tuple)) else e.get("loc", "unknown")),
                    "source": "body",
                }
                for e in self.errors
            ]
        envelope = _make_error_envelope(
            self.status_code,
            self.message,
            extra,
            code=self.code,
            hint=self.suggestion,
        )
        return JsonResponse(envelope, status=self.status_code)


class NotFoundAPIError(APIError):
    """Error raised when a resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: str | None = None,
        resource_id: str | None = None,
        status_code: int = 404,
        code: str = "not_found",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        context = context or {}
        if resource_type:
            context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
            message = f"{resource_type or 'Resource'} with ID '{resource_id}' not found"

        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion
            or "Check that the resource exists and that you have the correct ID.",
        )


class PermissionAPIError(APIError):
    """Error raised when a user doesn't have permission."""

    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: str | None = None,
        status_code: int = 403,
        code: str = "permission_denied",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        context = context or {}
        if required_permission:
            context["required_permission"] = required_permission
            message = f"Permission denied: '{required_permission}' is required"

        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion
            or "Ensure the user has the necessary permissions for this action.",
        )


class AuthenticationAPIError(APIError):
    """Error raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication required",
        auth_type: str | None = None,
        status_code: int = 401,
        code: str = "authentication_required",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        context = context or {}
        if auth_type:
            context["auth_type"] = auth_type

        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion or "Provide valid authentication credentials.",
        )


class RateLimitAPIError(APIError):
    """Error raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        limit: int | None = None,
        remaining: int | None = None,
        status_code: int = 429,
        code: str = "rate_limit_exceeded",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        context = context or {}
        if retry_after:
            context["retry_after"] = retry_after
        if limit:
            context["limit"] = limit
        if remaining is not None:
            context["remaining"] = remaining

        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion
            or f"Please wait {retry_after or 'some time'} seconds before retrying.",
        )


class ConfigurationError(APIError):
    """Error raised when a controller or component is misconfigured."""

    def __init__(
        self,
        message: str = "Configuration error",
        status_code: int = 500,
        code: str = "configuration_error",
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
            context=context,
            suggestion=suggestion or "Check the controller/component configuration.",
        )


# Alias for backward compatibility
PermissionDeniedAPIError = PermissionAPIError


class ValidationErrorFormatter:
    """
    Utility class to format Pydantic validation errors in a more user-friendly way.
    """

    @staticmethod
    def format_error_path(error_loc: tuple) -> str:
        """Format the error location path in a readable format."""
        path_parts = []
        for part in error_loc:
            if isinstance(part, int):
                path_parts.append(f"[{part}]")
            elif path_parts:
                path_parts.append(f".{part}")
            else:
                path_parts.append(str(part))

        return "".join(path_parts)

    @staticmethod
    def format_validation_error(error: ValidationError) -> dict[str, Any]:
        """Format a Pydantic validation error into a user-friendly structure."""
        formatted_errors = []

        for error_dict in error.errors():
            loc = error_dict.get("loc", ())
            msg = error_dict.get("msg", "")
            error_type = error_dict.get("type", "")

            formatted_error = {
                "path": ValidationErrorFormatter.format_error_path(loc),
                "message": msg,
                "error_type": error_type,
            }

            # Add a more user-friendly message based on the error type
            if error_type == "missing":
                formatted_error["friendly_message"] = (
                    f"The field '{formatted_error['path']}' is required but was not provided."
                )
            elif error_type == "type_error":
                formatted_error["friendly_message"] = (
                    f"The field '{formatted_error['path']}' has an incorrect type."
                )
            elif error_type == "value_error":
                formatted_error["friendly_message"] = (
                    f"The field '{formatted_error['path']}' has an invalid value."
                )

            formatted_errors.append(formatted_error)

        return {
            "detail": "Validation error",
            "errors": formatted_errors,
        }


class ErrorMiddleware:
    """
    Middleware for handling exceptions in Django Matt.

    Catches exceptions and returns formatted error responses.
    Supports both WSGI (sync) and ASGI (async) request paths.

    API paths (/api/…) return JSON; non-API paths re-raise the exception.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_handler = ErrorHandler(
            debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
        )

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            if request.path.startswith("/api/"):
                return ErrorHandler.json_response(e)
            raise  # Re-raise for non-API requests

    async def __acall__(self, request):
        try:
            response = await self.get_response(request)
            return response
        except Exception as e:
            if request.path.startswith("/api/"):
                return ErrorHandler.json_response(e)
            raise

    def process_exception(self, request, exception):
        """Process an exception and return a formatted error response."""
        error_detail = self.error_handler.capture_exception(exception, request)

        include_traceback = self.error_handler.debug
        include_snippet = self.error_handler.debug

        return error_detail.to_response(
            include_traceback=include_traceback, include_snippet=include_snippet
        )


# ------------------------------------------------------------------
# Helper decorators
# ------------------------------------------------------------------


def handle_exceptions(func):
    """
    Decorator for handling exceptions in view functions.

    Catches exceptions and returns formatted error responses.
    """

    async def wrapper(request, *args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(request, *args, **kwargs)
            return func(request, *args, **kwargs)
        except Exception as exc:
            error_handler = ErrorHandler(
                debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
            )
            error_detail = error_handler.capture_exception(exc, request)

            include_traceback = error_handler.debug
            include_snippet = error_handler.debug

            return error_detail.to_response(
                include_traceback=include_traceback, include_snippet=include_snippet
            )

    return wrapper


def error_handler(view_func):
    """
    Decorator to add error handling to view functions (utils/errors style).

    Catches exceptions, formats them with detailed information,
    and returns a JSON response with the error details.
    """

    @wraps(view_func)
    async def wrapper(request: HttpRequest, *args, **kwargs):
        try:
            if inspect.iscoroutinefunction(view_func):
                result = await view_func(request, *args, **kwargs)
            else:
                result = view_func(request, *args, **kwargs)
            return result
        except Exception as e:
            return ErrorHandler.json_response(e)

    return wrapper
