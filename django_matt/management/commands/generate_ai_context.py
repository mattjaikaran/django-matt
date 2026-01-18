"""
Management command for generating AI assistant context files.

Generates CLAUDE.md, .cursorrules, and other files that help
AI assistants understand your Django project.

Usage:
    # Generate all context files
    python manage.py generate_ai_context

    # Generate to specific directory
    python manage.py generate_ai_context --output ./docs

    # Generate only CLAUDE.md
    python manage.py generate_ai_context --format claude

    # Generate only .cursorrules
    python manage.py generate_ai_context --format cursor

    # Include third-party apps
    python manage.py generate_ai_context --include-third-party

    # Dry run (show what would be generated)
    python manage.py generate_ai_context --dry-run
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate AI assistant context files (CLAUDE.md, .cursorrules)"

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
            choices=["all", "claude", "cursor"],
            default="all",
            help="Format to generate: all, claude (CLAUDE.md), cursor (.cursorrules)",
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

    def handle(self, *args, **options):
        from django_matt.ai.ide import (
            ClaudeMdGenerator,
            CursorRulesGenerator,
            ProjectIntrospector,
        )

        output_dir = Path(options["output"])
        format_type = options["format"]
        include_third_party = options["include_third_party"]
        exclude_apps = options["exclude_apps"]
        dry_run = options["dry_run"]
        quiet = options["quiet"]

        # Ensure output directory exists
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Create introspector
        introspector = ProjectIntrospector(
            include_third_party=include_third_party,
            exclude_apps=exclude_apps,
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
                f"  Found {len(project_info.apps)} apps, "
                f"{sum(len(a.models) for a in project_info.apps)} models"
            )

        generated_files = []

        # Generate CLAUDE.md
        if format_type in ("all", "claude"):
            generator = ClaudeMdGenerator(introspector=introspector)
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
        if format_type in ("all", "cursor"):
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
