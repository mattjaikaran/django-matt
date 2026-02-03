"""URL configuration for e-commerce API."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from ecommerce.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
