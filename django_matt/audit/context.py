"""
Audit context management.

Provides thread-local storage for request context (user, IP, etc.)
that can be accessed from anywhere during request processing.
"""

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import HttpRequest


@dataclass
class AuditContextData:
    """Container for audit context data."""

    user: Optional["AbstractUser"] = None
    request: Optional["HttpRequest"] = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    extra: dict = field(default_factory=dict)


# Context variable for async-safe storage
_audit_context: contextvars.ContextVar[AuditContextData | None] = contextvars.ContextVar(
    "audit_context", default=None
)


def get_audit_context() -> AuditContextData | None:
    """Get the current audit context."""
    return _audit_context.get()


def set_audit_context(
    user: Optional["AbstractUser"] = None,
    request: Optional["HttpRequest"] = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_method: str | None = None,
    request_path: str | None = None,
    **extra,
) -> AuditContextData:
    """
    Set the audit context.

    Typically called by middleware at the start of request processing.
    """
    ctx = AuditContextData(
        user=user,
        request=request,
        ip_address=ip_address,
        user_agent=user_agent,
        request_method=request_method,
        request_path=request_path,
        extra=extra,
    )
    _audit_context.set(ctx)
    return ctx


def clear_audit_context() -> None:
    """Clear the audit context."""
    _audit_context.set(None)


def get_current_user() -> Optional["AbstractUser"]:
    """Get the current user from audit context."""
    ctx = get_audit_context()
    if ctx and ctx.user:
        return ctx.user
    return None


def get_current_request() -> Optional["HttpRequest"]:
    """Get the current request from audit context."""
    ctx = get_audit_context()
    if ctx:
        return ctx.request
    return None


def get_request_ip() -> str | None:
    """Get the client IP address from audit context."""
    ctx = get_audit_context()
    if ctx:
        return ctx.ip_address
    return None


def get_user_agent() -> str | None:
    """Get the User-Agent from audit context."""
    ctx = get_audit_context()
    if ctx:
        return ctx.user_agent
    return None


def get_request_method() -> str | None:
    """Get the HTTP method from audit context."""
    ctx = get_audit_context()
    if ctx:
        return ctx.request_method
    return None


def get_request_path() -> str | None:
    """Get the request path from audit context."""
    ctx = get_audit_context()
    if ctx:
        return ctx.request_path
    return None


def update_audit_context(**kwargs) -> None:
    """Update specific fields in the audit context."""
    ctx = get_audit_context()
    if ctx:
        for key, value in kwargs.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
            else:
                ctx.extra[key] = value


@contextmanager
def audit_context(
    user: Optional["AbstractUser"] = None,
    request: Optional["HttpRequest"] = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    **extra,
):
    """
    Context manager for setting audit context.

    Usage:
        with audit_context(user=user, ip_address="127.0.0.1"):
            # All audit logs in this block will use this context
            my_model.save()  # Will log with the specified user/IP
    """
    token = _audit_context.set(
        AuditContextData(
            user=user,
            request=request,
            ip_address=ip_address,
            user_agent=user_agent,
            extra=extra,
        )
    )
    try:
        yield
    finally:
        _audit_context.reset(token)


def extract_client_ip(request: "HttpRequest") -> str:
    """
    Extract client IP address from request.

    Handles X-Forwarded-For and other proxy headers.
    """
    # Check for forwarded headers (in order of preference)
    forwarded_headers = [
        "HTTP_X_FORWARDED_FOR",
        "HTTP_X_REAL_IP",
        "HTTP_CF_CONNECTING_IP",  # Cloudflare
        "HTTP_TRUE_CLIENT_IP",  # Akamai
    ]

    for header in forwarded_headers:
        value = request.META.get(header)
        if value:
            # X-Forwarded-For can contain multiple IPs, take the first
            ip = value.split(",")[0].strip()
            if ip:
                return ip

    # Fall back to REMOTE_ADDR
    return request.META.get("REMOTE_ADDR", "")


def extract_user_agent(request: "HttpRequest") -> str:
    """Extract User-Agent from request."""
    return request.META.get("HTTP_USER_AGENT", "")
