"""Robyn server backend (experimental, Rust-powered)."""

from __future__ import annotations

import importlib.util
from typing import Any

from django_matt.servers.base import ServerBackend


class RobynBackend(ServerBackend):
    """Robyn — Rust-powered async Python web server.

    Requires the ``robyn`` package: ``uv add robyn``

    Note: experimental. Robyn natively runs its own router, but can serve
    ASGI apps via ``robyn --asgi``. Check Robyn docs for ASGI compatibility.
    """

    name = "robyn"
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

        cmd = [
            "robyn",
            app_path,
            "--host",
            host,
            "--port",
            str(port),
            "--processes",
            str(workers),
        ]

        log_level = kwargs.get("log_level", "info")
        cmd.extend(["--log-level", log_level])

        return cmd

    def get_config(self, settings: dict[str, Any]) -> dict[str, Any]:
        workers = self.resolve_workers(settings.get("workers"))
        return {
            "host": settings.get("host", "0.0.0.0"),
            "port": settings.get("port", 8000),
            "processes": workers,
            "log_level": "info" if settings.get("access_log", True) else "warning",
        }

    def check_available(self) -> bool:
        return importlib.util.find_spec("robyn") is not None
