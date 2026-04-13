"""URL configuration for {{ project_name }}."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("{{ project_name }}_app.urls")),
]
