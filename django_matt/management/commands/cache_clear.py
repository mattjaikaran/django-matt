"""
Management command to clear Django caches.

Usage:
    python manage.py cache_clear                    # clear all backends
    python manage.py cache_clear --backend default  # clear specific backend
    python manage.py cache_clear --dry-run           # show what would be cleared
"""

from __future__ import annotations

from typing import Any

from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Clear Django cache backends"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--backend",
            type=str,
            default=None,
            help="Specific cache backend to clear (default: all backends)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be cleared without actually clearing",
        )

    def handle(self, **options: Any) -> str | None:
        backend_name: str | None = options["backend"]
        dry_run: bool = options["dry_run"]

        try:
            from django.conf import settings

            all_backends = list(getattr(settings, "CACHES", {"default": {}}).keys())
        except Exception:
            all_backends = ["default"]

        if backend_name:
            if backend_name not in all_backends:
                raise CommandError(
                    f"Unknown cache backend '{backend_name}'. "
                    f"Available: {', '.join(all_backends)}"
                )
            targets = [backend_name]
        else:
            targets = all_backends

        cleared: list[str] = []
        errors: list[str] = []

        for name in targets:
            if dry_run:
                self.stdout.write(f"  Would clear: {name}")
                cleared.append(name)
                continue

            try:
                cache = caches[name]
                cache.clear()
                cleared.append(name)
                self.stdout.write(self.style.SUCCESS(f"  Cleared: {name}"))
            except Exception as e:
                errors.append(f"{name}: {e}")
                self.stderr.write(self.style.ERROR(f"  Failed: {name} — {e}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\nDry run: {len(cleared)} backend(s) would be cleared")
            )
        elif cleared:
            self.stdout.write(
                self.style.SUCCESS(f"\nCleared {len(cleared)} cache backend(s)")
            )

        if errors:
            self.stderr.write(
                self.style.ERROR(f"\n{len(errors)} backend(s) failed")
            )

        return None
