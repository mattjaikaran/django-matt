"""
Base command classes for Django Matt CLI.

Provides consistent output, progress indicators, and file generation utilities.

Usage:
    from django_matt.cli import MattCommand, InteractiveCommand, GeneratorCommand

    class MyCommand(MattCommand):
        help = "My command description"

        def handle(self, *args, **options):
            self.console.header("My Command")
            self.console.success("Done!")

    class MyWizard(InteractiveCommand):
        help = "Interactive setup wizard"

        def handle(self, *args, **options):
            name = self.prompt_text("What is your name?")
            self.console.success(f"Hello, {name}!")

    class MyGenerator(GeneratorCommand):
        help = "Generate files"

        def handle(self, *args, **options):
            self.write_file("output.py", "# Generated file")
            self.show_summary()
"""

from collections.abc import Callable
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from django_matt.cli.console import console
from django_matt.cli.prompts import (
    autocomplete,
    confirm,
    multiselect,
    path,
    select,
    text,
    validate_model_path,
    validate_not_empty,
    validate_python_identifier,
)


class MattCommand(BaseCommand):
    """
    Base command with rich console output.

    Features:
    - Beautiful colored output
    - Progress indicators
    - Tables and trees
    - Consistent styling

    Attributes:
        console: Rich console instance for output
    """

    # Suppress Django's default output handling
    requires_system_checks = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = console

    def add_arguments(self, parser):
        """Add common arguments."""
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Suppress non-essential output",
        )
        # Note: --no-color is already provided by Django's BaseCommand

    def execute(self, *args, **options):
        """Execute with console configuration."""
        if options.get("quiet"):
            self.console.quiet = True

        return super().execute(*args, **options)

    # =========================================================================
    # Output Shortcuts
    # =========================================================================

    def success(self, message: str):
        """Print success message."""
        self.console.success(message)

    def error(self, message: str, raise_error: bool = False):
        """Print error message, optionally raising CommandError."""
        self.console.error(message)
        if raise_error:
            raise CommandError(message)

    def warning(self, message: str):
        """Print warning message."""
        self.console.warning(message)

    def info(self, message: str):
        """Print info message."""
        self.console.info(message)

    def debug(self, message: str):
        """Print debug message (muted)."""
        self.console.debug(message)

    def header(self, title: str, subtitle: str = ""):
        """Print header."""
        self.console.header(title, subtitle)

    def section(self, title: str):
        """Print section header."""
        self.console.section(title)

    def table(self, data: list, columns: list[str] | None = None, **kwargs):
        """Print table."""
        self.console.table(data, columns, **kwargs)

    def tree(self, data: dict, title: str = "", **kwargs):
        """Print tree."""
        self.console.tree(data, title, **kwargs)

    def code(self, content: str, language: str = "python", **kwargs):
        """Print syntax-highlighted code."""
        self.console.code(content, language, **kwargs)

    def panel(self, content: str, **kwargs):
        """Print panel."""
        self.console.panel(content, **kwargs)

    def next_steps(self, steps: list[str], **kwargs):
        """Print next steps."""
        self.console.next_steps(steps, **kwargs)


