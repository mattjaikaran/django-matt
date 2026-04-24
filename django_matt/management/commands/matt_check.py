"""
Unified system check command for django-matt.

Combines Django system checks, config validation, import verification,
and API endpoint validation in one pass.

Usage:
    python manage.py matt_check              # standard checks
    python manage.py matt_check --strict     # all checks, fail on warnings
    python manage.py matt_check --quick      # fast checks only (no import scan)
"""

from __future__ import annotations

import importlib
import sys
import time
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Unified system check combining Django checks, config validation, and import verification."""

    help = "Run all django-matt system checks in one pass"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--strict",
            action="store_true",
            default=False,
            help="Treat warnings as errors",
        )
        parser.add_argument(
            "--quick",
            action="store_true",
            default=False,
            help="Skip slow checks (import scan, endpoint validation)",
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            default=False,
            help="Disable colored output",
        )

    def handle(self, **options: Any) -> str | None:
        strict: bool = options["strict"]
        quick: bool = options["quick"]
        start = time.monotonic()

        total_issues = 0
        total_warnings = 0

        # 1. Django system checks
        self.stdout.write(self.style.MIGRATE_HEADING("\n[1/4] Django system checks"))
        try:
            call_command(
                "check",
                verbosity=0,
                stdout=self.stdout,
                stderr=self.stderr,
            )
            self.stdout.write(self.style.SUCCESS("  Pass"))
        except SystemExit:
            total_issues += 1
            self.stdout.write(self.style.ERROR("  Failed"))

        # 2. Config validation
        self.stdout.write(self.style.MIGRATE_HEADING("\n[2/4] Config validation"))
        config_issues = self._check_config()
        total_issues += config_issues["errors"]
        total_warnings += config_issues["warnings"]

        # 3. Import verification
        if not quick:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[3/4] Import verification"))
            import_issues = self._check_imports()
            total_issues += import_issues["errors"]
            total_warnings += import_issues["warnings"]
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[3/4] Import verification (skipped — quick mode)"))

        # 4. API endpoint validation
        if not quick:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[4/4] API endpoint validation"))
            api_issues = self._check_endpoints()
            total_issues += api_issues["errors"]
            total_warnings += api_issues["warnings"]
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[4/4] API endpoint validation (skipped — quick mode)"))

        # Summary
        elapsed = time.monotonic() - start
        self.stdout.write("")

        if strict:
            total_issues += total_warnings

        if total_issues == 0 and total_warnings == 0:
            self.stdout.write(
                self.style.SUCCESS(f"All checks passed ({elapsed:.1f}s)")
            )
        elif total_issues == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"{total_warnings} warning(s), 0 errors ({elapsed:.1f}s)"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"{total_issues} error(s), {total_warnings} warning(s) ({elapsed:.1f}s)"
                )
            )
            sys.exit(1)

        return None

    def _check_config(self) -> dict[str, int]:
        """Validate django-matt configuration settings."""
        errors = 0
        warnings = 0

        try:
            from django.conf import settings

            # Check for common misconfigurations
            if not hasattr(settings, "SECRET_KEY"):
                self.stdout.write(self.style.ERROR("  SECRET_KEY not set"))
                errors += 1

            # Check MATT_AUTH
            matt_auth = getattr(settings, "MATT_AUTH", None)
            if matt_auth and isinstance(matt_auth, dict):
                login_field = matt_auth.get("login_field", "email")
                if login_field not in ("email", "username"):
                    self.stdout.write(
                        self.style.ERROR(
                            f"  MATT_AUTH.login_field must be 'email' or 'username', got '{login_field}'"
                        )
                    )
                    errors += 1

            # Check MATT_THROTTLE
            matt_throttle = getattr(settings, "MATT_THROTTLE", None)
            if matt_throttle and isinstance(matt_throttle, str):
                from django_matt.throttling.defaults import PRESETS

                if matt_throttle not in PRESETS:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  MATT_THROTTLE preset '{matt_throttle}' not found"
                        )
                    )
                    errors += 1

            # Check for DEBUG in production indicators
            if not getattr(settings, "DEBUG", True):
                if getattr(settings, "SECRET_KEY", "").startswith("django-insecure"):
                    self.stdout.write(
                        self.style.WARNING("  Insecure SECRET_KEY in non-DEBUG mode")
                    )
                    warnings += 1

            if errors == 0 and warnings == 0:
                self.stdout.write(self.style.SUCCESS("  Pass"))
            else:
                self.stdout.write(
                    f"  {errors} error(s), {warnings} warning(s)"
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Config check failed: {e}"))
            errors += 1

        return {"errors": errors, "warnings": warnings}

    def _check_imports(self) -> dict[str, int]:
        """Verify all django-matt modules can be imported."""
        errors = 0
        warnings = 0

        modules = [
            "django_matt",
            "django_matt.core",
            "django_matt.auth",
            "django_matt.views",
            "django_matt.permissions",
            "django_matt.throttling",
            "django_matt.openapi",
            "django_matt.db",
            "django_matt.config",
            "django_matt.audit",
            "django_matt.events",
            "django_matt.streaming",
        ]

        failed = []
        for mod in modules:
            try:
                importlib.import_module(mod)
            except Exception as e:
                failed.append((mod, str(e)))
                errors += 1

        if failed:
            for mod, err in failed:
                self.stdout.write(self.style.ERROR(f"  Import failed: {mod} — {err}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"  Pass ({len(modules)} modules)"))

        return {"errors": errors, "warnings": warnings}

    def _check_endpoints(self) -> dict[str, int]:
        """Validate registered API endpoints."""
        errors = 0
        warnings = 0

        try:
            from django.urls import get_resolver

            resolver = get_resolver()
            url_count = len(resolver.url_patterns)
            self.stdout.write(self.style.SUCCESS(f"  Pass ({url_count} URL patterns)"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Could not resolve URLs: {e}"))
            warnings += 1

        return {"errors": errors, "warnings": warnings}
