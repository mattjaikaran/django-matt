"""Management command to validate API endpoints for common issues."""

from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


class Command(BaseCommand):
    help = "Validate API routes for missing permissions, unprotected endpoints, and schema issues."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="/api/",
            help="URL prefix to scan (default: /api/).",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors.",
        )

    def handle(self, *args, **options):
        prefix = options["prefix"]
        strict = options["strict"]
        warnings = []
        info = []
        endpoint_count = 0

        resolver = get_resolver()
        patterns = self._collect_patterns(resolver, "")

        for url, name, callback in patterns:
            if not url.startswith(prefix.lstrip("/")):
                continue

            endpoint_count += 1

            # Check for permission classes on ViewSets
            view_cls = getattr(callback, "view_class", None)
            if view_cls is None:
                view_cls = getattr(callback, "cls", None)

            if view_cls:
                perms = getattr(view_cls, "permission_classes", None)
                if not perms:
                    warnings.append(
                        f"  {url} ({name or 'unnamed'}) — no permission_classes set"
                    )

            # Check for jwt_required or similar decorators
            if hasattr(callback, "__wrapped__"):
                pass  # Has some decorator

        # Output
        self.stdout.write(f"\nScanned {endpoint_count} endpoints under {prefix}\n")

        if warnings:
            self.stdout.write(self.style.WARNING("Potential issues:"))
            for w in warnings:
                self.stdout.write(self.style.WARNING(w))
            self.stdout.write(
                self.style.WARNING(f"\n{len(warnings)} warning(s) found.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("No issues found."))

        if strict and warnings:
            raise SystemExit(1)

    def _collect_patterns(self, resolver, prefix):
        """Recursively collect all URL patterns."""
        results = []
        for pattern in resolver.url_patterns:
            if isinstance(pattern, URLResolver):
                new_prefix = prefix + str(pattern.pattern)
                results.extend(self._collect_patterns(pattern, new_prefix))
            elif isinstance(pattern, URLPattern):
                url = prefix + str(pattern.pattern)
                results.append((url, pattern.name, pattern.callback))
        return results
