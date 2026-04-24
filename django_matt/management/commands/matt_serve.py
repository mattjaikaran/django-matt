"""
Production server launcher for django-matt.

Starts the application with the configured (or specified) server backend.

Usage:
    python manage.py matt_serve                          # configured backend
    python manage.py matt_serve --backend granian         # specific backend
    python manage.py matt_serve --backend granian -w 4    # 4 workers
    python manage.py matt_serve --list                    # show available backends
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Start the production ASGI server using the configured or specified backend."""

    help = "Start production server with configured backend"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--backend",
            "-b",
            type=str,
            default=None,
            help="Server backend: uvicorn, robyn, granian (default: from MATT_SERVER or uvicorn)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default=None,
            help="Bind host (default: from MATT_SERVER or 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            "-p",
            type=int,
            default=None,
            help="Bind port (default: from MATT_SERVER or 8000)",
        )
        parser.add_argument(
            "--workers",
            "-w",
            type=str,
            default=None,
            help="Worker count or 'auto' (default: from MATT_SERVER or auto)",
        )
        parser.add_argument(
            "--app-path",
            type=str,
            default=None,
            help="ASGI application path (default: config.asgi:application)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            default=False,
            help="List available server backends and exit",
        )
        parser.add_argument(
            "--http2",
            action="store_true",
            default=None,
            help="Enable HTTP/2 (backend must support it)",
        )
        parser.add_argument(
            "--no-access-log",
            action="store_true",
            default=False,
            help="Disable access logging",
        )

    def handle(self, **options: Any) -> str | None:
        from django_matt.servers.config import get_server_config
        from django_matt.servers.registry import get_backend

        if options["list"]:
            return self._list_backends()

        config = get_server_config()

        # CLI overrides > MATT_SERVER config > defaults
        backend_name = options["backend"] or config.backend
        host = options["host"] or config.host
        port = options["port"] or config.port
        workers = options["workers"] or config.workers
        app_path = options["app_path"] or self._detect_app_path()
        http2 = options["http2"] if options["http2"] is not None else config.http2
        access_log = not options["no_access_log"] and config.access_log

        try:
            backend = get_backend(backend_name)
        except KeyError as exc:
            raise CommandError(str(exc))

        if not backend.check_available():
            raise CommandError(
                f"Server backend '{backend_name}' is not installed. "
                f"Install it with: uv add {backend_name}"
            )

        if http2 and not backend.supports_http2:
            self.stderr.write(
                self.style.WARNING(
                    f"  Backend '{backend_name}' does not support HTTP/2 — ignoring --http2"
                )
            )
            http2 = False

        cmd = backend.get_command(
            host=host,
            port=port,
            workers=workers,
            app_path=app_path,
            http2=http2,
            access_log=access_log,
            ssl_cert=config.ssl_cert,
            ssl_key=config.ssl_key,
            graceful_timeout=config.graceful_timeout,
        )

        resolved_workers = backend.resolve_workers(workers)

        # Startup banner
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  django-matt serve"))
        self.stdout.write(f"  Backend:  {backend.name}")
        self.stdout.write(f"  Address:  http://{host}:{port}")
        self.stdout.write(f"  Workers:  {resolved_workers}")
        if http2:
            self.stdout.write("  HTTP/2:   enabled")
        if config.ssl_cert:
            self.stdout.write(f"  SSL:      {config.ssl_cert}")
        self.stdout.write(f"  App:      {app_path}")
        self.stdout.write("")

        # Exec the server
        try:
            proc = subprocess.run(cmd, env=self._build_env())
            sys.exit(proc.returncode)
        except FileNotFoundError:
            raise CommandError(
                f"Could not find '{cmd[0]}' executable. "
                f"Is {backend_name} installed? Try: uv add {backend_name}"
            )
        except KeyboardInterrupt:
            self.stdout.write("\nShutting down...")

        return None

    def _list_backends(self) -> str | None:
        from django_matt.servers.registry import ServerRegistry

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  Available server backends:"))
        self.stdout.write("")

        for name, available in ServerRegistry.list_backends():
            status = self.style.SUCCESS("installed") if available else self.style.ERROR("not installed")
            backend = ServerRegistry.get(name)
            features = []
            if backend.supports_http2:
                features.append("http2")
            if backend.supports_websockets:
                features.append("websockets")
            feat_str = f" [{', '.join(features)}]" if features else ""
            self.stdout.write(f"  {name:12s} {status}{feat_str}")

        self.stdout.write("")
        return None

    def _detect_app_path(self) -> str:
        """Auto-detect the ASGI application path."""
        try:
            from django.conf import settings

            module = getattr(settings, "SETTINGS_MODULE", "config.settings")
            # config.settings -> config.asgi:application
            package = module.rsplit(".", 1)[0]
            return f"{package}.asgi:application"
        except Exception:
            return "config.asgi:application"

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        return env
