# file-length-max: 650
"""
Rich console utilities for beautiful CLI output.

Usage:
    from django_matt.cli import console

    console.success("Operation completed!")
    console.error("Something went wrong")
    console.warning("Be careful")
    console.info("FYI...")

    # Tables
    console.table(data, columns=["Name", "Email", "Role"])

    # Trees
    console.tree({"src": {"models.py": None, "views.py": None}})

    # Code
    console.code("def hello(): pass", language="python")

    # Progress
    with console.progress("Processing...") as progress:
        for item in items:
            progress.advance()

    # Panels and boxes
    console.panel("Important message", title="Notice")
"""

from pathlib import Path
from typing import Any

from rich.console import Console as RichConsole
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree


class Console:
    """
    Beautiful console output for Django Matt CLI.

    Provides consistent, colorful output with spinners, tables, trees, and more.
    """

    # Brand colors
    BRAND_PRIMARY = "#7c3aed"  # Purple
    BRAND_SECONDARY = "#06b6d4"  # Cyan
    SUCCESS_COLOR = "#22c55e"  # Green
    ERROR_COLOR = "#ef4444"  # Red
    WARNING_COLOR = "#f59e0b"  # Amber
    INFO_COLOR = "#3b82f6"  # Blue
    MUTED_COLOR = "#6b7280"  # Gray

    def __init__(self):
        self._console = RichConsole()
        self._quiet = False

    @property
    def quiet(self) -> bool:
        """Check if quiet mode is enabled."""
        return self._quiet

    @quiet.setter
    def quiet(self, value: bool):
        """Set quiet mode."""
        self._quiet = value

    def print(self, *args, **kwargs):
        """Print to console."""
        if not self._quiet:
            self._console.print(*args, **kwargs)

    # =========================================================================
    # Status Messages
    # =========================================================================

    def success(self, message: str, prefix: str = ""):
        """Print success message with checkmark."""
        if not self._quiet:
            icon = "[bold green]:heavy_check_mark:[/]" if not prefix else ""
            prefix_text = f"[bold green]{prefix}[/] " if prefix else ""
            self._console.print(f"{icon} {prefix_text}[green]{message}[/]")

    def error(self, message: str, prefix: str = ""):
        """Print error message with X."""
        icon = "[bold red]:cross_mark:[/]" if not prefix else ""
        prefix_text = f"[bold red]{prefix}[/] " if prefix else ""
        self._console.print(f"{icon} {prefix_text}[red]{message}[/]")

    def warning(self, message: str, prefix: str = ""):
        """Print warning message."""
        if not self._quiet:
            icon = "[bold yellow]:warning:[/]" if not prefix else ""
            prefix_text = f"[bold yellow]{prefix}[/] " if prefix else ""
            self._console.print(f"{icon} {prefix_text}[yellow]{message}[/]")

    def info(self, message: str, prefix: str = ""):
        """Print info message."""
        if not self._quiet:
            icon = "[bold blue]:information:[/]" if not prefix else ""
            prefix_text = f"[bold blue]{prefix}[/] " if prefix else ""
            self._console.print(f"{icon} {prefix_text}[blue]{message}[/]")

    def debug(self, message: str):
        """Print debug message (muted)."""
        if not self._quiet:
            self._console.print(f"[dim]{message}[/]")

    def muted(self, message: str):
        """Print muted/secondary text."""
        if not self._quiet:
            self._console.print(f"[dim]{message}[/]")

    # =========================================================================
    # Headers and Sections
    # =========================================================================

    def header(self, title: str, subtitle: str = ""):
        """Print a branded header."""
        if not self._quiet:
            self._console.print()
            self._console.print(f"[bold magenta]  {title}[/]")
            if subtitle:
                self._console.print(f"[dim]  {subtitle}[/]")
            self._console.print()

    def section(self, title: str):
        """Print a section header."""
        if not self._quiet:
            self._console.print()
            self._console.print(f"[bold cyan]{title}[/]")
            self._console.print("[dim]" + "─" * len(title) + "[/]")

    def divider(self, char: str = "─", width: int = 60):
        """Print a divider line."""
        if not self._quiet:
            self._console.print(f"[dim]{char * width}[/]")

    def newline(self, count: int = 1):
        """Print empty lines."""
        if not self._quiet:
            for _ in range(count):
                self._console.print()

    # =========================================================================
    # Structured Output
    # =========================================================================

    def table(
        self,
        data: list[dict[str, Any]] | list[list[Any]],
        columns: list[str] | None = None,
        title: str = "",
        show_header: bool = True,
        row_styles: list[str] | None = None,
    ):
        """
        Print a formatted table.

        Args:
            data: List of dicts or list of lists
            columns: Column names (required for list of lists)
            title: Optional table title
            show_header: Whether to show column headers
            row_styles: Alternating row styles
        """
        if not data or self._quiet:
            return

        table = Table(
            title=title if title else None,
            show_header=show_header,
            header_style="bold cyan",
            row_styles=row_styles or ["", "dim"],
        )

        # Determine columns
        if isinstance(data[0], dict):
            cols = columns or list(data[0].keys())
        else:
            cols = columns or [f"Col {i + 1}" for i in range(len(data[0]))]

        for col in cols:
            table.add_column(col)

        # Add rows
        for row in data:
            if isinstance(row, dict):
                table.add_row(*[str(row.get(c, "")) for c in cols])
            else:
                table.add_row(*[str(v) for v in row])

        self._console.print(table)

    def tree(
        self,
        data: dict[str, Any],
        title: str = "",
        guide_style: str = "dim",
    ):
        """
        Print a tree structure.

        Args:
            data: Nested dict representing tree (None values are leaves)
            title: Root node title
            guide_style: Style for tree lines
        """
        if self._quiet:
            return

        root = Tree(f"[bold]{title or 'Root'}[/]", guide_style=guide_style)
        self._build_tree(root, data)
        self._console.print(root)

    def _build_tree(self, parent: Tree, data: dict[str, Any]):
        """Recursively build tree nodes."""
        for key, value in data.items():
            if isinstance(value, dict):
                branch = parent.add(f"[cyan]{key}/[/]")
                self._build_tree(branch, value)
            elif value is None:
                parent.add(f"[green]{key}[/]")
            else:
                parent.add(f"[green]{key}[/] [dim]({value})[/]")

    def code(
        self,
        content: str,
        language: str = "python",
        line_numbers: bool = True,
        title: str = "",
    ):
        """
        Print syntax-highlighted code.

        Args:
            content: Code content
            language: Programming language for highlighting
            line_numbers: Whether to show line numbers
            title: Optional title above code block
        """
        if self._quiet:
            return

        if title:
            self._console.print(f"[bold]{title}[/]")

        syntax = Syntax(
            content,
            language,
            theme="monokai",
            line_numbers=line_numbers,
            word_wrap=True,
        )
        self._console.print(syntax)

    def diff(
        self,
        old: str,
        new: str,
        old_title: str = "Before",
        new_title: str = "After",
    ):
        """
        Print a simple diff view.

        Args:
            old: Original content
            new: New content
            old_title: Title for old content
            new_title: Title for new content
        """
        if self._quiet:
            return

        self._console.print(f"[bold red]--- {old_title}[/]")
        self._console.print(f"[bold green]+++ {new_title}[/]")
        self._console.print()

        old_lines = old.splitlines()
        new_lines = new.splitlines()

        # Simple line-by-line comparison
        max_lines = max(len(old_lines), len(new_lines))
        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""

            if old_line != new_line:
                if old_line:
                    self._console.print(f"[red]- {escape(old_line)}[/]")
                if new_line:
                    self._console.print(f"[green]+ {escape(new_line)}[/]")
            else:
                self._console.print(f"  {escape(old_line)}")

    # =========================================================================
    # Panels and Boxes
    # =========================================================================

    def panel(
        self,
        content: str,
        title: str = "",
        subtitle: str = "",
        border_style: str = "cyan",
        expand: bool = False,
    ):
        """
        Print content in a bordered panel.

        Args:
            content: Panel content
            title: Optional title
            subtitle: Optional subtitle
            border_style: Border color
            expand: Whether to expand to full width
        """
        if self._quiet:
            return

        self._console.print(
            Panel(
                content,
                title=title if title else None,
                subtitle=subtitle if subtitle else None,
                border_style=border_style,
                expand=expand,
            )
        )

    def box_success(self, message: str, title: str = "Success"):
        """Print a success box."""
        self.panel(f"[green]{message}[/]", title=title, border_style="green")

    def box_error(self, message: str, title: str = "Error"):
        """Print an error box."""
        self.panel(f"[red]{message}[/]", title=title, border_style="red")

    def box_warning(self, message: str, title: str = "Warning"):
        """Print a warning box."""
        self.panel(f"[yellow]{message}[/]", title=title, border_style="yellow")

    def box_info(self, message: str, title: str = "Info"):
        """Print an info box."""
        self.panel(f"[blue]{message}[/]", title=title, border_style="blue")

    # =========================================================================
    # Progress Indicators
    # =========================================================================

    def progress(
        self,
        description: str = "Processing...",
        total: int | None = None,
        transient: bool = True,
    ) -> Progress:
        """
        Create a progress bar context manager.

        Args:
            description: Task description
            total: Total steps (None for spinner only)
            transient: Whether to remove after completion

        Usage:
            with console.progress("Processing...", total=100) as progress:
                task = progress.add_task("Working", total=100)
                for i in range(100):
                    progress.advance(task)
        """
        if total:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self._console,
                transient=transient,
            )
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self._console,
            transient=transient,
        )

    def spinner(self, description: str = "Loading..."):
        """
        Create a spinner context manager.

        Usage:
            with console.spinner("Loading..."):
                do_something()
        """
        return self._console.status(description)

    # =========================================================================
    # Files and Paths
    # =========================================================================

    def file_created(self, path: str | Path):
        """Print file created message."""
        if not self._quiet:
            self._console.print(f"[green]:heavy_plus_sign:[/] [green]Created[/] {path}")

    def file_modified(self, path: str | Path):
        """Print file modified message."""
        if not self._quiet:
            self._console.print(f"[yellow]:pencil:[/] [yellow]Modified[/] {path}")

    def file_deleted(self, path: str | Path):
        """Print file deleted message."""
        if not self._quiet:
            self._console.print(f"[red]:heavy_minus_sign:[/] [red]Deleted[/] {path}")

    def file_skipped(self, path: str | Path, reason: str = ""):
        """Print file skipped message."""
        if not self._quiet:
            suffix = f" ({reason})" if reason else ""
            self._console.print(f"[dim]:fast-forward_button:[/] [dim]Skipped[/] {path}{suffix}")

    def files_summary(
        self,
        created: list[str | Path] = None,
        modified: list[str | Path] = None,
        deleted: list[str | Path] = None,
    ):
        """Print a summary of file changes."""
        if self._quiet:
            return

        created = created or []
        modified = modified or []
        deleted = deleted or []

        total = len(created) + len(modified) + len(deleted)
        if total == 0:
            self.muted("No files changed")
            return

        self.newline()
        self.section("Files Changed")

        for path in created:
            self.file_created(path)
        for path in modified:
            self.file_modified(path)
        for path in deleted:
            self.file_deleted(path)

        self.newline()
        parts = []
        if created:
            parts.append(f"[green]{len(created)} created[/]")
        if modified:
            parts.append(f"[yellow]{len(modified)} modified[/]")
        if deleted:
            parts.append(f"[red]{len(deleted)} deleted[/]")

        self._console.print(f"[bold]Total:[/] {', '.join(parts)}")

    # =========================================================================
    # Lists and Steps
    # =========================================================================

    def list_item(self, text: str, bullet: str = "•", style: str = ""):
        """Print a list item."""
        if not self._quiet:
            style_prefix = f"[{style}]" if style else ""
            style_suffix = "[/]" if style else ""
            self._console.print(f"  {bullet} {style_prefix}{text}{style_suffix}")

    def numbered_list(self, items: list[str], start: int = 1):
        """Print a numbered list."""
        if self._quiet:
            return

        for i, item in enumerate(items, start=start):
            self._console.print(f"  [cyan]{i}.[/] {item}")

    def step(self, number: int, text: str, total: int | None = None):
        """Print a step indicator."""
        if not self._quiet:
            if total:
                self._console.print(f"[bold cyan]Step {number}/{total}:[/] {text}")
            else:
                self._console.print(f"[bold cyan]Step {number}:[/] {text}")

    def next_steps(self, steps: list[str], title: str = "Next Steps"):
        """Print next steps instructions."""
        if self._quiet:
            return

        self.newline()
        self.section(title)
        self.numbered_list(steps)

    # =========================================================================
    # Help and Documentation
    # =========================================================================

    def command_help(
        self,
        command: str,
        description: str,
        usage: str,
        options: list[dict] | None = None,
        examples: list[dict] | None = None,
    ):
        """
        Display rich help for a command.

        Args:
            command: Command name
            description: Command description
            usage: Usage string
            options: List of dicts with 'name', 'description', 'default'
            examples: List of dicts with 'command', 'description'
        """
        if self._quiet:
            return

        options = options or []
        examples = examples or []

        self.newline()
        self._console.print(f"[bold magenta]{command}[/]")
        self._console.print(f"[dim]{description}[/]")
        self.newline()

        # Usage
        self._console.print("[bold]Usage:[/]")
        self._console.print(f"  [cyan]{usage}[/]")
        self.newline()

        # Options
        if options:
            self._console.print("[bold]Options:[/]")
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Option", style="green", no_wrap=True)
            table.add_column("Description")
            table.add_column("Default", style="dim")

            for opt in options:
                default = f"[{opt.get('default', '')}]" if opt.get("default") else ""
                table.add_row(opt["name"], opt["description"], default)

            self._console.print(table)
            self.newline()

        # Examples
        if examples:
            self._console.print("[bold]Examples:[/]")
            for ex in examples:
                self._console.print(f"  [dim]# {ex['description']}[/]")
                self._console.print(f"  [cyan]{ex['command']}[/]")
                self.newline()

    def did_you_mean(self, input_cmd: str, suggestion: str):
        """Show a 'did you mean' suggestion for typos."""
        if not self._quiet:
            self._console.print(
                f"[yellow]Unknown command:[/] {input_cmd}\n"
                f"[dim]Did you mean:[/] [cyan]{suggestion}[/]?"
            )

    def command_group(self, title: str, commands: list[tuple[str, str]]):
        """
        Display a group of commands in a panel.

        Args:
            title: Group title
            commands: List of (command, description) tuples
        """
        if self._quiet:
            return

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description")

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self._console.print(Panel(table, title=f"[bold]{title}[/]", border_style="blue"))

    # =========================================================================
    # Branding
    # =========================================================================

    def banner(self):
        """Print the Django Matt banner."""
        if self._quiet:
            return

        banner_text = """
[bold magenta]     ___  _                          __  __       _   _   [/]
[bold magenta]    |   \\(_)__ _ _ _  __ _ ___      |  \\/  |__ _ | |_| |_ [/]
[bold magenta]    | |) | / _` | ' \\/ _` / _ \\     | |\\/| / _` ||  _|  _|[/]
[bold magenta]    |___// \\__,_|_||_\\__, \\___/     |_|  |_\\__,_| \\__|\\__|[/]
[bold magenta]       |__/          |___/                                [/]
"""
        self._console.print(banner_text)

    def version_info(self, version: str):
        """Print version information."""
        if not self._quiet:
            self._console.print(f"[dim]Django Matt v{version}[/]")


# Global console instance
console = Console()
