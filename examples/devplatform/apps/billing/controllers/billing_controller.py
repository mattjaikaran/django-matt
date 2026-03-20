from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError

from apps.billing.models import Invoice, Subscription
from apps.billing.schemas import (
    InvoiceSchema,
    SubscriptionSchema,
    SubscriptionUpdateSchema,
    UsageSchema,
)
from apps.organizations.controllers.utils import get_membership, require_owner

PLAN_LIMITS = {
    "free": 10000,
    "starter": 100000,
    "pro": 1000000,
    "enterprise": 10000000,
}


class BillingController(APIController):
    prefix = "/organizations/{org_id}/billing"
    tags = ["Billing"]

    @staticmethod
    @jwt_required
    async def get_subscription(request, org_id: str) -> dict:
        """Get the subscription for an organization. Creates a free one if none exists."""
        await get_membership(request.user, org_id)

        subscription = await Subscription.objects.filter(
            organization_id=org_id
        ).afirst()

        if not subscription:
            subscription = await Subscription.objects.acreate(
                organization_id=org_id,
                plan="free",
                status="active",
                api_calls_limit=PLAN_LIMITS["free"],
            )

        return SubscriptionSchema(
            id=str(subscription.id),
            organization_id=str(subscription.organization_id),
            stripe_subscription_id=subscription.stripe_subscription_id,
            plan=subscription.plan,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            api_calls_limit=subscription.api_calls_limit,
            api_calls_used=subscription.api_calls_used,
            created_at=subscription.created_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_subscription(request, org_id: str, body: SubscriptionUpdateSchema) -> dict:
        """Update the subscription plan. Requires owner role."""
        await require_owner(request.user, org_id)

        subscription = await Subscription.objects.filter(
            organization_id=org_id
        ).afirst()

        if not subscription:
            subscription = await Subscription.objects.acreate(
                organization_id=org_id,
                plan="free",
                status="active",
                api_calls_limit=PLAN_LIMITS["free"],
            )

        updates = body.model_dump(exclude_unset=True)

        if "plan" in updates:
            new_plan = updates["plan"]
            if new_plan not in PLAN_LIMITS:
                raise APIError(
                    status_code=400,
                    message=f"Invalid plan. Choose from: {', '.join(PLAN_LIMITS.keys())}",
                )
            subscription.plan = new_plan
            subscription.api_calls_limit = PLAN_LIMITS[new_plan]

        await subscription.asave()

        return SubscriptionSchema(
            id=str(subscription.id),
            organization_id=str(subscription.organization_id),
            stripe_subscription_id=subscription.stripe_subscription_id,
            plan=subscription.plan,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            api_calls_limit=subscription.api_calls_limit,
            api_calls_used=subscription.api_calls_used,
            created_at=subscription.created_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_usage(request, org_id: str) -> dict:
        """Get current usage stats for an organization."""
        await get_membership(request.user, org_id)

        subscription = await Subscription.objects.filter(
            organization_id=org_id
        ).afirst()

        if not subscription:
            return UsageSchema(
                api_calls_used=0,
                api_calls_limit=PLAN_LIMITS["free"],
                usage_percentage=0.0,
                period_start=None,
                period_end=None,
            ).model_dump(mode="json")

        usage_pct = 0.0
        if subscription.api_calls_limit > 0:
            usage_pct = round(
                (subscription.api_calls_used / subscription.api_calls_limit) * 100, 2
            )

        return UsageSchema(
            api_calls_used=subscription.api_calls_used,
            api_calls_limit=subscription.api_calls_limit,
            usage_percentage=usage_pct,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def list_invoices(request, org_id: str) -> dict:
        """List invoices for an organization."""
        await get_membership(request.user, org_id)

        invoices = Invoice.objects.filter(
            organization_id=org_id
        ).order_by("-period_end")

        items = []
        async for invoice in invoices[:50]:
            items.append(
                InvoiceSchema(
                    id=str(invoice.id),
                    organization_id=str(invoice.organization_id),
                    stripe_invoice_id=invoice.stripe_invoice_id,
                    amount=float(invoice.amount),
                    currency=invoice.currency,
                    status=invoice.status,
                    period_start=str(invoice.period_start),
                    period_end=str(invoice.period_end),
                    paid_at=invoice.paid_at,
                    created_at=invoice.created_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}
