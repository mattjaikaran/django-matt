"""
Deploy commands - Deployment and Docker management.

Usage:
    matt deploy fly         # Deploy to Fly.io
    matt deploy railway     # Deploy to Railway
    matt docker build       # Build Docker image
    matt docker up          # Start Docker compose
"""

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from django_matt.cli.utils import run_manage_command

app = typer.Typer(help="Deployment and Docker commands")
console = Console()


def run_command(command: list[str], cwd: Optional[Path] = None):
    """Run a shell command."""
    result = subprocess.run(command, cwd=cwd, check=False)
    return result


@app.callback(invoke_without_command=True)
def deploy(ctx: typer.Context):
    """
    Deployment and Docker commands.

    Deploy to cloud platforms or manage Docker containers.
    """
    if ctx.invoked_subcommand is None:
        console.print("\n[bold magenta]Deployment Commands[/]\n")
        console.print("  [bold cyan]Platforms:[/]")
        console.print("    [cyan]matt deploy fly[/]      - Deploy to Fly.io")
        console.print("    [cyan]matt deploy railway[/]  - Deploy to Railway")
        console.print("    [cyan]matt deploy render[/]   - Deploy to Render")
        console.print()
        console.print("  [bold cyan]Docker:[/]")
        console.print("    [cyan]matt deploy docker[/]   - Generate Docker files")
        console.print("    [cyan]matt deploy build[/]    - Build Docker image")
        console.print("    [cyan]matt deploy up[/]       - Start containers")
        console.print("    [cyan]matt deploy down[/]     - Stop containers")
        console.print()
        console.print("  [bold cyan]Configuration:[/]")
        console.print("    [cyan]matt deploy config[/]   - Generate platform config")
        console.print("    [cyan]matt deploy env[/]      - Manage environment files")
        console.print()


@app.command()
def fly(
    app_name: Optional[str] = typer.Option(None, "--app", "-a", help="Fly app name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Generate config without deploying"),
):
    """
    Deploy to Fly.io.

    Generates fly.toml and deploys your application.
    """
    console.print("\n[bold magenta]Deploying to Fly.io...[/]\n")

    if dry_run:
        command = ["deploy", "config", "--platform", "fly"]
    else:
        command = ["deploy", "--platform", "fly"]

    if app_name:
        command.extend(["--app-name", app_name])
    if dry_run:
        command.append("--dry-run")

    run_manage_command(command)


@app.command()
def railway(
    dry_run: bool = typer.Option(False, "--dry-run", help="Generate config without deploying"),
):
    """
    Deploy to Railway.

    Generates railway.json and deploys your application.
    """
    console.print("\n[bold magenta]Deploying to Railway...[/]\n")

    command = ["deploy", "--platform", "railway"]

    if dry_run:
        command.append("--dry-run")

    run_manage_command(command)


@app.command()
def render(
    dry_run: bool = typer.Option(False, "--dry-run", help="Generate config without deploying"),
):
    """
    Deploy to Render.

    Generates render.yaml and deploys your application.
    """
    console.print("\n[bold magenta]Deploying to Render...[/]\n")

    command = ["deploy", "--platform", "render"]

    if dry_run:
        command.append("--dry-run")

    run_manage_command(command)


