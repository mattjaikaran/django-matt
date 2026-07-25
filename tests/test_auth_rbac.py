"""Tests for RBAC decorators (async paths) and resource-scoped permissions."""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.auth.rbac.config import RBACConfig, Role
from django_matt.auth.rbac.decorators import requires_rbac_permission, requires_role_hierarchy
from django_matt.auth.rbac.utils import (
    get_user_permissions,
    get_user_roles,
    user_has_permission,
)

User = get_user_model()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture(autouse=True)
def _reset_rbac():
    """Reset RBAC singleton between tests."""
    RBACConfig._instance = None
    RBACConfig()
    yield
    RBACConfig._instance = None


@pytest.fixture
@pytest.mark.django_db
def editor_user(db):
    user = User.objects.create_user(
        username="rbaceditor",
        email="rbaceditor@example.com",
        password="TestPass123!",
        is_active=True,
    )
    group, _ = Group.objects.get_or_create(name="editor")
    viewer_group, _ = Group.objects.get_or_create(name="viewer")
    user.groups.add(group, viewer_group)
    return user


@pytest.fixture
@pytest.mark.django_db
def admin_user(db):
    user = User.objects.create_user(
        username="rbacadmin",
        email="rbacadmin@example.com",
        password="TestPass123!",
        is_active=True,
    )
    group, _ = Group.objects.get_or_create(name="admin")
    user.groups.add(group)
    return user


@pytest.fixture
@pytest.mark.django_db
def superuser(db):
    return User.objects.create_superuser(
        username="rbacsuperadmin",
        email="rbacsuperadmin@example.com",
        password="TestPass123!",
    )


@pytest.fixture
@pytest.mark.django_db
def plain_user(db):
    return User.objects.create_user(
        username="rbacplain",
        email="rbacplain@example.com",
        password="TestPass123!",
        is_active=True,
    )


# =============================================================================
# Resource-scoped permissions
# =============================================================================


class TestResourceScopedPermissions:
    def test_has_permission_with_resource(self):
        config = RBACConfig()
        config.register_role(
            Role(
                name="project_editor",
                permissions=["projects.read", "projects.update"],
                priority=2,
            )
        )
        assert config.has_permission("project_editor", "read", resource="projects") is True
        assert config.has_permission("project_editor", "delete", resource="projects") is False

    def test_resource_wildcard_permission(self):
        config = RBACConfig()
        config.register_role(
            Role(
                name="project_admin",
                permissions=["projects.*"],
                priority=3,
            )
        )
        assert config.has_permission("project_admin", "delete", resource="projects") is True
        assert config.has_permission("project_admin", "read", resource="projects") is True

    def test_resource_scoped_no_match_other_resource(self):
        config = RBACConfig()
        config.register_role(
            Role(
                name="project_editor",
                permissions=["projects.read"],
                priority=2,
            )
        )
        # Should not have permission for a different resource
        assert config.has_permission("project_editor", "read", resource="users") is False

    def test_clear_cache(self):
        config = RBACConfig()
        # Prime the cache
        config.get_role_permissions("viewer")
        assert len(config._permission_cache) > 0
        config.clear_cache()
        assert len(config._permission_cache) == 0

    def test_circular_inheritance_protection(self):
        """Circular role inheritance should not cause infinite loop."""
        config = RBACConfig()
        config.register_role(Role(name="role_a", permissions=["perm_a"], inherits=["role_b"]))
        config.register_role(Role(name="role_b", permissions=["perm_b"], inherits=["role_a"]))
        config.clear_cache()
        perms = config.get_role_permissions("role_a")
        assert "perm_a" in perms
        assert "perm_b" in perms

    def test_nonexistent_role_permissions_empty(self):
        config = RBACConfig()
        perms = config.get_role_permissions("nonexistent")
        assert perms == set()

    def test_nonexistent_role_priority_zero(self):
        config = RBACConfig()
        assert config.get_role_priority("nonexistent") == 0


# =============================================================================
# Async RBAC decorators
# =============================================================================


