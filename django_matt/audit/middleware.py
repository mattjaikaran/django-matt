"""
Audit middleware.

Captures request context for audit logging.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional, TYPE_CHECKING

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from .context import (
    set_audit_context,
    clear_audit_context,
    extract_client_ip,
    extract_user_agent,
)

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


@dataclass
class AuditContext:
    """
    Container for audit context data.

    Can be accessed via request.audit_context
    """

    user: Any = None
    ip_address: str = ""
    user_agent: str = ""
    request_method: str = ""
    request_path: str = ""
    session_key: Optional[str] = None
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware that captures request context for audit logging.

    Add to MIDDLEWARE to enable automatic context capture:

        MIDDLEWARE = [
            ...
            'django_matt.audit.AuditMiddleware',
        ]

    Configuration via settings.py:

        AUDIT_MIDDLEWARE = {
            "LOG_REQUESTS": True,  # Log all API requests
            "LOG_RESPONSES": False,  # Log response data
            "EXCLUDE_PATHS": ["/health", "/metrics"],  # Paths to skip
            "EXCLUDE_METHODS": ["OPTIONS", "HEAD"],  # Methods to skip
            "SENSITIVE_FIELDS": ["password", "token"],  # Fields to mask
        }
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self._config = getattr(settings, "AUDIT_MIDDLEWARE", {})

    def __call__(self, request: "HttpRequest") -> "HttpResponse":
        """Process request and capture audit context."""
        # Extract context from request
        ip_address = extract_client_ip(request)
        user_agent = extract_user_agent(request)
        user = getattr(request, "user", None)

        # Check if user is authenticated
        if user and not user.is_authenticated:
            user = None

        # Create audit context object
        audit_ctx = AuditContext(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_path=request.path,
            session_key=request.session.session_key if hasattr(request, "session") else None,
        )

        # Attach to request for easy access
        request.audit_context = audit_ctx

        # Set thread-local context
        set_audit_context(
            user=user,
            request=request,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_path=request.path,
        )

        try:
            # Check if we should log this request
            if self._should_log_request(request):
                self._log_request(request, audit_ctx)

            # Process the request
            response = self.get_response(request)

            # Log response if configured
            if self._config.get("LOG_RESPONSES", False):
                self._log_response(request, response, audit_ctx)

            return response

        finally:
            # Always clear context
            clear_audit_context()

    def _should_log_request(self, request: "HttpRequest") -> bool:
        """Determine if this request should be logged."""
        if not self._config.get("LOG_REQUESTS", False):
            return False

        # Check excluded paths
        exclude_paths = self._config.get("EXCLUDE_PATHS", [])
        if any(request.path.startswith(p) for p in exclude_paths):
            return False

        # Check excluded methods
        exclude_methods = self._config.get("EXCLUDE_METHODS", ["OPTIONS", "HEAD"])
        if request.method in exclude_methods:
            return False

        return True

    def _log_request(self, request: "HttpRequest", ctx: AuditContext) -> None:
        """Log an API request."""
        from .models import AuditLog
        from .enums import AuditAction, AuditSeverity

        # Build metadata
        metadata = {
            "method": request.method,
            "path": request.path,
            "query_string": request.META.get("QUERY_STRING", ""),
            "content_type": request.content_type,
        }

        # Add headers (excluding sensitive ones)
        safe_headers = {}
        sensitive_headers = {"HTTP_AUTHORIZATION", "HTTP_COOKIE", "HTTP_X_API_KEY"}
        for key, value in request.META.items():
            if key.startswith("HTTP_") and key not in sensitive_headers:
                safe_headers[key[5:].lower().replace("_", "-")] = value
        metadata["headers"] = safe_headers

        AuditLog.log(
            action=AuditAction.API_CALL,
            user=ctx.user,
            description=f"{request.method} {request.path}",
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            request_method=request.method,
            request_path=request.path,
            metadata=metadata,
            severity=AuditSeverity.DEBUG,
        )

    def _log_response(
        self, request: "HttpRequest", response: "HttpResponse", ctx: AuditContext
    ) -> None:
        """Log response details."""
        # This is typically disabled for performance
        # Can be enabled for debugging or compliance
        pass


class AsyncAuditMiddleware:
    """
    Async version of AuditMiddleware.

    Use this for ASGI applications.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self._config = getattr(settings, "AUDIT_MIDDLEWARE", {})

    async def __call__(self, request: "HttpRequest") -> "HttpResponse":
        """Process request asynchronously."""
        # Extract context
        ip_address = extract_client_ip(request)
        user_agent = extract_user_agent(request)
        user = getattr(request, "user", None)

        if user and hasattr(user, "is_authenticated"):
            if not user.is_authenticated:
                user = None

        # Create context
        audit_ctx = AuditContext(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_path=request.path,
        )

        request.audit_context = audit_ctx

        set_audit_context(
            user=user,
            request=request,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_path=request.path,
        )

        try:
            response = await self.get_response(request)
            return response
        finally:
            clear_audit_context()


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Lightweight middleware that only logs requests without full audit context.

    Useful when you just need request logging without the full audit system.

    Configuration:
        REQUEST_LOGGING = {
            "ENABLED": True,
            "LOG_BODY": False,
            "MAX_BODY_LENGTH": 1000,
            "EXCLUDE_PATHS": ["/health"],
        }
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self._config = getattr(settings, "REQUEST_LOGGING", {})

    def __call__(self, request: "HttpRequest") -> "HttpResponse":
        if not self._config.get("ENABLED", True):
            return self.get_response(request)

        import logging
        import time

        logger = logging.getLogger("django_matt.audit.requests")

        # Skip excluded paths
        exclude_paths = self._config.get("EXCLUDE_PATHS", [])
        if any(request.path.startswith(p) for p in exclude_paths):
            return self.get_response(request)

        start_time = time.time()
        ip_address = extract_client_ip(request)

        response = self.get_response(request)

        duration = (time.time() - start_time) * 1000  # ms

        # Log the request
        user = getattr(request, "user", None)
        user_str = str(user) if user and user.is_authenticated else "anonymous"

        logger.info(
            f"{request.method} {request.path} - "
            f"{response.status_code} - "
            f"{duration:.2f}ms - "
            f"{user_str} - "
            f"{ip_address}"
        )

        return response
