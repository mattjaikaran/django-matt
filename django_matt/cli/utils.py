"""
Shared CLI utilities for Django Matt commands.

Consolidates setup_django(), find_manage_py(), and run_manage_command()
which were duplicated across multiple CLI command modules.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def find_manage_py() -> Optional[Path]:
    """Find manage.py in current or parent directories."""
    current = Path.cwd()

    if (current / "manage.py").exists():
        return current / "manage.py"

    for _ in range(3):
        current = current.parent
        if (current / "manage.py").exists():
            return current / "manage.py"

    return None


def find_project_root() -> Optional[Path]:
    """Find the project root (directory containing manage.py)."""
    current = Path.cwd()

    if (current / "manage.py").exists():
        return current

    for _ in range(5):
        current = current.parent
        if (current / "manage.py").exists():
            return current

    return None


def run_manage_command(
    command: list[str],
    capture_output: bool = False,
    replace_process: bool = False,
) -> subprocess.CompletedProcess | None:
    """
    Run a Django management command.

    Args:
        command: Command arguments (e.g., ["migrate", "--run-syncdb"])
        capture_output: Capture stdout/stderr instead of printing
        replace_process: Replace current process (uses os.execv)

    Returns:
        CompletedProcess result, or None if replace_process=True
    """
    manage_py = find_manage_py()
    if not manage_py:
        console.print("[red]Error: Could not find manage.py[/]")
        console.print("[dim]Make sure you're in a Django project directory[/]")
        raise typer.Exit(1)

    full_command = [sys.executable, str(manage_py)] + command

    if replace_process:
        os.execv(sys.executable, full_command)  # noqa: S606
        return None  # unreachable, but keeps type checker happy

    return subprocess.run(
        full_command,
        capture_output=capture_output,
        text=capture_output,
        check=False,
    )


def setup_django() -> bool:
    """
    Set up Django before running commands.

    Auto-detects DJANGO_SETTINGS_MODULE if not set.
    """
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")

    if not settings_module:
        for pattern in [
            "config.settings",
            "settings",
            "core.settings",
            "project.settings",
        ]:
            try:
                os.environ["DJANGO_SETTINGS_MODULE"] = pattern
                import django

                django.setup()
                return True
            except Exception:
                if "DJANGO_SETTINGS_MODULE" in os.environ:
                    del os.environ["DJANGO_SETTINGS_MODULE"]

        console.print("[yellow]Warning: Could not find Django settings.[/]")
        console.print("Set DJANGO_SETTINGS_MODULE environment variable.")
        return False

    try:
        import django

        django.setup()
        return True
    except Exception as e:
        console.print(f"[red]Error setting up Django: {e}[/]")
        return False
