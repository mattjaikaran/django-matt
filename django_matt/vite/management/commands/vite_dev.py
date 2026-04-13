"""
Management command to start Vite dev server alongside Django.

Starts both the Vite dev server and Django's runserver, managing
both processes with clean shutdown on Ctrl+C.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from django_matt.vite.config import get_vite_config


class Command(BaseCommand):
    help = "Start Vite dev server and Django runserver together"

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(  # type: ignore[attr-defined]
            "--vite-port",
            type=int,
            default=None,
            help="Vite dev server port (default: from config or 5173)",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--django-port",
            type=int,
            default=8000,
            help="Django runserver port (default: 8000)",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--no-django",
            action="store_true",
            default=False,
            help="Only start Vite dev server, not Django",
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--runner",
            choices=["bun", "npx"],
            default=None,
            help="JS runner to use (auto-detected if not set)",
        )

    def handle(self, **options: object) -> None:
        config = get_vite_config()
        runner = options.get("runner") or self._detect_runner()
        vite_port = options.get("vite_port")
        django_port = options["django_port"]
        no_django = options["no_django"]

        processes: list[subprocess.Popen[str]] = []

        # Build Vite command
        vite_cmd = [str(runner), "vite"]
        if vite_port:
            vite_cmd.extend(["--port", str(vite_port)])

        self.stdout.write(f"Starting Vite dev server: {' '.join(vite_cmd)}")

        vite_proc = subprocess.Popen(
            vite_cmd,
            cwd=str(settings.BASE_DIR),
            stdout=sys.stdout,
            stderr=sys.stderr,
            env={**os.environ},
        )
        processes.append(vite_proc)

        django_thread = None
        if not no_django:
            self.stdout.write(
                f"Starting Django runserver on port {django_port}"
            )

            def run_django() -> None:
                try:
                    call_command(
                        "runserver", str(django_port), use_reloader=False
                    )
                except SystemExit:
                    pass

            django_thread = threading.Thread(
                target=run_django, daemon=True
            )
            django_thread.start()

        def shutdown(signum: int, frame: object) -> None:
            self.stdout.write("\nShutting down...")
            for proc in processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        try:
            vite_proc.wait()
        except KeyboardInterrupt:
            shutdown(signal.SIGINT, None)

    def _detect_runner(self) -> str:
        """Detect available JS runner, preferring bun."""
        if shutil.which("bunx"):
            return "bunx"
        if shutil.which("npx"):
            return "npx"
        raise CommandError(
            "Neither bunx nor npx found. Install bun or Node.js."
        )
