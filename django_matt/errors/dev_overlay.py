"""Developer error overlay — rich terminal output for development errors."""

from __future__ import annotations

import sys
from typing import Any

from django_matt.errors.formatters import format_for_human
from django_matt.errors.structured import StructuredError


def render_dev_error(error: StructuredError, *, use_rich: bool | None = None) -> str:
    """Render a structured error for developer consumption.

    Tries to use ``rich`` for pretty terminal output. Falls back to
    ANSI-colored plain text if rich is not installed.

    Args:
        error: The structured error to render.
        use_rich: Force rich on/off. None = auto-detect.

    Returns:
        Formatted string ready for terminal output.
    """
    if use_rich is None:
        try:
            import rich  # noqa: F401

            use_rich = True
        except ImportError:
            use_rich = False

    if use_rich:
        return _render_rich(error)
    return format_for_human(error, color=sys.stderr.isatty())


def _render_rich(error: StructuredError) -> str:
    """Render using rich library for pretty terminal output."""
    from io import StringIO

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=100)

    # header
    severity_color = "red" if error.status_code >= 500 else "yellow"
    title = Text(f" {error.code} ", style=f"bold white on {severity_color}")
    console.print(Panel(title, expand=False))
    console.print(f"[bold]{error.message}[/bold]")
    if error.detail:
        console.print(f"[dim]{error.detail}[/dim]")
    console.print()

    # suggestions
    if error.fix_suggestions:
        console.print("[bold yellow]Suggestions:[/bold yellow]")
        for i, s in enumerate(error.fix_suggestions, 1):
            console.print(f"  [cyan]{i}.[/cyan] {s}")
        console.print()

    # context table
    if error.context:
        table = Table(title="Context", show_header=True, header_style="bold")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        for k, v in _flatten_dict(error.context).items():
            table.add_row(str(k), str(v))
        console.print(table)
        console.print()

    # settings
    if error.related_settings:
        console.print(f"[dim]Related settings: {', '.join(error.related_settings)}[/dim]")

    # docs
    if error.docs_url:
        console.print(f"[dim]Docs: {error.docs_url}[/dim]")

    # code snippet from traceback
    if error.traceback_str:
        console.print()
        console.print("[dim]Traceback:[/dim]")
        console.print(f"[dim]{error.traceback_str.rstrip()}[/dim]")

    return buf.getvalue()


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict for table display."""
    items: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, key))
        else:
            items[key] = v
    return items


def print_dev_error(error: StructuredError) -> None:
    """Print a structured error to stderr for developer visibility."""
    output = render_dev_error(error)
    print(output, file=sys.stderr)  # noqa: T201
