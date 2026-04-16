"""
Vite dev server command for django-matt.

Starts Vite dev server alongside Django, with HMR proxying configured.
For combined Django+Vite startup, use `matt_dev` instead.

Usage:
    python manage.py vite_dev                      # start Vite dev server
    python manage.py vite_dev --port 5174          # custom port
    python manage.py vite_dev --host 0.0.0.0       # expose to network
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_matt.vite.config import get_vite_config, reset_vite_config


class Command(BaseCommand):
    help = "Start Vite dev server with Django integration"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="Vite dev server port (default: from MATT_VITE config or 5173)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="localhost",
            help="Vite dev server host (default: localhost)",
        )
        parser.add_argument(
            "--open",
            action="store_true",
            default=False,
            help="Open browser on startup",
        )
        parser.add_argument(
            "--https",
            action="store_true",
            default=False,
            help="Enable HTTPS",
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

        port = options["port"] or int(config.dev_server_url.split(":")[-1])
        host = options["host"]
        runner = options["runner"] or self._detect_runner()

        if runner is None:
            raise CommandError(
                "Neither bunx nor npx found. Install bun or Node.js."
            )

        cmd = [runner, "vite"]
        cmd.extend(["--port", str(port)])
        cmd.extend(["--host", host])
        cmd.append("--strictPort")

        if options["open"]:
            cmd.append("--open")

        if options["https"]:
            cmd.append("--https")

        self.stdout.write(
            self.style.SUCCESS(f"Starting Vite dev server at http://{host}:{port}")
        )

        env = os.environ.copy()
        env["DJANGO_BASE_DIR"] = str(settings.BASE_DIR)
        if not options["open"]:
            env["BROWSER"] = "none"

        proc = subprocess.Popen(cmd, env=env, cwd=settings.BASE_DIR)

        def cleanup(signum: int = 0, frame: Any = None) -> None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            sys.exit(0)

        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)

        try:
            proc.wait()
        except KeyboardInterrupt:
            cleanup()

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
