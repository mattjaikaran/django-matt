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

app = typer.Typer(help="Analyze your Django project")
console = Console()


def setup_django():
    """Set up Django before running commands."""
    import os

    # Try to find Django settings
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")

    if not settings_module:
        # Try common patterns
        for pattern in ["config.settings", "settings", "core.settings", "project.settings"]:
            try:
                os.environ["DJANGO_SETTINGS_MODULE"] = pattern
                import django
                django.setup()
                return True
            except Exception:
                pass

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


@app.command()
def routes(
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter routes by pattern"),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
):
    """List all API routes in the project."""
    if not setup_django():
        raise typer.Exit(1)

    from django.urls import URLPattern, URLResolver, get_resolver

    console.print("\n[bold magenta]API Routes[/]\n")

    def collect_routes(resolver=None, prefix=""):
        """Recursively collect all URL routes."""
        if resolver is None:
            resolver = get_resolver()

        routes_list = []

        for pattern in resolver.url_patterns:
            path = prefix + str(pattern.pattern)

            if isinstance(pattern, URLResolver):
                routes_list.extend(collect_routes(pattern, path))
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

                routes_list.append({
                    "methods": methods,
                    "path": "/" + path.lstrip("^").rstrip("$"),
                    "name": pattern.name or "-",
                    "view": view_name or "-",
                })

        return routes_list

    routes_list = collect_routes()

    # Apply filters
    if filter_pattern:
        routes_list = [r for r in routes_list if filter_pattern.lower() in r["path"].lower()]
    if method:
        routes_list = [r for r in routes_list if method.upper() in r["methods"]]

    if not routes_list:
        console.print("[yellow]No routes found[/]")
        return

    table = Table(title=f"Found {len(routes_list)} routes")
    table.add_column("Methods", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Name", style="dim")
    table.add_column("View", style="dim")

    for route in routes_list:
        table.add_row(route["methods"], route["path"], route["name"], route["view"])

    console.print(table)


# Alias for routes
@app.command(name="endpoints")
def endpoints_command(
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter endpoints by pattern"),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Filter by HTTP method"),
):
    """List all API endpoints (alias for 'routes')."""
    routes(filter_pattern, method)
