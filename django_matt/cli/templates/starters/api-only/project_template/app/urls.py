"""URL routes for {{ project_name }} API."""

from django.urls import path

from . import controllers

urlpatterns = [
    path("health/", controllers.health),
    path("items/", controllers.list_items),
    path("items/create/", controllers.create_item),
    path("items/<int:item_id>/", controllers.get_item),
    path("items/<int:item_id>/update/", controllers.update_item),
    path("items/<int:item_id>/delete/", controllers.delete_item),
]
