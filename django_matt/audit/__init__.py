"""
Operational Audit Logging — model change tracking and user action history.

This module tracks WHO did WHAT to WHICH model at runtime:
creates, updates, deletes, logins, permission changes, etc.

For codebase quality auditing (security scans, performance analysis,
scalability checks), see the sibling package: django_matt.audits

Disambiguation:
  - django_matt.audit.AuditSeverity = operational log level (DEBUG..CRITICAL)
  - django_matt.audits.AuditSeverity = code-quality finding severity (LOW..CRITICAL)
  - Prefer aliases: LogSeverity, LogAction
"""

"""
Provides comprehensive audit logging for Django applications including:
- Model change tracking (create, update, delete)
- User action logging
- Request context capture (IP, User-Agent)
- Query utilities for audit history

Usage:
    # In models.py - automatic change tracking
    from django_matt.audit import AuditableMixin

    class Article(AuditableMixin, models.Model):
        title = models.CharField(max_length=200)
        content = models.TextField()

    # In settings.py - enable middleware
    MIDDLEWARE = [
        ...
        'django_matt.audit.AuditMiddleware',
    ]

    # Manual action logging
    from django_matt.audit import log_action, AuditAction

    @api.post("/articles/{id}/publish")
    @log_action(AuditAction.CUSTOM, description="Published article")
    async def publish_article(request, id: int):
        ...

    # Query audit history
    from django_matt.audit import get_audit_history

    history = get_audit_history(article)
    user_actions = get_user_actions(user, days=30)
"""

from .context import (
    audit_context,
    clear_audit_context,
    get_current_request,
    get_current_user,
    get_request_ip,
    get_user_agent,
    set_audit_context,
)
from .decorators import audit_action, log_action, skip_audit
from .enums import AuditAction, LogAction, LogSeverity
from .middleware import AuditContext, AuditMiddleware
from .mixins import AuditableManager, AuditableMixin, AuditableQuerySet
from .models import AuditLog
from .signals import (
    connect_audit_signals,
    disconnect_audit_signals,
    post_audit,
    pre_audit,
)
from .utils import (
    cleanup_old_logs,
    export_audit_logs,
    get_audit_history,
    get_model_changes,
    get_recent_activity,
    get_user_actions,
)

__all__ = [
    # Enums
    "AuditAction",
    "LogAction",
    "LogSeverity",
    # Models
    "AuditLog",
    # Mixins
    "AuditableMixin",
    "AuditableQuerySet",
    "AuditableManager",
    # Middleware
    "AuditMiddleware",
    "AuditContext",
    # Context
    "get_current_user",
    "get_current_request",
    "get_request_ip",
    "get_user_agent",
    "set_audit_context",
    "clear_audit_context",
    "audit_context",
    # Decorators
    "log_action",
    "audit_action",
    "skip_audit",
    # Signals
    "pre_audit",
    "post_audit",
    "connect_audit_signals",
    "disconnect_audit_signals",
    # Utilities
    "get_audit_history",
    "get_user_actions",
    "get_model_changes",
    "get_recent_activity",
    "cleanup_old_logs",
    "export_audit_logs",
]
