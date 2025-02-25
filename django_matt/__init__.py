"""
Django Matt - A modern Django API framework

Django Matt is a custom Django API framework that combines the best features of
Django Rest Framework, Django Ninja, Django Ninja Extra, and other modern frameworks
while adding custom DX tools and performance optimizations.
"""

__version__ = "0.1.0"

# Import core components for easy access
from django_matt.core.controller import APIController, Controller, CRUDController
from django_matt.core.router import APIRouter, delete, get, patch, post, put
from django_matt.core.schema import Schema

# Create a default router instance
api = APIRouter()

# Export commonly used components
__all__ = [
    "APIRouter",
    "Controller",
    "APIController",
    "CRUDController",
    "Schema",
    "api",
    "get",
    "post",
    "put",
    "patch",
    "delete",
]