@app.command(name="config")
def deploy_config(
    platform: str = typer.Argument(..., help="Platform: fly, railway, render, docker"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """
    Generate deployment configuration files.

    Creates platform-specific config without deploying.
    """
    console.print(f"\n[bold magenta]Generating {platform} configuration...[/]\n")

    command = ["deploy", "config", "--platform", platform]

    if output:
        command.extend(["--output", output])

    run_manage_command(command)


@app.command()
def docker(
    mode: str = typer.Option("production", "--mode", "-m", help="Mode: production, development"),
    include_db: bool = typer.Option(True, "--db/--no-db", help="Include PostgreSQL"),
    include_redis: bool = typer.Option(False, "--redis", help="Include Redis"),
    include_celery: bool = typer.Option(False, "--celery", help="Include Celery workers"),
    proxy: str = typer.Option("caddy", "--proxy", help="Proxy: caddy, nginx, none"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Domain for SSL"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """
    Generate Docker configuration.

    Creates Dockerfile, docker-compose.yml, and related files.
    """
    console.print(f"\n[bold magenta]Generating Docker configuration ({mode})...[/]\n")

    command = ["deploy", "docker", "--mode", mode]

    if not include_db:
        command.append("--no-db")
    if include_redis:
        command.append("--include-redis")
    if include_celery:
        command.append("--include-celery")
    if proxy != "caddy":
        command.extend(["--proxy", proxy])
    if domain:
        command.extend(["--domain", domain])
    if output:
        command.extend(["--output", output])

    run_manage_command(command)


@app.command()
def build(
    tag: str = typer.Option("latest", "--tag", "-t", help="Image tag"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Build without cache"),
    platform: Optional[str] = typer.Option(None, "--platform", help="Target platform"),
):
    """
    Build Docker image.

    Builds the application Docker image.
    """
    console.print("\n[bold magenta]Building Docker image...[/]\n")

    command = ["docker", "build"]

    if no_cache:
        command.append("--no-cache")
    if platform:
        command.extend(["--platform", platform])

    command.extend(["-t", f"app:{tag}", "."])

    run_command(command)


@app.command()
def up(
    detach: bool = typer.Option(True, "--detach/--no-detach", "-d", help="Run in background"),
    build_flag: bool = typer.Option(False, "--build", "-b", help="Build images before starting"),
    dev: bool = typer.Option(False, "--dev", help="Use development compose file"),
):
    """
    Start Docker containers.

    Starts all services defined in docker-compose.yml.
    """
    console.print("\n[bold magenta]Starting containers...[/]\n")

    command = ["docker", "compose"]

    if dev and Path("docker-compose.dev.yml").exists():
        command.extend(["-f", "docker-compose.dev.yml"])

    command.append("up")

    if detach:
        command.append("-d")
    if build_flag:
        command.append("--build")

    run_command(command)


@app.command()
def down(
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove volumes"),
    remove_orphans: bool = typer.Option(False, "--remove-orphans", help="Remove orphan containers"),
):
    """
    Stop Docker containers.

    Stops and removes containers.
    """
    console.print("\n[bold magenta]Stopping containers...[/]\n")

    command = ["docker", "compose", "down"]

    if volumes:
        command.append("-v")
    if remove_orphans:
        command.append("--remove-orphans")

    run_command(command)


@app.command()
def logs(
    service: Optional[str] = typer.Argument(None, help="Service name"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
):
    """
    View container logs.

    Shows logs from Docker containers.
    """
    command = ["docker", "compose", "logs"]

    if follow:
        command.append("-f")
    if tail:
        command.extend(["--tail", str(tail)])
    if service:
        command.append(service)

    run_command(command)


@app.command()
def env(
    action: str = typer.Argument("init", help="Action: init, list, validate, generate"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Production domain"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """
    Manage environment configurations.

    Initialize, list, or validate environment files.
    """
    console.print(f"\n[bold magenta]Environment: {action}[/]\n")

    command = ["deploy", "env", action]

    if domain and action == "init":
        command.extend(["--domain", domain])
    if output:
        command.extend(["--output", output])

    run_manage_command(command)


@app.command()
def health():
    """
    Show health check endpoint information.

    Displays available health check endpoints and configuration.
    """
    console.print("\n[bold magenta]Health Check Endpoints[/]\n")

    console.print(
        Panel(
            "[cyan]/health/[/]  - Full health check (database, cache, custom checks)\n"
            "[cyan]/ready/[/]   - Kubernetes readiness probe\n"
            "[cyan]/live/[/]    - Kubernetes liveness probe",
            title="Available Endpoints",
            border_style="cyan",
        )
    )

    console.print("\n[bold]Add to urls.py:[/]")
    console.print()
    console.print("[dim]from django_matt.deploy.health import get_health_urls[/]")
    console.print("[dim]urlpatterns = [..., *get_health_urls()][/]")
    console.print()
