"""Celery tasks for users app."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.users.tasks.cleanup_expired_sessions")
def cleanup_expired_sessions():
    """Clean up expired sessions."""
    logger.info("Cleaning up expired sessions...")

    # Delete expired sessions
    deleted, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()

    logger.info(f"Deleted {deleted} expired sessions")
    return deleted


@shared_task(name="ecommerce.users.tasks.send_welcome_email")
def send_welcome_email(user_id: str):
    """Send welcome email to new user."""
    from ecommerce.users.models import User

    user = User.objects.filter(id=user_id).first()
    if not user:
        return

    context = {
        "user": user,
        "shop_url": settings.FRONTEND_URL,
    }

    subject = "Welcome to Our Store!"
    html_message = render_to_string("emails/welcome.html", context)
    text_message = render_to_string("emails/welcome.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info(f"Sent welcome email to {user.email}")


@shared_task(name="ecommerce.users.tasks.send_password_reset_email")
def send_password_reset_email(user_id: str, token: str):
    """Send password reset email."""
    from ecommerce.users.models import User

    user = User.objects.filter(id=user_id).first()
    if not user:
        return

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    context = {
        "user": user,
        "reset_url": reset_url,
    }

    subject = "Reset Your Password"
    html_message = render_to_string("emails/password_reset.html", context)
    text_message = render_to_string("emails/password_reset.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info(f"Sent password reset email to {user.email}")


@shared_task(name="ecommerce.users.tasks.cleanup_inactive_users")
def cleanup_inactive_users():
    """Clean up users who never verified their email (if applicable)."""
    from ecommerce.users.models import User

    logger.info("Checking for inactive users...")

    # Find users who haven't logged in for 2 years and have no orders
    threshold = timezone.now() - timedelta(days=730)
    inactive_users = User.objects.filter(
        last_login__lt=threshold,
        orders__isnull=True,
        is_staff=False,
        is_superuser=False,
    )

    count = inactive_users.count()
    # Don't actually delete, just log for now
    # inactive_users.delete()

    logger.info(f"Found {count} inactive users (not deleted, just logging)")
    return count


@shared_task(name="ecommerce.users.tasks.sync_user_stats")
def sync_user_stats():
    """Sync user statistics (total orders, total spent, etc.)."""
    from django.db.models import Count, Sum

    from ecommerce.orders.models import Order
    from ecommerce.users.models import User

    logger.info("Syncing user stats...")

    users = User.objects.annotate(
        order_count=Count("orders", filter=models.Q(orders__status__in=["confirmed", "processing", "shipped", "delivered"])),
        total_spent=Sum("orders__total", filter=models.Q(orders__status__in=["confirmed", "processing", "shipped", "delivered"])),
    )

    from django.core.cache import cache

    for user in users:
        cache.set(
            f"user:{user.id}:stats",
            {
                "order_count": user.order_count,
                "total_spent": str(user.total_spent or 0),
            },
            timeout=3600,
        )

    logger.info("User stats synced")


@shared_task(name="ecommerce.users.tasks.export_user_data")
def export_user_data(user_id: str):
    """Export all user data (GDPR compliance)."""
    import json

    from ecommerce.orders.models import Order
    from ecommerce.reviews.models import Review
    from ecommerce.users.models import Address, User, Wishlist

    user = User.objects.filter(id=user_id).first()
    if not user:
        return None

    # Collect all user data
    data = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
            "created_at": str(user.created_at),
        },
        "addresses": [
            {
                "id": str(a.id),
                "address_type": a.address_type,
                "address_line_1": a.address_line_1,
                "city": a.city,
                "state": a.state,
                "postal_code": a.postal_code,
                "country": a.country,
            }
            for a in Address.objects.filter(user=user)
        ],
        "orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status,
                "total": str(o.total),
                "created_at": str(o.created_at),
            }
            for o in Order.objects.filter(user=user)
        ],
        "reviews": [
            {
                "id": str(r.id),
                "product_name": r.product.name,
                "rating": r.rating,
                "content": r.content,
                "created_at": str(r.created_at),
            }
            for r in Review.objects.filter(user=user).select_related("product")
        ],
        "wishlists": [
            {
                "id": str(w.id),
                "name": w.name,
                "items": [
                    {"product_name": i.product.name}
                    for i in w.items.select_related("product").all()
                ],
            }
            for w in Wishlist.objects.filter(user=user).prefetch_related("items")
        ],
    }

    # In production, save to S3 and email download link
    logger.info(f"Exported data for user {user.email}")

    return json.dumps(data, indent=2)


from django.db import models
