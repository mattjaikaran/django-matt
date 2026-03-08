"""
Celery tasks for billing.

Includes:
- Subscription sync
- Usage reporting
- Expiration notifications
"""

from datetime import timedelta

import stripe
from celery import shared_task
from django.conf import settings
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY


@shared_task
def sync_subscriptions():
    """
    Sync subscription status with Stripe.

    Runs every 6 hours.
    """
    from billing.models import Subscription

    synced = 0
    errors = []

    for subscription in Subscription.objects.filter(status__in=["active", "trialing", "past_due"]):
        try:
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

            # Update local record
            subscription.status = stripe_sub.status
            subscription.current_period_start = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = timezone.datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
            subscription.save()

            synced += 1

        except stripe.error.StripeError as e:
            errors.append(f"{subscription.id}: {str(e)}")

    return f"Synced {synced} subscriptions, {len(errors)} errors"


@shared_task
def send_expiration_notifications():
    """
    Send notifications for subscriptions expiring soon.

    Runs daily.
    """
    from billing.models import Subscription
    from notifications.models import Notification, NotificationType

    # Find subscriptions expiring in 7 days
    expiring_soon = timezone.now() + timedelta(days=7)

    subscriptions = Subscription.objects.filter(
        status="active",
        cancel_at_period_end=True,
        current_period_end__lte=expiring_soon,
        current_period_end__gt=timezone.now(),
    ).select_related("organization", "organization__owner")

    notifications_created = 0

    for sub in subscriptions:
        if sub.organization.owner:
            # Check if we already sent this notification
            existing = Notification.objects.filter(
                user=sub.organization.owner,
                type=NotificationType.BILLING_SUBSCRIPTION_EXPIRING,
                resource_type="subscription",
                resource_id=str(sub.id),
                created_at__gte=timezone.now() - timedelta(days=1),
            ).exists()

            if not existing:
                days_left = (sub.current_period_end - timezone.now()).days

                Notification.objects.create(
                    user=sub.organization.owner,
                    organization=sub.organization,
                    type=NotificationType.BILLING_SUBSCRIPTION_EXPIRING,
                    title="Subscription expiring soon",
                    message=f"Your subscription will expire in {days_left} days.",
                    resource_type="subscription",
                    resource_id=str(sub.id),
                    action_url=f"/organizations/{sub.organization.slug}/settings/billing",
                )
                notifications_created += 1

    return f"Created {notifications_created} expiration notifications"


@shared_task
def report_usage_to_stripe():
    """
    Report metered usage to Stripe.

    Runs hourly.
    """
    from billing.models import UsageRecord

    reported = 0

    # Get unreported usage records
    for record in UsageRecord.objects.filter(stripe_usage_record_id=""):
        try:
            subscription = record.subscription

            # Find the subscription item for metered billing
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

            for item in stripe_sub["items"]["data"]:
                # Check if this is a metered price
                if item["price"].get("recurring", {}).get("usage_type") == "metered":
                    # Report usage
                    usage_record = stripe.SubscriptionItem.create_usage_record(
                        item["id"],
                        quantity=int(record.quantity),
                        timestamp=int(record.timestamp.timestamp()),
                        action=record.action,
                    )

                    record.stripe_usage_record_id = usage_record.id
                    record.save()
                    reported += 1
                    break

        except stripe.error.StripeError:
            # Log error but continue with other records
            pass

    return f"Reported {reported} usage records to Stripe"


@shared_task
def sync_invoices_from_stripe():
    """
    Sync recent invoices from Stripe.

    Runs daily.
    """
    from billing.models import Invoice
    from core.models import Organization

    synced = 0

    for org in Organization.objects.filter(stripe_customer_id__isnull=False):
        try:
            # Get recent invoices from Stripe
            invoices = stripe.Invoice.list(
                customer=org.stripe_customer_id,
                limit=10,
            )

            for stripe_invoice in invoices.data:
                # Create or update local invoice
                Invoice.objects.update_or_create(
                    stripe_invoice_id=stripe_invoice.id,
                    defaults={
                        "organization": org,
                        "number": stripe_invoice.number or "",
                        "status": stripe_invoice.status,
                        "subtotal": stripe_invoice.subtotal,
                        "tax": stripe_invoice.tax or 0,
                        "total": stripe_invoice.total,
                        "amount_paid": stripe_invoice.amount_paid,
                        "amount_due": stripe_invoice.amount_due,
                        "currency": stripe_invoice.currency,
                        "invoice_date": timezone.datetime.fromtimestamp(
                            stripe_invoice.created, tz=timezone.utc
                        ),
                        "invoice_pdf_url": stripe_invoice.invoice_pdf or "",
                        "hosted_invoice_url": stripe_invoice.hosted_invoice_url or "",
                    },
                )
                synced += 1

        except stripe.error.StripeError:
            pass

    return f"Synced {synced} invoices from Stripe"
