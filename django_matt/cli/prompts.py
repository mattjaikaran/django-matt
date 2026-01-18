"""
Interactive CLI prompts using questionary.

Usage:
    from django_matt.cli import text, select, multiselect, confirm, path

    name = text("What is your name?")
    choice = select("Pick one:", choices=["A", "B", "C"])
    choices = multiselect("Pick many:", choices=["A", "B", "C"])
    proceed = confirm("Continue?")
    file_path = path("Enter file path:")
"""

from collections.abc import Callable
from pathlib import Path as PathLib
from typing import Any

import questionary
from questionary import Style

# Custom style matching Django Matt branding
MATT_STYLE = Style(
    [
        ("qmark", "fg:#7c3aed bold"),  # Purple question mark
        ("question", "bold"),  # Bold question text
        ("answer", "fg:#22c55e bold"),  # Green answer
        ("pointer", "fg:#7c3aed bold"),  # Purple pointer
        ("highlighted", "fg:#7c3aed bold"),  # Purple highlight
        ("selected", "fg:#22c55e"),  # Green selected
        ("separator", "fg:#6b7280"),  # Gray separator
        ("instruction", "fg:#6b7280"),  # Gray instructions
        ("text", ""),  # Default text
        ("disabled", "fg:#6b7280 italic"),  # Gray disabled
    ]
)


def text(
    message: str,
    default: str = "",
    validate: Callable | None = None,
    instruction: str = "",
) -> str:
    """
    Prompt for text input.

    Args:
        message: Question to ask
        default: Default value
        validate: Validation function (returns True or error message)
        instruction: Help text shown below prompt

    Returns:
        User's text input
    """
    return questionary.text(
        message,
        default=default,
        validate=validate,
        instruction=instruction,
        style=MATT_STYLE,
    ).ask()


def password(
    message: str,
    validate: Callable | None = None,
) -> str:
    """
    Prompt for password input (hidden).

    Args:
        message: Question to ask
        validate: Validation function

    Returns:
        User's password input
    """
    return questionary.password(
        message,
        validate=validate,
        style=MATT_STYLE,
    ).ask()


def select(
    message: str,
    choices: list[str] | list[dict[str, Any]],
    default: str | None = None,
    instruction: str = "(Use arrow keys)",
) -> str:
    """
    Prompt to select one option.

    Args:
        message: Question to ask
        choices: List of choices (strings or dicts with 'name' and 'value')
        default: Default selection
        instruction: Help text

    Returns:
        Selected choice value
    """
    return questionary.select(
        message,
        choices=choices,
        default=default,
        instruction=instruction,
        style=MATT_STYLE,
    ).ask()


def multiselect(
    message: str,
    choices: list[str] | list[dict[str, Any]],
    default: list[str] | None = None,
    instruction: str = "(Space to select, Enter to confirm)",
    validate: Callable | None = None,
) -> list[str]:
    """
    Prompt to select multiple options.

    Args:
        message: Question to ask
        choices: List of choices
        default: Default selections
        instruction: Help text
        validate: Validation function

    Returns:
        List of selected choice values
    """
    return questionary.checkbox(
        message,
        choices=choices,
        default=default,
        instruction=instruction,
        validate=validate,
        style=MATT_STYLE,
    ).ask()


def confirm(
    message: str,
    default: bool = True,
    auto_enter: bool = True,
) -> bool:
    """
    Prompt for yes/no confirmation.

    Args:
        message: Question to ask
        default: Default value (True = yes)
        auto_enter: Whether Enter confirms default

    Returns:
        True if confirmed, False otherwise
    """
    return questionary.confirm(
        message,
        default=default,
        auto_enter=auto_enter,
        style=MATT_STYLE,
    ).ask()


def path(
    message: str,
    default: str = "",
    only_directories: bool = False,
    file_filter: Callable | None = None,
    validate: Callable | None = None,
) -> str:
    """
    Prompt for file/directory path with autocomplete.

    Args:
        message: Question to ask
        default: Default path
        only_directories: Only show directories
        file_filter: Filter function for files
        validate: Validation function

    Returns:
        Selected path as string
    """
    return questionary.path(
        message,
        default=default,
        only_directories=only_directories,
        file_filter=file_filter,
        validate=validate,
        style=MATT_STYLE,
    ).ask()


def autocomplete(
    message: str,
    choices: list[str],
    default: str = "",
    validate: Callable | None = None,
    match_middle: bool = True,
) -> str:
    """
    Prompt with autocomplete suggestions.

    Args:
        message: Question to ask
        choices: List of autocomplete suggestions
        default: Default value
        validate: Validation function
        match_middle: Match anywhere in string, not just start

    Returns:
        User's input
    """
    return questionary.autocomplete(
        message,
        choices=choices,
        default=default,
        validate=validate,
        match_middle=match_middle,
        style=MATT_STYLE,
    ).ask()


# =========================================================================
# Validation Helpers
# =========================================================================


def validate_not_empty(value: str) -> bool | str:
    """Validate that input is not empty."""
    if not value or not value.strip():
        return "This field is required"
    return True


def validate_path_exists(value: str) -> bool | str:
    """Validate that path exists."""
    if not PathLib(value).exists():
        return f"Path does not exist: {value}"
    return True


def validate_path_not_exists(value: str) -> bool | str:
    """Validate that path does not exist."""
    if PathLib(value).exists():
        return f"Path already exists: {value}"
    return True


def validate_is_directory(value: str) -> bool | str:
    """Validate that path is a directory."""
    path = PathLib(value)
    if not path.exists():
        return f"Path does not exist: {value}"
    if not path.is_dir():
        return f"Not a directory: {value}"
    return True


def validate_is_file(value: str) -> bool | str:
    """Validate that path is a file."""
    path = PathLib(value)
    if not path.exists():
        return f"Path does not exist: {value}"
    if not path.is_file():
        return f"Not a file: {value}"
    return True


def validate_python_identifier(value: str) -> bool | str:
    """Validate that value is a valid Python identifier."""
    if not value.isidentifier():
        return "Must be a valid Python identifier (letters, numbers, underscores, not starting with number)"
    return True


def validate_model_path(value: str) -> bool | str:
    """Validate model path format (app.Model)."""
    if "." not in value:
        return "Model must be in format: app_name.ModelName"
    parts = value.split(".")
    if len(parts) != 2:
        return "Model must be in format: app_name.ModelName"
    if not all(part.strip() for part in parts):
        return "Both app name and model name are required"
    return True


# =========================================================================
# Choice Helpers
# =========================================================================


def choice(name: str, value: Any = None, disabled: str | None = None) -> dict:
    """
    Create a choice dict for select/multiselect.

    Args:
        name: Display name
        value: Return value (defaults to name)
        disabled: If set, disables the choice with this message

    Returns:
        Choice dict
    """
    return questionary.Choice(
        title=name,
        value=value if value is not None else name,
        disabled=disabled,
    )


def separator(text: str = "─" * 20) -> questionary.Separator:
    """Create a separator for choice lists."""
    return questionary.Separator(text)
