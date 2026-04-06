"""
Acceleration layer — dispatches to Rust extensions when available,
falls back to pure Python implementations otherwise.

Usage:
    from django_matt._accel import HAS_RUST, RadixRouter
"""

from __future__ import annotations

try:
    from django_matt._rust import HAS_RUST_EXTENSIONS as HAS_RUST
    from django_matt._rust import RadixRouter
except ImportError:
    HAS_RUST = False
    RadixRouter = None  # type: ignore[assignment, misc]

__all__ = [
    "HAS_RUST",
    "RadixRouter",
]
