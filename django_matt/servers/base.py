"""Abstract base class for server backends."""

from __future__ import annotations

import multiprocessing
from abc import ABC, abstractmethod
from typing import Any


class ServerBackend(ABC):
    """Base class for production server backends."""

    name: str
    supports_http2: bool = False
    supports_http3: bool = False
    supports_websockets: bool = False

    @abstractmethod
    def get_command(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build the CLI command to start this server.

        Args:
            host: Bind address.
            port: Bind port.
            workers: Number of worker processes. None = auto-detect.
            **kwargs: Backend-specific options.

        Returns:
            Command as a list of strings (subprocess-ready).
        """
        ...

    @abstractmethod
    def get_config(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Map django-matt MATT_SERVER settings to backend-native config.

        Args:
            settings: The MATT_SERVER dict from Django settings.

        Returns:
            Backend-native configuration dict.
        """
        ...

    @abstractmethod
    def check_available(self) -> bool:
        """Return True if this backend's package is importable."""
        ...

    @staticmethod
    def auto_workers() -> int:
        """Calculate worker count: 2 * cpu_count + 1 (gunicorn formula)."""
        try:
            cpus = multiprocessing.cpu_count()
        except NotImplementedError:
            cpus = 1
        return 2 * cpus + 1

    def resolve_workers(self, workers: int | str | None) -> int:
        """Resolve worker count from value or 'auto'."""
        if workers is None or workers == "auto":
            return self.auto_workers()
        return int(workers)
