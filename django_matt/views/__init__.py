"""
Django Matt Views - Composable CRUD Views.

Provides declarative, composable view classes inspired by django-ninja-crud.
Create complete CRUD APIs with minimal code using the ViewSet pattern.

Example:
    from django_matt import MattAPI
    from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
    
    class UserViewSet(APIViewSet):
        api = api
        model = User
        default_response_schema = UserSchema
        default_request_schema = UserCreateSchema
        
        list_users = ListView()
        create_user = CreateView()
        read_user = ReadView()
        update_user = UpdateView()
        delete_user = DeleteView()
"""

from django_matt.views.base import APIView
from django_matt.views.crud import (
    ListView,
    CreateView,
    ReadView,
    RetrieveView,  # Alias for ReadView
    UpdateView,
    DeleteView,
    PatchView,
)
from django_matt.views.viewset import APIViewSet, ViewSet

__all__ = [
    # Base
    "APIView",
    # CRUD Views
    "ListView",
    "CreateView",
    "ReadView",
    "RetrieveView",
    "UpdateView",
    "DeleteView",
    "PatchView",
    # ViewSets
    "APIViewSet",
    "ViewSet",
]
