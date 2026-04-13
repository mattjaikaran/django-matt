"""
Production server backends for Django Matt.

Supports uvicorn (default), robyn, and granian as ASGI server backends
with a unified configuration and registry system.

Usage:
    from django_matt.servers import ServerRegistry, get_backend

    # Get configured backend
    backend = get_backend("uvicorn")
    cmd = backend.get_command(host="0.0.0.0", port=8000, workers=4)

    # List available backends
    for name, available in ServerRegistry.list_backends():
        print(f"{name}: {'available' if available else 'not installed'}")
"""

from django_matt.servers.base import ServerBackend
from django_matt.servers.config import ServerConfig, get_server_config
from django_matt.servers.granian_backend import GranianBackend
from django_matt.servers.registry import ServerRegistry, get_backend
from django_matt.servers.robyn_backend import RobynBackend
from django_matt.servers.uvicorn_backend import UvicornBackend

__all__ = [
    "ServerBackend",
    "ServerConfig",
    "ServerRegistry",
    "UvicornBackend",
    "RobynBackend",
    "GranianBackend",
    "get_backend",
    "get_server_config",
]
