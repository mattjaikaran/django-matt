from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="secrets",
    help="Manage secrets",
    no_args_is_help=True,
)

console = Console()


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@app.command("list")
def list_secrets():
    """List all configured secret keys."""
    from django_matt.secrets.manager import get_secrets_manager

    async def _list():
        manager = get_secrets_manager()
        return await manager.list_keys()

    keys = _run_async(_list())
    if not keys:
        console.print("[dim]No secrets found.[/dim]")
        return

    table = Table(title="Secrets")
    table.add_column("Key", style="cyan")
    for key in sorted(keys):
        table.add_row(key)
    console.print(table)


@app.command("get")
def get_secret(key: str = typer.Argument(..., help="Secret key")):
    """Retrieve a secret value."""
    from django_matt.secrets.manager import get_secrets_manager

    async def _get():
        manager = get_secrets_manager()
        return await manager.get(key)

    value = _run_async(_get())
    if value is None:
        console.print(f"[red]Secret not found:[/red] {key}")
        raise typer.Exit(1)
    console.print(value)


@app.command("set")
def set_secret(
    key: str = typer.Argument(..., help="Secret key"),
    value: str = typer.Argument(..., help="Secret value"),
):
    """Store a secret value."""
    from django_matt.secrets.manager import get_secrets_manager

    async def _set():
        manager = get_secrets_manager()
        await manager.set(key, value)

    _run_async(_set())
    console.print(f"[green]Secret stored:[/green] {key}")


@app.command("rotate")
def rotate_secret(key: str = typer.Argument(..., help="Secret key")):
    """Force rotation of a secret."""
    from django_matt.secrets.manager import get_secrets_manager

    async def _rotate():
        manager = get_secrets_manager()
        await manager.rotate(key)

    _run_async(_rotate())
    console.print(f"[green]Secret rotated:[/green] {key}")


@app.command("encrypt")
def encrypt_file(
    input_path: str = typer.Argument(..., help="Input JSON file path"),
    output_path: str = typer.Argument(..., help="Output encrypted file path"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Fernet encryption key (generates one if not provided)"),
):
    """Encrypt a JSON secrets file."""
    from pathlib import Path

    import orjson

    from django_matt.secrets.backends import EncryptedFileBackend

    input_file = Path(input_path)
    if not input_file.exists():
        console.print(f"[red]File not found:[/red] {input_path}")
        raise typer.Exit(1)

    data = orjson.loads(input_file.read_bytes())
    if not isinstance(data, dict):
        console.print("[red]File must contain a JSON object[/red]")
        raise typer.Exit(1)

    if key is None:
        key = EncryptedFileBackend.generate_key()
        console.print(f"[yellow]Generated key:[/yellow] {key}")
        console.print("[dim]Store this key securely — you need it to decrypt.[/dim]")

    backend = EncryptedFileBackend(path=output_path, key=key)
    backend._data = {k: str(v) for k, v in data.items()}
    backend._save()
    console.print(f"[green]Encrypted file written:[/green] {output_path}")
