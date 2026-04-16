"""
Vite build command for django-matt.

Wraps `vite build` with Django environment awareness — sets NODE_ENV,
resolves paths from MATT_VITE config, and validates the output manifest.

Usage:
    python manage.py vite_build                    # standard production build
    python manage.py vite_build --mode staging     # custom Vite mode
    python manage.py vite_build --outdir dist      # override output directory
    python manage.py vite_build --watch            # rebuild on changes
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_matt.vite.config import get_vite_config, reset_vite_config


class Command(BaseCommand):
    help = "Run Vite build with Django environment"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--mode",
            type=str,
            default="production",
            help="Vite build mode (default: production)",
        )
        parser.add_argument(
            "--outdir",
            type=str,
            default=None,
            help="Override output directory",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            default=False,
            help="Watch for changes and rebuild",
        )
        parser.add_argument(
            "--sourcemap",
            action="store_true",
            default=False,
            help="Generate source maps",
        )
        parser.add_argument(
            "--minify",
            action="store_true",
            default=True,
            help="Minify output (default: True)",
        )
        parser.add_argument(
            "--no-minify",
            action="store_true",
            default=False,
            help="Skip minification",
        )
        parser.add_argument(
            "--runner",
            type=str,
            default=None,
            choices=["bunx", "npx"],
            help="JS runner (default: auto-detect, prefers bunx)",
        )

    def handle(self, **options: Any) -> str | None:
        reset_vite_config()
        config = get_vite_config()

        # Verify vite config exists
        vite_config = self._find_vite_config()
        if vite_config is None:
            raise CommandError(
                "No vite.config.{ts,js,mts,mjs} found. "
                "Initialize Vite first: bunx create-vite"
            )

        outdir = options["outdir"] or config.build_dir
        runner = options["runner"] or self._detect_runner()

        if runner is None:
            raise CommandError(
                "Neither bunx nor npx found. "
                "Install bun (curl -fsSL https://bun.sh/install | bash) "
                "or Node.js (https://nodejs.org)"
            )

        # Build command
        cmd = [runner, "vite", "build"]
        cmd.extend(["--mode", options["mode"]])
        cmd.extend(["--outDir", outdir])

        if options["sourcemap"]:
            cmd.append("--sourcemap")

        if options["no_minify"]:
            cmd.append("--minify=false")

        if options["watch"]:
            cmd.append("--watch")

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Building with Vite ({runner})...")
        )
        self.stdout.write(f"  Mode:   {options['mode']}")
        self.stdout.write(f"  Output: {outdir}")
        self.stdout.write("")

        result = subprocess.run(
            cmd,
            env=self._build_env(),
            cwd=settings.BASE_DIR,
        )

        if result.returncode != 0:
            raise CommandError(f"Vite build failed with exit code {result.returncode}")

        # Validate manifest was created
        manifest_path = Path(settings.BASE_DIR) / config.manifest_path
        if not options["watch"] and not manifest_path.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  Warning: manifest not found at {config.manifest_path}"
                )
            )
        elif not options["watch"]:
            self.stdout.write(
                self.style.SUCCESS(f"  Manifest: {config.manifest_path}")
            )

        self.stdout.write(self.style.SUCCESS("\nBuild complete."))
        return None

    def _find_vite_config(self) -> Path | None:
        """Find the Vite config file."""
        base = Path(settings.BASE_DIR)
        for name in [
            "vite.config.ts",
            "vite.config.js",
            "vite.config.mts",
            "vite.config.mjs",
        ]:
            path = base / name
            if path.exists():
                return path
        return None

    def _detect_runner(self) -> str | None:
        """Auto-detect available JS runner, preferring bunx."""
        for runner in ["bunx", "npx"]:
            try:
                subprocess.run(
                    [runner, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                return runner
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    def _build_env(self) -> dict[str, str]:
        """Build environment for the Vite process."""
        import os

        env = os.environ.copy()
        env["NODE_ENV"] = "production"
        # Pass Django's BASE_DIR so Vite plugins can resolve paths
        env["DJANGO_BASE_DIR"] = str(settings.BASE_DIR)
        env["DJANGO_STATIC_URL"] = settings.STATIC_URL or "/static/"
        return env
