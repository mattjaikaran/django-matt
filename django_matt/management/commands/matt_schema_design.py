"""
AI-powered schema design command.

Given a natural-language description, uses an LLM to generate a complete
Django app stack: models, schemas, controller, service, and tests.

Usage:
    python manage.py matt_schema_design "A blog with posts and comments"
    python manage.py matt_schema_design --description "A task manager with projects and tasks"
    python manage.py matt_schema_design --app blog --output ./myapp/ --provider anthropic "A blog with posts and comments"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from django_matt.cli import MattCommand


class Command(MattCommand):
    """AI-powered schema designer: generate Django apps from natural language."""

    help = (
        "Generate a complete Django app (models, schemas, controller, service, tests) "
        "from a natural-language description using AI"
    )

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "description",
            nargs="?",
            help="Natural-language description of the desired models",
        )
        parser.add_argument(
            "--description",
            "-d",
            dest="description_opt",
            help="Natural-language description (alternative to positional arg)",
        )
        parser.add_argument(
            "--app",
            "-a",
            dest="app_name",
            help="App name (default: inferred by AI)",
        )
        parser.add_argument(
            "--output",
            "-o",
            dest="output_dir",
            default=".",
            help="Output directory for generated files (default: current directory)",
        )
        parser.add_argument(
            "--provider",
            "-p",
            default="openai",
            help="LLM provider (openai, anthropic, gemini, groq, deepseek, etc.)",
        )
        parser.add_argument(
            "--model",
            "-m",
            default=None,
            help="Model override for the LLM provider",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview generated code without writing files",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output result as JSON instead of writing files",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show detailed output including warnings",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        description = options.get("description") or options.get("description_opt")
        if not description:
            self._show_usage()
            return

        app_name = options.get("app_name")
        output_dir = Path(options["output_dir"])
        provider = options["provider"]
        model_name = options.get("model")
        dry_run = options.get("dry_run", False)
        json_output = options.get("json", False)
        verbose = options.get("verbose", False)

        self.console.header("AI Schema Designer")
        self.console.print(f"[bold]Description:[/] {description}")
        if app_name:
            self.console.print(f"[bold]App name:[/] {app_name}")
        self.console.print(f"[bold]Provider:[/] {provider}")
        if model_name:
            self.console.print(f"[bold]Model:[/] {model_name}")
        self.console.newline()

        # Run the AI designer
        try:
            from django_matt.schema_designer.ai_designer import SchemaDesignerAI

            self.console.status_start("Generating schema with AI...")

            designer = SchemaDesignerAI(
                provider_name=provider,
                model=model_name,
            )
            result = designer.design(description, app_name=app_name)

            self.console.status_stop()

        except Exception as e:
            self.console.status_stop()
            self.error(f"AI schema design failed: {e}", raise_error=True)
            return

        # Show warnings
        if result.warnings and verbose:
            self.console.section("Warnings")
            for w in result.warnings:
                self.console.warning(w)

        # JSON output mode
        if json_output:
            import orjson

            payload = {
                "app_name": result.app_name,
                "entities": result.entities,
                "files": {
                    k: v[:200] + "..." if len(v) > 200 else v
                    for k, v in result.files.items()
                },
                "warnings": result.warnings,
            }
            self.console.print(
                orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode()
            )
            if not dry_run:
                self._write_files(result, output_dir)
            return

        # Display results
        self.console.section("Generated App")
        self.console.print(f"  App name: [cyan]{result.app_name}[/cyan]")
        self.console.print(f"  Entities: [green]{', '.join(result.entities)}[/green]")
        self.console.newline()

        self.console.section("Files Generated")
        for filepath, content in sorted(result.files.items()):
            line_count = content.count("\n") + 1
            size_kb = len(content) / 1024
            self.console.print(
                f"  [cyan]{filepath}[/cyan] — {line_count} lines ({size_kb:.1f} KB)"
            )

        # Preview first few lines of files
        if verbose:
            for filepath, content in sorted(result.files.items()):
                self.console.section(f"Preview: {filepath}")
                preview_lines = content.split("\n")[:15]
                self.console.print("\n".join(preview_lines))
                if content.count("\n") > 15:
                    self.console.muted(f"  ... ({content.count('\n') - 15} more lines)")

        # Write files
        if not dry_run:
            if result.files:
                self.console.newline()
                self.console.status_start("Writing files...")
                self._write_files(result, output_dir)
                self.console.status_stop()
                self.console.success(
                    f"Generated {len(result.files)} files in {output_dir.resolve()}"
                )
            else:
                self.console.warning("No files were generated by the AI.")
        else:
            self.console.newline()
            self.console.muted("[dry-run] No files written to disk.")

    # ── Helpers ────────────────────────────────────────────────────────────

    def _show_usage(self) -> None:
        """Show usage information."""
        self.console.header("AI Schema Designer")
        self.console.print("[bold]Usage:[/] python manage.py matt_schema_design <description>")
        self.console.newline()
        self.console.print("[bold]Examples:[/]")
        self.console.print(
            '  python manage.py matt_schema_design "A blog with posts and comments"'
        )
        self.console.print(
            '  python manage.py matt_schema_design --app ecommerce --provider anthropic \\'
        )
        self.console.print(
            '    "An online store with products, carts, and orders"'
        )
        self.console.newline()
        self.console.print("[bold]Options:[/]")
        options = [
            {"Option": "--app, -a", "Description": "App name hint"},
            {"Option": "--output, -o", "Description": "Output directory (default: .)"},
            {"Option": "--provider, -p", "Description": "LLM provider (default: openai)"},
            {"Option": "--model, -m", "Description": "Model override"},
            {"Option": "--dry-run", "Description": "Preview without writing"},
            {"Option": "--json", "Description": "Output as JSON"},
            {"Option": "--verbose, -v", "Description": "Show detailed output"},
        ]
        self.console.table(options)

    def _write_files(self, result, output_dir: Path) -> None:
        """Write generated files to disk."""
        from django_matt.schema_designer.ai_designer import _write_files

        _write_files(result, output_dir)
