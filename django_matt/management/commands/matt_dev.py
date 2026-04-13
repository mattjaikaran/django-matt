"""
Unified development server command for django-matt.

Starts Django dev server + optional Vite + file watcher in one process.
Auto-detects available tools and starts what's needed.

Usage:
    python manage.py matt_dev                        # auto-detect everything
    python manage.py matt_dev --port 8080            # custom port
    python manage.py matt_dev --no-vite              # skip Vite
    python manage.py matt_dev --no-hot-reload        # skip file watcher
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start Django + Vite + hot reload in one command"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Django server port (default: 8000, auto-increments if taken)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="127.0.0.1",
            help="Django server host (default: 127.0.0.1)",
        )
        parser.add_argument(
            "--no-vite",
            action="store_true",
            default=False,
            help="Skip starting Vite dev server",
        )
        parser.add_argument(
            "--no-hot-reload",
            action="store_true",
            default=False,
            help="Skip hot reload file watcher",
        )
        parser.add_argument(
            "--vite-port",
            type=int,
            default=5173,
            help="Vite dev server port (default: 5173)",
        )
        parser.add_argument(
            "--server",
            type=str,
            default=None,
            choices=["uvicorn", "robyn", "granian"],
            help="Server backend for dev (default: Django runserver)",
        )

    def handle(self, **options: Any) -> str | None:
        host: str = options["host"]
        port: int = options["port"]
        skip_vite: bool = options["no_vite"]
        skip_hot_reload: bool = options["no_hot_reload"]
        vite_port: int = options["vite_port"]
        server_backend: str | None = options.get("server")

        # Auto-detect available port
        port = self._find_open_port(host, port)

        processes: list[subprocess.Popen] = []

        # Register signal handler for clean shutdown
        def cleanup(signum: int = 0, frame: Any = None) -> None:
            self.stdout.write("\n\nShutting down...")
            for proc in processes:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            sys.exit(0)

        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)

        try:
            # 1. Start Vite if available
            if not skip_vite and self._has_vite():
                vite_port = self._find_open_port("localhost", vite_port)
                vite_proc = self._start_vite(vite_port)
                if vite_proc:
                    processes.append(vite_proc)
                    self.stdout.write(
                        self.style.SUCCESS(f"  Vite dev server: http://localhost:{vite_port}")
                    )

            # 2. Start Django
            self.stdout.write(
                self.style.SUCCESS(f"  Django server:   http://{host}:{port}")
            )
            self.stdout.write("")

            # Build runserver command
            if server_backend:
                # Use matt_serve with the chosen backend in dev mode
                cmd = [
                    sys.executable, "manage.py", "matt_serve",
                    "--backend", server_backend,
                    "--host", host,
                    "--port", str(port),
                    "--workers", "1",
                ]
            else:
                cmd = [sys.executable, "manage.py"]
                if not skip_hot_reload and self._has_hot_reload():
                    cmd.append("runserver_hot")
                else:
                    cmd.append("runserver")
                cmd.append(f"{host}:{port}")

            # Run Django as the main process (blocks until exit)
            django_proc = subprocess.Popen(cmd, env=self._build_env(vite_port))
            processes.append(django_proc)
            django_proc.wait()

        except KeyboardInterrupt:
            pass
        finally:
            cleanup()

        return None

    def _find_open_port(self, host: str, start_port: int) -> int:
        """Find an open port, starting from start_port."""
        port = start_port
        max_attempts = 10

        for _ in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                    return port
            except OSError:
                if port == start_port:
                    self.stdout.write(
                        self.style.WARNING(f"  Port {port} in use, trying {port + 1}...")
                    )
                port += 1

        # Fall back to original if all attempts fail
        return start_port

    def _has_vite(self) -> bool:
        """Check if a Vite project is configured."""
        markers = ["vite.config.ts", "vite.config.js", "vite.config.mts"]
        return any(Path(m).exists() for m in markers)

    def _has_hot_reload(self) -> bool:
        """Check if hot reload command is available."""
        try:
            from django_matt.dev.hot_reload import run_hot_reload  # noqa: F401

            return True
        except ImportError:
            return False

    def _start_vite(self, port: int) -> subprocess.Popen | None:
        """Start Vite dev server as a subprocess."""
        # Prefer bun over npx
        for runner in ["bunx", "npx"]:
            try:
                proc = subprocess.Popen(
                    [runner, "vite", "--port", str(port), "--strictPort"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={**os.environ, "BROWSER": "none"},
                )
                # Give it a moment to start
                time.sleep(0.5)
                if proc.poll() is None:
                    return proc
            except FileNotFoundError:
                continue

        self.stdout.write(
            self.style.WARNING("  Vite not found (install with: bun add -D vite)")
        )
        return None

    def _build_env(self, vite_port: int) -> dict[str, str]:
        """Build environment variables for Django process."""
        env = os.environ.copy()
        env["VITE_DEV_SERVER_URL"] = f"http://localhost:{vite_port}"
        env["DJANGO_MATT_DEV_MODE"] = "1"
        return env
