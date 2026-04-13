"""
Management command to run Vite production build.

Runs `bunx vite build` (or `npx vite build`) with proper Django
environment variables and reports output stats.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_matt.vite.config import get_vite_config


class Command(BaseCommand):
    help = "Run Vite production build"

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(  # type: ignore[attr-defined]
            "--mode",
            default="production",
            help="Vite build mode (default: production)",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--outdir",
            default=None,
            help="Override output directory",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--runner",
            choices=["bun", "npx"],
            default=None,
            help="JS runner to use (auto-detected if not set)",
        )

    def handle(self, **options: object) -> None:
        config = get_vite_config()
        mode = options["mode"]
        outdir = options.get("outdir") or config.build_dir
        runner = options.get("runner") or self._detect_runner()

        self.stdout.write(f"Building with {runner}, mode={mode}")
        self.stdout.write(f"Output directory: {outdir}")

        cmd = [
            runner,
            "vite",
            "build",
            "--mode",
            str(mode),
            "--outDir",
            str(outdir),
        ]

        env = {**os.environ}
        env["DJANGO_SETTINGS_MODULE"] = os.environ.get(
            "DJANGO_SETTINGS_MODULE",
            getattr(settings, "SETTINGS_MODULE", "config.settings"),
        )

        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(settings.BASE_DIR),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            raise CommandError(
                f"'{runner}' not found. Install bun or Node.js."
            )

        elapsed = time.monotonic() - start

        if result.stdout:
            self.stdout.write(result.stdout)
        if result.stderr:
            self.stderr.write(result.stderr)

        if result.returncode != 0:
            raise CommandError(
                f"Vite build failed with exit code {result.returncode}"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Build completed in {elapsed:.2f}s")
        )
        self._report_stats(outdir)

    def _detect_runner(self) -> str:
        """Detect available JS runner, preferring bun."""
        if shutil.which("bunx"):
            return "bunx"
        if shutil.which("npx"):
            return "npx"
        raise CommandError(
            "Neither bunx nor npx found. Install bun or Node.js."
        )

    def _report_stats(self, outdir: str) -> None:
        """Report basic build output stats."""
        from pathlib import Path

        build_path = Path(settings.BASE_DIR) / outdir
        if not build_path.exists():
            return

        files = list(build_path.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        size_kb = total_size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"

        self.stdout.write(f"  Files: {file_count}")
        self.stdout.write(f"  Total size: {size_str}")
