"""
Django Matt CLI - Main entry point.

A modern CLI for Django Matt projects.

Usage:
    matt serve              # Start development server
    matt db migrate         # Run migrations
    matt new controller     # Generate a controller
    matt crud myapp.Model   # Generate full CRUD
    matt types ts           # Generate TypeScript types
    matt deploy fly         # Deploy to Fly.io
    matt status             # Project health check
    matt --help             # Show all commands
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from django_matt.cli.utils import run_manage_command

# Create the main Typer app
app = typer.Typer(
    name="matt",
    help="Django Matt CLI - A modern toolkit for Django APIs",
    no_args_is_help=False,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            from django_matt import __version__

            version = __version__
        except (ImportError, AttributeError):
            version = "0.1.0"

        console.print(f"\n[bold magenta]Django Matt[/] v{version}\n")
        raise typer.Exit()


def show_banner():
    """Show the Django Matt banner."""
    banner = """
[bold magenta]     ___  _                          __  __       _   _   [/]
[bold magenta]    |   \\(_)__ _ _ _  __ _ ___      |  \\/  |__ _ | |_| |_ [/]
[bold magenta]    | |) | / _` | ' \\/ _` / _ \\     | |\\/| / _` ||  _|  _|[/]
[bold magenta]    |___// \\__,_|_||_\\__, \\___/     |_|  |_\\__,_| \\__|\\__|[/]
[bold magenta]       |__/          |___/                                [/]
"""
    console.print(banner)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    Django Matt CLI - A modern toolkit for Django APIs.

    Use 'matt <command> --help' for more information on a command.
    """
    if ctx.invoked_subcommand is None:
        show_banner()

        try:
            from django_matt import __version__

            v = __version__
        except (ImportError, AttributeError):
            v = "0.1.0"

        console.print(f"[dim]v{v}[/]\n")

        # Show command groups
        console.print("[bold]Available Commands:[/]\n")

        # Development
        dev_table = Table(show_header=False, box=None, padding=(0, 2))
        dev_table.add_column("Command", style="cyan", no_wrap=True)
        dev_table.add_column("Description")
        dev_table.add_row("serve", "Start the development server")
        dev_table.add_row("shell", "Open Django interactive shell")
        dev_table.add_row("test", "Run project tests")

        console.print(Panel(dev_table, title="[bold]Development[/]", border_style="blue"))

        # Database
        db_table = Table(show_header=False, box=None, padding=(0, 2))
        db_table.add_column("Command", style="cyan", no_wrap=True)
        db_table.add_column("Description")
        db_table.add_row("db migrate", "Run database migrations")
        db_table.add_row("db make", "Create new migrations")
        db_table.add_row("db show", "Show migration status")
        db_table.add_row("db reset", "Reset the database")

        console.print(Panel(db_table, title="[bold]Database[/]", border_style="blue"))

        # Code Generation
        gen_table = Table(show_header=False, box=None, padding=(0, 2))
        gen_table.add_column("Command", style="cyan", no_wrap=True)
        gen_table.add_column("Description")
        gen_table.add_row("new controller", "Generate an API controller")
        gen_table.add_row("new schema", "Generate Pydantic schemas")
        gen_table.add_row("crud", "Generate full CRUD for a model")

        console.print(Panel(gen_table, title="[bold]Code Generation[/]", border_style="blue"))

        # Type Generation
        types_table = Table(show_header=False, box=None, padding=(0, 2))
        types_table.add_column("Command", style="cyan", no_wrap=True)
        types_table.add_column("Description")
        types_table.add_row("types ts", "Generate TypeScript types")
        types_table.add_row("types zod", "Generate Zod schemas")
        types_table.add_row("types swift", "Generate Swift types")

        console.print(Panel(types_table, title="[bold]Type Generation[/]", border_style="blue"))

        # Analysis & Deployment
        other_table = Table(show_header=False, box=None, padding=(0, 2))
        other_table.add_column("Command", style="cyan", no_wrap=True)
        other_table.add_column("Description")
        other_table.add_row("analyze", "Analyze your Django project")
        other_table.add_row("routes", "List all API routes")
        other_table.add_row("status", "Check project health")
        other_table.add_row("deploy", "Deploy to cloud platforms")
        other_table.add_row("ai", "Generate AI context files")
        other_table.add_row("explain", "Explain request flow for a URL path")
        other_table.add_row("schemas", "List all Pydantic schemas")
        other_table.add_row("validate", "Validate API endpoints")
        other_table.add_row("migrate-from", "Migrate from another framework")

        console.print(
            Panel(other_table, title="[bold]Analysis & Deployment[/]", border_style="blue")
        )

        console.print("\n[dim]Run 'matt <command> --help' for more information on a command.[/]\n")


# Import and register command groups
from django_matt.cli.commands.analyze import app as analyze_app
from django_matt.cli.commands.db import app as db_app
from django_matt.cli.commands.deploy import app as deploy_app
from django_matt.cli.commands.generate import app as generate_app
from django_matt.cli.commands.serve import app as serve_app
from django_matt.cli.commands.status import app as status_app
from django_matt.cli.commands.types import app as types_app

# Add command groups
app.add_typer(serve_app, name="serve", help="Development server")
app.add_typer(db_app, name="db", help="Database management")
app.add_typer(generate_app, name="new", help="Generate new components")
app.add_typer(generate_app, name="generate", help="Code generation (alias for 'new')", hidden=True)
app.add_typer(types_app, name="types", help="Type generation")
app.add_typer(analyze_app, name="analyze", help="Project analysis")
app.add_typer(deploy_app, name="deploy", help="Deployment and Docker")
app.add_typer(status_app, name="status", help="Project health")


# Add aliases for common commands
@app.command()
def routes(
    filter_pattern: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter routes by pattern"
    ),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
):
    """List all API routes (alias for 'analyze routes')."""
    from django_matt.cli.commands.analyze import routes as analyze_routes

    analyze_routes(filter_pattern, method)


@app.command()
def endpoints(
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter by pattern"),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
):
    """List all API endpoints (alias for 'routes')."""
    from django_matt.cli.commands.analyze import routes as analyze_routes

    analyze_routes(filter_pattern, method)


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues"),
):
    """Run project diagnostics (alias for 'status doctor')."""
    from django_matt.cli.commands.status import doctor as status_doctor

    status_doctor(fix)


@app.command()
def crud(
    model: str = typer.Argument(..., help="Model path (e.g., myapp.MyModel)"),
    full: bool = typer.Option(False, "--full", "-f", help="Generate everything"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    wizard: bool = typer.Option(False, "--wizard", "-w", help="Interactive wizard"),
):
    """Generate full CRUD for a Django model."""
    from django_matt.cli.commands.generate import crud as gen_crud

    gen_crud(model, None, None, None, False, False, False, False, full, dry_run, wizard)


@app.command()
def shell():
    """Start Django interactive shell."""
    from django_matt.cli.commands.serve import shell as serve_shell

    serve_shell(False)


@app.command()
def dev(
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
):
    """Start development server (alias for 'serve')."""
    from django_matt.cli.commands.serve import serve

    serve(None, port, "127.0.0.1", False, False)


@app.command()
def ai(
    output: str = typer.Option(".", "--output", "-o", help="Output directory"),
    format: str = typer.Option("all", "--format", "-f", help="Format: all, claude, cursor"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Generate AI context files (CLAUDE.md, .cursorrules)."""
    console.print("\n[bold magenta]Generating AI context files...[/]\n")

    command = ["generate_ai_context", "--output", output, "--format", format]
    if dry_run:
        command.append("--dry-run")

    run_manage_command(command)


@app.command()
def explain(
    path: str = typer.Argument(..., help="URL path to explain (e.g., /api/users/)"),
):
    """Explain request flow for a URL path."""
    console.print(f"\n[bold magenta]Explaining request flow for {path}...[/]\n")
    run_manage_command(["matt_explain", path])


@app.command()
def schemas(
    app_name: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all Pydantic schemas in the project."""
    command = ["matt_schemas"]
    if app_name:
        command.extend(["--app", app_name])
    if json_output:
        command.append("--json")
    run_manage_command(command)


@app.command()
def validate(
    prefix: str = typer.Option("/api/", "--prefix", help="URL prefix to scan"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Validate API endpoints for common issues."""
    command = ["validate_api", "--prefix", prefix]
    if strict:
        command.append("--strict")
    if json_output:
        command.append("--json")
    run_manage_command(command)


@app.command(name="migrate-from")
def migrate_from(
    framework: str = typer.Argument(..., help="Source framework (e.g., ninja, drf)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
):
    """Migrate from another framework to django-matt."""
    command = ["matt_migrate_from", framework]
    if dry_run:
        command.append("--dry-run")
    run_manage_command(command)


if __name__ == "__main__":
    app()
