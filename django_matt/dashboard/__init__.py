"""
Django Matt Performance Dashboard.

A visual dashboard for monitoring API performance metrics including:
- Request timing and throughput
- Database query analysis
- Cache hit/miss rates
- Memory and CPU usage
- Error rates and response codes

Usage:
    # In urls.py
    from django_matt.dashboard import include_dashboard

    urlpatterns = [
        path("_dashboard/", include_dashboard()),
        # ... other urls
    ]

    # Or use the views directly
    from django_matt.dashboard import DashboardView
    path("performance/", DashboardView.as_view(), name="performance"),

    # Add middleware for automatic collection
    MIDDLEWARE = [
        ...
        "django_matt.dashboard.MetricsMiddleware",
    ]

Settings:
    DJANGO_MATT_DASHBOARD = {
        "ENABLED": True,
        "REQUIRE_STAFF": True,
        "COLLECT_METRICS": True,
        "RETENTION_HOURS": 24,
        "MAX_REQUESTS": 10000,
        "EXCLUDED_PATHS": ["/_dashboard/", "/static/", "/media/"],
        "TRACK_QUERIES": True,
        "TRACK_MEMORY": False,
    }
"""

from django_matt.dashboard.collector import (
    EndpointStats,
    MetricsCollector,
    RequestMetrics,
    get_collector,
)
from django_matt.dashboard.middleware import (
    MetricsMiddleware,
)
from django_matt.dashboard.views import (
    DashboardView,
    MetricsAPIView,
    include_dashboard,
)

__all__ = [
    # Views
    "DashboardView",
    "MetricsAPIView",
    "include_dashboard",
    # Collector
    "EndpointStats",
    "MetricsCollector",
    "RequestMetrics",
    "get_collector",
    # Middleware
    "MetricsMiddleware",
]
