import datetime
import inspect
import json
import logging
import os
import sys
import traceback
from typing import Any

from django.http import HttpRequest, JsonResponse
from pydantic import ValidationError

logger = logging.getLogger("django_matt.errors")


class ErrorDetail:
    """
    Detailed error information with context.

    This class provides rich error information including file location,
    code snippets, and suggestions for fixing the error.
    """

    def __init__(
        self,
        message: str,
        error_type: str,
        code: str = "error",
        status_code: int = 500,
        path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
        traceback_str: str | None = None,
        code_snippet: list[str] | None = None,
    ):
        self.message = message
        self.error_type = error_type
        self.code = code
        self.status_code = status_code
        self.path = path
        self.line_number = line_number
        self.context = context or {}
        self.suggestion = suggestion
        self.traceback_str = traceback_str
        self.code_snippet = code_snippet
        self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(
        self, include_traceback: bool = False, include_snippet: bool = False
    ) -> dict[str, Any]:
        """Convert error details to a dictionary."""
        result = {
            "message": self.message,
            "error_type": self.error_type,
            "code": self.code,
            "status_code": self.status_code,
            "timestamp": self.timestamp,
        }

        if self.path:
            result["location"] = {"path": self.path, "line": self.line_number}

        if self.context:
            result["context"] = self.context

        if self.suggestion:
            result["suggestion"] = self.suggestion

        if include_traceback and self.traceback_str:
            result["traceback"] = self.traceback_str

        if include_snippet and self.code_snippet:
            result["code_snippet"] = self.code_snippet

        return result

    def to_json(
        self, include_traceback: bool = False, include_snippet: bool = False
    ) -> str:
        """Convert error details to JSON."""
        return json.dumps(
            self.to_dict(
                include_traceback=include_traceback, include_snippet=include_snippet
            ),
            indent=2,
        )

    def to_response(
        self, include_traceback: bool = False, include_snippet: bool = False
    ) -> JsonResponse:
        """Convert error details to a JsonResponse."""
        return JsonResponse(
            self.to_dict(
                include_traceback=include_traceback, include_snippet=include_snippet
            ),
            status=self.status_code,
        )


class ErrorHandler:
    """
    Error handler for Django Matt framework.

    This class provides methods for capturing, formatting, and responding to errors
    with rich context and suggestions.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

    def capture_exception(
        self, exc: Exception, request: HttpRequest | None = None
    ) -> ErrorDetail:
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
            traceback_str = "".join(
                traceback.format_exception(type(exc), exc, sys.exc_info()[2])
            )

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
                    context["request"]["body"] = json.loads(request.body)
                except json.JSONDecodeError:
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
        elif isinstance(exc, PermissionError):
            return 403  # Forbidden
        elif isinstance(exc, FileNotFoundError):
            return 404  # Not Found
        elif (
            isinstance(exc, json.JSONDecodeError)
            or isinstance(exc, KeyError)
            or isinstance(exc, AttributeError)
        ):
            return 400  # Bad Request
        elif isinstance(exc, NotImplementedError):
            return 501  # Not Implemented

        # Default to 500 Internal Server Error
        return 500

    def _get_error_code(self, exc: Exception) -> str:
        """Get a machine-readable error code for an exception."""
        if hasattr(exc, "code"):
            return exc.code

        # Generate a code based on the exception type
        return exc.__class__.__name__.lower()

    def _get_code_snippet(
        self, path: str, line_number: int, context_lines: int = 5
    ) -> list[str]:
        """Get a code snippet around the error location."""
        try:
            if not os.path.exists(path):
                return None

            with open(path) as f:
                lines = f.readlines()

            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)

            return [
                f"{i + 1}: {lines[i].rstrip()}" for i in range(start_line, end_line)
            ]
        except Exception:
            return None

    def _generate_suggestion(self, exc: Exception, error_type: str) -> str:
        """Generate a helpful suggestion for fixing the error."""
        if isinstance(exc, ValidationError):
            return "Check the request data against the schema requirements."
        elif isinstance(exc, PermissionError):
            return "Ensure the user has the necessary permissions for this action."
        elif isinstance(exc, FileNotFoundError):
            return f"The file '{exc.filename}' could not be found. Check the path and file existence."
        elif isinstance(exc, json.JSONDecodeError):
            return "The JSON data is invalid. Check the syntax and structure."
        elif isinstance(exc, KeyError):
            return f"The key '{exc.args[0]}' was not found in the dictionary."
        elif isinstance(exc, AttributeError):
            return "Check that you're accessing a valid attribute on the object."
        elif isinstance(exc, NotImplementedError):
            return "This feature is not yet implemented."

        # Default suggestion
        return "Review the error message and traceback for more information."


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
            suggestion=suggestion
            or "Check the request data against the schema requirements.",
        )


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


class ErrorMiddleware:
    """
    Middleware for handling exceptions in Django Matt.

    This middleware catches exceptions and returns formatted error responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_handler = ErrorHandler(
            debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
        )

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Process an exception and return a formatted error response."""
        error_detail = self.error_handler.capture_exception(exception, request)

        # Determine if we should include debug information
        include_traceback = self.error_handler.debug
        include_snippet = self.error_handler.debug

        # Return a JSON response with error details
        return error_detail.to_response(
            include_traceback=include_traceback, include_snippet=include_snippet
        )


# Helper functions for error handling
def handle_exceptions(func):
    """
    Decorator for handling exceptions in view functions.

    This decorator catches exceptions and returns formatted error responses.
    """

    async def wrapper(request, *args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(request, *args, **kwargs)
            else:
                return func(request, *args, **kwargs)
        except Exception as exc:
            error_handler = ErrorHandler(
                debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
            )
            error_detail = error_handler.capture_exception(exc, request)

            # Determine if we should include debug information
            include_traceback = error_handler.debug
            include_snippet = error_handler.debug

            # Return a JSON response with error details
            return error_detail.to_response(
                include_traceback=include_traceback, include_snippet=include_snippet
            )

    return wrapper
