"""URL routes for {{ project_name }} API."""

from django.urls import path

from . import controllers

urlpatterns = [
    path("health/", controllers.health),
    path("products/", controllers.list_products),
    path("products/<int:product_id>/", controllers.get_product),
    path("products/<int:product_id>/reviews/", controllers.list_reviews),
    path("products/<int:product_id>/reviews/create/", controllers.create_review),
    path("stores/create/", controllers.create_store),
    path("stores/<slug:store_slug>/products/create/", controllers.create_product),
]