class InteractiveCommand(MattCommand):
    """
    Command with interactive prompts.

    Features:
    - Text input with validation
    - Single/multi select
    - Confirmations
    - Path autocomplete

    Use for wizards and guided setup flows.
    """

    def add_arguments(self, parser):
        """Add interactive-specific arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Accept all defaults without prompting",
        )
        parser.add_argument(
            "--wizard",
            "-w",
            action="store_true",
            help="Run in interactive wizard mode",
        )

    # =========================================================================
    # Prompt Shortcuts
    # =========================================================================

    def prompt_text(
        self,
        message: str,
        default: str = "",
        required: bool = False,
        validate: Callable | None = None,
    ) -> str:
        """Prompt for text input."""
        if required and not validate:
            validate = validate_not_empty
        return text(message, default=default, validate=validate)

    def prompt_password(self, message: str) -> str:
        """Prompt for password (hidden input)."""
        from django_matt.cli.prompts import password

        return password(message)

    def prompt_select(
        self,
        message: str,
        choices: list[str] | list[dict],
        default: str | None = None,
    ) -> str:
        """Prompt to select one option."""
        return select(message, choices=choices, default=default)

    def prompt_multiselect(
        self,
        message: str,
        choices: list[str] | list[dict],
        default: list[str] | None = None,
    ) -> list[str]:
        """Prompt to select multiple options."""
        return multiselect(message, choices=choices, default=default)

    def prompt_confirm(
        self,
        message: str,
        default: bool = True,
    ) -> bool:
        """Prompt for yes/no confirmation."""
        return confirm(message, default=default)

    def prompt_path(
        self,
        message: str,
        default: str = "",
        only_directories: bool = False,
    ) -> str:
        """Prompt for file/directory path with autocomplete."""
        return path(message, default=default, only_directories=only_directories)

    def prompt_model(self, message: str = "Enter model (app.Model):") -> str:
        """Prompt for Django model path."""
        return text(message, validate=validate_model_path)

    def prompt_identifier(self, message: str, default: str = "") -> str:
        """Prompt for Python identifier."""
        return text(message, default=default, validate=validate_python_identifier)

    def prompt_autocomplete(
        self,
        message: str,
        choices: list[str],
        default: str = "",
    ) -> str:
        """Prompt with autocomplete suggestions."""
        return autocomplete(message, choices=choices, default=default)


class GeneratorCommand(InteractiveCommand):
    """
    Command for generating files.

    Features:
    - File writing with conflict detection
    - Dry run mode
    - Summary of changes
    - Code preview

    Use for scaffolding and code generation commands.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files_created: list[Path] = []
        self._files_modified: list[Path] = []
        self._files_skipped: list[tuple[Path, str]] = []
        self._dry_run = False
        self._force = False

    def add_arguments(self, parser):
        """Add generator-specific arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing files",
        )
        parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Overwrite existing files without prompting",
        )

    def execute(self, *args, **options):
        """Execute with generator configuration."""
        self._dry_run = options.get("dry_run", False)
        self._force = options.get("force", False)
        return super().execute(*args, **options)

    # =========================================================================
    # File Operations
    # =========================================================================

    def write_file(
        self,
        path: str | Path,
        content: str,
        preview: bool = True,
    ) -> bool:
        """
        Write content to file.

        Args:
            path: File path
            content: File content
            preview: Whether to show preview in dry-run mode

        Returns:
            True if file was written/would be written
        """
        path = Path(path)

        # Check if file exists
        exists = path.exists()

        if exists and not self._force:
            if self._dry_run:
                self._files_skipped.append((path, "already exists"))
                self.console.file_skipped(path, "already exists")
                return False

            # Ask to overwrite
            if not self.prompt_confirm(f"Overwrite {path}?", default=False):
                self._files_skipped.append((path, "user declined"))
                self.console.file_skipped(path, "user declined")
                return False

        if self._dry_run:
            # Show preview
            if preview:
                self.console.newline()
                self.console.code(content, title=f"Would create: {path}")
            else:
                self.console.file_created(path)
                self.console.muted("  (content hidden in preview)")

            if exists:
                self._files_modified.append(path)
            else:
                self._files_created.append(path)
            return True

        # Actually write file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        if exists:
            self._files_modified.append(path)
            self.console.file_modified(path)
        else:
            self._files_created.append(path)
            self.console.file_created(path)

        return True

    def append_to_file(
        self,
        path: str | Path,
        content: str,
        separator: str = "\n\n",
    ) -> bool:
        """
        Append content to existing file.

        Args:
            path: File path
            content: Content to append
            separator: Separator between existing and new content

        Returns:
            True if file was modified/would be modified
        """
        path = Path(path)

        if not path.exists():
            return self.write_file(path, content)

        if self._dry_run:
            self.console.file_modified(path)
            self.console.muted("  (would append content)")
            self._files_modified.append(path)
            return True

        existing = path.read_text()
        path.write_text(existing + separator + content)

        self._files_modified.append(path)
        self.console.file_modified(path)
        return True

    def delete_file(self, path: str | Path) -> bool:
        """
        Delete a file.

        Args:
            path: File path

        Returns:
            True if file was deleted/would be deleted
        """
        path = Path(path)

        if not path.exists():
            return False

        if self._dry_run:
            self.console.file_deleted(path)
            return True

        path.unlink()
        self.console.file_deleted(path)
        return True

    def ensure_directory(self, path: str | Path) -> Path:
        """
        Ensure directory exists.

        Args:
            path: Directory path

        Returns:
            Path object
        """
        path = Path(path)

        if not self._dry_run:
            path.mkdir(parents=True, exist_ok=True)

        return path

    # =========================================================================
    # Summary
    # =========================================================================

    def show_summary(self):
        """Show summary of file operations."""
        self.console.files_summary(
            created=[str(p) for p in self._files_created],
            modified=[str(p) for p in self._files_modified],
        )

        if self._files_skipped:
            self.console.newline()
            self.console.section("Skipped Files")
            for path, reason in self._files_skipped:
                self.console.file_skipped(path, reason)

        if self._dry_run:
            self.console.newline()
            self.console.box_warning(
                "This was a dry run. No files were actually written.\n"
                "Run without --dry-run to apply changes.",
                title="Dry Run",
            )

    def reset_tracking(self):
        """Reset file tracking for multiple generations."""
        self._files_created = []
        self._files_modified = []
        self._files_skipped = []

    @property
    def files_created(self) -> list[Path]:
        """List of created files."""
        return self._files_created

    @property
    def files_modified(self) -> list[Path]:
        """List of modified files."""
        return self._files_modified

    @property
    def total_changes(self) -> int:
        """Total number of file changes."""
        return len(self._files_created) + len(self._files_modified)
