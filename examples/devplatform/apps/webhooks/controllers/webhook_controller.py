import secrets

import orjson
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.organizations.controllers.utils import get_membership, require_admin
from apps.projects.models import Project
from apps.webhooks.models import Webhook, WebhookDelivery
from apps.webhooks.schemas import (
    WebhookCreateSchema,
    WebhookDeliverySchema,
    WebhookSchema,
    WebhookUpdateSchema,
)


class WebhookController(APIController):
    prefix = "/organizations/{org_id}/projects/{project_id}/webhooks"
    tags = ["Webhooks"]

    @staticmethod
    @jwt_required
    async def list_webhooks(request, org_id: str, project_id: str) -> dict:
        """List all webhooks for a project."""
        await get_membership(request.user, org_id)

        project = await Project.objects.filter(
            id=project_id, organization_id=org_id
        ).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")

        webhooks = Webhook.objects.filter(project_id=project_id).order_by("-created_at")

        items = []
        async for webhook in webhooks:
            items.append(
                WebhookSchema(
                    id=str(webhook.id),
                    project_id=str(webhook.project_id),
                    url=webhook.url,
                    events=webhook.events,
                    is_active=webhook.is_active,
                    description=webhook.description,
                    created_at=webhook.created_at,
                    updated_at=webhook.updated_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_webhook(request, org_id: str, project_id: str) -> dict:
        """Create a new webhook. Requires admin role."""
        await require_admin(request.user, org_id)

        project = await Project.objects.filter(
            id=project_id, organization_id=org_id
        ).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")

        body = orjson.loads(request.body)
        data = WebhookCreateSchema(**body)

        webhook = await Webhook.objects.acreate(
            project_id=project_id,
            url=str(data.url),
            secret=secrets.token_hex(32),
            events=data.events,
            description=data.description,
        )

        return WebhookSchema(
            id=str(webhook.id),
            project_id=str(webhook.project_id),
            url=webhook.url,
            events=webhook.events,
            is_active=webhook.is_active,
            description=webhook.description,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_webhook(
        request, org_id: str, project_id: str, webhook_id: str
    ) -> dict:
        """Get a specific webhook."""
        await get_membership(request.user, org_id)

        webhook = await Webhook.objects.filter(
            id=webhook_id,
            project_id=project_id,
            project__organization_id=org_id,
        ).afirst()

        if not webhook:
            raise NotFoundAPIError("Webhook not found")

        return WebhookSchema(
            id=str(webhook.id),
            project_id=str(webhook.project_id),
            url=webhook.url,
            events=webhook.events,
            is_active=webhook.is_active,
            description=webhook.description,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_webhook(
        request, org_id: str, project_id: str, webhook_id: str
    ) -> dict:
        """Update a webhook. Requires admin role."""
        await require_admin(request.user, org_id)

        webhook = await Webhook.objects.filter(
            id=webhook_id,
            project_id=project_id,
            project__organization_id=org_id,
        ).afirst()

        if not webhook:
            raise NotFoundAPIError("Webhook not found")

        body = orjson.loads(request.body)
        data = WebhookUpdateSchema(**body)
        updates = data.model_dump(exclude_unset=True)

        # Convert HttpUrl to string if url was provided
        if "url" in updates and updates["url"] is not None:
            updates["url"] = str(updates["url"])

        for field, value in updates.items():
            setattr(webhook, field, value)
        await webhook.asave()

        return WebhookSchema(
            id=str(webhook.id),
            project_id=str(webhook.project_id),
            url=webhook.url,
            events=webhook.events,
            is_active=webhook.is_active,
            description=webhook.description,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_webhook(
        request, org_id: str, project_id: str, webhook_id: str
    ) -> dict:
        """Delete a webhook. Requires admin role."""
        await require_admin(request.user, org_id)

        webhook = await Webhook.objects.filter(
            id=webhook_id,
            project_id=project_id,
            project__organization_id=org_id,
        ).afirst()

        if not webhook:
            raise NotFoundAPIError("Webhook not found")

        await webhook.adelete()
        return {"message": "Webhook deleted"}

    @staticmethod
    @jwt_required
    async def list_deliveries(
        request, org_id: str, project_id: str, webhook_id: str
    ) -> dict:
        """List deliveries for a webhook."""
        await get_membership(request.user, org_id)

        webhook = await Webhook.objects.filter(
            id=webhook_id,
            project_id=project_id,
            project__organization_id=org_id,
        ).afirst()

        if not webhook:
            raise NotFoundAPIError("Webhook not found")

        deliveries = WebhookDelivery.objects.filter(
            webhook_id=webhook_id
        ).order_by("-attempted_at")

        items = []
        async for delivery in deliveries[:50]:
            items.append(
                WebhookDeliverySchema(
                    id=str(delivery.id),
                    webhook_id=str(delivery.webhook_id),
                    event_type=delivery.event_type,
                    payload=delivery.payload,
                    status_code=delivery.status_code,
                    response_body=delivery.response_body,
                    success=delivery.success,
                    attempted_at=delivery.attempted_at,
                    duration_ms=delivery.duration_ms,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def retry_delivery(
        request,
        org_id: str,
        project_id: str,
        webhook_id: str,
        delivery_id: str,
    ) -> dict:
        """Retry a webhook delivery. Marks as pending for re-attempt."""
        await get_membership(request.user, org_id)

        delivery = await WebhookDelivery.objects.filter(
            id=delivery_id,
            webhook_id=webhook_id,
            webhook__project_id=project_id,
            webhook__project__organization_id=org_id,
        ).afirst()

        if not delivery:
            raise NotFoundAPIError("Delivery not found")

        # Reset delivery status for retry
        delivery.success = False
        delivery.status_code = None
        delivery.response_body = ""
        delivery.duration_ms = None
        await delivery.asave()

        return {"message": "Delivery queued for retry"}
