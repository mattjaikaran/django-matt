"""
Django Matt Views - Composable CRUD Views with Lifecycle Hooks.

Provides declarative, composable view classes inspired by django-ninja-crud.
Create complete CRUD APIs with minimal code using the ViewSet pattern.

Lifecycle hooks allow you to execute custom logic before/after CRUD operations:
- before_list, after_list
- before_create, after_create
- before_read, after_read
- before_update, after_update
- before_delete, after_delete
- on_error

Example:
    from django_matt import MattAPI
    from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
    from django_matt.views.hooks import before_create, after_create

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

        # Class-based hooks
        async def before_create(self, request, data):
            data["created_by_id"] = request.user.id
            return data

        async def after_create(self, request, instance):
            await send_notification(f"User {instance.email} created")
            return instance

    # Or use decorator-based hooks
    @before_create(UserViewSet)
    async def validate_user(context, data):
        if not data.get("email"):
            raise ValueError("Email is required")
        return data
"""

from django_matt.views.base import APIView
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.list import ListView
from django_matt.views.read import ReadView, RetrieveView
from django_matt.views.update import PatchView, UpdateView
from django_matt.views.viewset import APIViewSet, ViewSet

# Hook system
from django_matt.views.hooks import (
    HookContext,
    HookManager,
    HooksMixin,
    HookType,
    RegisteredHook,
    StopHookChain,
    after_create,
    after_delete,
    after_list,
    after_read,
    after_update,
    before_create,
    before_delete,
    before_list,
    before_read,
    before_update,
    create_hook_context,
    hook_manager,
    on_error,
    register_global_hook,
    register_hook,
    run_hooks,
)

# Decorators
from django_matt.views.decorators import (
    catch_and_continue,
    compose_hooks,
    hook_method,
    log_hook,
    priority,
    retry,
    timed_hook,
    unless,
    when,
    with_hooks,
)

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
    # Hooks - Types and Classes
    "HookType",
    "HookContext",
    "RegisteredHook",
    "HookManager",
    "HooksMixin",
    "StopHookChain",
    "hook_manager",
    # Hooks - Decorators
    "before_list",
    "after_list",
    "before_create",
    "after_create",
    "before_read",
    "after_read",
    "before_update",
    "after_update",
    "before_delete",
    "after_delete",
    "on_error",
    "register_global_hook",
    "register_hook",
    # Hooks - Utilities
    "create_hook_context",
    "run_hooks",
    # Decorators - Composition
    "with_hooks",
    "compose_hooks",
    "hook_method",
    # Decorators - Conditional
    "when",
    "unless",
    "priority",
    # Decorators - Error Handling
    "catch_and_continue",
    "retry",
    # Decorators - Debugging
    "log_hook",
    "timed_hook",
]

