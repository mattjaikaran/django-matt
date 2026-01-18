"""
CLI error types and codes.

Defines error classifications for consistent handling and messaging.
"""

from enum import Enum
from typing import Any


class CLIErrorCode(Enum):
    """Error codes for CLI operations."""

    # File operations
    FILE_NOT_FOUND = "file_not_found"
    FILE_EXISTS = "file_exists"
    FILE_PERMISSION = "file_permission"
    FILE_READ_ERROR = "file_read_error"
    FILE_WRITE_ERROR = "file_write_error"

    # Model/App operations
    MODEL_NOT_FOUND = "model_not_found"
    APP_NOT_FOUND = "app_not_found"
    INVALID_MODEL_PATH = "invalid_model_path"

    # Configuration
    CONFIG_NOT_FOUND = "config_not_found"
    CONFIG_INVALID = "config_invalid"
    CONFIG_PARSE_ERROR = "config_parse_error"

    # Command execution
    COMMAND_NOT_FOUND = "command_not_found"
    INVALID_ARGUMENT = "invalid_argument"
    MISSING_ARGUMENT = "missing_argument"

    # Dependencies
    MISSING_DEPENDENCY = "missing_dependency"
    IMPORT_ERROR = "import_error"

    # Django-specific
    DJANGO_NOT_CONFIGURED = "django_not_configured"
    MIGRATION_ERROR = "migration_error"
    DATABASE_ERROR = "database_error"

    # Template/Generation
    TEMPLATE_ERROR = "template_error"
    GENERATION_ERROR = "generation_error"

    # General
    UNKNOWN_ERROR = "unknown_error"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_DENIED = "permission_denied"


class CLIError(Exception):
    """
    CLI-specific error with rich context.

    Attributes:
        message: Human-readable error message
        code: Error code for categorization
        context: Additional context data
        suggestion: Auto-generated or custom suggestion
        doc_url: Link to relevant documentation
    """

    def __init__(
        self,
        message: str,
        code: CLIErrorCode = CLIErrorCode.UNKNOWN_ERROR,
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
        doc_url: str | None = None,
    ):
        self.message = message
        self.code = code
        self.context = context or {}
        self.suggestion = suggestion
        self.doc_url = doc_url
        super().__init__(message)

    def with_suggestion(self, suggestion: str) -> "CLIError":
        """Add a suggestion to the error."""
        self.suggestion = suggestion
        return self

    def with_context(self, **kwargs) -> "CLIError":
        """Add context data to the error."""
        self.context.update(kwargs)
        return self

    def with_doc_url(self, url: str) -> "CLIError":
        """Add documentation URL to the error."""
        self.doc_url = url
        return self
