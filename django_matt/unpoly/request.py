"""
Unpoly request detection and information.

Provides utilities for detecting Unpoly requests and accessing
X-Up-* request headers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest

import orjson


@dataclass
class UnpolyDetails:
    """
    Unpoly request details extracted from X-Up-* headers.

    Attributes:
        target: CSS selector being updated (X-Up-Target)
        fail_target: CSS selector for failed responses (X-Up-Fail-Target)
        mode: Layer mode — root, modal, drawer, popup, cover (X-Up-Mode)
        fail_mode: Layer mode for failed responses (X-Up-Fail-Mode)
        validate: Field name being validated (X-Up-Validate)
        context: Layer context data (X-Up-Context, JSON-decoded)
        version: Unpoly version on the client (X-Up-Version)
        is_unpoly: Whether this is an Unpoly request
        is_validating: Whether this is a validation request
    """

    target: str | None = None
    fail_target: str | None = None
    mode: str | None = None
    fail_mode: str | None = None
    validate: str | None = None
    context: dict[str, Any] | None = None
    version: str | None = None
    is_unpoly: bool = False
    is_validating: bool = False

    @classmethod
    def from_request(cls, request: HttpRequest) -> UnpolyDetails:
        """Extract Unpoly details from a Django request."""
        target = request.headers.get("X-Up-Target")
        validate = request.headers.get("X-Up-Validate")

        context_raw = request.headers.get("X-Up-Context")
        context: dict[str, Any] | None = None
        if context_raw:
            try:
                context = orjson.loads(context_raw)
            except (orjson.JSONDecodeError, TypeError):
                context = None

        return cls(
            target=target,
            fail_target=request.headers.get("X-Up-Fail-Target"),
            mode=request.headers.get("X-Up-Mode"),
            fail_mode=request.headers.get("X-Up-Fail-Mode"),
            validate=validate,
            context=context,
            version=request.headers.get("X-Up-Version"),
            is_unpoly=target is not None,
            is_validating=validate is not None,
        )

    def __bool__(self) -> bool:
        """Allow using UnpolyDetails in boolean context."""
        return self.is_unpoly


def is_unpoly_request(request: HttpRequest) -> bool:
    """Check if a request is an Unpoly request."""
    return request.headers.get("X-Up-Target") is not None


def get_up_target(request: HttpRequest) -> str | None:
    """Get the target selector from an Unpoly request."""
    return request.headers.get("X-Up-Target")


def get_up_mode(request: HttpRequest) -> str | None:
    """Get the layer mode from an Unpoly request."""
    return request.headers.get("X-Up-Mode")


def get_up_validate(request: HttpRequest) -> str | None:
    """Get the field being validated from an Unpoly request."""
    return request.headers.get("X-Up-Validate")


__all__ = [
    "UnpolyDetails",
    "get_up_mode",
    "get_up_target",
    "get_up_validate",
    "is_unpoly_request",
]
