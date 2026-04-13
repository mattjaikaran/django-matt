"""
Serve command - Development server and utilities.

Usage:
    matt serve                      # Start dev server on port 8000
    matt serve --port 8080          # Start on custom port
    matt serve --server granian     # Use Granian (Rust ASGI server)
    matt serve --server robyn       # Use Robyn (Rust HTTP framework)
    matt dev                        # Alias for serve
    matt shell                      # Django shell
"""

import os
import sys
from typing import Optional

import typer
from rich.console import Console

from django_matt.cli.utils import run_manage_command
from django_matt.deploy.base import ServerBackend

app = typer.Typer(help="Development server and utilities")
console = Console()

_SERVER_BACKEND_HELP = (
    "Server backend: django (built-in runserver), uvicorn, granian, robyn"
)


def _find_asgi_module() -> str:
    """Detect the project's ASGI module from DJANGO_SETTINGS_MODULE."""
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings")
    return settings_module.rsplit(".", 1)[0] + ".asgi:application"


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the server on"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    server: str = typer.Option("django", "--server", "-s", help=_SERVER_BACKEND_HELP),
    https: bool = typer.Option(False, "--https", help="Enable HTTPS (requires django-extensions)"),
    no_hot: bool = typer.Option(False, "--no-hot", help="Disable hot reload"),
):
    """
    Start the Django development server.

    By default, starts on localhost:8000 with hot reload enabled.
    Use --server to choose a production-grade ASGI server for development.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Use a non-Django server backend (granian, uvicorn, robyn)
    if server != "django":
        try:
            backend = ServerBackend(server)
        except ValueError:
            console.print(
                f"[red]Unknown server backend: {server}[/]\n"
                f"Available: django, {', '.join(b.value for b in ServerBackend)}"
            )
            raise typer.Exit(1)

        asgi_module = _find_asgi_module()
        dev_cmd = backend.get_dev_command(asgi_module, host=host, port=port)
        console.print(
            f"\n[bold magenta]Starting {backend.value} dev server on {host}:{port}...[/]\n"
        )
        console.print(f"[dim]$ {dev_cmd}[/]\n")
        parts = dev_cmd.split()
        os.execvp(parts[0], parts)  # noqa: S606
        return

    console.print(f"\n[bold magenta]Starting development server on {host}:{port}...[/]\n")

    command = ["runserver"]

    if https:
        # Use django-extensions runserver_plus with SSL
        import tempfile

        cert_dir = tempfile.gettempdir()
        command = ["runserver_plus", "--cert-file", f"{cert_dir}/cert.crt"]

    if no_hot:
        command.append("--noreload")

    command.append(f"{host}:{port}")

    run_manage_command(command, replace_process=True)


@app.command()
def dev(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the server on"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    server: str = typer.Option("django", "--server", "-s", help=_SERVER_BACKEND_HELP),
):
    """Start development server (alias for 'serve')."""
    serve(None, port, host, server, False, False)


@app.command()
def shell(
    ipython: bool = typer.Option(False, "--ipython", "-i", help="Use IPython shell"),
):
    """
    Start Django interactive shell.

    Opens a Python shell with Django models and utilities pre-loaded.
    """
    console.print("\n[bold magenta]Starting Django shell...[/]\n")

    if ipython:
        command = ["shell", "-i", "ipython"]
    else:
        command = ["shell"]

    run_manage_command(command, replace_process=True)


@app.command()
def test(
    path: Optional[str] = typer.Argument(None, help="Test path or module"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    failfast: bool = typer.Option(False, "--failfast", "-f", help="Stop on first failure"),
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Run with coverage"),
):
    """
    Run project tests.

    Uses pytest if available, otherwise falls back to Django's test runner.
    """
    console.print("\n[bold magenta]Running tests...[/]\n")

    # Check if pytest is available
    import importlib.util

    use_pytest = importlib.util.find_spec("pytest") is not None

    if use_pytest:
        command = ["pytest"]
        if verbose:
            command.append("-v")
        if failfast:
            command.append("-x")
        if coverage:
            command.extend(["--cov", "--cov-report=term-missing"])
        if path:
            command.append(path)

        os.execv(sys.executable, [sys.executable, "-m"] + command)  # noqa: S606
    else:
        command = ["test"]
        if verbose:
            command.append("-v")
        if failfast:
            command.append("--failfast")
        if path:
            command.append(path)

        run_manage_command(command, replace_process=True)


@app.command()
def check():
    """Run Django system checks."""
    console.print("\n[bold magenta]Running Django system checks...[/]\n")
    run_manage_command(["check"], replace_process=True)


@app.command()
def collectstatic(
    no_input: bool = typer.Option(True, "--no-input", help="Skip prompts"),
    clear: bool = typer.Option(False, "--clear", help="Clear existing files first"),
):
    """Collect static files."""
    console.print("\n[bold magenta]Collecting static files...[/]\n")

    command = ["collectstatic"]
    if no_input:
        command.append("--noinput")
    if clear:
        command.append("--clear")

    run_manage_command(command, replace_process=True)
