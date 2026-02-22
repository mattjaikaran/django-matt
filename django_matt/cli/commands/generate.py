"""
Generate commands - Code scaffolding and generation.

Usage:
    matt new controller User     # Generate a controller
    matt new schema User         # Generate Pydantic schemas
    matt new service User        # Generate a service layer
    matt new model User          # Generate a model
    matt crud myapp.User         # Generate full CRUD for a model
    matt generate crud myapp.User  # Alias for crud
"""

from typing import Optional

import typer
from rich.console import Console

from django_matt.cli.utils import run_manage_command

app = typer.Typer(help="Code generation and scaffolding")
console = Console()


@app.callback(invoke_without_command=True)
def generate(ctx: typer.Context):
    """
    Code generation and scaffolding commands.

    Use 'matt new <component>' for scaffolding or 'matt crud' for full CRUD.
    """
    if ctx.invoked_subcommand is None:
        console.print("\n[bold magenta]Code Generation[/]\n")
        console.print("  [cyan]matt new controller <Name>[/]  - Generate an API controller")
        console.print("  [cyan]matt new schema <Name>[/]      - Generate Pydantic schemas")
        console.print("  [cyan]matt new service <Name>[/]     - Generate a service layer")
        console.print("  [cyan]matt new test <Name>[/]        - Generate test files")
        console.print("  [cyan]matt crud <app.Model>[/]       - Generate full CRUD")
        console.print()


@app.command()
def new(
    component: str = typer.Argument(
        ..., help="Component type: controller, schema, service, model, test"
    ),
    name: str = typer.Argument(..., help="Component name (e.g., User, Product)"),
    app: Optional[str] = typer.Option(None, "--app", "-a", help="Target Django app"),
    crud: bool = typer.Option(
        False, "--crud", help="Generate full CRUD endpoints (for controllers)"
    ),
):
    """
    Generate a new component.

    Creates controllers, schemas, services, models, or tests.
    """
    valid_components = ["controller", "schema", "service", "model", "test"]

    if component not in valid_components:
        console.print(f"[red]Unknown component type: {component}[/]")
        console.print(f"[dim]Valid types: {', '.join(valid_components)}[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold magenta]Generating {component}: {name}[/]\n")

    # Use existing Django management command
    command = ["matt", "new", component, name]

    if app:
        command.extend(["--app", app])
    if crud and component == "controller":
        command.append("--crud")

    run_manage_command(command)


@app.command()
def crud(
    model: str = typer.Argument(..., help="Model path (e.g., myapp.MyModel)"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    prefix: Optional[str] = typer.Option(None, "--prefix", help="URL prefix"),
    permissions: Optional[list[str]] = typer.Option(
        None, "--permissions", "-p", help="Permission classes"
    ),
    with_tests: bool = typer.Option(False, "--with-tests", "-t", help="Generate tests"),
    with_admin: bool = typer.Option(False, "--with-admin", help="Generate admin configuration"),
    no_service: bool = typer.Option(False, "--no-service", help="Skip service layer"),
    soft_delete: bool = typer.Option(False, "--soft-delete", help="Use soft delete"),
    full: bool = typer.Option(False, "--full", "-f", help="Generate everything"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    wizard: bool = typer.Option(False, "--wizard", "-w", help="Interactive wizard mode"),
):
    """
    Generate full CRUD for a Django model.

    Creates controller, schemas, service layer, tests, and admin.
    """
    console.print(f"\n[bold magenta]Generating CRUD for {model}[/]\n")

    command = ["generate_crud", model]

    if output_dir:
        command.extend(["--output-dir", output_dir])
    if prefix:
        command.extend(["--prefix", prefix])
    if permissions:
        command.extend(["--permissions"] + list(permissions))
    if with_tests:
        command.append("--with-tests")
    if with_admin:
        command.append("--with-admin")
    if no_service:
        command.append("--no-service")
    if soft_delete:
        command.append("--soft-delete")
    if full:
        command.append("--full")
    if dry_run:
        command.append("--dry-run")
    if wizard:
        command.append("--wizard")

    run_manage_command(command)


@app.command()
def api(
    name: str = typer.Argument(..., help="API/app name"),
    template: str = typer.Option("basic", "--template", "-t", help="Template: basic, crud, b2b"),
    auth: str = typer.Option("jwt", "--auth", "-a", help="Auth type: jwt, session, none"),
    docker: bool = typer.Option(False, "--docker", help="Include Docker configuration"),
):
    """
    Generate a new API project or app.

    Creates a complete API structure with controllers, schemas, and tests.
    """
    console.print(f"\n[bold magenta]Creating API: {name}[/]\n")

    command = ["startapi", name, "--template", template, "--auth", auth]

    if docker:
        command.append("--docker")

    run_manage_command(command)


@app.command(name="admin")
def generate_admin(
    model: str = typer.Argument(..., help="Model path (e.g., myapp.MyModel)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """
    Generate Django Unfold admin for a model.

    Creates a configured admin class with list display, filters, and search.
    """
    console.print(f"\n[bold magenta]Generating admin for {model}[/]\n")

    command = ["generate_admin", model]

    if output:
        command.extend(["--output", output])

    run_manage_command(command)
