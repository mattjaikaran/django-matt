"""Celery tasks for orders app."""

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.orders.tasks.send_order_confirmation_email")
def send_order_confirmation_email(order_id: str):
    """Send order confirmation email."""
    from ecommerce.orders.models import Order

    order = Order.objects.filter(id=order_id).prefetch_related("items").first()
    if not order:
        logger.error(f"Order {order_id} not found")
        return

    context = {
        "order": order,
        "items": list(order.items.all()),
        "order_url": f"{settings.FRONTEND_URL}/orders/{order.id}",
    }

    subject = f"Order Confirmation - {order.order_number}"
    html_message = render_to_string("emails/order_confirmation.html", context)
    text_message = render_to_string("emails/order_confirmation.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )

    logger.info(f"Sent order confirmation email for {order.order_number}")


@shared_task(name="ecommerce.orders.tasks.send_order_status_update_email")
def send_order_status_update_email(order_id: str, new_status: str):
    """Send order status update email."""
    from ecommerce.orders.models import Order

    order = Order.objects.filter(id=order_id).first()
    if not order:
        return

    status_messages = {
        "confirmed": "Your order has been confirmed",
        "processing": "Your order is being processed",
        "shipped": "Your order has been shipped",
        "delivered": "Your order has been delivered",
        "cancelled": "Your order has been cancelled",
    }

    context = {
        "order": order,
        "status_message": status_messages.get(new_status, f"Status: {new_status}"),
        "tracking_number": order.tracking_number,
        "order_url": f"{settings.FRONTEND_URL}/orders/{order.id}",
    }

    subject = f"Order Update - {order.order_number}"
    html_message = render_to_string("emails/order_status_update.html", context)
    text_message = render_to_string("emails/order_status_update.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )

    logger.info(f"Sent status update email for {order.order_number}: {new_status}")


@shared_task(name="ecommerce.orders.tasks.send_shipping_notification")
def send_shipping_notification(order_id: str):
    """Send shipping notification with tracking info."""
    from ecommerce.orders.models import Order

    order = Order.objects.filter(id=order_id).first()
    if not order or not order.tracking_number:
        return

    context = {
        "order": order,
        "tracking_number": order.tracking_number,
        "tracking_url": f"https://track.carrier.com/{order.tracking_number}",
        "order_url": f"{settings.FRONTEND_URL}/orders/{order.id}",
    }

    subject = f"Your Order Has Shipped - {order.order_number}"
    html_message = render_to_string("emails/shipping_notification.html", context)
    text_message = render_to_string("emails/shipping_notification.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )

    logger.info(f"Sent shipping notification for {order.order_number}")


@shared_task(name="ecommerce.orders.tasks.generate_daily_report")
def generate_daily_report():
    """Generate daily sales report."""
    from django.db.models import Avg, Count, Sum

    from ecommerce.orders.models import Order

    logger.info("Generating daily sales report...")

    yesterday = timezone.now().date() - timedelta(days=1)
    orders = Order.objects.filter(
        created_at__date=yesterday,
        status__in=["confirmed", "processing", "shipped", "delivered"],
    )

    stats = orders.aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("total"),
        avg_order_value=Avg("total"),
    )

    # Get top products
    from django.db.models import F

    from ecommerce.orders.models import OrderItem

    top_products = (
        OrderItem.objects.filter(order__created_at__date=yesterday)
        .values("product_name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("total"),
        )
        .order_by("-quantity_sold")[:10]
    )

    # Get orders by status
    status_counts = orders.values("status").annotate(count=Count("id"))

    report = {
        "date": str(yesterday),
        "total_orders": stats.get("total_orders", 0),
        "total_revenue": str(stats.get("total_revenue") or Decimal("0.00")),
        "avg_order_value": str(stats.get("avg_order_value") or Decimal("0.00")),
        "top_products": list(top_products),
        "orders_by_status": {s["status"]: s["count"] for s in status_counts},
    }

    # Cache the report
    from django.core.cache import cache

    cache.set(f"daily_report:{yesterday}", report, timeout=86400 * 7)

    # In production, send to admin/analytics
    logger.info(f"Daily report for {yesterday}: {stats}")

    return report


@shared_task(name="ecommerce.orders.tasks.process_pending_orders")
def process_pending_orders():
    """Process orders that are stuck in pending status."""
    from ecommerce.orders.models import Order
    from ecommerce.payments.models import Payment

    logger.info("Processing pending orders...")

    # Find orders pending for more than 30 minutes
    threshold = timezone.now() - timedelta(minutes=30)
    pending_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lt=threshold,
    )

    for order in pending_orders:
        # Check if payment was successful
        payment = Payment.objects.filter(
            order=order, status=Payment.Status.SUCCEEDED
        ).first()

        if payment:
            # Payment succeeded but order not updated - fix it
            order.status = Order.Status.CONFIRMED
            order.save()
            logger.info(f"Fixed stuck order {order.order_number}")

            # Send confirmation if not sent
            send_order_confirmation_email.delay(str(order.id))
        else:
            # No successful payment - might need to release inventory
            logger.warning(f"Order {order.order_number} has no successful payment")


@shared_task(name="ecommerce.orders.tasks.cancel_stale_orders")
def cancel_stale_orders():
    """Cancel orders that have been pending for too long without payment."""
    from ecommerce.orders.models import Order
    from ecommerce.payments.models import Payment

    logger.info("Cancelling stale orders...")

    # Cancel orders pending for more than 24 hours without payment
    threshold = timezone.now() - timedelta(hours=24)
    stale_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lt=threshold,
    )

    cancelled_count = 0
    for order in stale_orders:
        # Check for any payment attempt
        has_payment = Payment.objects.filter(
            order=order, status__in=[Payment.Status.SUCCEEDED, Payment.Status.PROCESSING]
        ).exists()

        if not has_payment:
            order.status = Order.Status.CANCELLED
            order.save()

            # Release inventory
            from ecommerce.catalog.models import Inventory

            for item in order.items.select_related("product", "variant").all():
                if item.variant:
                    inv = Inventory.objects.filter(variant=item.variant).first()
                else:
                    inv = Inventory.objects.filter(
                        product=item.product, variant__isnull=True
                    ).first()
                if inv:
                    inv.release(item.quantity)

            cancelled_count += 1
            logger.info(f"Cancelled stale order {order.order_number}")

    logger.info(f"Cancelled {cancelled_count} stale orders")
    return cancelled_count


@shared_task(name="ecommerce.orders.tasks.request_review")
def request_review(order_id: str):
    """Send review request email after delivery."""
    from ecommerce.orders.models import Order

    order = Order.objects.filter(id=order_id).prefetch_related("items").first()
    if not order:
        return

    context = {
        "order": order,
        "items": list(order.items.all()),
        "review_url": f"{settings.FRONTEND_URL}/reviews/new?order={order.id}",
    }

    subject = f"How was your purchase? - {order.order_number}"
    html_message = render_to_string("emails/review_request.html", context)
    text_message = render_to_string("emails/review_request.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        fail_silently=False,
    )

    logger.info(f"Sent review request for {order.order_number}")
