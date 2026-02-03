"""Celery configuration for e-commerce API."""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ecommerce")

# Load config from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    # Check for abandoned carts every hour
    "check-abandoned-carts": {
        "task": "ecommerce.cart.tasks.check_abandoned_carts",
        "schedule": crontab(minute=0),  # Every hour
    },
    # Update inventory cache every 5 minutes
    "update-inventory-cache": {
        "task": "ecommerce.catalog.tasks.update_inventory_cache",
        "schedule": crontab(minute="*/5"),
    },
    # Generate daily sales report at midnight
    "daily-sales-report": {
        "task": "ecommerce.orders.tasks.generate_daily_report",
        "schedule": crontab(hour=0, minute=0),
    },
    # Clean up expired sessions weekly
    "cleanup-expired-sessions": {
        "task": "ecommerce.users.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3am
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
