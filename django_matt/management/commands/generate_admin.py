"""
Management command to generate admin.py from Django models.

Usage:
    # Generate admin for all models in an app
    python manage.py generate_admin myapp

    # Generate admin for specific models
    python manage.py generate_admin myapp.User myapp.Post

    # Preview without writing
    python manage.py generate_admin myapp --dry-run

    # Include soft delete support
    python manage.py generate_admin myapp --soft-delete

    # Output to specific file
    python manage.py generate_admin myapp --output myapp/admin.py
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models


class Command(BaseCommand):
    help = "Generate admin.py from Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "models",
            nargs="+",
            type=str,
            help="App labels or model paths (e.g., 'myapp' or 'myapp.User')",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (default: <app>/admin.py)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview generated code without writing",
        )
        parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Overwrite existing admin.py",
        )
        parser.add_argument(
            "--append",
            "-a",
            action="store_true",
            help="Append to existing admin.py instead of overwriting",
        )
        parser.add_argument(
            "--audit",
            action="store_true",
            default=True,
            help="Include audit mixin (default: True)",
        )
        parser.add_argument(
            "--no-audit",
            action="store_true",
            help="Exclude audit mixin",
        )
        parser.add_argument(
            "--soft-delete",
            action="store_true",
            help="Include soft delete mixin",
        )
        parser.add_argument(
            "--export",
            action="store_true",
            default=True,
            help="Include export actions (default: True)",
        )
        parser.add_argument(
            "--no-export",
            action="store_true",
            help="Exclude export actions",
        )
        parser.add_argument(
            "--multi-tenant",
            action="store_true",
            help="Include multi-tenant mixin",
        )
        parser.add_argument(
            "--tenant-field",
            type=str,
            default="organization",
            help="Field name for tenant (default: organization)",
        )

    def handle(self, *args, **options):
        model_args = options["models"]
        output_path = options["output"]
        dry_run = options["dry_run"]
        force = options["force"]
        append = options["append"]
        include_audit = options["audit"] and not options["no_audit"]
        include_soft_delete = options["soft_delete"]
        include_export = options["export"] and not options["no_export"]
        include_multi_tenant = options["multi_tenant"]
        tenant_field = options["tenant_field"]

        # Collect models
        collected_models: list[type[models.Model]] = []
        app_label = None

        for arg in model_args:
            if "." in arg:
                # Specific model path
                try:
                    app_label_part, model_name = arg.rsplit(".", 1)
                    model = apps.get_model(app_label_part, model_name)
                    collected_models.append(model)
                    if app_label is None:
                        app_label = app_label_part
                except LookupError as e:
                    raise CommandError(f"Model not found: {arg}") from e
            else:
                # App label - get all models
                try:
                    app_config = apps.get_app_config(arg)
                    app_label = arg
                    for model in app_config.get_models():
                        if model not in collected_models:
                            collected_models.append(model)
                except LookupError as e:
                    raise CommandError(f"App not found: {arg}") from e

        if not collected_models:
            raise CommandError("No models found to generate admin for.")

        self.stdout.write(f"Found {len(collected_models)} model(s)")

        # Generate code
        from django_matt.admin.generator import AdminGenerator

        generator = AdminGenerator(
            include_audit=include_audit,
            include_soft_delete=include_soft_delete,
            include_export=include_export,
            include_multi_tenant=include_multi_tenant,
            tenant_field=tenant_field,
        )

        code = self._generate_code(
            collected_models,
            generator,
            include_audit,
            include_soft_delete,
            include_export,
            include_multi_tenant,
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Generated admin.py (dry run):"))
            self.stdout.write("")
            self.stdout.write(code)
            return

        # Determine output path
        if output_path:
            output_file = Path(output_path)
        elif app_label:
            # Try to find app directory
            try:
                app_config = apps.get_app_config(app_label)
                app_path = Path(app_config.path)
                output_file = app_path / "admin.py"
            except Exception:
                output_file = Path(f"{app_label}/admin.py")
        else:
            raise CommandError("Could not determine output path. Use --output.")

        # Check if file exists
        if output_file.exists() and not force and not append:
            raise CommandError(
                f"File already exists: {output_file}\n"
                "Use --force to overwrite or --append to add to existing file."
            )

        # Write file
        if append and output_file.exists():
            existing = output_file.read_text()
            # Remove duplicate imports
            code_without_imports = self._strip_imports(code)
            content = existing + "\n\n" + code_without_imports
        else:
            content = code

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content)

        self.stdout.write(self.style.SUCCESS(f"Generated admin.py: {output_file}"))

        # Show next steps
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Review the generated admin.py")
        self.stdout.write("  2. Customize list_display, search_fields, etc. as needed")
        self.stdout.write("  3. Add any custom actions or inlines")

    def _generate_code(
        self,
        models: list[type[models.Model]],
        generator,
        include_audit: bool,
        include_soft_delete: bool,
        include_export: bool,
        include_multi_tenant: bool,
    ) -> str:
        """Generate the admin.py code."""
        lines = [
            '"""',
            "Admin configuration.",
            "",
            "Auto-generated by: python manage.py generate_admin",
            '"""',
            "",
            "from django.contrib import admin",
            "",
            "from django_matt.admin import (",
            "    MattModelAdmin,",
        ]

        if include_audit:
            lines.append("    AuditAdminMixin,")
        if include_soft_delete:
            lines.append("    SoftDeleteAdminMixin,")
        if include_export:
            lines.append("    ExportAdminMixin,")
        if include_multi_tenant:
            lines.append("    MultiTenantAdminMixin,")

        lines.append(")")
        lines.append("")

        # Group models by module for imports
        model_imports: dict[str, list[str]] = {}
        for model in models:
            module = model.__module__
            name = model.__name__
            if module not in model_imports:
                model_imports[module] = []
            model_imports[module].append(name)

        for module, names in sorted(model_imports.items()):
            names_str = ", ".join(sorted(names))
            lines.append(f"from {module} import {names_str}")

        lines.append("")
        lines.append("")

        # Generate admin classes
        for model in models:
            opts = model._meta
            model_name = model.__name__

            # Determine mixins
            mixins = []
            if include_audit:
                mixins.append("AuditAdminMixin")
            if include_soft_delete and self._has_field(opts, "deleted_at"):
                mixins.append("SoftDeleteAdminMixin")
            if include_export:
                mixins.append("ExportAdminMixin")
            if include_multi_tenant and self._has_field(opts, generator.tenant_field):
                mixins.append("MultiTenantAdminMixin")

            mixins_str = ", ".join(mixins + ["MattModelAdmin"])

            lines.append(f"@admin.register({model_name})")
            lines.append(f"class {model_name}Admin({mixins_str}):")
            lines.append(f'    """Admin for {model_name} model."""')

            # list_display
            list_display = generator._generate_list_display(opts)
            lines.append(f"    list_display = {list_display!r}")

            # search_fields
            search_fields = generator._generate_search_fields(opts)
            if search_fields:
                lines.append(f"    search_fields = {search_fields!r}")

            # list_filter
            list_filter = generator._generate_list_filter(opts)
            if list_filter:
                lines.append(f"    list_filter = {list_filter!r}")

            # readonly_fields
            readonly = generator._generate_readonly_fields(opts)
            if readonly:
                lines.append(f"    readonly_fields = {readonly!r}")

            # date_hierarchy
            date_hierarchy = generator._generate_date_hierarchy(opts)
            if date_hierarchy:
                lines.append(f'    date_hierarchy = "{date_hierarchy}"')

            # ordering
            ordering = generator._generate_ordering(opts)
            if ordering:
                lines.append(f"    ordering = {ordering!r}")

            lines.append("")
            lines.append("")

        return "\n".join(lines)

    def _has_field(self, opts, field_name: str) -> bool:
        """Check if model has a field."""
        try:
            opts.get_field(field_name)
            return True
        except Exception:
            return False

    def _strip_imports(self, code: str) -> str:
        """Remove import statements from code for appending."""
        lines = code.split("\n")
        result = []
        in_imports = True

        for line in lines:
            if in_imports:
                if line.startswith("from ") or line.startswith("import "):
                    continue
                if line.startswith('"""') or line.startswith("#"):
                    continue
                if line.strip() == "" or line.strip() == ")":
                    continue
                in_imports = False

            result.append(line)

        return "\n".join(result)
