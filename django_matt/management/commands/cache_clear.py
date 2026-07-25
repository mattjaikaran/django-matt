"""Management command to clear Django cache backends."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError

from django_matt.cli.console import console


class Command(BaseCommand):
    """Clear one or all configured Django cache backends."""

    help = "Clear Django cache backends (all or specific)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--backend",
            type=str,
            default=None,
            help="Cache backend alias to clear (default: all configured backends).",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default=None,
            help="Only delete keys matching this prefix (requires backend support).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleared without actually clearing.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Clear the specified or all cache backends."""
        backend_alias: str | None = options["backend"]
        prefix: str | None = options["prefix"]
        dry_run: bool = options["dry_run"]

        cache_backends: dict[str, dict] = getattr(settings, "CACHES", {})
        if not cache_backends:
            raise CommandError("No CACHES configured in settings.")

        aliases: list[str] = [backend_alias] if backend_alias else list(cache_backends.keys())

        # validate requested alias exists
        if backend_alias and backend_alias not in cache_backends:
            available = ", ".join(cache_backends.keys())
            raise CommandError(f"Cache backend '{backend_alias}' not found. Available: {available}")

        if dry_run:
            console.warning("[dry-run] No caches will be modified.")

        cleared: list[str] = []
        skipped: list[tuple[str, str]] = []

        for alias in aliases:
            backend_config = cache_backends[alias]
            engine = backend_config.get("BACKEND", "unknown")

            if dry_run:
                action = f"clear keys with prefix '{prefix}'" if prefix else "clear all keys"
                console.info(f"  [{alias}] ({engine}) — would {action}")
                cleared.append(alias)
                continue

            try:
                cache = caches[alias]

                if prefix:
                    # prefix-based deletion: use delete_many if the backend
                    # exposes key enumeration, otherwise fall back to
                    # has_key / delete for known keys.  Most backends don't
                    # support key iteration so we note the limitation.
                    if hasattr(cache, "delete_pattern"):
                        # django-redis provides delete_pattern
                        cache.delete_pattern(f"{prefix}*")
                        console.success(f"  [{alias}] cleared keys matching '{prefix}*'")
                        cleared.append(alias)
                    elif hasattr(cache, "keys"):
                        matching = cache.keys(f"{prefix}*")
                        cache.delete_many(matching)
                        console.success(
                            f"  [{alias}] cleared {len(matching)} key(s) matching '{prefix}*'"
                        )
                        cleared.append(alias)
                    else:
                        skipped.append((alias, "backend does not support prefix-based deletion"))
                else:
                    cache.clear()
                    console.success(f"  [{alias}] ({engine}) — cleared")
                    cleared.append(alias)

            except Exception as exc:
                skipped.append((alias, str(exc)))

        # summary
        if cleared:
            verb = "would clear" if dry_run else "cleared"
            console.success(f"\n{len(cleared)} backend(s) {verb}.")
        if skipped:
            console.warning(f"\n{len(skipped)} backend(s) skipped:")
            for alias, reason in skipped:
                console.warning(f"  [{alias}] {reason}")
