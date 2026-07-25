"""
Enhanced Django shell with auto-imports.

Auto-imports all project models, django_matt core classes, common
Django utilities, and async helpers into the REPL namespace.

Usage:
    python manage.py matt_shell                # interactive shell
    python manage.py matt_shell --notebook     # IPython if available
    python manage.py matt_shell --print-imports  # show what gets imported
"""

from __future__ import annotations

import code
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand


def collect_auto_imports() -> dict[str, Any]:
    """Build a namespace dict of auto-imported objects.

    Returns mapping of name -> object for all auto-imported items.
    Catches ImportError for every optional dependency.
    """
    namespace: dict[str, Any] = {}
    import_log: list[str] = []

    # --- Django ORM utilities ---
    from django.db.models import (
        Avg,
        Count,
        F,
        Max,
        Min,
        Prefetch,
        Q,
        Sum,
        Value,
    )

    orm_names = {
        "Q": Q,
        "F": F,
        "Value": Value,
        "Count": Count,
        "Sum": Sum,
        "Avg": Avg,
        "Max": Max,
        "Min": Min,
        "Prefetch": Prefetch,
    }
    namespace.update(orm_names)
    import_log.append(f"django.db.models: {', '.join(sorted(orm_names.keys()))}")

    # --- Django settings ---
    from django.conf import settings

    namespace["settings"] = settings
    import_log.append("django.conf: settings")

    # --- Async utilities ---
    try:
        from asgiref.sync import async_to_sync, sync_to_async

        namespace["sync_to_async"] = sync_to_async
        namespace["async_to_sync"] = async_to_sync
        import_log.append("asgiref.sync: sync_to_async, async_to_sync")
    except ImportError:
        pass

    # --- django_matt core classes ---
    _matt_imports: list[tuple[str, str, list[str]]] = [
        ("django_matt.api", "django_matt.api", ["MattAPI"]),
        ("django_matt.core.router", "django_matt.core.router", ["Router"]),
        ("django_matt.core.schema", "django_matt.core.schema", ["Schema"]),
        (
            "django_matt.core.controller",
            "django_matt.core.controller",
            ["APIController"],
        ),
        ("django_matt.core.errors", "django_matt.core.errors", ["APIError"]),
    ]

    for label, module_path, names in _matt_imports:
        try:
            import importlib

            mod = importlib.import_module(module_path)
            imported: list[str] = []
            for name in names:
                obj = getattr(mod, name, None)
                if obj is not None:
                    namespace[name] = obj
                    imported.append(name)
            if imported:
                import_log.append(f"{label}: {', '.join(imported)}")
        except ImportError:
            pass

    # --- All project models ---
    model_names: list[str] = []
    for model in apps.get_models():
        name = model.__name__
        if name not in namespace:
            namespace[name] = model
            model_names.append(name)

    if model_names:
        import_log.append(f"models ({len(model_names)}): {', '.join(sorted(model_names))}")

    return namespace, import_log  # type: ignore[return-value]


def format_banner(import_log: list[str]) -> str:
    """Build a REPL banner string summarizing loaded imports."""
    lines = ["Django Matt Shell+", "=" * 40, "Auto-imported:"]
    for entry in import_log:
        lines.append(f"  {entry}")
    lines.append("=" * 40)
    return "\n".join(lines)


def format_banner_rich(import_log: list[str]) -> None:
    """Print a rich-formatted banner. Falls back to plain if rich missing."""
    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        body = "\n".join(f"  {entry}" for entry in import_log)
        console.print(
            Panel(
                body,
                title="[bold cyan]Django Matt Shell+[/bold cyan]",
                subtitle="Auto-imported",
                border_style="cyan",
            )
        )
    except ImportError:
        # Fallback handled by caller
        raise


class Command(BaseCommand):
    """Enhanced Django shell that auto-imports all models, ORM helpers, and django_matt classes."""

    help = "Enhanced Django shell with auto-imports for models, utils, and django_matt classes"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--notebook",
            action="store_true",
            default=False,
            help="Launch IPython notebook-style REPL if available",
        )
        parser.add_argument(
            "--print-imports",
            action="store_true",
            default=False,
            help="Print auto-imports and exit (don't start REPL)",
        )

    def handle(self, **options: Any) -> str | None:
        """Launch an interactive shell with auto-imported models and utilities."""
        namespace, import_log = collect_auto_imports()

        if options["print_imports"]:
            self.stdout.write("Auto-imports for matt_shell:\n")
            for entry in import_log:
                self.stdout.write(f"  {entry}\n")
            return None

        # Show banner
        try:
            format_banner_rich(import_log)
        except ImportError:
            self.stdout.write(format_banner(import_log) + "\n")

        # IPython mode
        if options["notebook"]:
            try:
                from IPython import start_ipython

                start_ipython(argv=[], user_ns=namespace)
                return None
            except ImportError:
                self.stderr.write(
                    self.style.WARNING("IPython not installed. Falling back to standard shell.\n")
                )

        # Standard interactive console
        banner = ""  # already printed
        console = code.InteractiveConsole(locals=namespace)
        console.interact(banner=banner, exitmsg="")
        return None
