"""
Status command - Project health check and diagnostics.

Usage:
    matt status      # Show project status
    matt doctor      # Run project diagnostics
"""

import os
import sys
from dataclasses import dataclass, field
from importlib import import_module
from typing import Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from django_matt.cli.utils import setup_django

app = typer.Typer(help="Check project health and status")
console = Console()

Tier = Literal["error", "warning", "info"]


@dataclass
class CheckResult:
    """Structured result from a health check."""

    tier: Tier
    name: str
    message: str
    fix: str = ""


def _collect_errors() -> list[CheckResult]:
    """Error tier: must fix. Returns list of CheckResult with tier='error'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # Access SECRET_KEY via _wrapped to bypass Django's validation guard,
        # so we can report a missing/bad key rather than raising.
        try:
            wrapped = getattr(settings, "_wrapped", settings)
            secret_key = getattr(wrapped, "SECRET_KEY", "")
        except Exception:
            secret_key = ""

        if not secret_key:
            results.append(
                CheckResult(
                    tier="error",
                    name="SECRET_KEY missing",
                    message="SECRET_KEY is not configured",
                    fix="Set SECRET_KEY in your settings file",
                )
            )
        elif secret_key in ("change-me", "changeme", "your-secret-key"):
            results.append(
                CheckResult(
                    tier="error",
                    name="SECRET_KEY insecure",
                    message="SECRET_KEY is set to a known-insecure placeholder",
                    fix=(
                        "Generate a new secret key: "
                        "python -c \"from django.core.management.utils import "
                        "get_random_secret_key; print(get_random_secret_key())\""
                    ),
                )
            )

        # django_matt not in INSTALLED_APPS
        try:
            installed_apps = getattr(settings, "INSTALLED_APPS", [])
        except Exception:
            installed_apps = []

        if "django_matt" not in installed_apps:
            results.append(
                CheckResult(
                    tier="error",
                    name="django_matt not installed",
                    message="'django_matt' is not in INSTALLED_APPS",
                    fix="Add 'django_matt' to INSTALLED_APPS in your settings",
                )
            )

        # DATABASES not configured
        try:
            databases = getattr(settings, "DATABASES", {})
        except Exception:
            databases = {}

        if not databases:
            results.append(
                CheckResult(
                    tier="error",
                    name="DATABASES not configured",
                    message="No database configuration found",
                    fix="Add a DATABASES setting to your settings file",
                )
            )

    except Exception as e:
        results.append(
            CheckResult(
                tier="error",
                name="Django settings failed to load",
                message=str(e),
                fix="Ensure DJANGO_SETTINGS_MODULE is set and settings file is valid",
            )
        )

    # Check required imports
    required_modules = ["django", "pydantic", "rich"]
    for module in required_modules:
        try:
            import_module(module)
        except ImportError:
            results.append(
                CheckResult(
                    tier="error",
                    name=f"Required module missing: {module}",
                    message=f"Could not import '{module}'",
                    fix=f"Install the missing dependency: uv add {module}",
                )
            )

    return results


def _collect_warnings() -> list[CheckResult]:
    """Warning tier: should fix. Returns list of CheckResult with tier='warning'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # DEBUG=True in apparent production
        if getattr(settings, "DEBUG", False):
            dsm = os.environ.get("DJANGO_SETTINGS_MODULE", "")
            if "prod" in dsm or "production" in dsm:
                results.append(
                    CheckResult(
                        tier="warning",
                        name="DEBUG=True in production",
                        message=f"DJANGO_SETTINGS_MODULE='{dsm}' looks like production, but DEBUG=True",
                        fix="Set DEBUG=False in your production settings",
                    )
                )

        # No cache backend configured (using default LocMemCache)
        caches = getattr(settings, "CACHES", {})
        default_cache = caches.get("default", {})
        backend = default_cache.get("BACKEND", "")
        if not backend or "LocMemCache" in backend:
            results.append(
                CheckResult(
                    tier="warning",
                    name="No persistent cache configured",
                    message="Using Django's LocMemCache (in-memory, not shared between processes)",
                    fix="Configure Redis or Memcached: CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:6379/1'}}",
                )
            )

        # ALLOWED_HOSTS is empty
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        if not allowed_hosts:
            results.append(
                CheckResult(
                    tier="warning",
                    name="ALLOWED_HOSTS is empty",
                    message="ALLOWED_HOSTS is not configured",
                    fix="Set ALLOWED_HOSTS to your domain(s) in production",
                )
            )

        # No CORS headers configured
        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", None)
        cors_all = getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False)
        cors_middleware = any(
            "CorsMiddleware" in m for m in getattr(settings, "MIDDLEWARE", [])
        )
        if not cors_middleware and cors_origins is None and not cors_all:
            results.append(
                CheckResult(
                    tier="warning",
                    name="No CORS configuration",
                    message="django-cors-headers is not configured",
                    fix="Install django-cors-headers and add CorsMiddleware + CORS_ALLOWED_ORIGINS",
                )
            )

    except Exception:
        pass

    return results


