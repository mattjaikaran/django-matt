"""
Acceleration layer — dispatches to Rust extensions when available,
falls back to pure Python implementations otherwise.

Usage:
    from django_matt._accel import HAS_RUST, RadixRouter
    from django_matt._accel import jwt_encode_rust, jwt_decode_rust, jwt_verify_rust
"""

from __future__ import annotations

from collections.abc import Callable

try:
    from django_matt._rust import HAS_RUST_EXTENSIONS as HAS_RUST
    from django_matt._rust import RadixRouter
    from django_matt._rust import jwt_decode as jwt_decode_rust
    from django_matt._rust import jwt_encode as jwt_encode_rust
    from django_matt._rust import jwt_verify as jwt_verify_rust
except ImportError:
    HAS_RUST = False
    RadixRouter = None  # type: ignore[assignment, misc]
    jwt_encode_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    jwt_decode_rust: Callable | None = None  # type: ignore[assignment, no-redef]
    jwt_verify_rust: Callable | None = None  # type: ignore[assignment, no-redef]

__all__ = [
    "HAS_RUST",
    "RadixRouter",
    "jwt_decode_rust",
    "jwt_encode_rust",
    "jwt_verify_rust",
]
