"""
Database commands - Migration and database management.

Usage:
    matt db migrate           # Run migrations
    matt db make              # Create migrations
    matt db reset             # Reset database
    matt db seed              # Seed data (if seeders exist)
    matt db show              # Show migration status
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(help="Database management commands")
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


def run_manage_command(command: list[str], capture_output: bool = False):
    """Run a Django management command."""
    manage_py = find_manage_py()

    if not manage_py:
        console.print("[red]Error: Could not find manage.py[/]")
        raise typer.Exit(1)

    full_command = [sys.executable, str(manage_py)] + command

    if capture_output:
        result = subprocess.run(full_command, capture_output=True, text=True, check=False)
        return result

    result = subprocess.run(full_command, check=False)
    return result


@app.callback(invoke_without_command=True)
def db(ctx: typer.Context):
    """
    Database management commands.

    Run 'matt db --help' to see available commands.
    """
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        console.print("\n[bold magenta]Database Commands[/]\n")
        console.print("  [cyan]matt db migrate[/]  - Run database migrations")
        console.print("  [cyan]matt db make[/]     - Create new migrations")
        console.print("  [cyan]matt db show[/]     - Show migration status")
        console.print("  [cyan]matt db reset[/]    - Reset database (dangerous!)")
        console.print("  [cyan]matt db seed[/]     - Run database seeders")
        console.print()


@app.command()
def migrate(
    app_label: Optional[str] = typer.Argument(None, help="App to migrate (optional)"),
    migration_name: Optional[str] = typer.Argument(None, help="Migration name (optional)"),
    fake: bool = typer.Option(False, "--fake", help="Mark migrations as run without running them"),
    plan: bool = typer.Option(False, "--plan", help="Show migration plan without running"),
):
    """
    Run database migrations.

    Applies pending migrations to the database.
    """
    console.print("\n[bold magenta]Running migrations...[/]\n")

    command = ["migrate"]

    if app_label:
        command.append(app_label)
    if migration_name:
        command.append(migration_name)
    if fake:
        command.append("--fake")
    if plan:
        command.append("--plan")

    run_manage_command(command)


@app.command()
def make(
    app_label: Optional[str] = typer.Argument(None, help="App to make migrations for"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Migration name"),
    empty: bool = typer.Option(False, "--empty", help="Create an empty migration"),
    merge: bool = typer.Option(False, "--merge", help="Enable merge mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be made"),
):
    """
    Create new database migrations.

    Detects model changes and creates migration files.
    """
    console.print("\n[bold magenta]Creating migrations...[/]\n")

    command = ["makemigrations"]

    if app_label:
        command.append(app_label)
    if name:
        command.extend(["--name", name])
    if empty:
        command.append("--empty")
    if merge:
        command.append("--merge")
    if dry_run:
        command.append("--dry-run")

    run_manage_command(command)


@app.command()
def show(
    app_label: Optional[str] = typer.Argument(None, help="App to show migrations for"),
    list_format: bool = typer.Option(False, "--list", "-l", help="List format"),
):
    """
    Show migration status.

    Lists all migrations and their applied/pending status.
    """
    console.print("\n[bold magenta]Migration Status[/]\n")

    command = ["showmigrations"]

    if app_label:
        command.append(app_label)
    if list_format:
        command.append("--list")

    run_manage_command(command)


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    keep_migrations: bool = typer.Option(False, "--keep-migrations", help="Keep migration files"),
):
    """
    Reset the database.

    WARNING: This will delete all data!
    """
    if not yes:
        console.print("[bold red]WARNING: This will delete all data in the database![/]")
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            console.print("[yellow]Aborted.[/]")
            raise typer.Exit(0)

    console.print("\n[bold magenta]Resetting database...[/]\n")

    # Flush database
    run_manage_command(["flush", "--no-input"])

    if not keep_migrations:
        console.print("[dim]Tip: Use --keep-migrations to preserve migration files[/]")

    console.print("\n[green]Database reset complete![/]")


@app.command()
def seed(
    app_label: Optional[str] = typer.Argument(None, help="App to seed"),
    fixture: Optional[str] = typer.Option(None, "--fixture", "-f", help="Fixture file to load"),
):
    """
    Seed the database with initial data.

    Looks for management command 'seed' or loads fixtures.
    """
    console.print("\n[bold magenta]Seeding database...[/]\n")

    if fixture:
        # Load specific fixture
        command = ["loaddata", fixture]
        run_manage_command(command)
        return

    # Try to find a seed command
    manage_py = find_manage_py()
    if not manage_py:
        console.print("[red]Error: Could not find manage.py[/]")
        raise typer.Exit(1)

    # Check if seed command exists
    result = run_manage_command(["help"], capture_output=True)

    if "seed" in (result.stdout or ""):
        command = ["seed"]
        if app_label:
            command.append(app_label)
        run_manage_command(command)
    else:
        console.print("[yellow]No seed command found.[/]")
        console.print(
            "[dim]Create a 'seed' management command or use --fixture to load fixtures.[/]"
        )
        console.print()
        console.print("Example seed command:")
        console.print("  [cyan]python manage.py loaddata fixtures/initial_data.json[/]")


@app.command()
def shell_db(
    database: str = typer.Option("default", "--database", "-d", help="Database alias"),
):
    """Open database shell (psql, sqlite3, etc.)."""
    console.print("\n[bold magenta]Opening database shell...[/]\n")
    run_manage_command(["dbshell", "--database", database])


@app.command()
def dump(
    output: str = typer.Option("dump.json", "--output", "-o", help="Output file"),
    app_label: Optional[str] = typer.Argument(None, help="App to dump"),
    indent: int = typer.Option(2, "--indent", help="JSON indentation"),
    natural_foreign: bool = typer.Option(
        False, "--natural-foreign", help="Use natural foreign keys"
    ),
    natural_primary: bool = typer.Option(
        False, "--natural-primary", help="Use natural primary keys"
    ),
):
    """
    Dump database data to a fixture file.

    Creates a JSON fixture that can be loaded with 'matt db seed --fixture'.
    """
    console.print(f"\n[bold magenta]Dumping database to {output}...[/]\n")

    command = ["dumpdata", "--indent", str(indent), "-o", output]

    if app_label:
        command.append(app_label)
    if natural_foreign:
        command.append("--natural-foreign")
    if natural_primary:
        command.append("--natural-primary")

    run_manage_command(command)
    console.print(f"\n[green]Data dumped to {output}[/]")


@app.command()
def squash(
    app_label: str = typer.Argument(..., help="App to squash migrations for"),
    start: Optional[str] = typer.Option(None, "--start", help="Start migration"),
    end: Optional[str] = typer.Option(None, "--end", help="End migration"),
):
    """
    Squash migrations for an app.

    Combines multiple migrations into a single migration.
    """
    console.print(f"\n[bold magenta]Squashing migrations for {app_label}...[/]\n")

    command = ["squashmigrations", app_label]

    if start:
        command.append(start)
    if end:
        command.append(end)

    run_manage_command(command)
