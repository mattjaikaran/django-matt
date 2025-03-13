import inspect
import os
import sys
import traceback
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from pydantic import ValidationError


class ErrorDetail:
    """
    Class to store and format detailed error information.
    """

    def __init__(
        self,
        message: str,
        exception_type: str,
        traceback_str: str,
        file_path: str | None = None,
        line_number: int | None = None,
        code_snippet: dict[int, str] | None = None,
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ):
        self.message = message
        self.exception_type = exception_type
        self.traceback_str = traceback_str
        self.file_path = file_path
        self.line_number = line_number
        self.code_snippet = code_snippet or {}
        self.context = context or {}
        self.suggestion = suggestion

    def to_dict(self, include_traceback: bool = True) -> dict[str, Any]:
        """Convert error details to a dictionary."""
        result = {
            "message": self.message,
            "exception_type": self.exception_type,
            "location": {
                "file": self.file_path,
                "line": self.line_number,
            },
            "context": self.context,
        }

        if self.suggestion:
            result["suggestion"] = self.suggestion

        if self.code_snippet:
            result["code_snippet"] = self.code_snippet

        if include_traceback:
            result["traceback"] = self.traceback_str

        return result


class ErrorHandler:
    """
    Main error handler class for Django Matt framework.

    This class provides methods to capture, format, and respond to errors
    with detailed information to help developers quickly identify and fix issues.
    """

    @staticmethod
    def get_code_snippet(
        file_path: str, line_number: int, context_lines: int = 3
    ) -> dict[int, str]:
        """Get a code snippet around the error location."""
        if not os.path.exists(file_path):
            return {}

        try:
            with open(file_path) as file:
                lines = file.readlines()

            start_line = max(0, line_number - context_lines - 1)
            end_line = min(len(lines), line_number + context_lines)

            return {i + 1: lines[i].rstrip() for i in range(start_line, end_line)}
        except Exception:
            return {}

    @staticmethod
    def extract_error_location(tb_frame):
        """Extract file path and line number from a traceback frame."""
        file_path = tb_frame.tb_frame.f_code.co_filename
        line_number = tb_frame.tb_lineno
        return file_path, line_number

    @staticmethod
    def generate_suggestion(exception: Exception, error_type: str) -> str | None:
        """Generate a helpful suggestion based on the exception type."""
        if error_type == "ValidationError":
            return "Check the data structure against the schema requirements."
        elif error_type == "TypeError":
            return "Verify the types of all arguments being passed."
        elif error_type == "AttributeError":
            return "Ensure the object has the attribute you're trying to access."
        elif error_type == "ImportError":
            return "Check that the module exists and is installed."
        elif error_type == "KeyError":
            return "Verify the key exists in the dictionary before accessing it."
        elif error_type == "IndexError":
            return "Ensure the index is within the bounds of the list."
        elif error_type == "SyntaxError":
            return "Fix the syntax error in your code."
        elif error_type == "NameError":
            return "Make sure the variable is defined before using it."
        elif error_type == "FileNotFoundError":
            return "Verify the file path is correct and the file exists."
        elif error_type == "PermissionError":
            return "Check file permissions or if you have the necessary access rights."
        elif error_type == "ConnectionError":
            return "Verify network connectivity and that the service is running."
        elif error_type == "ValueError":
            return "Check that the value is appropriate for the operation."
        elif error_type == "ZeroDivisionError":
            return "Avoid dividing by zero; add a check before division."
        elif error_type == "AssertionError":
            return "The assertion condition failed; check your assumptions."
        elif error_type == "RuntimeError":
            return "A runtime error occurred; check the execution flow."
        elif error_type == "NotImplementedError":
            return "This feature is not implemented yet; implement it or use an alternative."
        elif error_type == "RecursionError":
            return "Your recursion is too deep; check for infinite recursion or use iteration."
        elif error_type == "MemoryError":
            return "The operation is using too much memory; optimize memory usage."
        elif error_type == "TimeoutError":
            return "The operation timed out; check for long-running operations or increase timeout."
        elif error_type == "StopIteration":
            return "The iterator has no more items; check your iteration logic."
        else:
            return None

    @classmethod
    def capture_error(cls, exception: Exception) -> ErrorDetail:
        """Capture and format error details from an exception."""
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # Get the traceback as a string
        traceback_str = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )

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
        code_snippet = {}

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

        # Create and return the error detail
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
        cls, exception: Exception, include_traceback: bool = None
    ) -> dict[str, Any]:
        """Format an exception into a detailed error response."""
        # Determine whether to include traceback based on settings
        if include_traceback is None:
            include_traceback = getattr(settings, "DEBUG", False)

        error_detail = cls.capture_error(exception)
        return {"error": error_detail.to_dict(include_traceback=include_traceback)}

    @classmethod
    def json_response(
        cls,
        exception: Exception,
        status_code: int = 500,
        include_traceback: bool = None,
    ) -> JsonResponse:
        """Create a JSON response with detailed error information."""
        response_data = cls.format_response(exception, include_traceback)
        return JsonResponse(response_data, status=status_code)


def error_handler(view_func):
    """
    Decorator to add error handling to view functions.

    This decorator catches exceptions, formats them with detailed information,
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
            else:
                if path_parts:
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
    Middleware to handle exceptions globally in the Django application.

    This middleware catches exceptions, formats them with detailed information,
    and returns a JSON response with the error details.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Only handle API requests (you can customize this logic)
            if request.path.startswith("/api/"):
                return ErrorHandler.json_response(e)
            raise  # Re-raise the exception for non-API requests
