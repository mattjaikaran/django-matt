"""
CLI error handler.

Main handler that orchestrates error processing, suggestions, and formatting.
"""

import os
import sys
from typing import Any, Callable

from rich.console import Console

from django_matt.cli.errors.formatter import CLIErrorFormatter
from django_matt.cli.errors.suggestions import SuggestionEngine
from django_matt.cli.errors.types import CLIError, CLIErrorCode


class CLIErrorHandler:
    """
    Central error handler for CLI operations.

    Provides error capturing, suggestion generation, and formatted output.
    """

    def __init__(
        self,
        console: Console | None = None,
        debug: bool | None = None,
    ):
        # Auto-detect debug mode from environment
        if debug is None:
            debug = os.environ.get("DJANGO_MATT_DEBUG", "").lower() in ("1", "true")

        self._console = console or Console()
        self.debug = debug
        self.suggestion_engine = SuggestionEngine()
        self.formatter = CLIErrorFormatter(console=self._console, debug=debug)

    def handle(
        self,
        error: CLIError | Exception,
        exit_code: int | None = 1,
    ) -> None:
        """
        Handle an error with full formatting and optional exit.

        Args:
            error: The error to handle
            exit_code: Exit code (None to not exit)
        """
        # Get suggestion and doc URL
        suggestion = None
        doc_url = None

        if isinstance(error, CLIError):
            # Use error's suggestion or generate one
            suggestion = error.suggestion or self.suggestion_engine.get_suggestion(
                error.code, error.context
            )
            doc_url = error.doc_url or self.suggestion_engine.get_doc_url(error.code)
        else:
            # Map common exceptions to CLI errors
            cli_error = self._map_exception(error)
            suggestion = self.suggestion_engine.get_suggestion(cli_error.code, cli_error.context)
            doc_url = self.suggestion_engine.get_doc_url(cli_error.code)
            error = cli_error

        # Format and display
        self.formatter.format_error(error, suggestion, doc_url)

        # Exit if requested
        if exit_code is not None:
            sys.exit(exit_code)

    def _map_exception(self, exc: Exception) -> CLIError:
        """Map a standard exception to a CLIError."""
        if isinstance(exc, FileNotFoundError):
            return CLIError(
                message=str(exc),
                code=CLIErrorCode.FILE_NOT_FOUND,
                context={"filename": getattr(exc, "filename", None)},
            )

        if isinstance(exc, PermissionError):
            return CLIError(
                message=str(exc),
                code=CLIErrorCode.FILE_PERMISSION,
                context={"filename": getattr(exc, "filename", None)},
            )

        if isinstance(exc, ImportError):
            return CLIError(
                message=str(exc),
                code=CLIErrorCode.IMPORT_ERROR,
                context={"module": getattr(exc, "name", None)},
            )

        if isinstance(exc, ModuleNotFoundError):
            module_name = getattr(exc, "name", None)
            return CLIError(
                message=f"Required module not found: {module_name}",
                code=CLIErrorCode.MISSING_DEPENDENCY,
                context={"package": module_name},
            )

        if isinstance(exc, ValueError):
            return CLIError(
                message=str(exc),
                code=CLIErrorCode.VALIDATION_ERROR,
            )

        if isinstance(exc, KeyError):
            return CLIError(
                message=f"Missing key: {exc.args[0]}",
                code=CLIErrorCode.CONFIG_INVALID,
            )

        # Default to unknown error
        return CLIError(
            message=str(exc),
            code=CLIErrorCode.UNKNOWN_ERROR,
        )

    def wrap(
        self,
        func: Callable,
        exit_on_error: bool = True,
    ) -> Callable:
        """
        Decorator to wrap a function with error handling.

        Args:
            func: Function to wrap
            exit_on_error: Whether to exit on error

        Returns:
            Wrapped function
        """

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CLIError as e:
                self.handle(e, exit_code=1 if exit_on_error else None)
            except Exception as e:
                self.handle(e, exit_code=1 if exit_on_error else None)

        return wrapper

    def catch(self, exit_on_error: bool = True):
        """
        Context manager for catching and handling errors.

        Usage:
            with error_handler.catch():
                risky_operation()
        """
        return _ErrorCatcher(self, exit_on_error)

    # =========================================================================
    # Error Creation Helpers
    # =========================================================================

    def file_not_found(
        self,
        path: str,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle a file not found error."""
        error = CLIError(
            message=f"File not found: {path}",
            code=CLIErrorCode.FILE_NOT_FOUND,
            context={"path": path},
        )
        self.handle(error, exit_code)

    def file_exists(
        self,
        path: str,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle a file exists error."""
        error = CLIError(
            message=f"File already exists: {path}",
            code=CLIErrorCode.FILE_EXISTS,
            context={"path": path},
        )
        self.handle(error, exit_code)

    def model_not_found(
        self,
        model_path: str,
        available_models: list[str] | None = None,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle a model not found error."""
        error = CLIError(
            message=f"Model '{model_path}' not found",
            code=CLIErrorCode.MODEL_NOT_FOUND,
            context={
                "attempted_model": model_path,
                "available_models": available_models or [],
            },
        )
        self.handle(error, exit_code)

    def app_not_found(
        self,
        app_name: str,
        available_apps: list[str] | None = None,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle an app not found error."""
        error = CLIError(
            message=f"App '{app_name}' not found in INSTALLED_APPS",
            code=CLIErrorCode.APP_NOT_FOUND,
            context={
                "attempted_app": app_name,
                "available_apps": available_apps or [],
            },
        )
        self.handle(error, exit_code)

    def invalid_argument(
        self,
        argument: str,
        reason: str,
        valid_values: list[str] | None = None,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle an invalid argument error."""
        message = f"Invalid argument '{argument}': {reason}"
        context: dict[str, Any] = {"argument": argument}
        if valid_values:
            context["valid_values"] = valid_values
            message += f"\nValid values: {', '.join(valid_values)}"

        error = CLIError(
            message=message,
            code=CLIErrorCode.INVALID_ARGUMENT,
            context=context,
        )
        self.handle(error, exit_code)

    def missing_argument(
        self,
        argument: str,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle a missing argument error."""
        error = CLIError(
            message=f"Missing required argument: {argument}",
            code=CLIErrorCode.MISSING_ARGUMENT,
            context={"argument": argument},
        )
        self.handle(error, exit_code)

    def config_error(
        self,
        message: str,
        config_file: str | None = None,
        exit_code: int | None = 1,
    ) -> None:
        """Raise and handle a configuration error."""
        error = CLIError(
            message=message,
            code=CLIErrorCode.CONFIG_INVALID,
            context={"config_file": config_file} if config_file else {},
        )
        self.handle(error, exit_code)

    def quick_error(
        self,
        message: str,
        suggestion: str | None = None,
    ) -> None:
        """Print a quick error message without exiting."""
        self.formatter.print_quick_error(message, suggestion)


class _ErrorCatcher:
    """Context manager for catching errors."""

    def __init__(self, handler: CLIErrorHandler, exit_on_error: bool):
        self.handler = handler
        self.exit_on_error = exit_on_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.handler.handle(
                exc_val,
                exit_code=1 if self.exit_on_error else None,
            )
            return True  # Suppress the exception
        return False
