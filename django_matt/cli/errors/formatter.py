"""
CLI error formatter.

Formats errors for beautiful terminal output with Rich.
"""

import traceback
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from django_matt.cli.errors.types import CLIError, CLIErrorCode


class CLIErrorFormatter:
    """Formats CLI errors for rich terminal output."""

    def __init__(self, console: Console | None = None, debug: bool = False):
        self._console = console or Console()
        self.debug = debug

    def format_error(
        self,
        error: CLIError | Exception,
        suggestion: str | None = None,
        doc_url: str | None = None,
    ) -> None:
        """
        Format and print an error to the console.

        Args:
            error: The error to format
            suggestion: Optional suggestion override
            doc_url: Optional documentation URL
        """
        if isinstance(error, CLIError):
            self._format_cli_error(error, suggestion, doc_url)
        else:
            self._format_generic_error(error, suggestion, doc_url)

    def _format_cli_error(
        self,
        error: CLIError,
        suggestion: str | None = None,
        doc_url: str | None = None,
    ) -> None:
        """Format a CLIError with full context."""
        self._console.print()

        # Error header
        self._console.print(
            Panel(
                f"[bold red]{error.message}[/]",
                title="[bold red]Error[/]",
                border_style="red",
                expand=False,
            )
        )

        # Error code
        self._console.print(f"\n[dim]Error code:[/] [yellow]{error.code.value}[/]")

        # Context information
        if error.context:
            self._print_context(error.context)

        # Suggestion
        effective_suggestion = suggestion or error.suggestion
        if effective_suggestion:
            self._print_suggestion(effective_suggestion)

        # Documentation link
        effective_doc_url = doc_url or error.doc_url
        if effective_doc_url:
            self._print_doc_link(effective_doc_url)

        # Debug information
        if self.debug:
            self._print_debug_info(error)

        self._console.print()

    def _format_generic_error(
        self,
        error: Exception,
        suggestion: str | None = None,
        doc_url: str | None = None,
    ) -> None:
        """Format a generic Python exception."""
        self._console.print()

        # Error header
        error_type = type(error).__name__
        self._console.print(
            Panel(
                f"[bold red]{error_type}:[/] {error!s}",
                title="[bold red]Error[/]",
                border_style="red",
                expand=False,
            )
        )

        # Suggestion
        if suggestion:
            self._print_suggestion(suggestion)

        # Documentation link
        if doc_url:
            self._print_doc_link(doc_url)

        # Debug information
        if self.debug:
            self._print_traceback(error)

        self._console.print()

    def _print_context(self, context: dict[str, Any]) -> None:
        """Print context information."""
        if not context:
            return

        self._console.print("\n[bold]Context:[/]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for key, value in context.items():
            # Skip internal keys
            if key.startswith("_"):
                continue
            table.add_row(key, str(value))

        self._console.print(table)

    def _print_suggestion(self, suggestion: str) -> None:
        """Print a suggestion panel."""
        self._console.print()
        self._console.print(
            Panel(
                f"[green]{suggestion}[/]",
                title="[bold green]Suggestion[/]",
                border_style="green",
                expand=False,
            )
        )

    def _print_doc_link(self, url: str) -> None:
        """Print a documentation link."""
        self._console.print(f"\n[dim]Documentation:[/] [blue underline]{url}[/]")

    def _print_debug_info(self, error: CLIError | Exception) -> None:
        """Print debug information including stack trace."""
        self._console.print()
        self._console.print("[bold yellow]Debug Information[/]")
        self._console.print("[dim]" + "-" * 40 + "[/]")

        # Print traceback
        self._print_traceback(error)

    def _print_traceback(self, error: Exception) -> None:
        """Print formatted traceback."""
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_lines)

        self._console.print(Syntax(tb_text, "python", theme="monokai", line_numbers=False))

    def format_validation_errors(
        self,
        errors: list[dict[str, Any]],
        title: str = "Validation Errors",
    ) -> None:
        """
        Format validation errors as a table.

        Args:
            errors: List of validation error dicts
            title: Title for the error panel
        """
        self._console.print()

        table = Table(title=title, border_style="red")
        table.add_column("Field", style="cyan")
        table.add_column("Error", style="red")
        table.add_column("Value", style="dim")

        for error in errors:
            field = error.get("field", error.get("loc", ["unknown"])[-1])
            message = error.get("message", error.get("msg", "Invalid"))
            value = str(error.get("value", error.get("input", "")))[:50]
            table.add_row(str(field), message, value)

        self._console.print(table)

    def format_file_error(
        self,
        path: str | Path,
        error_code: CLIErrorCode,
        details: str = "",
    ) -> None:
        """
        Format a file-related error.

        Args:
            path: The file path that caused the error
            error_code: The error code
            details: Additional details
        """
        path = Path(path)

        error_messages = {
            CLIErrorCode.FILE_NOT_FOUND: f"File not found: {path}",
            CLIErrorCode.FILE_EXISTS: f"File already exists: {path}",
            CLIErrorCode.FILE_PERMISSION: f"Permission denied: {path}",
            CLIErrorCode.FILE_READ_ERROR: f"Cannot read file: {path}",
            CLIErrorCode.FILE_WRITE_ERROR: f"Cannot write file: {path}",
        }

        message = error_messages.get(error_code, f"File error: {path}")
        if details:
            message += f"\n{details}"

        cli_error = CLIError(
            message=message,
            code=error_code,
            context={"path": str(path), "exists": path.exists()},
        )

        self.format_error(cli_error)

    def format_model_error(
        self,
        model_path: str,
        available_models: list[str] | None = None,
    ) -> None:
        """
        Format a model-not-found error with suggestions.

        Args:
            model_path: The attempted model path
            available_models: List of available models for suggestions
        """
        cli_error = CLIError(
            message=f"Model '{model_path}' not found",
            code=CLIErrorCode.MODEL_NOT_FOUND,
            context={
                "attempted_model": model_path,
                "available_models": available_models or [],
            },
        )

        self.format_error(cli_error)

    def print_quick_error(self, message: str, suggestion: str | None = None) -> None:
        """
        Print a quick, simple error message.

        Args:
            message: Error message
            suggestion: Optional suggestion
        """
        self._console.print(f"\n[red]Error:[/] {message}")
        if suggestion:
            self._console.print(f"[dim]Hint:[/] {suggestion}")
        self._console.print()
