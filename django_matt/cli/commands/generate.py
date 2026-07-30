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
import importlib
import sys
from pathlib import Path

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
        console.print("  [cyan]matt generate tests <module>[/]  - Generate edge-case tests from schemas")
        console.print("  [cyan]matt new test <Name>[/]        - Generate test files")
        console.print("  [cyan]matt crud <app.Model>[/]       - Generate full CRUD")
        console.print()


@app.command()
def new(
    component: str = typer.Argument(
        ..., help="Component type: controller, schema, service, model, test"
    ),
    name: str = typer.Argument(..., help="Component name (e.g., User, Product)"),
    app: str | None = typer.Option(None, "--app", "-a", help="Target Django app"),
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
    output_dir: str | None = typer.Option(None, "--output", "-o", help="Output directory"),
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
    output: str | None = typer.Option(None, "--output", "-o", help="Output file"),
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

@app.command()
def tests(
    module: str = typer.Argument(..., help="Python module path containing schemas"),
    schema: str = typer.Option(None, "--schema", "-s", help="Specific schema class name"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
    smart: bool = typer.Option(False, "--smart", help="Register with smart testing"),
    edge_cases: bool = typer.Option(
        True, "--edge-cases/--no-edge-cases", help="Include edge case tests"
    ),
):
    """Generate edge-case tests from Pydantic schemas.

    Discovers Schema subclasses in a module and generates pytest tests
    covering edge cases: empty strings, boundary values, None for
    optional fields, missing required fields, type mismatches, long
    strings, special characters, empty lists, and nested validation.

    Examples:
        matt generate tests myapp.schemas
        matt generate tests myapp.schemas --schema UserCreate
        matt generate tests myapp.schemas --smart --output tests/test_gen.py
    """
    console.print(f"\n[bold magenta]Generating tests from schemas in {module}[/]\n")

    # --- Resolve and import the module ---
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        console.print(f"[red]Module not found: {module}[/]")
        console.print("[dim]Make sure the module is on PYTHONPATH and you're in a Django project.[/]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to import {module}: {exc}[/]")
        raise typer.Exit(1)

    # --- Discover Schema subclasses ---
    from pydantic import BaseModel

    schemas_found: list[tuple[str, type[BaseModel]]] = []

    if schema:
        # Look for the specific schema class
        cls = getattr(mod, schema, None)
        if cls is None or not (isinstance(cls, type) and issubclass(cls, BaseModel)):
            console.print(f"[red]Schema class '{schema}' not found in {module}[/]")
            console.print("[dim]Check the class name and that it inherits from BaseModel.[/]")
            raise typer.Exit(1)
        schemas_found.append((schema, cls))
    else:
        for name, obj in mod.__dict__.items():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj is not BaseModel
                and not name.startswith("_")
            ):
                schemas_found.append((name, obj))

    if not schemas_found:
        console.print(f"[yellow]No Schema subclasses found in {module}[/]")
        raise typer.Exit(0)

    console.print(f"[dim]Found {len(schemas_found)} schema(s): {', '.join(n for n, _ in schemas_found)}[/]\n")

    # --- Generate tests ---
    generated_files: list[Path] = []

    if smart:
        try:
            from django_matt.guardrails.testgen_smart import SmartTestGenerator
            from django_matt.testing.smart.tracker import TestDependencyTracker
        except ImportError as exc:
            console.print(f"[red]Smart testing not available: {exc}[/]")
            console.print("[dim]Install with: pip install django-matt[smart][/]")
            raise typer.Exit(1)

        tracker_inst = TestDependencyTracker()
        try:
            for s_name, s_cls in schemas_found:
                gen = SmartTestGenerator(s_cls, tracker=tracker_inst)
                out_path = Path(output) if output else Path(f"tests/test_{s_name.lower()}_gen.py")
                result = gen.generate_test_file(out_path)
                generated_files.append(result)
                console.print(f"  [green]✓[/] {s_name} → [cyan]{result}[/] (smart)")
        finally:
            tracker_inst.close()
    else:
        try:
            from django_matt.guardrails.testgen import SchemaTestGenerator
        except ImportError as exc:
            console.print(f"[red]Test generator not available: {exc}[/]")
            console.print("[dim]Make sure django_matt.guardrails.testgen is installed.[/]")
            raise typer.Exit(1)

        if output and len(schemas_found) > 1:
            console.print("[yellow]--output specified with multiple schemas; each gets its own file.[/]")

        for s_name, s_cls in schemas_found:
            gen = SchemaTestGenerator(s_cls)
            if output and len(schemas_found) == 1:
                out_path = Path(output)
            else:
                out_path = Path(f"tests/test_{s_name.lower()}_gen.py")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            result = gen.generate_test_file(out_path)
            generated_files.append(result)
            console.print(f"  [green]✓[/] {s_name} → [cyan]{result}[/]")

    # --- Summary ---
    console.print()
    console.print(f"[bold green]{len(generated_files)} test file(s) generated[/]")
    for f in generated_files:
        console.print(f"  [dim]{f}[/]")
    console.print()
