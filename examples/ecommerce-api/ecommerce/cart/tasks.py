"""Celery tasks for cart app."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.cart.tasks.check_abandoned_carts")
def check_abandoned_carts():
    """Check for abandoned carts and send recovery emails."""
    from ecommerce.cart.models import Cart

    logger.info("Checking for abandoned carts...")

    # Find carts abandoned for more than 1 hour with items
    threshold = timezone.now() - timedelta(hours=1)
    abandoned_carts = (
        Cart.objects.filter(
            user__isnull=False,
            updated_at__lt=threshold,
            items__isnull=False,
        )
        .distinct()
        .select_related("user")
    )

    emails_sent = 0
    for cart in abandoned_carts:
        # Check if we already sent a recovery email recently
        cache_key = f"cart_recovery:{cart.id}"
        from django.core.cache import cache

        if cache.get(cache_key):
            continue

        # Send recovery email
        try:
            send_abandoned_cart_email.delay(str(cart.id))
            cache.set(cache_key, True, timeout=86400)  # Don't send again for 24 hours
            emails_sent += 1
        except Exception as e:
            logger.error(f"Failed to queue recovery email for cart {cart.id}: {e}")

    logger.info(f"Queued {emails_sent} abandoned cart recovery emails")
    return emails_sent


@shared_task(name="ecommerce.cart.tasks.send_abandoned_cart_email")
def send_abandoned_cart_email(cart_id: str):
    """Send abandoned cart recovery email."""
    from ecommerce.cart.models import Cart

    cart = Cart.objects.filter(id=cart_id).select_related("user").first()
    if not cart or not cart.user:
        return

    # Build cart summary
    items = list(cart.items.select_related("product").all())
    if not items:
        return

    context = {
        "user": cart.user,
        "items": items,
        "subtotal": cart.subtotal,
        "cart_url": f"{settings.FRONTEND_URL}/cart",
    }

    # Render email
    subject = "You left items in your cart!"
    html_message = render_to_string("emails/abandoned_cart.html", context)
    text_message = render_to_string("emails/abandoned_cart.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[cart.user.email],
        fail_silently=False,
    )

    logger.info(f"Sent abandoned cart email to {cart.user.email}")


@shared_task(name="ecommerce.cart.tasks.cleanup_expired_carts")
def cleanup_expired_carts():
    """Clean up old session-based carts."""
    from ecommerce.cart.models import Cart

    logger.info("Cleaning up expired carts...")

    # Delete session carts older than 30 days
    threshold = timezone.now() - timedelta(days=30)
    deleted, _ = Cart.objects.filter(
        user__isnull=True,
        updated_at__lt=threshold,
    ).delete()

    logger.info(f"Deleted {deleted} expired session carts")
    return deleted


@shared_task(name="ecommerce.cart.tasks.merge_user_carts")
def merge_user_carts(user_id: str, session_key: str):
    """Merge session cart into user cart after login."""
    from ecommerce.cart.models import Cart

    logger.info(f"Merging carts for user {user_id}")

    # Get user cart
    user_cart = Cart.objects.filter(user_id=user_id).first()

    # Get session cart
    session_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()

    if not session_cart:
        return

    if not user_cart:
        # Just assign session cart to user
        session_cart.user_id = user_id
        session_cart.session_key = None
        session_cart.save()
        return

    # Merge items
    for item in session_cart.items.all():
        existing = user_cart.items.filter(product=item.product, variant=item.variant).first()
        if existing:
            existing.quantity += item.quantity
            existing.save()
        else:
            item.cart = user_cart
            item.save()

    # Copy coupon if user cart doesn't have one
    if session_cart.coupon and not user_cart.coupon:
        user_cart.coupon = session_cart.coupon
        user_cart.save()

    # Delete session cart
    session_cart.delete()

    logger.info(f"Merged session cart into user cart for user {user_id}")
