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
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.list import ListView
from django_matt.views.read import ReadView, RetrieveView
from django_matt.views.update import PatchView, UpdateView
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
