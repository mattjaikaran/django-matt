"""
URL configuration for SaaS Starter project.

Includes:
- Admin interface
- API endpoints (django-matt)
- WebSocket routing
- OpenAPI documentation
"""

from django.contrib import admin
from django.urls import path, include

from api.main import api

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # API endpoints (handled by django-matt)
    path("api/", api.urls),

    # Health check endpoint
    path("health/", include("core.healthcheck")),
]

# Serve static files in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
