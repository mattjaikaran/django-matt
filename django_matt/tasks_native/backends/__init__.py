"""
Task backends for the native task engine.

Provides multiple backend implementations:
- DjangoNativeBackend: Django 6.0+ native tasks (preferred)
- CeleryNativeBackend: Celery compatibility layer
- DramatiqNativeBackend: Dramatiq compatibility layer
- DjangoQNativeBackend: Django-Q2 compatibility layer
- SyncNativeBackend: Synchronous execution (development)
"""

from .base import BaseNativeBackend
from .sync import SyncNativeBackend

__all__ = [
    "BaseNativeBackend",
    "SyncNativeBackend",
]


def __getattr__(name: str):
    """Lazy load backend classes to avoid import errors when dependencies missing."""
    if name == "DjangoNativeBackend":
        from .django_native import DjangoNativeBackend

        return DjangoNativeBackend
    if name == "CeleryNativeBackend":
        from .celery_compat import CeleryNativeBackend

        return CeleryNativeBackend
    if name == "DramatiqNativeBackend":
        from .dramatiq_compat import DramatiqNativeBackend

        return DramatiqNativeBackend
    if name == "DjangoQNativeBackend":
        from .django_q_compat import DjangoQNativeBackend

        return DjangoQNativeBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
