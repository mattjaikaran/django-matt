"""Granian server backend (Rust-powered, HTTP/2 + HTTP/3 capable).

Granian is a Rust HTTP server with ASGI/RSGI/WSGI support. Each worker
process runs in complete isolation — no shared memory, no coordinating
locks, no cross-worker state. This shared-nothing architecture (Stage 21E)
means:

- Each worker has its own Python interpreter, its own Rust router, and
  its own response cache.
- No cache-coherency protocol is needed because workers never share state.
- Scale out by adding workers; each adds linear throughput.
- Failure isolation: a crashed worker affects only its in-flight requests.

This is the same architecture that powers production deployments of
FastAPI, Litestar, and other ASGI frameworks on top of Uvicorn/Gunicorn
--- Granian just replaces the Python event loop with a Rust one.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from django_matt.servers.base import ServerBackend


class GranianBackend(ServerBackend):
    """Granian --- Rust HTTP server with ASGI/RSGI/WSGI support.

    Requires the ``granian`` package: ``uv add granian``

    Supports HTTP/2, HTTP/3, multiple threading modes, and is a drop-in
    replacement for gunicorn+uvicorn with potentially better throughput.
    """

    name = "granian"
    supports_http2 = True
    supports_http3 = True
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
        http2 = kwargs.get("http2", False)
        http3 = kwargs.get("http3", False)
        ssl_cert = kwargs.get("ssl_cert")
        ssl_key = kwargs.get("ssl_key")
        threading_mode = kwargs.get("threading_mode", "workers")
        access_log = kwargs.get("access_log", True)

        cmd = [
            "granian",
            "--interface",
            "asgi",
            "--host",
            host,
            "--port",
            str(port),
            "--workers",
            str(workers),
            "--threading-mode",
            threading_mode,
            app_path,
        ]

        if http3:
            # HTTP/3 requires QUIC, which Granian supports via --http 3
            cmd.extend(["--http", "3"])
        elif http2:
            cmd.append("--http2")

        if not access_log:
            cmd.extend(["--log-level", "warning"])

        if ssl_cert and ssl_key:
            cmd.extend(["--ssl-certificate", ssl_cert, "--ssl-keyfile", ssl_key])

        return cmd

    def get_config(self, settings: dict[str, Any]) -> dict[str, Any]:
        workers = self.resolve_workers(settings.get("workers"))
        return {
            "interface": "asgi",
            "host": settings.get("host", "0.0.0.0"),
            "port": settings.get("port", 8000),
            "workers": workers,
            "threading_mode": settings.get("threading_mode", "workers"),
            "http2": settings.get("http2", False),
            "http3": settings.get("http3", False),
            "ssl_certificate": settings.get("ssl_cert"),
            "ssl_keyfile": settings.get("ssl_key"),
            "log_level": "info" if settings.get("access_log", True) else "warning",
        }

    def check_available(self) -> bool:
        return importlib.util.find_spec("granian") is not None
