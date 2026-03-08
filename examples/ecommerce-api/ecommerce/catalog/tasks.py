"""Celery tasks for catalog app."""

import logging

from celery import shared_task
from django.contrib.postgres.search import SearchVector
from django.core.cache import cache
from django.db import models

logger = logging.getLogger(__name__)


@shared_task(name="ecommerce.catalog.tasks.update_search_vectors")
def update_search_vectors():
    """Update search vectors for all products."""
    from ecommerce.catalog.models import Product

    logger.info("Updating product search vectors...")

    Product.objects.update(
        search_vector=SearchVector("name", weight="A")
        + SearchVector("description", weight="B")
        + SearchVector("short_description", weight="C")
    )

    logger.info("Search vectors updated successfully")


@shared_task(name="ecommerce.catalog.tasks.update_inventory_cache")
def update_inventory_cache():
    """Update inventory cache for frequently accessed products."""
    from ecommerce.catalog.models import Inventory, Product

    logger.info("Updating inventory cache...")

    # Get active products
    products = Product.objects.filter(status="active")[:100]

    for product in products:
        inventory = Inventory.objects.filter(product=product)
        total_stock = sum(inv.available_quantity for inv in inventory)
        cache_key = f"product:{product.id}:stock"
        cache.set(cache_key, total_stock, timeout=300)

    logger.info("Inventory cache updated")


@shared_task(name="ecommerce.catalog.tasks.check_low_inventory")
def check_low_inventory():
    """Check for products with low inventory and send alerts."""
    from ecommerce.catalog.models import Inventory

    logger.info("Checking low inventory...")

    low_stock = Inventory.objects.filter(
        quantity__lte=models.F("reorder_level")
    ).select_related("product", "variant")

    alerts = []
    for inv in low_stock:
        product_name = inv.product.name
        if inv.variant:
            product_name += f" - {inv.variant.name}"

        alerts.append({
            "product": product_name,
            "location": inv.location,
            "quantity": inv.quantity,
            "reorder_level": inv.reorder_level,
        })

    if alerts:
        # In production, send email/Slack notification
        logger.warning(f"Low inventory alerts: {len(alerts)} items need restocking")
        for alert in alerts:
            logger.warning(
                f"  - {alert['product']} @ {alert['location']}: "
                f"{alert['quantity']} (reorder at {alert['reorder_level']})"
            )

    return len(alerts)


@shared_task(name="ecommerce.catalog.tasks.sync_product_ratings")
def sync_product_ratings():
    """Sync product ratings from reviews."""
    from django.db.models import Avg, Count

    from ecommerce.catalog.models import Product
    from ecommerce.reviews.models import Review

    logger.info("Syncing product ratings...")

    products = Product.objects.filter(status="active")

    for product in products:
        stats = Review.objects.filter(
            product=product, status="approved"
        ).aggregate(
            avg_rating=Avg("rating"),
            count=Count("id"),
        )

        # Cache the stats
        cache_key = f"product:{product.id}:rating"
        cache.set(
            cache_key,
            {
                "average": stats.get("avg_rating"),
                "count": stats.get("count", 0),
            },
            timeout=3600,
        )

    logger.info("Product ratings synced")


@shared_task(name="ecommerce.catalog.tasks.generate_product_sitemap")
def generate_product_sitemap():
    """Generate sitemap for products."""
    from ecommerce.catalog.models import Category, Product

    logger.info("Generating product sitemap...")

    # Get all active products and categories
    products = Product.objects.filter(status="active").values("slug", "updated_at")
    categories = Category.objects.filter(is_active=True).values("slug", "updated_at")

    sitemap_data = {
        "products": list(products),
        "categories": list(categories),
    }

    # In production, save to file or S3
    cache.set("sitemap:products", sitemap_data, timeout=86400)

    logger.info(
        f"Sitemap generated: {len(sitemap_data['products'])} products, "
        f"{len(sitemap_data['categories'])} categories"
    )


@shared_task(name="ecommerce.catalog.tasks.cleanup_orphaned_images")
def cleanup_orphaned_images():
    """Clean up product images that are no longer associated with products."""
    import os

    from django.conf import settings

    from ecommerce.catalog.models import ProductImage

    logger.info("Cleaning up orphaned images...")

    # Get all image paths in use
    used_images = set(ProductImage.objects.values_list("image", flat=True))

    # Get all files in products directory
    products_dir = os.path.join(settings.MEDIA_ROOT, "products")
    if not os.path.exists(products_dir):
        return 0

    orphaned_count = 0
    for filename in os.listdir(products_dir):
        file_path = f"products/{filename}"
        if file_path not in used_images:
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            os.remove(full_path)
            orphaned_count += 1
            logger.info(f"Removed orphaned image: {file_path}")

    logger.info(f"Cleaned up {orphaned_count} orphaned images")
    return orphaned_count
