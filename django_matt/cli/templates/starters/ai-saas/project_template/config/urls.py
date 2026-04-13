"""URL configuration for {{ project_name }}."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("{{ project_name }}_app.urls")),
]
