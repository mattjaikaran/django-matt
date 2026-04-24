"""
Build fingerprint manifest for static files.

Usage:
    python manage.py fingerprint_static
    python manage.py fingerprint_static --dry-run
"""

from django_matt.cli import MattCommand
from django_matt.vite.fingerprint import FingerprintManifest


class Command(MattCommand):
    """Build a content-hash fingerprint manifest for static files."""

    help = "Build content-hash fingerprints for static files"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fingerprinted without writing",
        )

    def handle(self, *args, **options):
        """Build the fingerprint manifest for all static files."""
        from pathlib import Path

        from django.conf import settings

        static_root = getattr(settings, "STATIC_ROOT", None)
        if not static_root:
            self.console.error("STATIC_ROOT is not configured")
            return

        self.console.header("Static File Fingerprinting")

        manifest = FingerprintManifest(static_root)

        if options["dry_run"]:
            self.console.info("Dry run — no files will be written")
            from django_matt.vite.fingerprint import (
                _compute_file_hash,
                _insert_hash,
            )

            root = Path(static_root)
            count = 0
            for file_path in sorted(root.rglob("*")):
                if not file_path.is_file() or file_path.name == "fingerprint-manifest.json":
                    continue
                rel = str(file_path.relative_to(root)).replace("\\", "/")
                h = _compute_file_hash(file_path)
                hashed = _insert_hash(rel, h)
                self.console.info(f"  {rel} → {hashed}")
                count += 1
            self.console.success(f"Would fingerprint {count} files")
            return

        result = manifest.build()
        self.console.success(f"Fingerprinted {len(result)} static files")
        self.console.info(f"Manifest: {manifest.manifest_path}")
