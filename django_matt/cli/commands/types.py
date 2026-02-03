"""
Type generation commands - TypeScript, Swift, Zod.

Usage:
    matt types ts            # Generate TypeScript types
    matt types swift         # Generate Swift types
    matt types zod           # Generate Zod schemas
    matt types watch         # Watch mode for type generation
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(help="Type generation for frontend clients")
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


def run_manage_command(command: list[str]):
    """Run a Django management command."""
    manage_py = find_manage_py()

    if not manage_py:
        console.print("[red]Error: Could not find manage.py[/]")
        raise typer.Exit(1)

    full_command = [sys.executable, str(manage_py)] + command
    result = subprocess.run(full_command, check=False)
    return result


@app.callback(invoke_without_command=True)
def types(ctx: typer.Context):
    """
    Generate types for frontend clients.

    Converts Pydantic schemas to TypeScript, Swift, or Zod.
    """
    if ctx.invoked_subcommand is None:
        console.print("\n[bold magenta]Type Generation[/]\n")
        console.print("  [cyan]matt types ts[/]     - Generate TypeScript interfaces")
        console.print("  [cyan]matt types zod[/]    - Generate Zod schemas")
        console.print("  [cyan]matt types swift[/]  - Generate Swift Codable structs")
        console.print("  [cyan]matt types client[/] - Generate API client")
        console.print("  [cyan]matt types watch[/]  - Watch and regenerate on changes")
        console.print()


@app.command(name="ts")
def typescript(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated app names"),
    modules: Optional[str] = typer.Option(None, "--modules", "-m", help="Comma-separated module paths"),
    models: bool = typer.Option(False, "--models", help="Include Django models"),
    camel_case: bool = typer.Option(False, "--camel-case", help="Convert to camelCase"),
):
    """
    Generate TypeScript interfaces from Pydantic schemas.

    Scans your app for Pydantic models and generates corresponding TypeScript types.
    """
    console.print("\n[bold magenta]Generating TypeScript types...[/]\n")

    command = ["sync_types", "--target", "typescript"]

    if output:
        command.extend(["--output", output])
    if apps:
        command.extend(["--apps", apps])
    if modules:
        command.extend(["--modules", modules])
    if models:
        command.append("--models")
    if camel_case:
        command.append("--camel-case")

    run_manage_command(command)


@app.command()
def zod(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated app names"),
    modules: Optional[str] = typer.Option(None, "--modules", "-m", help="Comma-separated module paths"),
    camel_case: bool = typer.Option(False, "--camel-case", help="Convert to camelCase"),
):
    """
    Generate Zod schemas from Pydantic models.

    Creates Zod validation schemas for runtime type checking in TypeScript.
    """
    console.print("\n[bold magenta]Generating Zod schemas...[/]\n")

    command = ["sync_types", "--target", "zod"]

    if output:
        command.extend(["--output", output])
    if apps:
        command.extend(["--apps", apps])
    if modules:
        command.extend(["--modules", modules])
    if camel_case:
        command.append("--camel-case")

    run_manage_command(command)


@app.command()
def swift(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated app names"),
    modules: Optional[str] = typer.Option(None, "--modules", "-m", help="Comma-separated module paths"),
):
    """
    Generate Swift Codable structs from Pydantic models.

    Creates Swift structs for iOS/macOS apps.
    """
    console.print("\n[bold magenta]Generating Swift types...[/]\n")

    command = ["sync_types", "--target", "swift"]

    if output:
        command.extend(["--output", output])
    if apps:
        command.extend(["--apps", apps])
    if modules:
        command.extend(["--modules", modules])

    run_manage_command(command)


@app.command()
def client(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated app names"),
    base_url: str = typer.Option("/api", "--base-url", help="API base URL"),
    react_query: bool = typer.Option(False, "--react-query", help="Include React Query hooks"),
    swr: bool = typer.Option(False, "--swr", help="Include SWR hooks"),
    camel_case: bool = typer.Option(False, "--camel-case", help="Convert to camelCase"),
):
    """
    Generate a typed API client.

    Creates a fetch-based TypeScript client with full type safety.
    """
    console.print("\n[bold magenta]Generating API client...[/]\n")

    command = ["sync_types", "--target", "api-client"]

    if output:
        command.extend(["--output", output])
    if apps:
        command.extend(["--apps", apps])
    if base_url:
        command.extend(["--base-url", base_url])
    if react_query:
        command.append("--include-react-query")
    if swr:
        command.append("--include-swr")
    if camel_case:
        command.append("--camel-case")

    run_manage_command(command)


@app.command()
def watch(
    target: str = typer.Option("typescript", "--target", "-t", help="Target: typescript, zod, swift"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    apps: Optional[str] = typer.Option(None, "--apps", "-a", help="Comma-separated app names"),
    modules: Optional[str] = typer.Option(None, "--modules", "-m", help="Comma-separated module paths"),
    watch_dirs: Optional[str] = typer.Option(None, "--watch-dirs", help="Directories to watch"),
    interval: float = typer.Option(1.0, "--interval", help="Watch interval in seconds"),
    clear: bool = typer.Option(False, "--clear", help="Clear screen on regeneration"),
):
    """
    Watch for changes and regenerate types.

    Monitors Python files and regenerates frontend types on changes.
    """
    console.print("\n[bold magenta]Starting watch mode...[/]\n")

    command = ["sync_types", "--target", target, "--watch"]

    if output:
        command.extend(["--output", output])
    if apps:
        command.extend(["--apps", apps])
    if modules:
        command.extend(["--modules", modules])
    if watch_dirs:
        command.extend(["--watch-dirs", watch_dirs])
    if interval != 1.0:
        command.extend(["--watch-interval", str(interval)])
    if clear:
        command.append("--clear-screen")

    run_manage_command(command)


@app.command(name="config")
def types_config():
    """
    Generate type config from project analysis.

    Creates django_matt_codegen.py with discovered schemas.
    """
    console.print("\n[bold magenta]Generating type configuration...[/]\n")

    command = ["init_codegen"]
    run_manage_command(command)
