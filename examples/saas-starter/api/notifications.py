"""
Notification API controllers.

Includes:
- Notification listing and management
- Mark as read
- Preferences
"""

from uuid import UUID

from django.db import models
from django_matt.auth import jwt_required
from django_matt.core import APIController, api_controller
from django_matt.permissions import IsAuthenticated

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


@api_controller("/notifications", tags=["Notifications"])
class NotificationController(APIController):
    """Notification management endpoints."""

    # =========================================================================
    # Notifications
    # =========================================================================

    @APIController.get("/", response=NotificationListResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def list_notifications(
        self,
        request,
        org_slug: str | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ):
        """
        List notifications for the current user.

        Optionally filter by organization.
        """
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

    @APIController.get("/count", response=NotificationCountResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_notification_count(self, request, org_slug: str | None = None):
        """
        Get notification counts for the current user.
        """
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

    @APIController.get("/{notification_id}", response=NotificationResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_notification(self, request, notification_id: UUID):
        """
        Get notification details.
        """
        try:
            notification = await Notification.objects.select_related("actor").aget(
                id=notification_id,
                user=request.user,
            )
            return NotificationResponse.model_validate(notification)
        except Notification.DoesNotExist:
            return {"error": "Notification not found"}, 404

    @APIController.post("/mark-read", permissions=[IsAuthenticated])
    @jwt_required
    async def mark_notifications_read(self, request, data: NotificationMarkReadRequest):
        """
        Mark specific notifications as read.
        """
        await Notification.objects.filter(
            id__in=data.notification_ids,
            user=request.user,
            is_read=False,
        ).aupdate(is_read=True)

        return {"marked": len(data.notification_ids)}

    @APIController.post("/mark-all-read", permissions=[IsAuthenticated])
    @jwt_required
    async def mark_all_read(self, request, data: NotificationMarkAllReadRequest):
        """
        Mark all notifications as read.
        """
        queryset = Notification.objects.filter(user=request.user, is_read=False)

        if data.organization_id:
            queryset = queryset.filter(organization_id=data.organization_id)

        count = await queryset.aupdate(is_read=True)

        return {"marked": count}

    @APIController.delete("/{notification_id}", permissions=[IsAuthenticated])
    @jwt_required
    async def delete_notification(self, request, notification_id: UUID):
        """
        Delete a notification.
        """
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
    # Preferences
    # =========================================================================

    @APIController.get("/preferences", response=NotificationPreferenceResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_preferences(self, request):
        """
        Get notification preferences for the current user.
        """
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

    @APIController.patch("/preferences", response=NotificationPreferenceResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_preferences(self, request, data: NotificationPreferenceUpdate):
        """
        Update notification preferences.
        """
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
