"""Management command for smart migration squashing.

Provides improved squashing over Django's built-in squashmigrations with:
- Preview mode to see what will happen
- Warnings for RunPython/RunSQL that can't be optimized
- Automatic version-based squashing at release boundaries
- Bulk squash across all apps

Usage:
    # Preview a squash
    python manage.py matt_squash myapp 0001 0042 --preview

    # Execute the squash
    python manage.py matt_squash myapp 0001 0042

    # Squash all migrations up to a tag/version
    python manage.py matt_squash --all --to-tag v1.0.0

    # Show squash opportunities
    python manage.py matt_squash --analyze
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Smart migration squashing with preview, safety checks, and bulk support."""

    help = "Smart migration squashing with preview and safety checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App to squash migrations for.",
        )
        parser.add_argument(
            "start_migration",
            nargs="?",
            help="Starting migration (e.g., 0001).",
        )
        parser.add_argument(
            "end_migration",
            nargs="?",
            help="Ending migration (e.g., 0042).",
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Show what would be squashed without doing it.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Squash all apps.",
        )
        parser.add_argument(
            "--to-tag",
            type=str,
            help="Squash up to migrations applied at a git tag.",
        )
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Analyze and suggest squash opportunities.",
        )
        parser.add_argument(
            "--min-migrations",
            type=int,
            default=10,
            help="Minimum migrations to suggest squashing (default: 10).",
        )

    def handle(self, **options):
        if options.get("analyze"):
            self._handle_analyze(options)
        elif options.get("all"):
            self._handle_all(options)
        elif options.get("app_label"):
            self._handle_single(options)
        else:
            self.stderr.write(
                "Specify an app and migration range, or use --analyze or --all.\n"
                "Run 'python manage.py matt_squash --help' for details."
            )
            sys.exit(1)

    def _handle_analyze(self, options):
        """Analyze migrations and suggest squash opportunities."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        min_count = options.get("min_migrations", 10)

        # Group migrations by app
        apps: dict[str, list[str]] = {}
        for app_label, migration_name in loader.disk_migrations:
            apps.setdefault(app_label, []).append(migration_name)

        self.stdout.write("\nSquash Analysis")
        self.stdout.write("=" * 50)

        opportunities = []
        for app_label, migrations in sorted(apps.items()):
            applied_count = sum(
                1 for m in migrations if (app_label, m) in applied
            )
            if applied_count >= min_count:
                opportunities.append((app_label, migrations, applied_count))

        if not opportunities:
            self.stdout.write(
                f"No apps with {min_count}+ applied migrations found.\n"
                f"Adjust with --min-migrations if needed."
            )
            return

        for app_label, migrations, applied_count in opportunities:
            sorted_migs = sorted(migrations)
            first = sorted_migs[0]
            # Find last applied migration
            last_applied = None
            for m in sorted_migs:
                if (app_label, m) in applied:
                    last_applied = m

            self.stdout.write(
                f"\n{self.style.SUCCESS(app_label)}: {applied_count} applied migrations"
            )
            self.stdout.write(f"  Range: {first} → {last_applied}")
            self.stdout.write(
                f"  Suggested: python manage.py matt_squash {app_label} {first} {last_applied}"
            )

        self.stdout.write(
            f"\n{len(opportunities)} app(s) could benefit from squashing."
        )

    def _handle_single(self, options):
        """Squash a single app's migrations."""
        from django_matt.migration_tools.squash import SmartSquasher

        app_label = options["app_label"]
        start = options.get("start_migration")
        end = options.get("end_migration")

        if not start or not end:
            self.stderr.write("Both start_migration and end_migration are required.")
            sys.exit(1)

        squasher = SmartSquasher()

        # Always preview first
        preview = squasher.preview(app_label, start, end)

        self.stdout.write(f"\nSquash Preview: {app_label}")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Migrations to squash: {len(preview.migrations_to_squash)}")
        self.stdout.write(f"  {', '.join(preview.migrations_to_squash[:5])}")
        if len(preview.migrations_to_squash) > 5:
            self.stdout.write(f"  ... and {len(preview.migrations_to_squash) - 5} more")
        self.stdout.write(f"\nOperations: {preview.total_operations} → {preview.optimized_operations}")

        reduction = preview.total_operations - preview.optimized_operations
        if reduction > 0:
            pct = (reduction / preview.total_operations) * 100
            self.stdout.write(
                self.style.SUCCESS(f"Reduction: {reduction} operations ({pct:.1f}%)")
            )

        if preview.warnings:
            self.stdout.write(self.style.WARNING("\nWarnings:"))
            for warning in preview.warnings:
                self.stdout.write(f"  ⚠ {warning}")

        if options.get("preview"):
            return

        # Confirm and execute
        confirm = input("\nProceed with squash? [y/N] ")
        if confirm.lower() != "y":
            self.stdout.write("Cancelled.")
            return

        self.stdout.write("\nSquashing...")
        result = squasher.squash(app_label, start, end)

        if result.success:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSquash complete! Created: {result.new_migration_name}"
                )
            )
            self.stdout.write(
                "\nNext steps:\n"
                "1. Review the generated migration file\n"
                "2. Test with: python manage.py migrate --check\n"
                "3. After deploying, delete the old migration files\n"
                "4. Remove the replaces list from the squashed migration"
            )
        else:
            self.stderr.write(self.style.ERROR(f"\nSquash failed: {result.error}"))
            sys.exit(1)

    def _handle_all(self, options):
        """Squash all apps with significant migration history."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        from django_matt.migration_tools.squash import SmartSquasher

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        min_count = options.get("min_migrations", 10)

        # Find apps to squash
        apps: dict[str, list[str]] = {}
        for app_label, migration_name in loader.disk_migrations:
            if (app_label, migration_name) in applied:
                apps.setdefault(app_label, []).append(migration_name)

        candidates = [
            (app, sorted(migs))
            for app, migs in apps.items()
            if len(migs) >= min_count
        ]

        if not candidates:
            self.stdout.write(
                f"No apps with {min_count}+ applied migrations to squash."
            )
            return

        self.stdout.write(f"\nWill squash {len(candidates)} apps:")
        for app, migs in candidates:
            self.stdout.write(f"  {app}: {migs[0]} → {migs[-1]} ({len(migs)} migrations)")

        if options.get("preview"):
            return

        confirm = input("\nProceed with all squashes? [y/N] ")
        if confirm.lower() != "y":
            self.stdout.write("Cancelled.")
            return

        squasher = SmartSquasher()
        successes = 0
        failures = 0

        for app, migs in candidates:
            self.stdout.write(f"\nSquashing {app}...")
            result = squasher.squash(app, migs[0], migs[-1])

            if result.success:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created {result.new_migration_name}")
                )
                successes += 1
            else:
                self.stderr.write(self.style.ERROR(f"  ✗ Failed: {result.error}"))
                failures += 1

        self.stdout.write(f"\n\nSummary: {successes} succeeded, {failures} failed")

        if failures > 0:
            sys.exit(1)
