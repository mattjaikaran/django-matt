"""
Management command for generating AI assistant context files.

Generates CLAUDE.md, .cursorrules, .copilot-instructions, and other files
that help AI assistants understand your Django project.

Usage:
    # Generate all context files (claude, cursor, copilot)
    python manage.py generate_ai_context

    # Generate all formats including JSON
    python manage.py generate_ai_context --format all

    # Generate specific format
    python manage.py generate_ai_context --format claude
    python manage.py generate_ai_context --format cursor
    python manage.py generate_ai_context --format copilot

    # Generate to specific directory
    python manage.py generate_ai_context --output ./docs

    # Include code examples from codebase
    python manage.py generate_ai_context --include-examples

    # Output machine-readable JSON
    python manage.py generate_ai_context --output-json

    # Watch mode - auto-update on file changes
    python manage.py generate_ai_context --watch

    # Include third-party apps
    python manage.py generate_ai_context --include-third-party

    # Dry run (show what would be generated)
    python manage.py generate_ai_context --dry-run

    # Install pre-commit hook
    python manage.py generate_ai_context --install-hook
"""

import signal
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate AI assistant context files (CLAUDE.md, .cursorrules, .copilot-instructions)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=".",
            help="Output directory for generated files (default: current directory)",
        )
        parser.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["all", "claude", "cursor", "copilot", "json"],
            default="default",
            help=(
                "Format to generate: all (all formats), claude (CLAUDE.md), "
                "cursor (.cursorrules), copilot (.copilot-instructions), json (introspection.json). "
                "Default generates claude, cursor, and copilot."
            ),
        )
        parser.add_argument(
            "--include-third-party",
            action="store_true",
            help="Include third-party apps in analysis",
        )
        parser.add_argument(
            "--exclude-apps",
            type=str,
            nargs="*",
            default=[],
            help="Apps to exclude from analysis",
        )
        parser.add_argument(
            "--include-examples",
            action="store_true",
            help="Include code examples from the codebase",
        )
        parser.add_argument(
            "--output-json",
            action="store_true",
            help="Output machine-readable JSON introspection data",
        )
        parser.add_argument(
            "--watch",
            "-w",
            action="store_true",
            help="Watch for file changes and auto-regenerate",
        )
        parser.add_argument(
            "--debounce",
            type=float,
            default=1.0,
            help="Debounce delay in seconds for watch mode (default: 1.0)",
        )
        parser.add_argument(
            "--install-hook",
            action="store_true",
            help="Install pre-commit hook for auto-regeneration",
        )
        parser.add_argument(
            "--show-hook",
            action="store_true",
            help="Show pre-commit hook script without installing",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be generated without writing files",
        )
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Minimal output",
        )
        parser.add_argument(
            "--depth",
            "-d",
            type=str,
            choices=["minimal", "standard", "full"],
            default="standard",
            help=(
                "Content depth: minimal (routes only), standard (routes + types), "
                "full (routes + types + relationships + conventions + settings). "
                "Default: standard."
            ),
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output"])
        format_type = options["format"]
        include_third_party = options["include_third_party"]
        exclude_apps = options["exclude_apps"]
        include_examples = options["include_examples"]
        output_json = options["output_json"]
        watch_mode = options["watch"]
        debounce_delay = options["debounce"]
        install_hook = options["install_hook"]
        show_hook = options["show_hook"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]
        depth = options.get("depth", "standard")

        # Handle hook commands
        if show_hook:
            self._show_hook()
            return

        if install_hook:
            self._install_hook(output_dir, quiet)
            return

        # Handle watch mode
        if watch_mode:
            self._run_watch_mode(
                output_dir=output_dir,
                formats=self._get_formats(format_type),
                debounce_delay=debounce_delay,
                include_third_party=include_third_party,
                exclude_apps=exclude_apps,
                include_examples=include_examples,
                quiet=quiet,
            )
            return

        # Handle JSON output
        if output_json:
            self._output_json(
                include_third_party=include_third_party,
                exclude_apps=exclude_apps,
                include_examples=include_examples,
            )
            return

        # Normal generation
        self._generate(
            output_dir=output_dir,
            format_type=format_type,
            include_third_party=include_third_party,
            exclude_apps=exclude_apps,
            include_examples=include_examples,
            dry_run=dry_run,
            quiet=quiet,
            depth=depth,
        )

    def _get_formats(self, format_type: str) -> list[str]:
        """Get list of formats to generate."""
        if format_type == "all":
            return ["claude", "cursor", "copilot", "json"]
        if format_type == "default":
            return ["claude", "cursor", "copilot"]
        return [format_type]

    def _generate(
        self,
        output_dir: Path,
        format_type: str,
        include_third_party: bool,
        exclude_apps: list[str],
        include_examples: bool,
        dry_run: bool,
        quiet: bool,
        depth: str = "standard",
    ):
        """Generate context files.

        Args:
            depth: Content depth — "minimal" (routes only), "standard" (routes + types),
                   "full" (routes + types + relationships + conventions + settings).
        """
        from django_matt.ai.context import (
            ClaudeMdGenerator,
            CopilotInstructionsGenerator,
            CursorRulesGenerator,
            EnhancedIntrospector,
            JsonIntrospectionGenerator,
        )

        # Ensure output directory exists
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Map depth to content controls
        # minimal: routes only (no examples, few schemas/models)
        # standard: routes + types (some examples, standard counts)
        # full: everything (all examples, high counts)
        depth_config = {
            "minimal": {
                "include_examples": False,
                "max_endpoints": 100,
                "max_models": 0,
                "max_schemas": 0,
            },
            "standard": {
                "include_examples": include_examples,
                "max_endpoints": 50,
                "max_models": 30,
                "max_schemas": 30,
            },
            "full": {
                "include_examples": True,
                "max_endpoints": 200,
                "max_models": 100,
                "max_schemas": 100,
            },
        }
        cfg = depth_config.get(depth, depth_config["standard"])

        # Create introspector — use depth-driven include_examples
        introspector = EnhancedIntrospector(
            include_third_party=include_third_party,
            exclude_apps=exclude_apps,
            include_examples=cfg["include_examples"],
        )

        if not quiet:
            self.stdout.write("Analyzing Django project...")

        # Introspect project
        try:
            project_info = introspector.introspect()
        except Exception as e:
            raise CommandError(f"Failed to introspect project: {e}")

        if not quiet:
            self.stdout.write(
                f"  Found {len(project_info.endpoints)} endpoints, "
                f"{len(project_info.models)} models, "
                f"{len(project_info.schemas)} schemas"
            )

        formats = self._get_formats(format_type)
        generated_files = []

        # Generate CLAUDE.md
        if "claude" in formats:
            generator = ClaudeMdGenerator(
                introspector=introspector,
                include_examples=cfg["include_examples"],
                max_endpoints=cfg["max_endpoints"],
                max_models=cfg["max_models"],
                max_schemas=cfg["max_schemas"],
            )
            content = generator.generate(project_info)

            if dry_run:
                self.stdout.write("\n--- CLAUDE.md ---")
                self.stdout.write(content[:2000] + "..." if len(content) > 2000 else content)
            else:
                file_path = output_dir / "CLAUDE.md"
                file_path.write_text(content)
                generated_files.append(file_path)

                if not quiet:
                    self.stdout.write(self.style.SUCCESS(f"  Generated: {file_path}"))

        # Generate .cursorrules
        if "cursor" in formats:
            generator = CursorRulesGenerator(introspector=introspector)
            content = generator.generate(project_info)

            if dry_run:
                self.stdout.write("\n--- .cursorrules ---")
                self.stdout.write(content[:1500] + "..." if len(content) > 1500 else content)
            else:
                file_path = output_dir / ".cursorrules"
                file_path.write_text(content)
                generated_files.append(file_path)

                if not quiet:
                    self.stdout.write(self.style.SUCCESS(f"  Generated: {file_path}"))

        # Generate .copilot-instructions
        if "copilot" in formats:
            generator = CopilotInstructionsGenerator(introspector=introspector)
            content = generator.generate(project_info)

            if dry_run:
                self.stdout.write("\n--- .copilot-instructions ---")
                self.stdout.write(content[:1500] + "..." if len(content) > 1500 else content)
            else:
                file_path = output_dir / ".copilot-instructions"
                file_path.write_text(content)
                generated_files.append(file_path)

                if not quiet:
                    self.stdout.write(self.style.SUCCESS(f"  Generated: {file_path}"))

        # Generate introspection.json
        if "json" in formats:
            generator = JsonIntrospectionGenerator(introspector=introspector)
            content = generator.generate_json(project_info)

            if dry_run:
                self.stdout.write("\n--- introspection.json ---")
                self.stdout.write(content[:2000] + "..." if len(content) > 2000 else content)
            else:
                file_path = output_dir / "introspection.json"
                file_path.write_text(content)
                generated_files.append(file_path)

                if not quiet:
                    self.stdout.write(self.style.SUCCESS(f"  Generated: {file_path}"))

        # Summary
        if not dry_run and not quiet:
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully generated {len(generated_files)} AI context file(s)"
                )
            )

            self.stdout.write("\nNext steps:")
            self.stdout.write("  1. Review the generated files")
            self.stdout.write("  2. Add project-specific instructions")
            self.stdout.write("  3. Commit to version control")
            self.stdout.write("  4. Run with --watch for auto-updates during development")

    def _run_watch_mode(
        self,
        output_dir: Path,
        formats: list[str],
        debounce_delay: float,
        include_third_party: bool,
        exclude_apps: list[str],
        include_examples: bool,
        quiet: bool,
    ):
        """Run in watch mode."""
        from django_matt.ai.context import ContextWatcher

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create watcher
        watcher = ContextWatcher(
            project_root=output_dir,
            formats=formats,
            debounce_delay=debounce_delay,
            quiet=quiet,
        )

        # Handle Ctrl+C
        def signal_handler(sig, frame):
            watcher.stop()
            self.stdout.write("\nWatch mode stopped.")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Generate initial files
        if not quiet:
            self.stdout.write("Generating initial context files...")

        self._generate(
            output_dir=output_dir,
            format_type="all" if "json" in formats else "default",
            include_third_party=include_third_party,
            exclude_apps=exclude_apps,
            include_examples=include_examples,
            dry_run=False,
            quiet=quiet,
        )

        # Start watching
        if not quiet:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Starting watch mode..."))

        watcher.start()

        # Keep running
        try:
            while True:
                signal.pause()
        except KeyboardInterrupt:
            watcher.stop()

    def _output_json(
        self,
        include_third_party: bool,
        exclude_apps: list[str],
        include_examples: bool,
    ):
        """Output JSON introspection data to stdout."""
        from django_matt.ai.context import EnhancedIntrospector, JsonIntrospectionGenerator

        introspector = EnhancedIntrospector(
            include_third_party=include_third_party,
            exclude_apps=exclude_apps,
            include_examples=include_examples,
        )

        generator = JsonIntrospectionGenerator(introspector=introspector)
        json_output = generator.generate_json()

        self.stdout.write(json_output)

    def _show_hook(self):
        """Show pre-commit hook script."""
        from django_matt.ai.context.watcher import (
            generate_precommit_config,
            generate_precommit_hook,
        )

        self.stdout.write("# Pre-commit hook script:")
        self.stdout.write("# Save this to .git/hooks/pre-commit and make it executable")
        self.stdout.write("")
        self.stdout.write(generate_precommit_hook())

        self.stdout.write("")
        self.stdout.write("# Or add this to .pre-commit-config.yaml:")
        self.stdout.write("")
        self.stdout.write(generate_precommit_config())

    def _install_hook(self, output_dir: Path, quiet: bool):
        """Install pre-commit hook."""
        from django_matt.ai.context.watcher import install_precommit_hook

        try:
            hook_path = install_precommit_hook(output_dir)
            if not quiet:
                self.stdout.write(self.style.SUCCESS(f"Pre-commit hook installed: {hook_path}"))
                self.stdout.write("AI context files will be regenerated on each commit.")
        except FileNotFoundError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Failed to install hook: {e}")
