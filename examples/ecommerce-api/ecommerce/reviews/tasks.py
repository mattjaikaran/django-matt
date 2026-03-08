"""Celery tasks for reviews app."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.reviews.tasks.notify_new_review")
def notify_new_review(review_id: str):
    """Notify admin of new review for moderation."""
    from ecommerce.reviews.models import Review

    review = Review.objects.filter(id=review_id).select_related(
        "product", "user"
    ).first()

    if not review:
        return

    context = {
        "review": review,
        "moderate_url": f"{settings.SITE_URL}/admin/reviews/review/{review.id}/change/",
    }

    subject = f"New Review for Moderation - {review.product.name}"
    html_message = render_to_string("emails/admin/new_review.html", context)
    text_message = render_to_string("emails/admin/new_review.txt", context)

    # Send to admin email
    admin_email = getattr(settings, "ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[admin_email],
        fail_silently=False,
    )

    logger.info(f"Sent new review notification for review {review.id}")


@shared_task(name="ecommerce.reviews.tasks.notify_review_approved")
def notify_review_approved(review_id: str):
    """Notify user that their review was approved."""
    from ecommerce.reviews.models import Review

    review = Review.objects.filter(id=review_id).select_related(
        "product", "user"
    ).first()

    if not review or not review.user:
        return

    context = {
        "review": review,
        "product": review.product,
    }

    subject = f"Your Review Has Been Published - {review.product.name}"
    html_message = render_to_string("emails/review_approved.html", context)
    text_message = render_to_string("emails/review_approved.txt", context)

    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[review.user.email],
        fail_silently=False,
    )

    logger.info(f"Sent review approved notification for review {review.id}")


@shared_task(name="ecommerce.reviews.tasks.auto_moderate_reviews")
def auto_moderate_reviews():
    """Auto-approve reviews from trusted users."""

    from ecommerce.reviews.models import Review

    logger.info("Running auto-moderation for reviews...")

    # Find pending reviews
    pending_reviews = Review.objects.filter(status="pending").select_related("user")

    approved_count = 0
    for review in pending_reviews:
        # Auto-approve if user has multiple approved reviews already
        approved_reviews = Review.objects.filter(
            user=review.user, status="approved"
        ).count()

        if approved_reviews >= 3:
            # User is trusted
            review.status = Review.Status.APPROVED
            review.moderation_notes = "Auto-approved (trusted user)"
            review.moderated_at = timezone.now()
            review.save()
            approved_count += 1

            # Notify user
            notify_review_approved.delay(str(review.id))

    logger.info(f"Auto-approved {approved_count} reviews")
    return approved_count


@shared_task(name="ecommerce.reviews.tasks.calculate_product_ratings")
def calculate_product_ratings():
    """Calculate and cache product ratings."""
    from django.db.models import Avg, Count

    from ecommerce.catalog.models import Product
    from ecommerce.reviews.models import Review

    logger.info("Calculating product ratings...")

    products = Product.objects.filter(status="active")

    from django.core.cache import cache

    for product in products:
        stats = Review.objects.filter(
            product=product, status="approved"
        ).aggregate(
            avg_rating=Avg("rating"),
            count=Count("id"),
        )

        cache.set(
            f"product:{product.id}:rating",
            {
                "average": float(stats.get("avg_rating") or 0),
                "count": stats.get("count", 0),
            },
            timeout=3600,
        )

    logger.info("Product ratings calculated and cached")


@shared_task(name="ecommerce.reviews.tasks.request_reviews_for_delivered_orders")
def request_reviews_for_delivered_orders():
    """Send review requests for recently delivered orders."""
    from ecommerce.orders.models import Order
    from ecommerce.orders.tasks import request_review
    from ecommerce.reviews.models import Review

    logger.info("Requesting reviews for delivered orders...")

    # Find orders delivered 3-7 days ago
    start_date = timezone.now() - timedelta(days=7)
    end_date = timezone.now() - timedelta(days=3)

    delivered_orders = Order.objects.filter(
        status=Order.Status.DELIVERED,
        delivered_at__range=(start_date, end_date),
    )

    # Check if we already sent a review request (use cache)
    from django.core.cache import cache

    sent_count = 0
    for order in delivered_orders:
        cache_key = f"review_request_sent:{order.id}"
        if cache.get(cache_key):
            continue

        # Check if user already reviewed any product from this order
        product_ids = order.items.values_list("product_id", flat=True)
        existing_review = Review.objects.filter(
            user=order.user, product_id__in=product_ids
        ).exists()

        if not existing_review:
            request_review.delay(str(order.id))
            cache.set(cache_key, True, timeout=86400 * 30)  # Don't send again for 30 days
            sent_count += 1

    logger.info(f"Sent {sent_count} review requests")
    return sent_count


@shared_task(name="ecommerce.reviews.tasks.cleanup_rejected_reviews")
def cleanup_rejected_reviews():
    """Clean up old rejected reviews."""
    from ecommerce.reviews.models import Review

    logger.info("Cleaning up rejected reviews...")

    # Delete rejected reviews older than 90 days
    threshold = timezone.now() - timedelta(days=90)
    deleted, _ = Review.objects.filter(
        status=Review.Status.REJECTED,
        moderated_at__lt=threshold,
    ).delete()

    logger.info(f"Deleted {deleted} rejected reviews")
    return deleted
