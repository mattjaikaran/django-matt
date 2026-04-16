"""
Notification API controllers.

Includes:
- Notification listing and management
- Mark as read
- Preferences
"""

import asyncio

from django.db import models
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import delete, get, patch, post
from django_matt.streaming import event as sse_event
from django_matt.streaming import sse_response

from core.models import Membership, Organization
from notifications.models import Notification, NotificationPreference
from notifications.schemas import (
    NotificationCountResponse,
    NotificationListResponse,
    NotificationMarkAllReadRequest,
    NotificationMarkReadRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
)


class NotificationController(APIController):
    prefix = "/notifications"
    tags = ["Notifications"]

    # =========================================================================
    # Notifications
    # =========================================================================

    @get("/")
    @jwt_required
    async def list_notifications(self, request) -> dict:
        """List notifications for the current user."""
        org_slug = request.GET.get("org_slug")
        unread_only = request.GET.get("unread_only", "").lower() == "true"
        page = int(request.GET.get("page", "1"))
        page_size = int(request.GET.get("page_size", "20"))

        queryset = Notification.objects.filter(user=request.user)

        # Filter by organization if specified
        if org_slug:
            try:
                org = await Organization.objects.aget(slug=org_slug)
                # Verify membership
                is_member = await Membership.objects.filter(
                    user=request.user,
                    organization=org,
                    is_active=True,
                ).aexists()
                if not is_member:
                    return {"error": "Not a member of this organization"}, 403
                queryset = queryset.filter(organization=org)
            except Organization.DoesNotExist:
                return {"error": "Organization not found"}, 404

        # Filter by read status
        if unread_only:
            queryset = queryset.filter(is_read=False)

        # Get total and unread counts
        total = await queryset.acount()
        unread_count = await queryset.filter(is_read=False).acount()

        # Paginate
        offset = (page - 1) * page_size
        queryset = queryset.select_related("actor").order_by("-created_at")[offset:offset + page_size]

        items = []
        async for notification in queryset:
            items.append(NotificationResponse.model_validate(notification))

        return NotificationListResponse(
            items=items,
            total=total,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
        )

    @get("/count")
    @jwt_required
    async def get_notification_count(self, request) -> dict:
        """Get notification counts for the current user."""
        org_slug = request.GET.get("org_slug")
        queryset = Notification.objects.filter(user=request.user)

        if org_slug:
            try:
                org = await Organization.objects.aget(slug=org_slug)
                queryset = queryset.filter(organization=org)
            except Organization.DoesNotExist:
                pass

        total = await queryset.acount()
        unread = await queryset.filter(is_read=False).acount()

        # Count by type
        by_type = {}
        async for item in queryset.filter(is_read=False).values("type").annotate(count=models.Count("id")):
            by_type[item["type"]] = item["count"]

        return NotificationCountResponse(
            total=total,
            unread=unread,
            by_type=by_type,
        )

    @get("/<str:notification_id>")
    @jwt_required
    async def get_notification(self, request, notification_id: str) -> dict:
        """Get notification details."""
        try:
            notification = await Notification.objects.select_related("actor").aget(
                id=notification_id,
                user=request.user,
            )
            return NotificationResponse.model_validate(notification)
        except Notification.DoesNotExist:
            return {"error": "Notification not found"}, 404

    @post("/mark-read")
    @jwt_required
    async def mark_notifications_read(self, request, data: NotificationMarkReadRequest) -> dict:
        """Mark specific notifications as read."""
        await Notification.objects.filter(
            id__in=data.notification_ids,
            user=request.user,
            is_read=False,
        ).aupdate(is_read=True)

        return {"marked": len(data.notification_ids)}

    @post("/mark-all-read")
    @jwt_required
    async def mark_all_read(self, request, data: NotificationMarkAllReadRequest) -> dict:
        """Mark all notifications as read."""
        queryset = Notification.objects.filter(user=request.user, is_read=False)

        if data.organization_id:
            queryset = queryset.filter(organization_id=data.organization_id)

        count = await queryset.aupdate(is_read=True)

        return {"marked": count}

    @delete("/<str:notification_id>")
    @jwt_required
    async def delete_notification(self, request, notification_id: str) -> dict:
        """Delete a notification."""
        try:
            notification = await Notification.objects.aget(
                id=notification_id,
                user=request.user,
            )
            await notification.adelete()
            return {"message": "Notification deleted"}
        except Notification.DoesNotExist:
            return {"error": "Notification not found"}, 404

    # =========================================================================
    # SSE Streaming
    # =========================================================================

    @get("/stream")
    @jwt_required
    async def stream_notifications(self, request):
        """Stream new notifications via SSE."""
        async def generate():
            last_check = timezone.now()
            while True:
                new_notifs = []
                async for n in Notification.objects.filter(
                    user=request.user,
                    created_at__gt=last_check,
                    is_read=False,
                ).order_by("-created_at")[:10]:
                    new_notifs.append({
                        "id": str(n.id),
                        "title": n.title,
                        "message": n.message,
                        "type": n.type,
                        "created_at": n.created_at.isoformat(),
                    })
                if new_notifs:
                    yield sse_event(new_notifs, event_type="notifications")
                last_check = timezone.now()
                await asyncio.sleep(3)

        return sse_response(generate())

    # =========================================================================
    # Preferences
    # =========================================================================

    @get("/preferences")
    @jwt_required
    async def get_preferences(self, request) -> dict:
        """Get notification preferences for the current user."""
        preference, created = await NotificationPreference.objects.aget_or_create(
            user=request.user,
            defaults={
                "email_enabled": True,
                "email_digest": "instant",
                "push_enabled": True,
                "in_app_enabled": True,
            },
        )
        return NotificationPreferenceResponse.model_validate(preference)

    @patch("/preferences")
    @jwt_required
    async def update_preferences(self, request, data: NotificationPreferenceUpdate) -> dict:
        """Update notification preferences."""
        preference, _ = await NotificationPreference.objects.aget_or_create(
            user=request.user,
            defaults={
                "email_enabled": True,
                "email_digest": "instant",
                "push_enabled": True,
                "in_app_enabled": True,
            },
        )

        # Update fields
        update_data = data.model_dump(exclude_unset=True)

        # Handle type preferences merge
        if "type_preferences" in update_data:
            type_prefs = update_data.pop("type_preferences")
            preference.type_preferences = {**preference.type_preferences, **type_prefs}

        for field, value in update_data.items():
            setattr(preference, field, value)

        await preference.asave()

        return NotificationPreferenceResponse.model_validate(preference)
