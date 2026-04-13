"""URL routes for {{ project_name }} API."""

from django.urls import path

from . import controllers

urlpatterns = [
    path("health/", controllers.health),
    path("audit/", controllers.list_audit_entries),
    path("flags/", controllers.list_flags),
    path("flags/create/", controllers.create_flag),
    path("flags/<int:flag_id>/", controllers.update_flag),
]
