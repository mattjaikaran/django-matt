"""
Django Matt Resources — zero-config CRUD from models.

Usage:
    api.resource(Product)  # one-liner CRUD

    @resource(api, prefix="/products", permissions={"delete": [IsAdmin]})
    class ProductResource:
        model = Product
        search_fields = ["name", "description"]
"""

from django_matt.resources.actions import action
from django_matt.resources.resource import ResourceConfig, build_viewset, resource

__all__ = ["resource", "build_viewset", "ResourceConfig", "action"]
