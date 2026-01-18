"""
Audit logging decorators.

Decorators for logging specific actions on views/functions.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from .enums import AuditAction, AuditSeverity


def log_action(
    action: AuditAction | str = AuditAction.CUSTOM,
    description: str = "",
    severity: AuditSeverity = AuditSeverity.INFO,
    include_args: bool = False,
    include_result: bool = False,
    log_on_error: bool = True,
    error_severity: AuditSeverity = AuditSeverity.ERROR,
):
    """
    Decorator to log when a function/view is called.

    Usage:
        @api.post("/articles/{id}/publish")
        @log_action(AuditAction.CUSTOM, description="Published article")
        async def publish_article(request, id: int):
            ...

        @log_action("user.deactivate", severity=AuditSeverity.WARNING)
        def deactivate_user(user_id: int):
            ...

    Args:
        action: The action type (AuditAction or custom string)
        description: Human-readable description (can include {arg_name} placeholders)
        severity: Severity level for successful calls
        include_args: Include function arguments in metadata
        include_result: Include function return value in metadata
        log_on_error: Also log when function raises an exception
        error_severity: Severity level for errors
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            from .models import AuditLog

            # Build metadata
            metadata = _build_metadata(func, args, kwargs, include_args)

            # Format description with args
            desc = _format_description(description, func, args, kwargs)

            try:
                result = await func(*args, **kwargs)

                # Log success
                if include_result:
                    metadata["result"] = _safe_serialize(result)

                await AuditLog.alog(
                    action=action if isinstance(action, AuditAction) else AuditAction.CUSTOM,
                    description=desc or f"Called {func.__name__}",
                    severity=severity,
                    metadata={
                        **metadata,
                        "action_name": str(action),
                        "function": func.__name__,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                if log_on_error:
                    await AuditLog.alog(
                        action=action if isinstance(action, AuditAction) else AuditAction.CUSTOM,
                        description=desc or f"Failed: {func.__name__}",
                        severity=error_severity,
                        metadata={
                            **metadata,
                            "action_name": str(action),
                            "function": func.__name__,
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            from .models import AuditLog

            metadata = _build_metadata(func, args, kwargs, include_args)
            desc = _format_description(description, func, args, kwargs)

            try:
                result = func(*args, **kwargs)

                if include_result:
                    metadata["result"] = _safe_serialize(result)

                AuditLog.log(
                    action=action if isinstance(action, AuditAction) else AuditAction.CUSTOM,
                    description=desc or f"Called {func.__name__}",
                    severity=severity,
                    metadata={
                        **metadata,
                        "action_name": str(action),
                        "function": func.__name__,
                        "success": True,
                    },
                )

                return result

            except Exception as e:
                if log_on_error:
                    AuditLog.log(
                        action=action if isinstance(action, AuditAction) else AuditAction.CUSTOM,
                        description=desc or f"Failed: {func.__name__}",
                        severity=error_severity,
                        metadata={
                            **metadata,
                            "action_name": str(action),
                            "function": func.__name__,
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )
                raise

        return async_wrapper if is_async else sync_wrapper

    return decorator


def audit_action(
    action: AuditAction | str,
    description: str = "",
    **audit_kwargs,
):
    """
    Shortcut decorator for common audit actions.

    Usage:
        @audit_action(AuditAction.EXPORT, "Exported user data")
        def export_users():
            ...
    """
    return log_action(action=action, description=description, **audit_kwargs)


def skip_audit(func: Callable) -> Callable:
    """
    Decorator to skip audit logging for a function.

    Useful when you want to temporarily disable auditing
    or for functions that shouldn't be logged.

    Usage:
        @skip_audit
        def internal_function():
            # This won't be logged even if called from audited code
            ...
    """
    func._skip_audit = True
    return func


class AuditLogContext:
    """
    Context manager for grouping multiple operations under one audit entry.

    Usage:
        with AuditLogContext(action=AuditAction.BULK_UPDATE) as ctx:
            ctx.add_change("user", user.id, {"status": "active"})
            ctx.add_change("subscription", sub.id, {"active": True})
            # All changes logged as one entry when context exits
    """

    def __init__(
        self,
        action: AuditAction = AuditAction.CUSTOM,
        description: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        user=None,
    ):
        self.action = action
        self.description = description
        self.severity = severity
        self.user = user
        self.changes: list[dict] = []
        self.metadata: dict = {}

    def add_change(
        self,
        model_name: str,
        object_id: Any,
        changes: dict,
    ) -> None:
        """Add a change to be logged."""
        self.changes.append(
            {
                "model": model_name,
                "id": str(object_id),
                "changes": changes,
            }
        )

    def add_metadata(self, **kwargs) -> None:
        """Add metadata to the audit entry."""
        self.metadata.update(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from .context import get_current_user
        from .models import AuditLog

        if exc_type is not None:
            # Log error
            AuditLog.log(
                action=self.action,
                user=self.user or get_current_user(),
                description=f"{self.description} (failed)",
                severity=AuditSeverity.ERROR,
                metadata={
                    **self.metadata,
                    "changes": self.changes,
                    "error": str(exc_val),
                    "error_type": exc_type.__name__,
                },
            )
        elif self.changes:
            # Log success
            AuditLog.log(
                action=self.action,
                user=self.user or get_current_user(),
                description=self.description,
                severity=self.severity,
                metadata={
                    **self.metadata,
                    "changes": self.changes,
                    "count": len(self.changes),
                },
            )

        return False  # Don't suppress exceptions


class AsyncAuditLogContext:
    """Async version of AuditLogContext."""

    def __init__(
        self,
        action: AuditAction = AuditAction.CUSTOM,
        description: str = "",
        severity: AuditSeverity = AuditSeverity.INFO,
        user=None,
    ):
        self.action = action
        self.description = description
        self.severity = severity
        self.user = user
        self.changes: list[dict] = []
        self.metadata: dict = {}

    def add_change(self, model_name: str, object_id: Any, changes: dict) -> None:
        self.changes.append(
            {
                "model": model_name,
                "id": str(object_id),
                "changes": changes,
            }
        )

    def add_metadata(self, **kwargs) -> None:
        self.metadata.update(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        from .context import get_current_user
        from .models import AuditLog

        if exc_type is not None:
            await AuditLog.alog(
                action=self.action,
                user=self.user or get_current_user(),
                description=f"{self.description} (failed)",
                severity=AuditSeverity.ERROR,
                metadata={
                    **self.metadata,
                    "changes": self.changes,
                    "error": str(exc_val),
                    "error_type": exc_type.__name__,
                },
            )
        elif self.changes:
            await AuditLog.alog(
                action=self.action,
                user=self.user or get_current_user(),
                description=self.description,
                severity=self.severity,
                metadata={
                    **self.metadata,
                    "changes": self.changes,
                    "count": len(self.changes),
                },
            )

        return False


def _build_metadata(
    func: Callable,
    args: tuple,
    kwargs: dict,
    include_args: bool,
) -> dict:
    """Build metadata dict from function call."""
    metadata = {
        "module": func.__module__,
    }

    if include_args:
        # Get argument names
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Map positional args to names
        arg_dict = {}
        for i, arg in enumerate(args):
            if i < len(params):
                arg_dict[params[i]] = _safe_serialize(arg)

        # Add keyword args
        for key, value in kwargs.items():
            arg_dict[key] = _safe_serialize(value)

        # Remove request objects
        arg_dict.pop("request", None)
        arg_dict.pop("self", None)

        metadata["arguments"] = arg_dict

    return metadata


def _format_description(
    description: str,
    func: Callable,
    args: tuple,
    kwargs: dict,
) -> str:
    """Format description string with argument values."""
    if not description or "{" not in description:
        return description

    try:
        # Get argument names
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Build format dict
        format_dict = {}
        for i, arg in enumerate(args):
            if i < len(params):
                format_dict[params[i]] = arg

        format_dict.update(kwargs)

        return description.format(**format_dict)
    except (KeyError, IndexError):
        return description


def _safe_serialize(value: Any) -> Any:
    """Safely serialize a value for JSON storage."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "pk"):  # Model instance
        return f"{value.__class__.__name__}(pk={value.pk})"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value[:10]]  # Limit list size
    if isinstance(value, dict):
        return {k: _safe_serialize(v) for k, v in list(value.items())[:20]}
    return str(value)[:200]  # Limit string length
