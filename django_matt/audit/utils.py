"""
Audit logging utilities.

Query helpers and utility functions for working with audit logs.
"""

import csv
import io
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count
from django.utils import timezone

from .enums import AuditAction, AuditSeverity

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from .models import AuditLog


def get_audit_history(
    obj: models.Model,
    limit: int | None = None,
    actions: list[AuditAction] | None = None,
) -> models.QuerySet:
    """
    Get audit history for a specific object.

    Args:
        obj: The model instance to get history for
        limit: Maximum number of entries to return
        actions: Filter by specific action types

    Returns:
        QuerySet of AuditLog entries

    Usage:
        article = Article.objects.get(id=1)
        history = get_audit_history(article)
        for entry in history:
            print(f"{entry.created_at}: {entry.action} by {entry.user}")
    """
    from .models import AuditLog

    content_type = ContentType.objects.get_for_model(obj)
    qs = AuditLog.objects.filter(
        content_type=content_type,
        object_id=str(obj.pk),
    ).order_by("-created_at")

    if actions:
        action_values = [a.value for a in actions]
        qs = qs.filter(action__in=action_values)

    if limit:
        qs = qs[:limit]

    return qs


def get_user_actions(
    user: "AbstractUser",
    days: int | None = None,
    actions: list[AuditAction] | None = None,
    limit: int | None = None,
) -> models.QuerySet:
    """
    Get all actions performed by a specific user.

    Args:
        user: The user to get actions for
        days: Limit to last N days
        actions: Filter by specific action types
        limit: Maximum number of entries

    Returns:
        QuerySet of AuditLog entries
    """
    from .models import AuditLog

    qs = AuditLog.objects.filter(user=user).order_by("-created_at")

    if days:
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)

    if actions:
        action_values = [a.value for a in actions]
        qs = qs.filter(action__in=action_values)

    if limit:
        qs = qs[:limit]

    return qs


def get_model_changes(
    model: type[models.Model],
    since: datetime | None = None,
    until: datetime | None = None,
    user: Optional["AbstractUser"] = None,
) -> models.QuerySet:
    """
    Get all changes to a specific model type.

    Args:
        model: The model class to get changes for
        since: Start datetime
        until: End datetime
        user: Filter by user

    Returns:
        QuerySet of AuditLog entries
    """
    from .models import AuditLog

    content_type = ContentType.objects.get_for_model(model)
    qs = AuditLog.objects.filter(content_type=content_type).order_by("-created_at")

    if since:
        qs = qs.filter(created_at__gte=since)
    if until:
        qs = qs.filter(created_at__lte=until)
    if user:
        qs = qs.filter(user=user)

    return qs


def get_recent_activity(
    days: int = 7,
    actions: list[AuditAction] | None = None,
    severity_min: AuditSeverity | None = None,
    limit: int = 100,
) -> models.QuerySet:
    """
    Get recent audit activity across the system.

    Args:
        days: Number of days to look back
        actions: Filter by action types
        severity_min: Minimum severity level
        limit: Maximum entries to return

    Returns:
        QuerySet of AuditLog entries
    """
    from .models import AuditLog

    since = timezone.now() - timedelta(days=days)
    qs = AuditLog.objects.filter(created_at__gte=since).order_by("-created_at")

    if actions:
        action_values = [a.value for a in actions]
        qs = qs.filter(action__in=action_values)

    if severity_min:
        severities = [s.value for s in AuditSeverity if s.level >= severity_min.level]
        qs = qs.filter(severity__in=severities)

    return qs[:limit]


def get_activity_summary(
    days: int = 7,
    group_by: str = "action",
) -> dict[str, int]:
    """
    Get a summary of audit activity.

    Args:
        days: Number of days to look back
        group_by: Field to group by ("action", "user", "model")

    Returns:
        Dict mapping group values to counts
    """
    from .models import AuditLog

    since = timezone.now() - timedelta(days=days)
    qs = AuditLog.objects.filter(created_at__gte=since)

    if group_by == "action":
        results = qs.values("action").annotate(count=Count("id"))
        return {r["action"]: r["count"] for r in results}

    if group_by == "user":
        results = qs.values("user__username").annotate(count=Count("id"))
        return {r["user__username"] or "anonymous": r["count"] for r in results}

    if group_by == "model":
        results = qs.values("content_type__model").annotate(count=Count("id"))
        return {r["content_type__model"] or "none": r["count"] for r in results}

    return {}


def get_security_events(
    days: int = 7,
    include_failed_logins: bool = True,
    include_permission_denied: bool = True,
) -> models.QuerySet:
    """
    Get security-related audit events.

    Args:
        days: Number of days to look back
        include_failed_logins: Include failed login attempts
        include_permission_denied: Include permission denied events

    Returns:
        QuerySet of security-related AuditLog entries
    """
    from .models import AuditLog

    since = timezone.now() - timedelta(days=days)

    actions = []
    if include_failed_logins:
        actions.append(AuditAction.LOGIN_FAILED.value)
    if include_permission_denied:
        actions.append(AuditAction.PERMISSION_DENIED.value)

    # Always include high-severity security actions
    actions.extend(
        [
            AuditAction.PASSWORD_CHANGE.value,
            AuditAction.PASSWORD_RESET.value,
            AuditAction.ROLE_ASSIGNED.value,
            AuditAction.ROLE_REMOVED.value,
            AuditAction.CONFIGURATION_CHANGE.value,
        ]
    )

    return AuditLog.objects.filter(
        created_at__gte=since,
        action__in=actions,
    ).order_by("-created_at")


