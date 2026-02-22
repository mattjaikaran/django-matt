"""
Status command - Project health check and diagnostics.

Usage:
    matt status      # Show project status
    matt doctor      # Run project diagnostics
"""

import sys
from importlib import import_module

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from django_matt.cli.utils import setup_django

app = typer.Typer(help="Check project health and status")
console = Console()


@app.callback(invoke_without_command=True)
def status(ctx: typer.Context):
    """
    Show project status and health information.
    """
    if ctx.invoked_subcommand is not None:
        return

    doctor()


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues"),
):
    """
    Run comprehensive project diagnostics.

    Checks:
    - Django settings
    - Database connection
    - Required apps
    - Security settings (in production)
    - Dependencies
    """
    console.print("\n[bold magenta]Project Health Check[/]\n")

    checks = []
    all_passed = True

    # Check 1: Django settings
    check = _check_django_settings()
    checks.append(check)
    if not check["passed"]:
        all_passed = False

    # Check 2: Database connection
    if check["passed"]:  # Only check DB if Django is set up
        check = _check_database()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Check 3: Installed apps
        check = _check_installed_apps()
        checks.append(check)
        if not check["passed"]:
            all_passed = False

        # Check 4: Security settings (in production)
        from django.conf import settings

        if not settings.DEBUG:
            check = _check_security()
            checks.append(check)
            if not check["passed"]:
                all_passed = False

    # Check 5: Dependencies
    check = _check_dependencies()
    checks.append(check)
    if not check["passed"]:
        all_passed = False

    # Display results
    for check in checks:
        if check["passed"]:
            console.print(f"[green]:heavy_check_mark:[/] {check['name']}")
        elif check.get("warning"):
            console.print(f"[yellow]:warning:[/] {check['name']}: {check['message']}")
        else:
            console.print(f"[red]:cross_mark:[/] {check['name']}: {check['message']}")

    console.print()

    if all_passed:
        console.print(
            Panel(
                "[green]All checks passed! Your project is healthy.[/]",
                title="Health Check Complete",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[yellow]Some checks failed. Review the warnings above.[/]",
                title="Health Check Complete",
                border_style="yellow",
            )
        )


@app.command()
def info(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show detailed project information."""
    if not setup_django():
        console.print("[red]Could not set up Django[/]")
        raise typer.Exit(1)

    import django
    from django.apps import apps
    from django.conf import settings

    try:
        from django_matt import __version__ as matt_version
    except (ImportError, AttributeError):
        matt_version = "0.1.0"

    console.print("\n[bold magenta]Project Information[/]\n")

    # Environment info
    console.print("[bold cyan]Environment[/]")
    console.print("─" * 11)

    env_table = Table(show_header=False)
    env_table.add_column("Key", style="dim")
    env_table.add_column("Value", style="green")

    env_table.add_row(
        "Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    env_table.add_row("Django", django.get_version())
    env_table.add_row("django-matt", matt_version)
    env_table.add_row("Debug Mode", "Yes" if settings.DEBUG else "No")

    console.print(env_table)
    console.print()

    # Project stats
    console.print("[bold cyan]Project Stats[/]")
    console.print("─" * 13)

    stats_table = Table(show_header=False)
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Count", style="green")

    stats_table.add_row("Installed Apps", str(len(settings.INSTALLED_APPS)))
    stats_table.add_row("Models", str(len(list(apps.get_models()))))
    stats_table.add_row("Middleware", str(len(settings.MIDDLEWARE)))

    console.print(stats_table)
    console.print()

    # Database info
    console.print("[bold cyan]Database[/]")
    console.print("─" * 8)

    for alias in settings.DATABASES:
        db = settings.DATABASES[alias]
        engine = db.get("ENGINE", "").split(".")[-1]
        name = db.get("NAME", "")
        console.print(f"  [cyan]{alias}:[/] {engine} - {name}")

    console.print()


@app.command()
def version():
    """Show django-matt version."""
    try:
        from django_matt import __version__

        version_str = __version__
    except (ImportError, AttributeError):
        version_str = "0.1.0"

    console.print(f"\n[bold magenta]Django Matt[/] v{version_str}\n")


def _check_django_settings() -> dict:
    """Check Django settings."""
    if not setup_django():
        return {
            "name": "Django settings",
            "passed": False,
            "warning": False,
            "message": "Could not find or load Django settings",
        }

    try:
        from django.conf import settings

        _ = settings.DEBUG
        return {"name": "Django settings", "passed": True, "warning": False, "message": ""}
    except Exception as e:
        return {
            "name": "Django settings",
            "passed": False,
            "warning": False,
            "message": str(e),
        }


def _check_database() -> dict:
    """Check database connection."""
    from django.db import connection

    try:
        connection.ensure_connection()
        return {"name": "Database connection", "passed": True, "warning": False, "message": ""}
    except Exception as e:
        return {
            "name": "Database connection",
            "passed": False,
            "warning": True,
            "message": str(e),
        }


def _check_installed_apps() -> dict:
    """Check that required apps are installed."""
    from django.conf import settings

    required = ["django.contrib.contenttypes"]
    missing = [app for app in required if app not in settings.INSTALLED_APPS]

    if missing:
        return {
            "name": "Required apps",
            "passed": False,
            "warning": True,
            "message": f"Missing: {', '.join(missing)}",
        }

    return {"name": "Required apps", "passed": True, "warning": False, "message": ""}


def _check_security() -> dict:
    """Check security settings for production."""
    from django.conf import settings

    issues = []

    if not getattr(settings, "SECRET_KEY", None):
        issues.append("SECRET_KEY not set")
    if getattr(settings, "SECRET_KEY", "").startswith("django-insecure"):
        issues.append("Using insecure SECRET_KEY")
    if not getattr(settings, "ALLOWED_HOSTS", []):
        issues.append("ALLOWED_HOSTS is empty")

    if issues:
        return {
            "name": "Security settings",
            "passed": False,
            "warning": True,
            "message": "; ".join(issues),
        }

    return {"name": "Security settings", "passed": True, "warning": False, "message": ""}


def _check_dependencies() -> dict:
    """Check required dependencies are installed."""
    required = ["django", "pydantic", "rich"]
    missing = []

    for pkg in required:
        try:
            import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        return {
            "name": "Dependencies",
            "passed": False,
            "warning": False,
            "message": f"Missing: {', '.join(missing)}",
        }

    return {"name": "Dependencies", "passed": True, "warning": False, "message": ""}
