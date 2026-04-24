"""Management command for migration baseline management.

Baselines allow developers to skip running hundreds of migrations by loading
a SQL schema dump instead. This dramatically reduces setup time for large projects.

Usage:
    # Create a baseline from current state
    python manage.py matt_baseline create v1.0.0 --notes "Release 1.0 schema"

    # Load a baseline on a fresh database
    python manage.py matt_baseline load v1.0.0

    # List available baselines
    python manage.py matt_baseline list

    # Verify baseline integrity
    python manage.py matt_baseline verify v1.0.0

    # Delete a baseline
    python manage.py matt_baseline delete v1.0.0
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create, load, and manage SQL migration baselines for fast database setup."""

    help = "Manage migration baselines for fast database setup."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", help="Action to perform")

        # Create
        create_parser = subparsers.add_parser(
            "create", help="Create a baseline from current database state"
        )
        create_parser.add_argument(
            "version",
            nargs="?",
            help="Version identifier (e.g., v1.0.0, 2024-01). Auto-generated if not provided.",
        )
        create_parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Optional description for this baseline.",
        )
        create_parser.add_argument(
            "--no-compress",
            action="store_true",
            help="Don't gzip the schema dump.",
        )

        # Load
        load_parser = subparsers.add_parser(
            "load", help="Load a baseline into the database"
        )
        load_parser.add_argument(
            "version", help="Version of the baseline to load"
        )
        load_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without loading.",
        )

        # List
        subparsers.add_parser("list", help="List available baselines")

        # Verify
        verify_parser = subparsers.add_parser(
            "verify", help="Verify a baseline's integrity"
        )
        verify_parser.add_argument("version", help="Version to verify")

        # Delete
        delete_parser = subparsers.add_parser("delete", help="Delete a baseline")
        delete_parser.add_argument("version", help="Version to delete")
        delete_parser.add_argument(
            "--force",
            action="store_true",
            help="Delete without confirmation.",
        )

        # Info
        info_parser = subparsers.add_parser(
            "info", help="Show detailed info about a baseline"
        )
        info_parser.add_argument("version", help="Version to inspect")

    def handle(self, **options):
        action = options.get("action")

        if action == "create":
            self._handle_create(options)
        elif action == "load":
            self._handle_load(options)
        elif action == "list":
            self._handle_list()
        elif action == "verify":
            self._handle_verify(options)
        elif action == "delete":
            self._handle_delete(options)
        elif action == "info":
            self._handle_info(options)
        else:
            self.stderr.write(
                "Specify an action: create, load, list, verify, delete, info\n"
                "Run 'python manage.py matt_baseline --help' for details."
            )
            sys.exit(1)

    def _handle_create(self, options):
        from django_matt.migration_tools.baseline import (
            MigrationBaseline,
            suggest_baseline_version,
        )

        baseline = MigrationBaseline()

        version = options.get("version")
        if not version:
            version = suggest_baseline_version()
            self.stdout.write(f"Using auto-generated version: {version}")

        self.stdout.write(f"Creating baseline '{version}'...")

        result = baseline.create(
            version=version,
            notes=options.get("notes", ""),
            compress=not options.get("no_compress", False),
        )

        if result.success:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nBaseline '{version}' created successfully!\n"
                    f"  Schema dump: {result.dump_path}\n"
                    f"  Manifest: {result.manifest_path}\n"
                    f"  Schema hash: {result.schema_hash}\n"
                    f"  Migrations captured: {result.migrations_captured}"
                )
            )
            self.stdout.write(
                "\nTo use this baseline on a fresh database:\n"
                f"  python manage.py matt_baseline load {version}\n"
                "  python manage.py migrate"
            )
        else:
            self.stderr.write(self.style.ERROR(f"Failed to create baseline: {result.error}"))
            sys.exit(1)

    def _handle_load(self, options):
        from django_matt.migration_tools.baseline import MigrationBaseline

        baseline = MigrationBaseline()
        version = options["version"]

        if options.get("dry_run"):
            baselines = baseline.list()
            target = next((b for b in baselines if b.version == version), None)
            if target:
                total_migs = sum(len(v) for v in target.applied_migrations.values())
                self.stdout.write(
                    f"Would load baseline '{version}':\n"
                    f"  Created: {target.created_at}\n"
                    f"  DB vendor: {target.db_vendor}\n"
                    f"  Migrations to fake: {total_migs}"
                )
            else:
                self.stderr.write(self.style.ERROR(f"Baseline '{version}' not found"))
                sys.exit(1)
            return

        self.stdout.write(f"Loading baseline '{version}'...")

        result = baseline.load(version)

        if result.success:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nBaseline '{version}' loaded successfully!\n"
                    f"  Migrations faked: {result.migrations_faked}\n"
                    f"  Migrations remaining: {result.migrations_remaining}\n"
                    f"  Elapsed: {result.elapsed_seconds:.2f}s"
                )
            )
            if result.migrations_remaining > 0:
                self.stdout.write(
                    f"\nRun 'python manage.py migrate' to apply the remaining "
                    f"{result.migrations_remaining} migrations."
                )
        else:
            self.stderr.write(self.style.ERROR(f"Failed to load baseline: {result.error}"))
            sys.exit(1)

    def _handle_list(self):
        from django_matt.migration_tools.baseline import MigrationBaseline

        baseline = MigrationBaseline()
        baselines = baseline.list()

        if not baselines:
            self.stdout.write("No baselines found.")
            self.stdout.write(
                "Create one with: python manage.py matt_baseline create <version>"
            )
            return

        self.stdout.write("Available baselines:\n")

        for info in sorted(baselines, key=lambda b: b.created_at, reverse=True):
            total_migs = sum(len(v) for v in info.applied_migrations.values())
            apps = len(info.applied_migrations)
            self.stdout.write(
                f"  {self.style.SUCCESS(info.version)}\n"
                f"    Created: {info.created_at}\n"
                f"    DB: {info.db_vendor}\n"
                f"    Django: {info.django_version}\n"
                f"    Migrations: {total_migs} across {apps} apps\n"
                f"    Hash: {info.schema_hash}"
            )
            if info.notes:
                self.stdout.write(f"    Notes: {info.notes}")
            self.stdout.write("")

    def _handle_verify(self, options):
        from django_matt.migration_tools.baseline import MigrationBaseline

        baseline = MigrationBaseline()
        version = options["version"]

        valid, message = baseline.verify(version)

        if valid:
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stderr.write(self.style.ERROR(message))
            sys.exit(1)

    def _handle_delete(self, options):
        from django_matt.migration_tools.baseline import MigrationBaseline

        baseline = MigrationBaseline()
        version = options["version"]

        if not options.get("force"):
            confirm = input(f"Delete baseline '{version}'? [y/N] ")
            if confirm.lower() != "y":
                self.stdout.write("Cancelled.")
                return

        if baseline.delete(version):
            self.stdout.write(self.style.SUCCESS(f"Deleted baseline '{version}'"))
        else:
            self.stderr.write(self.style.ERROR(f"Baseline '{version}' not found"))
            sys.exit(1)

    def _handle_info(self, options):
        from django_matt.migration_tools.baseline import MigrationBaseline

        baseline = MigrationBaseline()
        version = options["version"]

        baselines = baseline.list()
        info = next((b for b in baselines if b.version == version), None)

        if not info:
            self.stderr.write(self.style.ERROR(f"Baseline '{version}' not found"))
            sys.exit(1)

        self.stdout.write(f"\nBaseline: {self.style.SUCCESS(info.version)}")
        self.stdout.write(f"Created: {info.created_at}")
        self.stdout.write(f"Database: {info.db_vendor}")
        self.stdout.write(f"Django version: {info.django_version}")
        self.stdout.write(f"Schema hash: {info.schema_hash}")
        if info.notes:
            self.stdout.write(f"Notes: {info.notes}")

        self.stdout.write("\nMigrations by app:")
        for app, migrations in sorted(info.applied_migrations.items()):
            self.stdout.write(f"  {app}: {len(migrations)} migrations")
            if len(migrations) <= 5:
                for m in migrations:
                    self.stdout.write(f"    - {m}")
            else:
                for m in migrations[:2]:
                    self.stdout.write(f"    - {m}")
                self.stdout.write(f"    ... {len(migrations) - 4} more ...")
                for m in migrations[-2:]:
                    self.stdout.write(f"    - {m}")

        total = sum(len(v) for v in info.applied_migrations.values())
        self.stdout.write(f"\nTotal: {total} migrations across {len(info.applied_migrations)} apps")
