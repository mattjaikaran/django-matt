"""
Error testing utilities for CLI.

Provides tools for testing CLI error handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type
from unittest.mock import patch

from django_matt.cli.errors.types import CLIError, CLIErrorCode


@dataclass
class ErrorCapture:
    """Captured error information."""

    error: Exception | None = None
    error_type: Type[Exception] | None = None
    error_code: CLIErrorCode | None = None
    message: str = ""
    context: dict[str, Any] | None = None
    suggestions: list[str] | None = None

    @property
    def has_error(self) -> bool:
        """Check if an error was captured."""
        return self.error is not None

    @property
    def is_cli_error(self) -> bool:
        """Check if error is a CLIError."""
        return isinstance(self.error, CLIError)

    def assert_error(self, error_type: Type[Exception] | None = None) -> ErrorCapture:
        """Assert an error was raised."""
        if not self.has_error:
            raise AssertionError("Expected an error but none was raised")
        if error_type and not isinstance(self.error, error_type):
            raise AssertionError(f"Expected {error_type.__name__}, got {type(self.error).__name__}")
        return self

    def assert_no_error(self) -> ErrorCapture:
        """Assert no error was raised."""
        if self.has_error:
            raise AssertionError(f"Expected no error but got: {self.error}")
        return self

    def assert_cli_error(self, code: CLIErrorCode | None = None) -> ErrorCapture:
        """Assert a CLIError with optional code check."""
        if not self.is_cli_error:
            raise AssertionError(
                f"Expected CLIError, got {type(self.error).__name__ if self.error else 'None'}"
            )
        if code and self.error_code != code:
            raise AssertionError(f"Expected error code {code}, got {self.error_code}")
        return self

    def assert_message_contains(self, text: str) -> ErrorCapture:
        """Assert error message contains text."""
        if text not in self.message:
            raise AssertionError(
                f"Expected error message to contain '{text}'\nActual message: {self.message}"
            )
        return self

    def assert_has_suggestion(self, text: str) -> ErrorCapture:
        """Assert error has a specific suggestion."""
        if not self.suggestions:
            raise AssertionError("Error has no suggestions")
        if not any(text in s for s in self.suggestions):
            raise AssertionError(
                f"Expected suggestion containing '{text}'\nActual suggestions: {self.suggestions}"
            )
        return self

    def assert_has_context(self, key: str, value: Any = None) -> ErrorCapture:
        """Assert error has context with key (and optionally value)."""
        if not self.context:
            raise AssertionError("Error has no context")
        if key not in self.context:
            raise AssertionError(f"Expected context key '{key}'\nActual context: {self.context}")
        if value is not None and self.context[key] != value:
            raise AssertionError(f"Expected context['{key}'] = {value}, got {self.context[key]}")
        return self


class ErrorCatcher:
    """
    Context manager to catch and inspect errors.

    Usage:
        with ErrorCatcher() as catcher:
            raise CLIError("Something went wrong", code=CLIErrorCode.VALIDATION_ERROR)

        catcher.captured.assert_cli_error(CLIErrorCode.VALIDATION_ERROR)
    """

    def __init__(self, reraise: bool = False):
        self.reraise = reraise
        self.captured = ErrorCapture()

    def __enter__(self) -> ErrorCatcher:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val:
            self.captured.error = exc_val
            self.captured.error_type = exc_type
            self.captured.message = str(exc_val)

            if isinstance(exc_val, CLIError):
                self.captured.error_code = exc_val.code
                self.captured.context = exc_val.context
                self.captured.suggestions = exc_val.suggestions

        # Return True to suppress exception (unless reraise is True)
        return not self.reraise and exc_val is not None


def assert_raises_cli_error(
    code: CLIErrorCode | None = None,
    message_contains: str | None = None,
):
    """
    Context manager that asserts a CLIError is raised.

    Usage:
        with assert_raises_cli_error(CLIErrorCode.FILE_NOT_FOUND):
            raise CLIError("File not found", code=CLIErrorCode.FILE_NOT_FOUND)
    """
    return _CLIErrorAssertion(code=code, message_contains=message_contains)


class _CLIErrorAssertion:
    """Context manager for asserting CLIError."""

    def __init__(
        self,
        code: CLIErrorCode | None = None,
        message_contains: str | None = None,
    ):
        self.code = code
        self.message_contains = message_contains
        self.error: CLIError | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val is None:
            raise AssertionError("Expected CLIError but no exception was raised")

        if not isinstance(exc_val, CLIError):
            raise AssertionError(f"Expected CLIError, got {type(exc_val).__name__}: {exc_val}")

        self.error = exc_val

        if self.code and exc_val.code != self.code:
            raise AssertionError(f"Expected error code {self.code}, got {exc_val.code}")

        if self.message_contains and self.message_contains not in str(exc_val):
            raise AssertionError(
                f"Expected message containing '{self.message_contains}'\nActual: {exc_val}"
            )

        return True  # Suppress the exception


def create_cli_error(
    message: str = "Test error",
    code: CLIErrorCode = CLIErrorCode.UNKNOWN_ERROR,
    context: dict[str, Any] | None = None,
    suggestions: list[str] | None = None,
) -> CLIError:
    """
    Create a CLIError for testing.

    Usage:
        error = create_cli_error(
            "File not found",
            code=CLIErrorCode.FILE_NOT_FOUND,
            context={"path": "/missing/file"},
            suggestions=["Check the file path"],
        )
    """
    error = CLIError(message, code=code)
    error.context = context or {}
    error.suggestions = suggestions or []
    return error


class MockErrorHandler:
    """
    Mock error handler for testing.

    Usage:
        handler = MockErrorHandler()

        with handler.patch():
            # Errors will be captured instead of displayed
            command.handle()

        assert handler.errors_captured == 1
        handler.assert_error_raised(CLIErrorCode.VALIDATION_ERROR)
    """

    def __init__(self):
        self.captured_errors: list[ErrorCapture] = []
        self._patches = []

    @property
    def errors_captured(self) -> int:
        """Number of errors captured."""
        return len(self.captured_errors)

    def patch(self):
        """Return context manager for patching error handler."""
        return _ErrorHandlerPatcher(self)

    def reset(self) -> None:
        """Reset captured errors."""
        self.captured_errors = []

    def assert_error_raised(
        self,
        code: CLIErrorCode | None = None,
        message_contains: str | None = None,
    ) -> MockErrorHandler:
        """Assert at least one error was raised."""
        if not self.captured_errors:
            raise AssertionError("Expected error but none was captured")

        if code:
            matching = [e for e in self.captured_errors if e.error_code == code]
            if not matching:
                raise AssertionError(
                    f"Expected error with code {code}\n"
                    f"Captured: {[e.error_code for e in self.captured_errors]}"
                )

        if message_contains:
            matching = [e for e in self.captured_errors if message_contains in e.message]
            if not matching:
                raise AssertionError(
                    f"Expected error containing '{message_contains}'\n"
                    f"Captured: {[e.message for e in self.captured_errors]}"
                )

        return self

    def assert_no_errors(self) -> MockErrorHandler:
        """Assert no errors were captured."""
        if self.captured_errors:
            raise AssertionError(
                f"Expected no errors but {len(self.captured_errors)} were captured"
            )
        return self


class _ErrorHandlerPatcher:
    """Context manager for patching error handler."""

    def __init__(self, mock_handler: MockErrorHandler):
        self.mock_handler = mock_handler
        self._patches = []

    def __enter__(self):
        def mock_handle(error):
            capture = ErrorCapture(
                error=error,
                error_type=type(error),
                message=str(error),
            )
            if isinstance(error, CLIError):
                capture.error_code = error.code
                capture.context = error.context
                capture.suggestions = error.suggestions
            self.mock_handler.captured_errors.append(capture)

        self._patches = [
            patch(
                "django_matt.cli.errors.handler.CLIErrorHandler.handle",
                mock_handle,
            ),
        ]
        for p in self._patches:
            p.start()
        return self.mock_handler

    def __exit__(self, *args):
        for p in self._patches:
            p.stop()
