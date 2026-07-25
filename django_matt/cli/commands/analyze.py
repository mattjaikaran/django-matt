"""
Analyze command - Codebase analysis and introspection.

Usage:
    matt analyze           # Full codebase analysis
    matt analyze models    # Analyze models only
    matt analyze routes    # Analyze routes only
    matt endpoints         # List all endpoints (alias)
"""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from django_matt.cli.utils import setup_django

app = typer.Typer(help="Analyze your Django project")
console = Console()


@app.callback(invoke_without_command=True)
def analyze(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Analyze your Django Matt project.

    Provides insights into your models, routes, and overall project health.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not setup_django():
        raise typer.Exit(1)

    from django.apps import apps
    from django.conf import settings

    console.print("\n[bold magenta]Project Analysis[/]\n")

    # Basic stats
    table = Table(title="Project Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    app_count = len(settings.INSTALLED_APPS)
    model_count = len(list(apps.get_models()))
    middleware_count = len(settings.MIDDLEWARE)

    table.add_row("Installed Apps", str(app_count))
    table.add_row("Models", str(model_count))
    table.add_row("Middleware", str(middleware_count))
    table.add_row("Debug Mode", "Yes" if settings.DEBUG else "No")

    console.print(table)
    console.print()


@app.command()
def models(
    app: Optional[str] = typer.Argument(None, help="Filter by app name"),
    fields: bool = typer.Option(False, "--fields", "-f", help="Show model fields"),
):
    """List all Django models in the project."""
    if not setup_django():
        raise typer.Exit(1)

    from django.apps import apps as django_apps

    console.print("\n[bold magenta]Django Models[/]\n")

    models_by_app = {}
    for model in django_apps.get_models():
        app_label = model._meta.app_label

        # Skip Django internal apps unless specifically requested
        if app_label in ("contenttypes", "sessions", "admin", "auth") and not app:
            continue

        if app and app_label != app:
            continue

        if app_label not in models_by_app:
            models_by_app[app_label] = []

        model_info = {
            "name": model.__name__,
            "table": model._meta.db_table,
            "fields": [f.name for f in model._meta.fields],
        }
        models_by_app[app_label].append(model_info)

    if not models_by_app:
        console.print("[yellow]No models found[/]")
        return

    for app_label, models_list in sorted(models_by_app.items()):
        console.print(f"\n[bold cyan]{app_label}[/]")
        console.print("─" * len(app_label))

        table = Table(show_header=True)
        table.add_column("Model", style="green")
        table.add_column("Table", style="dim")
        if fields:
            table.add_column("Fields")
        else:
            table.add_column("Fields", style="dim")

        for m in models_list:
            if fields:
                table.add_row(m["name"], m["table"], ", ".join(m["fields"]))
            else:
                table.add_row(m["name"], m["table"], str(len(m["fields"])))

        console.print(table)

    total = sum(len(models) for models in models_by_app.values())
    console.print(f"\n[dim]Total: {total} models in {len(models_by_app)} apps[/]")


def _get_type_hints_safe(func) -> dict:
    """Get type hints from a function, returning empty dict on failure."""
    import typing

    try:
        return typing.get_type_hints(func)
    except Exception:
        return {}


def _get_schema_name(annotation) -> str:
    """Extract a human-readable schema name from a type annotation."""
    if annotation is None:
        return "-"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    name = str(annotation)
    # Strip typing module prefix for readability
    return name.replace("typing.", "")


def collect_routes_data(
    filter_pattern: Optional[str] = None,
    method_filter: Optional[str] = None,
    verbose: bool = False,
) -> list[dict]:
    """Collect all URL routes as a list of dicts.

    Used by the routes command and directly testable.

    Args:
        filter_pattern: Filter routes by path substring.
        method_filter: Filter by HTTP method string.
        verbose: If True, include request_schema, response_schema, permissions fields.

    Returns:
        List of route dicts with at minimum: methods, path, name, view.
        When verbose=True also includes: request_schema, response_schema, permissions.
    """
    from django.urls import URLPattern, URLResolver, get_resolver

    def _collect(resolver=None, prefix=""):
        if resolver is None:
            resolver = get_resolver()

        routes_list = []
        for pattern in resolver.url_patterns:
            path = prefix + str(pattern.pattern)

            if isinstance(pattern, URLResolver):
                routes_list.extend(_collect(pattern, path))
            elif isinstance(pattern, URLPattern):
                callback = pattern.callback
                view_name = ""

                if hasattr(callback, "__name__"):
                    view_name = callback.__name__
                elif hasattr(callback, "__class__"):
                    view_name = callback.__class__.__name__

                methods = "GET"
                if hasattr(callback, "actions"):
                    methods = ", ".join(callback.actions.keys()).upper()
                elif hasattr(callback, "http_method_names"):
                    methods = ", ".join(
                        m.upper() for m in callback.http_method_names if m != "options"
                    )

                route_entry = {
                    "methods": methods,
                    "path": "/" + path.lstrip("^").rstrip("$"),
                    "name": pattern.name or "-",
                    "view": view_name or "-",
                }

                if verbose:
                    hints = _get_type_hints_safe(callback)
                    request_schema = "-"
                    response_schema = "-"

                    return_annotation = hints.get("return")
                    if return_annotation is not None and return_annotation is not type(None):
                        response_schema = _get_schema_name(return_annotation)

                    # Look for request body schemas (non-primitive type hints in params)
                    primitive_names = {
                        "-",
                        "str",
                        "int",
                        "bool",
                        "float",
                        "bytes",
                        "Request",
                        "None",
                    }
                    for param_name, hint in hints.items():
                        if param_name == "return":
                            continue
                        hint_name = _get_schema_name(hint)
                        if hint_name not in primitive_names:
                            request_schema = hint_name
                            break

                    # Permissions from controller class
                    permissions = "-"
                    cls = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
                    if cls:
                        perm_classes = getattr(cls, "permission_classes", [])
                        if perm_classes:
                            permissions = ", ".join(
                                getattr(p, "__name__", str(p)) for p in perm_classes
                            )

                    route_entry["request_schema"] = request_schema
                    route_entry["response_schema"] = response_schema
                    route_entry["permissions"] = permissions

                routes_list.append(route_entry)

        return routes_list

    result = _collect()

    if filter_pattern:
        result = [r for r in result if filter_pattern.lower() in r["path"].lower()]
    if method_filter:
        result = [r for r in result if method_filter.upper() in r["methods"]]

    return result


@app.command()
def routes(
    filter_pattern: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter routes by pattern"
    ),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show request/response schema and permissions"
    ),
):
    """List all API routes in the project.

    Default output: compact table with Method | Path | Handler columns.
    --verbose: adds Request Schema | Response Schema | Permissions columns.
    """
    if not setup_django():
        raise typer.Exit(1)

    console.print("\n[bold magenta]API Routes[/]\n")

    routes_list = collect_routes_data(
        filter_pattern=filter_pattern,
        method_filter=method,
        verbose=verbose,
    )

    if not routes_list:
        console.print("[yellow]No routes found[/]")
        return

    if verbose:
        table = Table(title=f"Found {len(routes_list)} routes (verbose)")
        table.add_column("Method", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Handler", style="dim")
        table.add_column("Request Schema", style="blue")
        table.add_column("Response Schema", style="magenta")
        table.add_column("Permissions", style="yellow")

        for route in routes_list:
            table.add_row(
                route["methods"],
                route["path"],
                route["view"],
                route.get("request_schema", "-"),
                route.get("response_schema", "-"),
                route.get("permissions", "-"),
            )
    else:
        table = Table(title=f"Found {len(routes_list)} routes")
        table.add_column("Method", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Handler", style="dim")

        for route in routes_list:
            table.add_row(route["methods"], route["path"], route["view"])

    console.print(table)


# Alias for routes
@app.command(name="endpoints")
def endpoints_command(
    filter_pattern: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter endpoints by pattern"
    ),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show request/response schema and permissions"
    ),
):
    """List all API endpoints (alias for 'routes')."""
    routes(filter_pattern, method, verbose)


@app.command()
def deep(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Run deep project analysis (delegates to matt_analyze)."""
    from django_matt.cli.utils import run_manage_command

    command = ["matt_analyze"]
    if json_output:
        command.append("--json")
    run_manage_command(command)


@app.command()
def explain(
    path: str = typer.Argument(..., help="URL path to explain"),
):
    """Explain request flow for a URL path."""
    from django_matt.cli.utils import run_manage_command

    run_manage_command(["matt_explain", path])


@app.command(name="schemas")
def schemas_command(
    app_name: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all Pydantic schemas."""
    from django_matt.cli.utils import run_manage_command

    command = ["matt_schemas"]
    if app_name:
        command.extend(["--app", app_name])
    if json_output:
        command.append("--json")
    run_manage_command(command)


@app.command(name="validate")
def validate_command(
    prefix: str = typer.Option("/api/", "--prefix", help="URL prefix to scan"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Validate API endpoints for issues."""
    from django_matt.cli.utils import run_manage_command

    command = ["validate_api", "--prefix", prefix]
    if strict:
        command.append("--strict")
    if json_output:
        command.append("--json")
    run_manage_command(command)
