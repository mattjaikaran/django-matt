"""Uvicorn/Gunicorn server backend (default)."""

from __future__ import annotations

import importlib.util
from typing import Any

from django_matt.servers.base import ServerBackend


class UvicornBackend(ServerBackend):
    """Gunicorn + UvicornWorker — the standard production stack."""

    name = "uvicorn"
    supports_http2 = False
    supports_websockets = True

    def get_command(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int | None = None,
        **kwargs: Any,
    ) -> list[str]:
        workers = self.resolve_workers(workers)
        app_path = kwargs.get("app_path", "config.asgi:application")
        access_log = kwargs.get("access_log", True)
        graceful_timeout = kwargs.get("graceful_timeout", 30)
        ssl_cert = kwargs.get("ssl_cert")
        ssl_key = kwargs.get("ssl_key")

        cmd = [
            "gunicorn",
            app_path,
            "--worker-class",
            "uvicorn.workers.UvicornWorker",
            "--bind",
            f"{host}:{port}",
            "--workers",
            str(workers),
            "--graceful-timeout",
            str(graceful_timeout),
        ]

        if not access_log:
            cmd.append("--no-access-log")

        if ssl_cert and ssl_key:
            cmd.extend(["--certfile", ssl_cert, "--keyfile", ssl_key])

        return cmd

    def get_config(self, settings: dict[str, Any]) -> dict[str, Any]:
        workers = self.resolve_workers(settings.get("workers"))
        return {
            "bind": f"{settings.get('host', '0.0.0.0')}:{settings.get('port', 8000)}",
            "workers": workers,
            "worker_class": "uvicorn.workers.UvicornWorker",
            "graceful_timeout": settings.get("graceful_timeout", 30),
            "accesslog": "-" if settings.get("access_log", True) else None,
            "ssl_certfile": settings.get("ssl_cert"),
            "ssl_keyfile": settings.get("ssl_key"),
        }

    def check_available(self) -> bool:
        return (
            importlib.util.find_spec("uvicorn") is not None
            and importlib.util.find_spec("gunicorn") is not None
        )
