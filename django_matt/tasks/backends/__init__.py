"""
Task queue backends.

Provides implementations for different task queue systems.
"""

from .base import BaseBackend
from .celery import CeleryBackend
from .django_q import DjangoQBackend
from .django_workers import DjangoWorkersBackend, auto_detect_backend
from .dramatiq import DramatiqBackend
from .sync import SyncBackend

__all__ = [
    "BaseBackend",
    "CeleryBackend",
    "DjangoQBackend",
    "DjangoWorkersBackend",
    "DramatiqBackend",
    "SyncBackend",
    "auto_detect_backend",
]
