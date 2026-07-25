"""
Suggestion engine for CLI errors.

Generates contextual suggestions based on error types and context.
"""

from typing import Any

from django_matt.cli.errors.types import CLIErrorCode

# Documentation URLs
DOCS_BASE = "https://django-matt.dev/docs"
DOCS_URLS = {
    CLIErrorCode.MODEL_NOT_FOUND: f"{DOCS_BASE}/models",
    CLIErrorCode.APP_NOT_FOUND: f"{DOCS_BASE}/apps",
    CLIErrorCode.CONFIG_NOT_FOUND: f"{DOCS_BASE}/configuration",
    CLIErrorCode.CONFIG_INVALID: f"{DOCS_BASE}/configuration",
    CLIErrorCode.MISSING_DEPENDENCY: f"{DOCS_BASE}/installation",
    CLIErrorCode.DJANGO_NOT_CONFIGURED: f"{DOCS_BASE}/getting-started",
    CLIErrorCode.TEMPLATE_ERROR: f"{DOCS_BASE}/code-generation",
    CLIErrorCode.GENERATION_ERROR: f"{DOCS_BASE}/code-generation",
}


class SuggestionEngine:
    """Generates helpful suggestions for CLI errors."""

    def __init__(self):
        self._suggestions = self._build_suggestion_map()

    def _build_suggestion_map(self) -> dict[CLIErrorCode, str]:
        """Build the default suggestion map."""
        return {
            # File operations
            CLIErrorCode.FILE_NOT_FOUND: (
                "Check that the file path is correct and the file exists."
            ),
            CLIErrorCode.FILE_EXISTS: (
                "Use --force to overwrite existing files, or choose a different name."
            ),
            CLIErrorCode.FILE_PERMISSION: (
                "Check file permissions. You may need to run with elevated privileges."
            ),
            CLIErrorCode.FILE_READ_ERROR: ("Ensure the file is readable and not corrupted."),
            CLIErrorCode.FILE_WRITE_ERROR: (
                "Ensure the directory exists and you have write permissions."
            ),
            # Model/App operations
            CLIErrorCode.MODEL_NOT_FOUND: (
                "Use format 'app_label.ModelName' (e.g., 'auth.User').\n"
                "Run 'python manage.py matt models' to see available models."
            ),
            CLIErrorCode.APP_NOT_FOUND: (
                "Check that the app is in INSTALLED_APPS in your settings.\n"
                "Available apps can be listed with 'python manage.py matt info'."
            ),
            CLIErrorCode.INVALID_MODEL_PATH: (
                "Model path should be 'app_label.ModelName' format.\n"
                "Example: 'myapp.Product' or 'auth.User'"
            ),
            # Configuration
            CLIErrorCode.CONFIG_NOT_FOUND: (
                "Run 'python manage.py config init' to create a configuration file."
            ),
            CLIErrorCode.CONFIG_INVALID: (
                "Check your matt.toml or pyproject.toml for syntax errors.\n"
                "Run 'python manage.py config validate' to check configuration."
            ),
            CLIErrorCode.CONFIG_PARSE_ERROR: (
                "The configuration file has invalid syntax.\n"
                "Check for missing quotes, brackets, or invalid TOML."
            ),
            # Command execution
            CLIErrorCode.COMMAND_NOT_FOUND: (
                "Run 'python manage.py matt --help' to see available commands."
            ),
            CLIErrorCode.INVALID_ARGUMENT: (
                "Check the command help with --help for valid arguments."
            ),
            CLIErrorCode.MISSING_ARGUMENT: (
                "Required arguments are missing. Use --help to see required options."
            ),
            # Dependencies
            CLIErrorCode.MISSING_DEPENDENCY: (
                "Install the missing package:\n  uv add <package-name>"
            ),
            CLIErrorCode.IMPORT_ERROR: (
                "Check that all required packages are installed.\n"
                "Run 'python manage.py matt doctor' to check dependencies."
            ),
            # Django-specific
            CLIErrorCode.DJANGO_NOT_CONFIGURED: (
                "Ensure DJANGO_SETTINGS_MODULE is set or run from project root.\n"
                "Example: export DJANGO_SETTINGS_MODULE=myproject.settings"
            ),
            CLIErrorCode.MIGRATION_ERROR: (
                "Run 'python manage.py makemigrations' and 'python manage.py migrate'."
            ),
            CLIErrorCode.DATABASE_ERROR: (
                "Check your database connection settings in settings.py.\n"
                "Ensure the database server is running."
            ),
            # Template/Generation
            CLIErrorCode.TEMPLATE_ERROR: ("The template contains errors. Check template syntax."),
            CLIErrorCode.GENERATION_ERROR: (
                "Code generation failed. Use --dry-run to preview output."
            ),
            # General
            CLIErrorCode.VALIDATION_ERROR: ("Check the input data format and requirements."),
            CLIErrorCode.PERMISSION_DENIED: ("You don't have permission for this operation."),
            CLIErrorCode.UNKNOWN_ERROR: (
                "An unexpected error occurred. Use --debug for more details."
            ),
        }

    def get_suggestion(
        self,
        code: CLIErrorCode,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Get a suggestion for an error code.

        Args:
            code: The error code
            context: Optional context for dynamic suggestions

        Returns:
            A helpful suggestion string
        """
        context = context or {}

        # Check for dynamic suggestions first
        dynamic = self._get_dynamic_suggestion(code, context)
        if dynamic:
            return dynamic

        # Fall back to static suggestions
        return self._suggestions.get(code, self._suggestions[CLIErrorCode.UNKNOWN_ERROR])

    def _get_dynamic_suggestion(
        self,
        code: CLIErrorCode,
        context: dict[str, Any],
    ) -> str | None:
        """Generate dynamic suggestions based on context."""
        if code == CLIErrorCode.MODEL_NOT_FOUND:
            return self._suggest_model(context)
        if code == CLIErrorCode.APP_NOT_FOUND:
            return self._suggest_app(context)
        if code == CLIErrorCode.MISSING_DEPENDENCY:
            return self._suggest_dependency(context)
        if code == CLIErrorCode.COMMAND_NOT_FOUND:
            return self._suggest_command(context)
        return None

    def _suggest_model(self, context: dict[str, Any]) -> str | None:
        """Suggest similar models."""
        attempted = context.get("attempted_model")
        available = context.get("available_models", [])

        if not attempted or not available:
            return None

        similar = self._find_similar(attempted, available)
        if similar:
            return (
                f"Model '{attempted}' not found.\n"
                f"Did you mean: {similar}?\n\n"
                f"Run 'python manage.py matt models' to see all available models."
            )
        return None

    def _suggest_app(self, context: dict[str, Any]) -> str | None:
        """Suggest similar apps."""
        attempted = context.get("attempted_app")
        available = context.get("available_apps", [])

        if not attempted or not available:
            return None

        similar = self._find_similar(attempted, available)
        if similar:
            return (
                f"App '{attempted}' not found.\n"
                f"Did you mean: {similar}?\n\n"
                f"Make sure the app is in INSTALLED_APPS."
            )
        return None

    def _suggest_dependency(self, context: dict[str, Any]) -> str | None:
        """Suggest how to install missing dependency."""
        package = context.get("package")
        if not package:
            return None

        return f"Package '{package}' is not installed.\n\nInstall with:\n  uv add {package}"

    def _suggest_command(self, context: dict[str, Any]) -> str | None:
        """Suggest similar commands."""
        attempted = context.get("attempted_command")
        available = context.get("available_commands", [])

        if not attempted or not available:
            return None

        similar = self._find_similar(attempted, available)
        if similar:
            return (
                f"Command '{attempted}' not found.\n"
                f"Did you mean: {similar}?\n\n"
                f"Run 'python manage.py matt --help' for available commands."
            )
        return None

    def _find_similar(self, target: str, candidates: list[str]) -> str | None:
        """Find the most similar string from candidates."""
        if not candidates:
            return None

        best_match = None
        best_score = 0.0

        target_lower = target.lower()
        for candidate in candidates:
            score = self._similarity(target_lower, candidate.lower())
            if score > best_score and score > 0.5:
                best_score = score
                best_match = candidate

        return best_match

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0

        # Simple character-based similarity
        matches = sum(1 for a, b in zip(s1, s2, strict=False) if a == b)
        max_len = max(len(s1), len(s2))
        return matches / max_len if max_len > 0 else 0.0

    def get_doc_url(self, code: CLIErrorCode) -> str | None:
        """Get documentation URL for an error code."""
        return DOCS_URLS.get(code)