def _collect_info() -> list[CheckResult]:
    """Info tier: suggestions. Returns list of CheckResult with tier='info'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # Recommend MATT_API_MODE for API-only projects
        if not getattr(settings, "MATT_API_MODE", False):
            results.append(
                CheckResult(
                    tier="info",
                    name="Consider MATT_API_MODE",
                    message="For API-only projects, enable MATT_API_MODE to strip unused middleware",
                    fix="Add MATT_API_MODE = True to your settings",
                )
            )

        # DI container not configured
        if not getattr(settings, "MATT_DI_CONTAINER", None):
            results.append(
                CheckResult(
                    tier="info",
                    name="DI container not configured",
                    message="Dependency injection container is available but not configured",
                    fix="Set MATT_DI_CONTAINER in settings to enable automatic dependency injection",
                )
            )

        # Suggest caching configuration if not already warned
        caches = getattr(settings, "CACHES", {})
        default_cache = caches.get("default", {})
        backend = default_cache.get("BACKEND", "")
        if backend and "LocMemCache" not in backend:
            results.append(
                CheckResult(
                    tier="info",
                    name="Cache configured",
                    message=f"Cache backend: {backend.split('.')[-1]}",
                )
            )

    except Exception:
        pass

    return results


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
    Run comprehensive project diagnostics with tiered output.

    Reports:
    - Errors (must fix): broken settings, missing modules
    - Warnings (should fix): suboptimal config, missing security
    - Info (suggestions): available but unused features
    """
    setup_django()

    console.print("\n[bold magenta]Project Health Check[/]\n")

    errors = _collect_errors()
    warnings = _collect_warnings()
    infos = _collect_info()

    # Display errors
    if errors:
        error_table = Table(title="[bold red]Errors (Must Fix)[/]", border_style="red")
        error_table.add_column("Check", style="red")
        error_table.add_column("Issue")
        error_table.add_column("Fix", style="dim")
        for r in errors:
            error_table.add_row(r.name, r.message, r.fix)
        console.print(error_table)
        console.print()

    # Display warnings
    if warnings:
        warn_table = Table(title="[bold yellow]Warnings (Should Fix)[/]", border_style="yellow")
        warn_table.add_column("Check", style="yellow")
        warn_table.add_column("Issue")
        warn_table.add_column("Fix", style="dim")
        for r in warnings:
            warn_table.add_row(r.name, r.message, r.fix)
        console.print(warn_table)
        console.print()

    # Display info
    if infos:
        info_table = Table(title="[bold blue]Info (Suggestions)[/]", border_style="blue")
        info_table.add_column("Feature", style="blue")
        info_table.add_column("Message")
        info_table.add_column("Action", style="dim")
        for r in infos:
            info_table.add_row(r.name, r.message, r.fix)
        console.print(info_table)
        console.print()

    # Summary line
    error_count = len(errors)
    warning_count = len(warnings)
    info_count = len(infos)

    summary_color = "red" if error_count else ("yellow" if warning_count else "green")
    summary = (
        f"[{summary_color}]{error_count} errors[/], "
        f"[yellow]{warning_count} warnings[/], "
        f"[blue]{info_count} info[/]"
    )
    console.print(
        Panel(
            summary,
            title="Health Check Complete",
            border_style=summary_color,
        )
    )

    if error_count:
        raise typer.Exit(1)


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
