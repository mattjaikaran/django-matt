"""
Django Matt CLI utilities.

Beautiful, interactive command-line interface tools.
"""

from django_matt.cli.base import GeneratorCommand, InteractiveCommand, MattCommand
from django_matt.cli.console import console
from django_matt.cli.errors import (
    CLIError,
    CLIErrorCode,
    CLIErrorFormatter,
    CLIErrorHandler,
    SuggestionEngine,
)
from django_matt.cli.help import show_help_for, show_main_help
from django_matt.cli.prompts import confirm, multiselect, path, select, text
from django_matt.cli.utils import (
    find_manage_py,
    find_project_root,
    run_manage_command,
    setup_django,
)

__all__ = [
    # Console
    "console",
    # Command base classes
    "MattCommand",
    "InteractiveCommand",
    "GeneratorCommand",
    # CLI utilities
    "find_manage_py",
    "find_project_root",
    "run_manage_command",
    "setup_django",
    # Prompts
    "text",
    "select",
    "multiselect",
    "confirm",
    "path",
    # Help
    "show_main_help",
    "show_help_for",
    # Error handling
    "CLIError",
    "CLIErrorCode",
    "CLIErrorHandler",
    "CLIErrorFormatter",
    "SuggestionEngine",
]
