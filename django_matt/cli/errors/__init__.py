"""
CLI error handling with friendly messages and suggestions.

Provides beautiful error output with contextual help and documentation links.
"""

from django_matt.cli.errors.formatter import CLIErrorFormatter
from django_matt.cli.errors.handler import CLIErrorHandler
from django_matt.cli.errors.suggestions import SuggestionEngine
from django_matt.cli.errors.types import CLIError, CLIErrorCode

__all__ = [
    "CLIError",
    "CLIErrorCode",
    "CLIErrorHandler",
    "CLIErrorFormatter",
    "SuggestionEngine",
]