def get_failed_logins_by_ip(
    days: int = 1,
    threshold: int = 5,
) -> list[dict[str, Any]]:
    """
    Get IP addresses with multiple failed login attempts.

    Useful for detecting brute force attacks.

    Args:
        days: Number of days to look back
        threshold: Minimum failed attempts to include

    Returns:
        List of dicts with IP and count
    """
    from .models import AuditLog

    since = timezone.now() - timedelta(days=days)

    results = (
        AuditLog.objects.filter(
            created_at__gte=since,
            action=AuditAction.LOGIN_FAILED.value,
        )
        .values("ip_address")
        .annotate(count=Count("id"))
        .filter(count__gte=threshold)
        .order_by("-count")
    )

    return [{"ip_address": r["ip_address"], "failed_attempts": r["count"]} for r in results]


def cleanup_old_logs(
    days: int = 90,
    dry_run: bool = True,
) -> int:
    """
    Delete audit logs older than specified days.

    Args:
        days: Delete logs older than this many days
        dry_run: If True, only return count without deleting

    Returns:
        Number of logs deleted (or would be deleted if dry_run)
    """
    from .models import AuditLog

    cutoff = timezone.now() - timedelta(days=days)
    qs = AuditLog.objects.filter(created_at__lt=cutoff)

    count = qs.count()

    if not dry_run:
        qs.delete()

    return count


def export_audit_logs(
    queryset: models.QuerySet | None = None,
    format: str = "json",
    **filters,
) -> str:
    """
    Export audit logs to JSON or CSV format.

    Args:
        queryset: Optional queryset to export (uses filters if not provided)
        format: Export format ("json" or "csv")
        **filters: Filters to apply (days, actions, user_id, model)

    Returns:
        String containing exported data
    """
    from .models import AuditLog

    if queryset is None:
        queryset = AuditLog.objects.all()

        if "days" in filters:
            since = timezone.now() - timedelta(days=filters["days"])
            queryset = queryset.filter(created_at__gte=since)

        if "actions" in filters:
            action_values = [
                a.value if isinstance(a, AuditAction) else a for a in filters["actions"]
            ]
            queryset = queryset.filter(action__in=action_values)

        if "user_id" in filters:
            queryset = queryset.filter(user_id=filters["user_id"])

        if "model" in filters:
            content_type = ContentType.objects.get_for_model(filters["model"])
            queryset = queryset.filter(content_type=content_type)

    queryset = queryset.order_by("-created_at")

    if format == "json":
        return _export_json(queryset)
    if format == "csv":
        return _export_csv(queryset)
    raise ValueError(f"Unknown export format: {format}")


def _export_json(queryset: models.QuerySet) -> str:
    """Export queryset to JSON."""
    data = []

    for log in queryset:
        data.append(
            {
                "id": log.id,
                "action": log.action,
                "severity": log.severity,
                "user": str(log.user) if log.user else None,
                "user_id": log.user_id,
                "object_type": log.content_type.model if log.content_type else None,
                "object_id": log.object_id,
                "object_repr": log.object_repr,
                "description": log.description,
                "changes": log.changes,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "request_method": log.request_method,
                "request_path": log.request_path,
                "metadata": log.metadata,
                "created_at": log.created_at.isoformat(),
            }
        )

    return json.dumps(data, indent=2, default=str)


def _export_csv(queryset: models.QuerySet) -> str:
    """Export queryset to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "id",
            "action",
            "severity",
            "user",
            "object_type",
            "object_id",
            "object_repr",
            "description",
            "ip_address",
            "request_method",
            "request_path",
            "created_at",
        ]
    )

    for log in queryset:
        writer.writerow(
            [
                log.id,
                log.action,
                log.severity,
                str(log.user) if log.user else "",
                log.content_type.model if log.content_type else "",
                log.object_id or "",
                log.object_repr,
                log.description,
                log.ip_address or "",
                log.request_method,
                log.request_path,
                log.created_at.isoformat(),
            ]
        )

    return output.getvalue()


def diff_object_versions(
    obj: models.Model,
    from_log: "AuditLog",
    to_log: "AuditLog",
) -> dict[str, dict[str, Any]]:
    """
    Get the diff between two versions of an object.

    Args:
        obj: The model instance
        from_log: Earlier audit log entry
        to_log: Later audit log entry

    Returns:
        Dict of changes between versions
    """
    old_values = from_log.new_values or from_log.old_values
    new_values = to_log.new_values or to_log.old_values

    changes = {}

    all_fields = set(old_values.keys()) | set(new_values.keys())

    for field in all_fields:
        old = old_values.get(field)
        new = new_values.get(field)

        if old != new:
            changes[field] = {"old": old, "new": new}

    return changes


def restore_object_version(
    obj: models.Model,
    audit_log: "AuditLog",
    save: bool = True,
) -> models.Model:
    """
    Restore an object to a previous version from audit log.

    Args:
        obj: The model instance to restore
        audit_log: The audit log entry with the desired version
        save: Whether to save the restored object

    Returns:
        The restored model instance (may have unsaved changes if save=False)

    Warning:
        This doesn't handle related objects or foreign keys well.
        Use with caution.
    """
    # Get the values from the audit log
    values = audit_log.new_values or audit_log.old_values

    if not values:
        raise ValueError("Audit log has no stored values")

    # Apply values to object
    for field_name, value in values.items():
        if hasattr(obj, field_name):
            try:
                setattr(obj, field_name, value)
            except (TypeError, ValueError):
                # Skip fields that can't be set
                pass

    if save:
        obj.save()

    return obj
