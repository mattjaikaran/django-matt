"""
Celery configuration for SaaS Starter project.

Handles background tasks:
- Email notifications
- Webhook processing
- Analytics aggregation
- Scheduled tasks
"""

import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saas_project.settings")

app = Celery("saas_project")

# Configure Celery using Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Aggregate analytics daily at midnight
    "aggregate-analytics-daily": {
        "task": "notifications.tasks.aggregate_analytics",
        "schedule": 60 * 60 * 24,  # Every 24 hours
    },
    # Clean up expired magic links every hour
    "cleanup-expired-tokens": {
        "task": "core.tasks.cleanup_expired_tokens",
        "schedule": 60 * 60,  # Every hour
    },
    # Sync subscription status with Stripe every 6 hours
    "sync-subscriptions": {
        "task": "billing.tasks.sync_subscriptions",
        "schedule": 60 * 60 * 6,  # Every 6 hours
    },
    # Send weekly digest emails every Monday at 9am
    "send-weekly-digest": {
        "task": "notifications.tasks.send_weekly_digest",
        "schedule": {
            "minute": 0,
            "hour": 9,
            "day_of_week": 1,  # Monday
        },
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f"Request: {self.request!r}")
