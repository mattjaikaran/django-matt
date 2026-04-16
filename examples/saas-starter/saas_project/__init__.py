# SaaS Starter Project
# Comprehensive example showcasing django-matt features

try:
    from .celery import app as celery_app
except ImportError:
    # Celery is an optional dep for this example — the server still runs
    # without it, only the background-task features become unavailable.
    celery_app = None

__all__ = ["celery_app"]