class TestRequiresRoleHierarchyAsync:
    """Async RBAC decorator tests.

    The RBAC decorators call ``get_user_roles()`` which does sync ORM.
    For async tests with authenticated users we mock ``get_user_roles``
    to avoid ``SynchronousOnlyOperation``.  The real ``get_user_roles``
    is already tested in sync tests above.
    """

    _ROLES_PATCH = "django_matt.auth.rbac.decorators.get_user_roles"

    @pytest.mark.django_db
    async def test_async_unauthenticated(self, rf):
        @requires_role_hierarchy("viewer")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = AnonymousUser()
        response = await view(request)
        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "unauthenticated"

    @pytest.mark.django_db
    async def test_async_no_user(self, rf):
        @requires_role_hierarchy("viewer")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        if hasattr(request, "user"):
            delattr(request, "user")
        response = await view(request)
        assert response.status_code == 401

    @pytest.mark.django_db
    async def test_async_pass(self, rf, editor_user):
        @requires_role_hierarchy("viewer")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = editor_user
        with patch(self._ROLES_PATCH, return_value=["editor", "viewer"]):
            response = await view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    async def test_async_fail_insufficient_role(self, rf, editor_user):
        @requires_role_hierarchy("admin")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = editor_user
        with patch(self._ROLES_PATCH, return_value=["editor", "viewer"]):
            response = await view(request)
        assert response.status_code == 403
        body = json.loads(response.content)
        assert body["code"] == "insufficient_role"

    @pytest.mark.django_db
    async def test_async_custom_message(self, rf, plain_user):
        @requires_role_hierarchy("admin", message="Admins only.")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = plain_user
        with patch(self._ROLES_PATCH, return_value=[]):
            response = await view(request)
        assert response.status_code == 403
        body = json.loads(response.content)
        assert body["detail"] == "Admins only."


class TestRequiresRbacPermissionAsync:
    _PERM_PATCH = "django_matt.auth.rbac.decorators.user_has_permission"

    @pytest.mark.django_db
    async def test_async_unauthenticated_returns_401(self, rf):
        @requires_rbac_permission("read")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = AnonymousUser()
        response = await view(request)
        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "unauthenticated"

    @pytest.mark.django_db
    async def test_async_permission_granted(self, rf, editor_user):
        @requires_rbac_permission("read")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = editor_user
        with patch(self._PERM_PATCH, return_value=True):
            response = await view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    async def test_async_permission_denied(self, rf, plain_user):
        @requires_rbac_permission("manage_users")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = plain_user
        with patch(self._PERM_PATCH, return_value=False):
            response = await view(request)
        assert response.status_code == 403
        body = json.loads(response.content)
        assert body["code"] == "permission_denied"

    @pytest.mark.django_db
    async def test_async_with_resource_scope(self, rf, editor_user):
        """Editor has 'create' but not scoped to 'billing'."""

        @requires_rbac_permission("create", resource="billing")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = editor_user
        with patch(self._PERM_PATCH, return_value=False):
            response = await view(request)
        assert response.status_code == 403

    @pytest.mark.django_db
    async def test_async_superuser_bypasses(self, rf, superuser):
        @requires_rbac_permission("any_permission", resource="any_resource")
        async def view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        request.user = superuser
        with patch(self._PERM_PATCH, return_value=True):
            response = await view(request)
        assert response.status_code == 200


# =============================================================================
# Sync decorators with controller-style self argument
# =============================================================================


class TestDecoratorRequestExtraction:
    @pytest.mark.django_db
    def test_self_with_request_attr(self, rf, editor_user):
        """Decorator should extract request from self.request (controller pattern)."""

        @requires_rbac_permission("read")
        def view(controller):
            return {"ok": True}

        class FakeController:
            pass

        ctrl = FakeController()
        ctrl.request = rf.get("/")
        ctrl.request.user = editor_user
        result = view(ctrl)
        assert isinstance(result, dict)
        assert result["ok"] is True

    @pytest.mark.django_db
    def test_request_as_second_arg(self, rf, editor_user):
        """Decorator should find request in args[0] if self is not HttpRequest."""

        @requires_rbac_permission("read")
        def view(self_arg, request):
            return {"ok": True}

        request = rf.get("/")
        request.user = editor_user
        result = view("not_self", request)
        assert isinstance(result, dict)


# =============================================================================
# get_user_permissions aggregation
# =============================================================================


class TestGetUserPermissions:
    @pytest.mark.django_db
    def test_editor_gets_inherited_permissions(self, editor_user):
        perms = get_user_permissions(editor_user)
        # Editor's own + inherited from viewer
        assert "create" in perms
        assert "update" in perms
        assert "read" in perms
        assert "list" in perms

    @pytest.mark.django_db
    def test_plain_user_no_permissions(self, plain_user):
        perms = get_user_permissions(plain_user)
        assert len(perms) == 0

    @pytest.mark.django_db
    def test_superuser_has_wildcard(self, superuser):
        perms = get_user_permissions(superuser)
        assert "*" in perms

    def test_anonymous_user_no_permissions(self):
        perms = get_user_permissions(AnonymousUser())
        assert len(perms) == 0

    def test_none_user_no_permissions(self):
        perms = get_user_permissions(None)
        assert len(perms) == 0
