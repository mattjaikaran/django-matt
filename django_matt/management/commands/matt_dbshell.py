"""
Enhanced Django DB shell with connection info, query execution, and output formatting.

Shows connection details, table size summary, and supports one-shot queries
with CSV or rich table output.

Usage:
    python manage.py matt_dbshell                     # interactive dbshell
    python manage.py matt_dbshell --read-only         # read-only session
    python manage.py matt_dbshell --query "SELECT 1"  # run query and exit
    python manage.py matt_dbshell --query "..." --csv # CSV output
    python manage.py matt_dbshell --query "..." --table  # rich table output
"""

from __future__ import annotations

import csv
import io
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections


def get_connection_info(alias: str = "default") -> dict[str, str]:
    """Extract connection info from Django database settings."""
    db_settings = settings.DATABASES.get(alias, {})
    engine = db_settings.get("ENGINE", "unknown")
    # Shorten engine name for display
    short_engine = engine.rsplit(".", 1)[-1] if "." in engine else engine

    return {
        "engine": short_engine,
        "name": db_settings.get("NAME", "unknown"),
        "host": db_settings.get("HOST", "localhost") or "localhost",
        "port": str(db_settings.get("PORT", "default") or "default"),
        "user": db_settings.get("USER", ""),
    }


def get_table_sizes(alias: str = "default", limit: int = 10) -> list[tuple[str, int]]:
    """Get top N tables by approximate row count.

    Returns list of (table_name, row_count) tuples.
    Works for PostgreSQL and SQLite. Falls back gracefully.
    """
    connection = connections[alias]
    engine = settings.DATABASES.get(alias, {}).get("ENGINE", "")
    results: list[tuple[str, int]] = []

    try:
        with connection.cursor() as cursor:
            if "postgresql" in engine or "postgis" in engine:
                cursor.execute(
                    "SELECT relname, n_live_tup "
                    "FROM pg_stat_user_tables "
                    "ORDER BY n_live_tup DESC "
                    f"LIMIT {limit}"
                )
                results = [(row[0], row[1]) for row in cursor.fetchall()]
            elif "sqlite" in engine:
                # SQLite: get all table names, count each
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]
                for table in tables:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    count = cursor.fetchone()[0]
                    results.append((table, count))
                results.sort(key=lambda x: x[1], reverse=True)
                results = results[:limit]
            else:
                # MySQL / other — skip table sizes
                pass
    except Exception:
        # Don't crash on stats failure
        pass

    return results


def execute_query(query: str, alias: str = "default") -> tuple[list[str], list[tuple[Any, ...]]]:
    """Execute a SQL query and return (column_names, rows)."""
    connection = connections[alias]
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []
    return columns, rows


def format_csv(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    """Format query results as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def format_rich_table(columns: list[str], rows: list[tuple[Any, ...]]) -> str | None:
    """Format query results as a rich table. Returns None if rich unavailable."""
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold cyan")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*(str(v) for v in row))

        console = Console(file=io.StringIO())
        console.print(table)
        return console.file.getvalue()  # type: ignore[union-attr]
    except ImportError:
        return None


def format_plain_table(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    """Format query results as a plain-text aligned table."""
    if not columns:
        return "(no results)"
    all_rows = [columns] + [tuple(str(v) for v in row) for row in rows]
    col_widths = [max(len(str(val)) for val in col_vals) for col_vals in zip(*all_rows)]
    lines: list[str] = []
    header = " | ".join(str(val).ljust(w) for val, w in zip(columns, col_widths))
    lines.append(header)
    lines.append("-+-".join("-" * w for w in col_widths))
    for row in rows:
        lines.append(" | ".join(str(val).ljust(w) for val, w in zip(row, col_widths)))
    return "\n".join(lines)


def set_read_only(alias: str = "default") -> bool:
    """Set the connection to read-only transaction mode.

    Returns True if successfully set, False otherwise.
    """
    engine = settings.DATABASES.get(alias, {}).get("ENGINE", "")
    connection = connections[alias]

    try:
        with connection.cursor() as cursor:
            if "postgresql" in engine or "postgis" in engine:
                cursor.execute("SET default_transaction_read_only = ON")
                return True
            if "sqlite" in engine:
                cursor.execute("PRAGMA query_only = ON")
                return True
    except Exception:
        pass
    return False


class Command(BaseCommand):
    """Enhanced DB shell with connection info, one-shot queries, and formatted output."""

    help = "Enhanced DB shell with connection info, query execution, and formatted output"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--read-only",
            action="store_true",
            default=False,
            help="Set transaction mode to read-only",
        )
        parser.add_argument(
            "--query",
            type=str,
            default=None,
            help="Execute a single SQL query and exit",
        )
        parser.add_argument(
            "--csv",
            action="store_true",
            default=False,
            help="Output query results as CSV (requires --query)",
        )
        parser.add_argument(
            "--table",
            action="store_true",
            default=False,
            help="Output query results as formatted table (requires --query)",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to use (default: 'default')",
        )

    def _print_connection_info(self, alias: str) -> None:
        """Display connection details."""
        info = get_connection_info(alias)
        try:
            from rich.console import Console
            from rich.panel import Panel

            console = Console()
            body = "\n".join(f"  {k}: {v}" for k, v in info.items())
            console.print(
                Panel(body, title="[bold cyan]Connection[/bold cyan]", border_style="cyan")
            )
        except ImportError:
            self.stdout.write("Connection Info:\n")
            for k, v in info.items():
                self.stdout.write(f"  {k}: {v}\n")

    def _print_table_sizes(self, alias: str) -> None:
        """Display top tables by row count."""
        sizes = get_table_sizes(alias)
        if not sizes:
            return

        try:
            from rich.console import Console
            from rich.table import Table as RichTable

            console = Console()
            t = RichTable(title="Top Tables by Row Count", header_style="bold cyan")
            t.add_column("Table")
            t.add_column("Rows", justify="right")
            for name, count in sizes:
                t.add_row(name, f"{count:,}")
            console.print(t)
        except ImportError:
            self.stdout.write("\nTop tables by row count:\n")
            for name, count in sizes:
                self.stdout.write(f"  {name}: {count:,}\n")

    def handle(self, **options: Any) -> str | None:
        alias: str = options["database"]
        read_only: bool = options["read_only"]
        query: str | None = options["query"]
        csv_output: bool = options["csv"]
        table_output: bool = options["table"]

        # Show connection info
        self._print_connection_info(alias)

        # Read-only mode
        if read_only:
            if set_read_only(alias):
                self.stdout.write(self.style.SUCCESS("Read-only mode enabled.\n"))
            else:
                self.stderr.write(self.style.WARNING("Could not enable read-only mode.\n"))

        # One-shot query mode
        if query:
            columns, rows = execute_query(query, alias)

            if csv_output:
                self.stdout.write(format_csv(columns, rows))
            elif table_output:
                rich_output = format_rich_table(columns, rows)
                if rich_output:
                    self.stdout.write(rich_output)
                else:
                    self.stdout.write(format_plain_table(columns, rows) + "\n")
            else:
                # Default: plain table
                self.stdout.write(format_plain_table(columns, rows) + "\n")

            return None

        # Show table sizes before entering interactive shell
        self._print_table_sizes(alias)
        self.stdout.write("\n")

        # Delegate to Django's dbshell
        call_command("dbshell", database=alias)
        return None
