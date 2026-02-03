"""Celery tasks for payments app."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.payments.tasks.process_webhook")
def process_webhook(webhook_id: str):
    """Process a payment webhook asynchronously."""
    from ecommerce.payments.models import PaymentWebhookLog

    webhook = PaymentWebhookLog.objects.filter(id=webhook_id).first()
    if not webhook:
        return

    if webhook.processed:
        return

    try:
        # Process based on provider
        if webhook.provider == "stripe":
            from ecommerce.payments.services import process_stripe_webhook_sync

            process_stripe_webhook_sync(webhook.payload)

        webhook.processed = True
        webhook.processed_at = timezone.now()
        webhook.save()

        logger.info(f"Processed webhook {webhook.event_id}")

    except Exception as e:
        webhook.error_message = str(e)
        webhook.save()
        logger.error(f"Failed to process webhook {webhook.event_id}: {e}")
        raise


@shared_task(name="ecommerce.payments.tasks.sync_stripe_payments")
def sync_stripe_payments():
    """Sync payment statuses with Stripe."""
    import stripe

    from ecommerce.payments.models import Payment

    stripe.api_key = settings.STRIPE_SECRET_KEY

    logger.info("Syncing payment statuses with Stripe...")

    # Get pending payments older than 5 minutes
    threshold = timezone.now() - timedelta(minutes=5)
    pending_payments = Payment.objects.filter(
        status=Payment.Status.PENDING,
        created_at__lt=threshold,
        stripe_payment_intent_id__isnull=False,
    )

    synced = 0
    for payment in pending_payments:
        try:
            intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)

            if intent.status == "succeeded":
                payment.status = Payment.Status.SUCCEEDED
                payment.paid_at = timezone.now()
            elif intent.status == "canceled":
                payment.status = Payment.Status.CANCELLED
            elif intent.status == "requires_payment_method":
                # Still waiting
                pass

            payment.save()
            synced += 1

        except Exception as e:
            logger.error(f"Failed to sync payment {payment.id}: {e}")

    logger.info(f"Synced {synced} payments")
    return synced


@shared_task(name="ecommerce.payments.tasks.send_refund_notification")
def send_refund_notification(refund_id: str):
    """Send refund notification email."""
    from ecommerce.payments.models import Refund

    refund = Refund.objects.filter(id=refund_id).select_related(
        "payment__order"
    ).first()

    if not refund:
        return

    order = refund.payment.order

    context = {
        "refund": refund,
        "order": order,
    }

    subject = f"Refund Processed - {order.order_number}"
    html_message = render_to_string("emails/refund_notification.html", context)
    text_message = render_to_string("emails/refund_notification.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )

    logger.info(f"Sent refund notification for order {order.order_number}")


@shared_task(name="ecommerce.payments.tasks.cleanup_webhook_logs")
def cleanup_webhook_logs():
    """Clean up old webhook logs."""
    from ecommerce.payments.models import PaymentWebhookLog

    logger.info("Cleaning up old webhook logs...")

    # Delete processed logs older than 30 days
    threshold = timezone.now() - timedelta(days=30)
    deleted, _ = PaymentWebhookLog.objects.filter(
        processed=True,
        received_at__lt=threshold,
    ).delete()

    logger.info(f"Deleted {deleted} old webhook logs")
    return deleted


@shared_task(name="ecommerce.payments.tasks.generate_payment_report")
def generate_payment_report(start_date: str, end_date: str):
    """Generate payment report for a date range."""
    from datetime import datetime
    from decimal import Decimal

    from django.db.models import Count, Sum

    from ecommerce.payments.models import Payment, Refund

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    # Payment stats
    payment_stats = Payment.objects.filter(
        created_at__range=(start, end),
        status=Payment.Status.SUCCEEDED,
    ).aggregate(
        total_payments=Count("id"),
        total_amount=Sum("amount"),
    )

    # Refund stats
    refund_stats = Refund.objects.filter(
        created_at__range=(start, end),
        status=Refund.Status.SUCCEEDED,
    ).aggregate(
        total_refunds=Count("id"),
        total_amount=Sum("amount"),
    )

    # Payments by method
    by_method = (
        Payment.objects.filter(
            created_at__range=(start, end),
            status=Payment.Status.SUCCEEDED,
        )
        .values("payment_method")
        .annotate(
            count=Count("id"),
            amount=Sum("amount"),
        )
    )

    report = {
        "period": {"start": start_date, "end": end_date},
        "payments": {
            "count": payment_stats.get("total_payments", 0),
            "amount": str(payment_stats.get("total_amount") or Decimal("0.00")),
        },
        "refunds": {
            "count": refund_stats.get("total_refunds", 0),
            "amount": str(refund_stats.get("total_amount") or Decimal("0.00")),
        },
        "by_method": [
            {
                "method": m["payment_method"],
                "count": m["count"],
                "amount": str(m["amount"]),
            }
            for m in by_method
        ],
    }

    # Cache the report
    from django.core.cache import cache

    cache.set(f"payment_report:{start_date}:{end_date}", report, timeout=86400)

    logger.info(f"Generated payment report for {start_date} to {end_date}")
    return report
