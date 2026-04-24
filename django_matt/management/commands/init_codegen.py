"""
Management command to initialize codegen configuration.

Usage:
    # Create default config file
    python manage.py init_codegen

    # Create with specific framework
    python manage.py init_codegen --framework svelte

    # Create with specific models
    python manage.py init_codegen --models users.User,posts.Post

    # Show config without creating file
    python manage.py init_codegen --dry-run

    # Force overwrite existing config
    python manage.py init_codegen --force
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Scaffold a codegen configuration file from project introspection."""

    help = "Initialize code generation configuration file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--framework",
            "-f",
            choices=["react", "svelte", "solid", "typescript"],
            default="react",
            help="Target frontend framework (default: react)",
        )
        parser.add_argument(
            "--ui-library",
            "-u",
            choices=["shadcn", "tailwind", "headless", "none"],
            default="shadcn",
            help="UI library to use (default: shadcn)",
        )
        parser.add_argument(
            "--output-dir",
            "-o",
            type=str,
            default="./frontend/src/generated",
            help="Output directory for generated files (default: ./frontend/src/generated)",
        )
        parser.add_argument(
            "--models",
            "-m",
            type=str,
            help="Comma-separated list of models (e.g., users.User,posts.Post)",
        )
        parser.add_argument(
            "--apps",
            "-a",
            type=str,
            help="Comma-separated list of Django apps to scan for models",
        )
        parser.add_argument(
            "--config-file",
            type=str,
            default="django_matt_codegen.py",
            help="Config file path (default: django_matt_codegen.py)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show config without creating file",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing config file",
        )
        parser.add_argument(
            "--toml",
            action="store_true",
            help="Add config to pyproject.toml instead of Python file",
        )

    def handle(self, *args, **options):
        framework = options["framework"]
        ui_library = options["ui_library"]
        output_dir = options["output_dir"]
        models_str = options["models"]
        apps_str = options["apps"]
        config_file = options["config_file"]
        dry_run = options["dry_run"]
        force = options["force"]
        use_toml = options["toml"]

        # Collect models
        models: list[str] = []

        if models_str:
            models.extend(m.strip() for m in models_str.split(","))

        if apps_str:
            for app_label in apps_str.split(","):
                app_label = app_label.strip()
                try:
                    app_config = apps.get_app_config(app_label)
                    for model in app_config.get_models():
                        model_path = f"{app_label}.{model.__name__}"
                        if model_path not in models:
                            models.append(model_path)
                except LookupError:
                    self.stderr.write(self.style.WARNING(f"App not found: {app_label}"))

        if use_toml:
            self._handle_toml(
                framework=framework,
                ui_library=ui_library,
                output_dir=output_dir,
                models=models,
                dry_run=dry_run,
                force=force,
            )
        else:
            self._handle_python(
                framework=framework,
                ui_library=ui_library,
                output_dir=output_dir,
                models=models,
                config_file=config_file,
                dry_run=dry_run,
                force=force,
            )

    def _handle_python(
        self,
        framework: str,
        ui_library: str,
        output_dir: str,
        models: list[str],
        config_file: str,
        dry_run: bool,
        force: bool,
    ):
        """Handle Python config file creation."""
        from django_matt.codegen.config import create_config_file

        config_path = Path(config_file)

        # Check if file exists
        if config_path.exists() and not force:
            raise CommandError(
                f"Config file already exists: {config_file}\nUse --force to overwrite."
            )

        # Generate config content
        content = create_config_file(
            output_path=None,  # Don't write yet
            framework=framework,  # type: ignore[arg-type]
            ui_library=ui_library,  # type: ignore[arg-type]
            output_dir=output_dir,
            models=models,
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Generated config (dry run):"))
            self.stdout.write("")
            self.stdout.write(content)
            return

        # Write config file
        config_path.write_text(content)
        self.stdout.write(self.style.SUCCESS(f"Created config file: {config_file}"))

        self._show_next_steps(framework, output_dir)

    def _handle_toml(
        self,
        framework: str,
        ui_library: str,
        output_dir: str,
        models: list[str],
        dry_run: bool,
        force: bool,
    ):
        """Handle pyproject.toml config addition."""
        pyproject_path = Path("pyproject.toml")

        if not pyproject_path.exists():
            raise CommandError("pyproject.toml not found in current directory")

        # Read existing content
        content = pyproject_path.read_text()

        # Check if codegen section exists
        if "[tool.django-matt.codegen]" in content and not force:
            raise CommandError(
                "Codegen config already exists in pyproject.toml\nUse --force to overwrite."
            )

        # Generate TOML section
        models_toml = ",\n    ".join(f'"{m}"' for m in models) if models else ""
        toml_section = f'''
[tool.django-matt.codegen]
framework = "{framework}"
ui_library = "{ui_library}"
output_dir = "{output_dir}"
models = [
    {models_toml}
]
use_typescript = true
camel_case = true
generate_zod = true
base_url = "/api"
include_api_client = true
ui_import_path = "@/components/ui"
hooks_import_path = "@/generated/hooks"
types_import_path = "@/generated/types"
generate_index = true
'''

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Generated TOML section (dry run):"))
            self.stdout.write("")
            self.stdout.write(toml_section)
            return

        # Remove existing section if force
        if force and "[tool.django-matt.codegen]" in content:
            # Find and remove the section
            lines = content.split("\n")
            new_lines = []
            in_section = False
            for line in lines:
                if line.strip() == "[tool.django-matt.codegen]":
                    in_section = True
                    continue
                if in_section and line.startswith("["):
                    in_section = False
                if not in_section:
                    new_lines.append(line)
            content = "\n".join(new_lines)

        # Append new section
        content = content.rstrip() + "\n" + toml_section

        # Write back
        pyproject_path.write_text(content)
        self.stdout.write(self.style.SUCCESS("Added codegen config to pyproject.toml"))

        self._show_next_steps(framework, output_dir)

    def _show_next_steps(self, framework: str, output_dir: str):
        """Show next steps after config creation."""
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Next steps:"))
        self.stdout.write("  1. Edit the config to add your models")
        self.stdout.write("  2. Run: python manage.py sync_types --config")
        self.stdout.write("  3. Use watch mode: python manage.py sync_types --config --watch")
        self.stdout.write("")
        self.stdout.write(f"Generated files will be placed in: {output_dir}")

        # Framework-specific tips
        if framework == "react":
            self.stdout.write("")
            self.stdout.write("For React with shadcn/ui:")
            self.stdout.write("  - Install: npx shadcn@latest init")
            self.stdout.write("  - Add components: npx shadcn@latest add form input button")
