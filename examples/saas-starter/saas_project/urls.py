"""
URL configuration for SaaS Starter project.

Includes:
- Admin interface
- API endpoints (django-matt)
- WebSocket routing
- OpenAPI documentation
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from api.main import api

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),
    # API endpoints (handled by django-matt)
    path("api/", include(api.urls)),
    # Health check endpoint
    path("health/", include("core.healthcheck")),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
