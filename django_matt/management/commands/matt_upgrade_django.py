"""
Django version upgrade assistant.

Usage:
    python manage.py matt_upgrade_django                    # Check available upgrades
    python manage.py matt_upgrade_django --target 6.0       # Upgrade to Django 6.0
    python manage.py matt_upgrade_django --check-only       # Show breaking changes only
    python manage.py matt_upgrade_django --dry-run          # Show what would change
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import django
from django.core.management.base import BaseCommand, CommandError

# Known breaking changes per Django version upgrade path
BREAKING_CHANGES: dict[str, list[dict[str, str]]] = {
    "5.2->6.0": [
        {
            "id": "python-version",
            "title": "Python 3.10 and 3.11 support dropped",
            "description": "Django 6.0 requires Python 3.12+. Check your runtime version.",
            "action": "Update python version in pyproject.toml, Dockerfile, CI config.",
            "pattern": r"python_requires\s*=.*3\.(10|11)",
        },
        {
            "id": "syncdb-removed",
            "title": "Automatic table creation for unmigrated apps removed",
            "description": (
                "Django 6.0 no longer auto-creates tables via syncdb for apps "
                "without migrations. All apps must have migrations."
            ),
            "action": "Run `python manage.py makemigrations <app>` for any app missing migrations.",
            "pattern": r"class Meta:.*managed\s*=\s*False",
        },
        {
            "id": "form-field-default",
            "title": "Form fields default to required=True explicitly",
            "description": "Fields that relied on implicit required behavior may need updating.",
            "action": "Review forms for fields that should be optional.",
            "pattern": r"forms\.\w+Field\(",
        },
        {
            "id": "deprecated-utils",
            "title": "Deprecated utilities removed",
            "description": (
                "Various deprecated utilities from Django 4.x have been fully removed "
                "in 6.0, including legacy test runner methods and template tag shims."
            ),
            "action": "Search for deprecated imports and update to modern equivalents.",
            "pattern": r"from django\.utils\.(encoding|translation)\s+import\s+(force_text|smart_text|ugettext)",
        },
        {
            "id": "login-required-default",
            "title": "LoginRequiredMiddleware behavior change",
            "description": (
                "Views now require authentication by default when LoginRequiredMiddleware "
                "is enabled. Use login_not_required decorator for public views."
            ),
            "action": "Add @login_not_required to public views, or remove LoginRequiredMiddleware.",
            "pattern": r"LoginRequiredMiddleware",
        },
    ],
    "6.0->6.1": [
        {
            "id": "placeholder",
            "title": "Django 6.1 not yet released",
            "description": "No breaking changes documented yet.",
            "action": "Check Django release notes when available.",
            "pattern": "",
        },
    ],
}

# Release notes URLs
RELEASE_NOTES: dict[str, str] = {
    "5.2": "https://docs.djangoproject.com/en/5.2/releases/5.2/",
    "6.0": "https://docs.djangoproject.com/en/6.0/releases/6.0/",
}


class Command(BaseCommand):
    """Upgrade Django version with guided breaking change resolution."""

    help = "Upgrade Django to a target version with breaking change detection and resolution"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            type=str,
            default=None,
            help="Target Django version (e.g., 6.0). Defaults to latest.",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only show breaking changes, don't upgrade.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without making modifications.",
        )
        parser.add_argument(
            "--no-branch",
            action="store_true",
            help="Don't create a new git branch for the upgrade.",
        )
        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Skip confirmation prompts.",
        )

    def handle(self, *args, **options):
        current_version = self._get_current_django_version()
        target = options["target"] or self._get_latest_django_version()
        check_only = options["check_only"]
        dry_run = options["dry_run"]
        no_branch = options["no_branch"]
        auto_yes = options["yes"]

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Django Upgrade Assistant ===\n"))
        self.stdout.write(f"  Current version: Django {current_version}")
        self.stdout.write(f"  Target version:  Django {target}")

        current_major_minor = self._parse_version(current_version)
        target_major_minor = self._parse_version(target)

        if current_major_minor >= target_major_minor:
            self.stdout.write(self.style.SUCCESS(
                f"\n  Already on Django {current_version} (>= {target}). Nothing to do.\n"
            ))
            return

        # Collect all breaking changes across upgrade path
        upgrade_path = self._get_upgrade_path(current_major_minor, target_major_minor)
        all_changes = []
        for step in upgrade_path:
            key = f"{step[0]}->{step[1]}"
            changes = BREAKING_CHANGES.get(key, [])
            if changes:
                all_changes.append((key, changes))

        # Show breaking changes
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n--- Breaking Changes ({current_major_minor[0]}.{current_major_minor[1]} -> "
            f"{target_major_minor[0]}.{target_major_minor[1]}) ---\n"
        ))

        if not all_changes:
            self.stdout.write(self.style.SUCCESS("  No known breaking changes for this upgrade path.\n"))
        else:
            total_findings = 0
            for path_key, changes in all_changes:
                self.stdout.write(self.style.WARNING(f"\n  Upgrade step: {path_key}"))
                if path_key.split("->")[1] in RELEASE_NOTES:
                    self.stdout.write(f"  Release notes: {RELEASE_NOTES[path_key.split('->')[1]]}")
                self.stdout.write("")

                for change in changes:
                    self.stdout.write(f"  [{change['id']}] {change['title']}")
                    self.stdout.write(f"    {change['description']}")
                    self.stdout.write(self.style.NOTICE(f"    Action: {change['action']}"))

                    # Scan codebase for matches
                    if change["pattern"]:
                        matches = self._scan_codebase(change["pattern"])
                        if matches:
                            total_findings += len(matches)
                            self.stdout.write(self.style.WARNING(
                                f"    Found {len(matches)} potential match(es):"
                            ))
                            for match_file, line_num, line_text in matches[:5]:
                                self.stdout.write(f"      {match_file}:{line_num}  {line_text.strip()}")
                            if len(matches) > 5:
                                self.stdout.write(f"      ... and {len(matches) - 5} more")
                        else:
                            self.stdout.write(self.style.SUCCESS("    No matches found in codebase."))
                    self.stdout.write("")

            if total_findings:
                self.stdout.write(self.style.WARNING(
                    f"\n  Total findings: {total_findings} potential issue(s) to review.\n"
                ))

        if check_only:
            return

        if dry_run:
            self.stdout.write(self.style.MIGRATE_HEADING("\n--- Dry Run: What Would Change ---\n"))
            self.stdout.write(f"  1. Create branch: upgrade/django-{target}")
            self.stdout.write(f"  2. Update Django requirement to >={target}")
            self.stdout.write("  3. Run: uv lock")
            self.stdout.write("  4. Run: python manage.py check")
            self.stdout.write("  5. Run: python manage.py migrate --check")
            self.stdout.write("")
            return

        # Confirm upgrade
        if not auto_yes:
            self.stdout.write(self.style.MIGRATE_HEADING("\n--- Ready to Upgrade ---\n"))
            self.stdout.write("  This will:")
            if not no_branch:
                self.stdout.write(f"  - Create a new branch: upgrade/django-{target}")
            self.stdout.write(f"  - Update Django dependency to >={target}")
            self.stdout.write("  - Lock dependencies with uv")
            self.stdout.write("  - Run Django system checks")
            self.stdout.write("")
            confirm = input("  Proceed? [y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                self.stdout.write(self.style.WARNING("\n  Upgrade cancelled.\n"))
                return

        # Execute upgrade
        self._execute_upgrade(target, no_branch=no_branch)

    def _get_current_django_version(self) -> str:
        """Get the currently installed Django version."""
        return django.__version__

    def _get_latest_django_version(self) -> str:
        """Get the latest Django version available on PyPI."""
        try:
            result = subprocess.run(
                ["uv", "pip", "index", "versions", "django"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # Parse the latest version from output
                for line in result.stdout.splitlines():
                    if "Available versions:" in line or "LATEST:" in line:
                        versions = re.findall(r"\d+\.\d+(?:\.\d+)?", line)
                        if versions:
                            return versions[0]
        except FileNotFoundError:
            pass

        # Fallback: check known versions
        return "6.0"

    def _parse_version(self, version: str) -> tuple[int, int]:
        """Parse version string to (major, minor) tuple."""
        parts = version.split(".")
        return (int(parts[0]), int(parts[1]))

    def _get_upgrade_path(
        self,
        current: tuple[int, int],
        target: tuple[int, int],
    ) -> list[tuple[str, str]]:
        """Get the step-by-step upgrade path between versions."""
        known_versions = [
            (5, 0), (5, 1), (5, 2),
            (6, 0), (6, 1),
        ]
        path = []
        started = False
        prev = None
        for v in known_versions:
            if v == current:
                started = True
                prev = v
                continue
            if started and prev is not None:
                path.append((f"{prev[0]}.{prev[1]}", f"{v[0]}.{v[1]}"))
                prev = v
                if v == target:
                    break
        return path

    def _scan_codebase(self, pattern: str) -> list[tuple[str, int, str]]:
        """Scan the codebase for a regex pattern, returning matches."""
        matches = []
        project_dir = Path.cwd()
        try:
            compiled = re.compile(pattern)
        except re.error:
            return matches

        for py_file in project_dir.rglob("*.py"):
            # Skip common non-project directories
            rel = str(py_file.relative_to(project_dir))
            if any(skip in rel for skip in [
                ".venv", "venv", "__pycache__", "node_modules",
                ".git", "site-packages", ".tox", "migrations",
            ]):
                continue

            try:
                content = py_file.read_text(errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        matches.append((rel, i, line))
            except OSError:
                continue

        return matches

    def _execute_upgrade(self, target: str, *, no_branch: bool = False):
        """Execute the Django upgrade."""
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Executing Upgrade ---\n"))

        # Step 1: Create branch
        if not no_branch:
            branch_name = f"upgrade/django-{target}"
            self.stdout.write(f"  Creating branch: {branch_name}")
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                if "already exists" in result.stderr:
                    self.stdout.write(self.style.WARNING(
                        f"  Branch {branch_name} already exists, switching to it."
                    ))
                    subprocess.run(
                        ["git", "checkout", branch_name],
                        capture_output=True,
                        check=False,
                    )
                else:
                    raise CommandError(f"Failed to create branch: {result.stderr}")

        # Step 2: Update pyproject.toml
        self.stdout.write(f"  Updating Django requirement to >={target}")
        pyproject = Path.cwd() / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Match patterns like "django>=5.2.0" or "Django>=5.2"
            updated = re.sub(
                r'(["\'])django>=[\d.]+(["\'])',
                f'\\1django>={target}\\2',
                content,
                flags=re.IGNORECASE,
            )
            if updated != content:
                pyproject.write_text(updated)
                self.stdout.write(self.style.SUCCESS("  Updated pyproject.toml"))
            else:
                self.stdout.write(self.style.WARNING(
                    "  Could not find Django version in pyproject.toml. Update manually."
                ))

        # Step 3: Lock dependencies
        self.stdout.write("  Locking dependencies with uv...")
        result = subprocess.run(
            ["uv", "lock"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS("  Dependencies locked."))
        else:
            self.stdout.write(self.style.ERROR(f"  uv lock failed: {result.stderr}"))
            self.stdout.write("  You may need to resolve dependency conflicts manually.")

        # Step 4: Run system checks
        self.stdout.write("  Running Django system checks...")
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS("  System checks passed."))
        else:
            self.stdout.write(self.style.WARNING("  System check issues:"))
            for line in result.stdout.splitlines():
                self.stdout.write(f"    {line}")

        # Step 5: Check migrations
        self.stdout.write("  Checking migrations...")
        result = subprocess.run(
            [sys.executable, "manage.py", "migrate", "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS("  Migrations are up to date."))
        else:
            self.stdout.write(self.style.WARNING(
                "  Pending migrations detected. Run: python manage.py migrate"
            ))

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\n  Django upgrade to {target} complete!"
        ))
        self.stdout.write("\n  Next steps:")
        self.stdout.write("  1. Review the breaking changes above")
        self.stdout.write("  2. Run your test suite: uv run pytest")
        self.stdout.write("  3. Fix any failing tests")
        if not no_branch:
            self.stdout.write("  4. Merge the upgrade branch when ready")
        self.stdout.write("")
