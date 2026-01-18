"""
Rich help text and command documentation.

Provides beautifully formatted help output with examples and command grouping.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_main_help():
    """Display main CLI help with all available commands."""
    console.print()
    console.print(
        Panel.fit(
            "[bold magenta]Django Matt CLI[/]\n"
            "[dim]A powerful toolkit for building modern Django APIs[/]",
            border_style="magenta",
        )
    )
    console.print()

    # Command groups
    _show_command_group(
        "Project Commands",
        [
            ("matt info", "Show project information and statistics"),
            ("matt doctor", "Check project health and configuration"),
            ("matt version", "Show django-matt version"),
        ],
    )

    _show_command_group(
        "Development Commands",
        [
            ("matt routes", "List all API routes"),
            ("matt models", "List all Django models"),
        ],
    )

    _show_command_group(
        "Scaffolding Commands",
        [
            ("matt new controller", "Generate a new API controller"),
            ("matt new schema", "Generate Pydantic schemas"),
            ("matt new service", "Generate a service layer"),
            ("matt new test", "Generate test files"),
        ],
    )

    _show_command_group(
        "Code Generation",
        [
            ("generate_crud", "Generate full CRUD from Django model"),
            ("sync_types", "Generate TypeScript/Swift types"),
            ("startapi", "Initialize a new Django Matt project"),
        ],
    )

    console.print()
    console.print("[dim]Run [bold]python manage.py <command> --help[/] for detailed help[/]")
    console.print()


def _show_command_group(title: str, commands: list[tuple[str, str]]):
    """Display a group of commands."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description")

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(Panel(table, title=f"[bold]{title}[/]", border_style="blue"))


def show_command_help(
    command: str, description: str, usage: str, options: list[dict], examples: list[dict]
):
    """
    Display rich help for a specific command.

    Args:
        command: Command name
        description: Command description
        usage: Usage string
        options: List of option dicts with 'name', 'description', 'default'
        examples: List of example dicts with 'command', 'description'
    """
    console.print()
    console.print(f"[bold magenta]{command}[/]")
    console.print(f"[dim]{description}[/]")
    console.print()

    # Usage
    console.print("[bold]Usage:[/]")
    console.print(f"  [cyan]{usage}[/]")
    console.print()

    # Options
    if options:
        console.print("[bold]Options:[/]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Option", style="green", no_wrap=True)
        table.add_column("Description")
        table.add_column("Default", style="dim")

        for opt in options:
            default = f"[{opt.get('default', '')}]" if opt.get("default") else ""
            table.add_row(opt["name"], opt["description"], default)

        console.print(table)
        console.print()

    # Examples
    if examples:
        console.print("[bold]Examples:[/]")
        for ex in examples:
            console.print(f"  [dim]# {ex['description']}[/]")
            console.print(f"  [cyan]{ex['command']}[/]")
            console.print()


# Pre-defined help for common commands
COMMAND_HELP = {
    "matt": {
        "description": "Django Matt CLI - Project utilities and scaffolding",
        "usage": "python manage.py matt <command> [options]",
        "options": [
            {"name": "--quiet, -q", "description": "Suppress non-essential output"},
            {"name": "--dry-run", "description": "Preview changes without writing files"},
            {"name": "--force, -f", "description": "Overwrite existing files"},
        ],
        "examples": [
            {"command": "python manage.py matt info", "description": "Show project info"},
            {"command": "python manage.py matt doctor", "description": "Check project health"},
            {
                "command": "python manage.py matt routes --filter api",
                "description": "List API routes",
            },
        ],
    },
    "matt new": {
        "description": "Scaffold new components for your Django Matt project",
        "usage": "python manage.py matt new <component> <name> [options]",
        "options": [
            {"name": "--app, -a", "description": "Target app directory"},
            {"name": "--crud", "description": "Generate full CRUD endpoints (controller only)"},
            {
                "name": "--type, -t",
                "description": "Test type: controller, service, unit",
                "default": "controller",
            },
        ],
        "examples": [
            {
                "command": "python manage.py matt new controller Product --crud",
                "description": "Create CRUD controller",
            },
            {
                "command": "python manage.py matt new schema User --app users",
                "description": "Create schemas in users app",
            },
            {
                "command": "python manage.py matt new service Order",
                "description": "Create service layer",
            },
            {
                "command": "python manage.py matt new test Product --type service",
                "description": "Create service tests",
            },
        ],
    },
    "generate_crud": {
        "description": "Generate complete CRUD from a Django model",
        "usage": "python manage.py generate_crud <app.Model> [options]",
        "options": [
            {"name": "--wizard, -w", "description": "Run interactive wizard mode"},
            {
                "name": "--components",
                "description": "Components to generate",
                "default": "controller schema",
            },
            {"name": "--full", "description": "Generate all components including admin and tests"},
            {"name": "--permissions", "description": "Permission classes to apply"},
            {"name": "--soft-delete", "description": "Use soft delete instead of hard delete"},
            {"name": "--no-service", "description": "Skip service layer generation"},
            {"name": "--with-admin", "description": "Generate Django Unfold admin"},
            {"name": "--dry-run", "description": "Preview without writing files"},
        ],
        "examples": [
            {"command": "python manage.py generate_crud", "description": "Run interactive wizard"},
            {
                "command": "python manage.py generate_crud myapp.Product --full",
                "description": "Generate everything",
            },
            {
                "command": "python manage.py generate_crud myapp.User --permissions IsAuthenticated",
                "description": "With auth",
            },
            {
                "command": "python manage.py generate_crud myapp.Order --dry-run",
                "description": "Preview changes",
            },
        ],
    },
    "sync_types": {
        "description": "Generate TypeScript or Swift types from Django models",
        "usage": "python manage.py sync_types [options]",
        "options": [
            {
                "name": "--target",
                "description": "Target language: typescript, swift",
                "default": "typescript",
            },
            {"name": "--output", "description": "Output directory"},
            {"name": "--watch", "description": "Watch for changes and regenerate"},
            {"name": "--models", "description": "Specific models to generate"},
        ],
        "examples": [
            {
                "command": "python manage.py sync_types --target typescript --output frontend/types",
                "description": "Generate TS types",
            },
            {"command": "python manage.py sync_types --watch", "description": "Watch mode"},
        ],
    },
}


def show_help_for(command: str):
    """Show rich help for a specific command."""
    if command in COMMAND_HELP:
        help_data = COMMAND_HELP[command]
        show_command_help(
            command,
            help_data["description"],
            help_data["usage"],
            help_data.get("options", []),
            help_data.get("examples", []),
        )
    else:
        console.print(f"[yellow]No detailed help available for '{command}'[/]")
        console.print("[dim]Try running the command with --help[/]")


def suggest_command(input_cmd: str, available_commands: list[str]) -> str | None:
    """
    Suggest a similar command if the user made a typo.

    Args:
        input_cmd: The command the user typed
        available_commands: List of valid commands

    Returns:
        Suggested command or None
    """
    # Simple Levenshtein-like matching
    best_match = None
    best_score = 0

    for cmd in available_commands:
        score = _similarity(input_cmd.lower(), cmd.lower())
        if score > best_score and score > 0.5:
            best_score = score
            best_match = cmd

    return best_match


def _similarity(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings."""
    if not s1 or not s2:
        return 0.0

    # Count matching characters
    matches = sum(1 for a, b in zip(s1, s2, strict=False) if a == b)
    max_len = max(len(s1), len(s2))

    return matches / max_len if max_len > 0 else 0.0
