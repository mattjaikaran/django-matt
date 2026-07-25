"""
Tests for django_matt/permissions/ — Permission classes, decorators, and utilities.

Covers:
- BasePermission / Permission / OperationPermission / PermissionDenied
- AllowAny, IsAuthenticated, IsAdmin, IsStaff, IsSuperUser
- IsOwner (object-level), HasRole, HasPermission
- IsAuthenticatedOrReadOnly, IsAdminOrReadOnly
- check_permissions, get_request helper
- Decorators: requires_permission, requires_permissions, requires_role,
  authenticated, allow_any, with_permissions
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.permissions.base import (
    BasePermission,
    OperationPermission,
    Permission,
    PermissionDenied,
)
from django_matt.permissions.common import (
    AllowAny,
    HasPermission,
    HasRole,
    IsAdmin,
    IsAdminOrReadOnly,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    IsOwner,
    IsStaff,
    IsSuperUser,
)
from django_matt.permissions.decorators.auth import allow_any as allow_any_decorator
from django_matt.permissions.decorators.auth import authenticated
from django_matt.permissions.decorators.base import check_permissions, get_request
from django_matt.permissions.decorators.permission import (
    requires_permission,
    requires_permissions,
    with_permissions,
)
from django_matt.permissions.decorators.role import requires_role

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    *,
    authenticated: bool = True,
    is_staff: bool = False,
    is_superuser: bool = False,
    pk: int = 1,
    groups: list[str] | None = None,
    role: str | None = None,
    perms: list[str] | None = None,
):
    """Build a mock user with the given attributes."""
    user = MagicMock()
    user.pk = pk
    user.is_authenticated = authenticated
    user.is_staff = is_staff
    user.is_superuser = is_superuser

    # Groups queryset mock
    group_names = groups or []
    group_qs = MagicMock()
    group_qs.values_list.return_value = group_names
    user.groups = group_qs

    # Role attribute
    if role is not None:
        user.role = role
    else:
        # Remove .role so hasattr returns False
        del user.role

    # Remove .roles (many-to-many) by default
    if not hasattr(user, "roles"):
        pass  # MagicMock auto-creates attrs; explicitly delete
    del user.roles

    # Django permissions
    _perms = set(perms or [])
    user.has_perm = lambda p: p in _perms
    user.has_perms = lambda ps: all(p in _perms for p in ps)

    return user


def _make_request(method: str = "GET", user=None) -> HttpRequest:
    """Build a Django request with the given method and user."""
    rf = RequestFactory()
    method_fn = getattr(rf, method.lower())
    request = method_fn("/test/")
    request.user = user if user is not None else AnonymousUser()
    return request


# ---------------------------------------------------------------------------
# BasePermission / Permission / PermissionDenied
# ---------------------------------------------------------------------------


class TestBasePermission:
    """Tests for base permission classes."""

    def test_permission_default_denies(self):
        """Permission (convenience base) denies by default."""
        perm = Permission()
        request = _make_request()
        assert perm.has_permission(request) is False

    def test_base_permission_has_object_permission_default(self):
        """BasePermission.has_object_permission defaults to True."""
        perm = Permission()
        request = _make_request()
        assert perm.has_object_permission(request, None, object()) is True

    def test_get_message(self):
        """get_message returns the class-level message."""
        perm = Permission()
        assert perm.get_message() == "Permission denied."

    def test_get_status_code(self):
        """get_status_code returns the class-level status_code."""
        perm = Permission()
        assert perm.get_status_code() == 403


class TestPermissionDenied:
    """Tests for the PermissionDenied exception."""

    def test_default(self):
        """Default PermissionDenied has 403 and message."""
        exc = PermissionDenied()
        assert exc.status_code == 403
        assert exc.message == "Permission denied."
        assert exc.permission is None
        assert str(exc) == "Permission denied."

    def test_custom_message(self):
        """PermissionDenied accepts custom message."""
        exc = PermissionDenied(message="Nope")
        assert exc.message == "Nope"

    def test_with_permission(self):
        """PermissionDenied str includes the permission when set."""
        exc = PermissionDenied(permission="admin.delete")
        assert "admin.delete" in str(exc)
        assert exc.permission == "admin.delete"

    def test_custom_status_code(self):
        """PermissionDenied accepts custom status code."""
        exc = PermissionDenied(status_code=401)
        assert exc.status_code == 401

    def test_is_exception(self):
        """PermissionDenied is a proper Exception."""
        with pytest.raises(PermissionDenied):
            raise PermissionDenied("test")


# ---------------------------------------------------------------------------
# AllowAny
# ---------------------------------------------------------------------------


class TestAllowAny:
    """Tests for the AllowAny permission class."""

    def test_allows_anonymous(self):
        """AllowAny grants access to anonymous users."""
        perm = AllowAny()
        request = _make_request()
        assert perm.has_permission(request) is True

    def test_allows_authenticated(self):
        """AllowAny grants access to authenticated users."""
        perm = AllowAny()
        user = _make_user(authenticated=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True


# ---------------------------------------------------------------------------
# IsAuthenticated
# ---------------------------------------------------------------------------


class TestIsAuthenticated:
    """Tests for the IsAuthenticated permission class."""

    def test_authenticated_user_allowed(self):
        """Authenticated user passes IsAuthenticated."""
        perm = IsAuthenticated()
        user = _make_user(authenticated=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_anonymous_user_denied(self):
        """Anonymous user is denied by IsAuthenticated."""
        perm = IsAuthenticated()
        request = _make_request()  # AnonymousUser
        assert perm.has_permission(request) is False

    def test_no_user_attribute(self):
        """Request without user attribute is denied."""
        perm = IsAuthenticated()
        rf = RequestFactory()
        request = rf.get("/test/")
        # Remove user attribute entirely
        if hasattr(request, "user"):
            delattr(request, "user")
        assert perm.has_permission(request) is False

    def test_status_code_is_401(self):
        """IsAuthenticated returns 401 on denial."""
        perm = IsAuthenticated()
        assert perm.get_status_code() == 401

    def test_message(self):
        """IsAuthenticated has correct message."""
        perm = IsAuthenticated()
        assert perm.get_message() == "Authentication required."


# ---------------------------------------------------------------------------
# IsAdmin
# ---------------------------------------------------------------------------


class TestIsAdmin:
    """Tests for the IsAdmin permission class."""

    def test_staff_user_allowed(self):
        """Staff user passes IsAdmin."""
        perm = IsAdmin()
        user = _make_user(is_staff=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_superuser_allowed(self):
        """Superuser passes IsAdmin."""
        perm = IsAdmin()
        user = _make_user(is_superuser=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_regular_user_denied(self):
        """Regular user is denied by IsAdmin."""
        perm = IsAdmin()
        user = _make_user(is_staff=False, is_superuser=False)
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_anonymous_denied(self):
        """Anonymous user is denied by IsAdmin."""
        perm = IsAdmin()
        request = _make_request()
        assert perm.has_permission(request) is False


# ---------------------------------------------------------------------------
# IsStaff
# ---------------------------------------------------------------------------


class TestIsStaff:
    """Tests for the IsStaff permission class."""

    def test_staff_allowed(self):
        perm = IsStaff()
        user = _make_user(is_staff=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_non_staff_denied(self):
        perm = IsStaff()
        user = _make_user(is_staff=False)
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_anonymous_denied(self):
        perm = IsStaff()
        request = _make_request()
        assert perm.has_permission(request) is False


# ---------------------------------------------------------------------------
# IsSuperUser
# ---------------------------------------------------------------------------


class TestIsSuperUser:
    """Tests for the IsSuperUser permission class."""

    def test_superuser_allowed(self):
        perm = IsSuperUser()
        user = _make_user(is_superuser=True)
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_staff_denied(self):
        perm = IsSuperUser()
        user = _make_user(is_staff=True, is_superuser=False)
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_anonymous_denied(self):
        perm = IsSuperUser()
        request = _make_request()
        assert perm.has_permission(request) is False


# ---------------------------------------------------------------------------
# IsOwner
# ---------------------------------------------------------------------------


class TestIsOwner:
    """Tests for the IsOwner permission class."""

    def test_has_permission_always_true(self):
        """IsOwner.has_permission always returns True (checked at object level)."""
        perm = IsOwner()
        request = _make_request()
        assert perm.has_permission(request) is True

    def test_owner_via_user_field(self):
        """User is identified as owner through obj.user."""
        perm = IsOwner()
        user = _make_user(pk=42)
        request = _make_request(user=user)
        obj = SimpleNamespace(user=MagicMock(pk=42))
        assert perm.has_object_permission(request, None, obj) is True

    def test_owner_via_owner_field(self):
        """User is identified as owner through obj.owner."""
        perm = IsOwner()
        user = _make_user(pk=7)
        request = _make_request(user=user)
        obj = SimpleNamespace(owner=MagicMock(pk=7))
        # Remove other owner fields
        assert perm.has_object_permission(request, None, obj) is True

    def test_owner_via_created_by_field(self):
        """User is identified as owner through obj.created_by."""
        perm = IsOwner()
        user = _make_user(pk=10)
        request = _make_request(user=user)
        # Only created_by set, user/owner not present
        obj = MagicMock(spec=["created_by"])
        obj.created_by = MagicMock(pk=10)
        assert perm.has_object_permission(request, None, obj) is True

    def test_owner_via_author_field(self):
        """User is identified as owner through obj.author."""
        perm = IsOwner()
        user = _make_user(pk=5)
        request = _make_request(user=user)
        obj = MagicMock(spec=["author"])
        obj.author = MagicMock(pk=5)
        assert perm.has_object_permission(request, None, obj) is True

    def test_not_owner(self):
        """Different user is denied."""
        perm = IsOwner()
        user = _make_user(pk=1)
        request = _make_request(user=user)
        obj = SimpleNamespace(user=MagicMock(pk=999))
        assert perm.has_object_permission(request, None, obj) is False

    def test_anonymous_not_owner(self):
        """Anonymous user is never an owner."""
        perm = IsOwner()
        request = _make_request()
        obj = SimpleNamespace(user=MagicMock(pk=1))
        assert perm.has_object_permission(request, None, obj) is False

    def test_no_owner_field(self):
        """Object without any owner field returns False."""
        perm = IsOwner()
        user = _make_user(pk=1)
        request = _make_request(user=user)
        obj = SimpleNamespace(title="no owner field")
        assert perm.has_object_permission(request, None, obj) is False

    def test_owner_field_direct_equality(self):
        """When owner field has no .pk, falls back to direct equality."""
        perm = IsOwner()
        user = _make_user(pk=1)
        request = _make_request(user=user)
        # owner is a plain value (e.g., user_id integer) — uses == comparison
        obj = SimpleNamespace(user=user)
        assert perm.has_object_permission(request, None, obj) is True


# ---------------------------------------------------------------------------
# HasRole
# ---------------------------------------------------------------------------


class TestHasRole:
    """Tests for the HasRole permission class."""

    def test_no_roles_required(self):
        """HasRole with no roles allows any authenticated user."""
        perm = HasRole(roles=[])
        user = _make_user()
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_none_roles(self):
        """HasRole(roles=None) treats as empty list."""
        perm = HasRole(roles=None)
        user = _make_user()
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_single_string_role(self):
        """HasRole accepts a single string role."""
        perm = HasRole(roles="admin")
        assert perm.roles == ["admin"]

    def test_user_in_group(self):
        """User with matching group passes HasRole."""
        perm = HasRole(roles=["editor", "admin"])
        user = _make_user(groups=["editor"])
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_user_not_in_group(self):
        """User without matching group is denied."""
        perm = HasRole(roles=["admin"])
        user = _make_user(groups=["viewer"])
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_user_with_role_attribute(self):
        """User with a .role string attribute passes."""
        perm = HasRole(roles=["manager"])
        user = _make_user(role="manager", groups=[])
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_user_with_wrong_role_attribute(self):
        """User with non-matching .role string is denied."""
        perm = HasRole(roles=["admin"])
        user = _make_user(role="viewer", groups=[])
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_anonymous_denied(self):
        """Anonymous user is denied by HasRole."""
        perm = HasRole(roles=["admin"])
        request = _make_request()
        assert perm.has_permission(request) is False


# ---------------------------------------------------------------------------
# HasPermission
# ---------------------------------------------------------------------------


class TestHasPermission:
    """Tests for the HasPermission permission class."""

    def test_no_permissions_required(self):
        """HasPermission with no perms allows any authenticated user."""
        perm = HasPermission(permissions=[])
        user = _make_user()
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_single_string_permission(self):
        """HasPermission accepts a single string."""
        perm = HasPermission(permissions="app.view_model")
        assert perm.permissions == ["app.view_model"]

    def test_user_has_any_permission(self):
        """User with any matching perm passes (require_all=False)."""
        perm = HasPermission(permissions=["app.view", "app.edit"], require_all=False)
        user = _make_user(perms=["app.view"])
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_user_has_all_permissions(self):
        """User with all perms passes (require_all=True)."""
        perm = HasPermission(permissions=["a.view", "a.edit"], require_all=True)
        user = _make_user(perms=["a.view", "a.edit"])
        request = _make_request(user=user)
        assert perm.has_permission(request) is True

    def test_user_missing_one_perm_require_all(self):
        """User missing one perm is denied when require_all=True."""
        perm = HasPermission(permissions=["a.view", "a.edit"], require_all=True)
        user = _make_user(perms=["a.view"])
        request = _make_request(user=user)
        assert perm.has_permission(request) is False

    def test_anonymous_denied(self):
        """Anonymous user is denied by HasPermission."""
        perm = HasPermission(permissions=["app.view"])
        request = _make_request()
        assert perm.has_permission(request) is False


# ---------------------------------------------------------------------------
# IsAuthenticatedOrReadOnly
# ---------------------------------------------------------------------------


class TestIsAuthenticatedOrReadOnly:
    """Tests for the IsAuthenticatedOrReadOnly permission class."""

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_allow_anonymous(self, method):
        """Safe methods are allowed for anonymous users."""
        perm = IsAuthenticatedOrReadOnly()
        request = _make_request(method=method)
        assert perm.has_permission(request) is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_unsafe_methods_deny_anonymous(self, method):
        """Unsafe methods deny anonymous users."""
        perm = IsAuthenticatedOrReadOnly()
        request = _make_request(method=method)
        assert perm.has_permission(request) is False

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_unsafe_methods_allow_authenticated(self, method):
        """Unsafe methods allow authenticated users."""
        perm = IsAuthenticatedOrReadOnly()
        user = _make_user()
        request = _make_request(method=method, user=user)
        assert perm.has_permission(request) is True


# ---------------------------------------------------------------------------
# IsAdminOrReadOnly
# ---------------------------------------------------------------------------


class TestIsAdminOrReadOnly:
    """Tests for the IsAdminOrReadOnly permission class."""

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_allow_anyone(self, method):
        """Safe methods are allowed for all users."""
        perm = IsAdminOrReadOnly()
        request = _make_request(method=method)
        assert perm.has_permission(request) is True

    def test_post_denied_for_regular_user(self):
        """POST denied for non-admin authenticated user."""
        perm = IsAdminOrReadOnly()
        user = _make_user(is_staff=False, is_superuser=False)
        request = _make_request(method="POST", user=user)
        assert perm.has_permission(request) is False

    def test_post_allowed_for_admin(self):
        """POST allowed for admin user."""
        perm = IsAdminOrReadOnly()
        user = _make_user(is_staff=True)
        request = _make_request(method="POST", user=user)
        assert perm.has_permission(request) is True


# ---------------------------------------------------------------------------
# OperationPermission
# ---------------------------------------------------------------------------


class TestOperationPermission:
    """Tests for the OperationPermission base class."""

    def test_no_permissions_configured_allows(self):
        """OperationPermission with no perms set allows all methods."""

        class NoPerms(OperationPermission):
            pass

        perm = NoPerms()
        user = _make_user()
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = _make_request(method=method, user=user)
            assert perm.has_permission(request) is True, f"Failed for {method}"

    def test_get_checks_read_permission(self):
        """GET checks read_permission."""

        class ReadPerm(OperationPermission):
            read_permission = "app.view"

        perm = ReadPerm()
        user_with = _make_user(perms=["app.view"])
        user_without = _make_user(perms=[])

        req_with = _make_request(method="GET", user=user_with)
        req_without = _make_request(method="GET", user=user_without)

        assert perm.has_permission(req_with) is True
        assert perm.has_permission(req_without) is False

    def test_post_checks_create_permission(self):
        """POST checks create_permission."""

        class CreatePerm(OperationPermission):
            create_permission = "app.add"

        perm = CreatePerm()
        user = _make_user(perms=["app.add"])
        request = _make_request(method="POST", user=user)
        assert perm.has_permission(request) is True

    def test_put_checks_update_permission(self):
        """PUT/PATCH check update_permission."""

        class UpdatePerm(OperationPermission):
            update_permission = "app.change"

        perm = UpdatePerm()
        user = _make_user(perms=["app.change"])
        for method in ["PUT", "PATCH"]:
            request = _make_request(method=method, user=user)
            assert perm.has_permission(request) is True

    def test_delete_checks_delete_permission(self):
        """DELETE checks delete_permission."""

        class DeletePerm(OperationPermission):
            delete_permission = "app.delete"

        perm = DeletePerm()
        user = _make_user(perms=["app.delete"])
        request = _make_request(method="DELETE", user=user)
        assert perm.has_permission(request) is True

    def test_anonymous_denied(self):
        """Anonymous user is denied when permission is required."""

        class ReadPerm(OperationPermission):
            read_permission = "app.view"

        perm = ReadPerm()
        request = _make_request(method="GET")
        assert perm.has_permission(request) is False

    def test_unknown_method_allows(self):
        """Unknown HTTP method (e.g., TRACE) is allowed by default."""

        class SomePerm(OperationPermission):
            read_permission = "app.view"

        perm = SomePerm()
        user = _make_user()
        rf = RequestFactory()
        request = rf.generic("TRACE", "/test/")
        request.user = user
        assert perm.has_permission(request) is True


# ---------------------------------------------------------------------------
# check_permissions helper
# ---------------------------------------------------------------------------


class TestCheckPermissions:
    """Tests for the check_permissions utility function."""

    def test_all_pass(self):
        """When all permissions pass, returns (True, None, 200)."""
        perm = AllowAny()
        request = _make_request()
        allowed, msg, code = check_permissions(request, [perm])
        assert allowed is True
        assert msg is None
        assert code == 200

    def test_first_fails(self):
        """When first permission fails, returns failure info."""
        perm = IsAuthenticated()
        request = _make_request()  # Anonymous
        allowed, msg, code = check_permissions(request, [perm])
        assert allowed is False
        assert msg == "Authentication required."
        assert code == 401

    def test_object_permission_checked(self):
        """Object-level permission is checked when obj is provided."""
        perm = IsOwner()
        user = _make_user(pk=1)
        request = _make_request(user=user)
        obj = SimpleNamespace(user=MagicMock(pk=999))  # Different user
        allowed, msg, code = check_permissions(request, [perm], obj=obj)
        assert allowed is False

    def test_multiple_permissions_all_pass(self):
        """All permissions must pass."""
        perms = [AllowAny(), AllowAny()]
        request = _make_request()
        allowed, msg, code = check_permissions(request, perms)
        assert allowed is True

    def test_multiple_permissions_one_fails(self):
        """If any permission fails, access is denied."""
        perms = [AllowAny(), IsAuthenticated()]
        request = _make_request()  # Anonymous
        allowed, msg, code = check_permissions(request, perms)
        assert allowed is False
        assert code == 401


# ---------------------------------------------------------------------------
# get_request helper
# ---------------------------------------------------------------------------


class TestGetRequest:
    """Tests for the get_request utility function."""

    def test_from_self_with_request_attr(self):
        """Extracts request from self.request."""
        rf = RequestFactory()
        request = rf.get("/test/")
        obj = SimpleNamespace(request=request)
        assert get_request(obj, (), {}) is request

    def test_from_direct_request(self):
        """Extracts when first arg is an HttpRequest."""
        rf = RequestFactory()
        request = rf.get("/test/")
        assert get_request(request, (), {}) is request

    def test_from_args(self):
        """Extracts request from args[0]."""
        rf = RequestFactory()
        request = rf.get("/test/")
        assert get_request("self", (request,), {}) is request

    def test_from_kwargs(self):
        """Extracts request from kwargs['request']."""
        rf = RequestFactory()
        request = rf.get("/test/")
        assert get_request("self", (), {"request": request}) is request

    def test_returns_none(self):
        """Returns None if no request found."""
        assert get_request("self", (), {}) is None


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


class TestAuthenticatedDecorator:
    """Tests for the @authenticated decorator."""

    def test_sync_authenticated_allowed(self):
        """Authenticated user passes @authenticated on sync function."""

        @authenticated
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user()
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_sync_anonymous_denied(self):
        """Anonymous user is denied by @authenticated on sync function."""

        @authenticated
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        resp = my_view(request)
        assert resp.status_code == 401
        body = json.loads(resp.content)
        assert body["code"] == "authentication_required"

    @pytest.mark.asyncio
    async def test_async_authenticated_allowed(self):
        """Authenticated user passes @authenticated on async function."""

        @authenticated
        async def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user()
        request = _make_request(user=user)
        resp = await my_view(request)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_async_anonymous_denied(self):
        """Anonymous user is denied by @authenticated on async function."""

        @authenticated
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        resp = await my_view(request)
        assert resp.status_code == 401


class TestAllowAnyDecorator:
    """Tests for the @allow_any decorator."""

    def test_marks_function(self):
        """@allow_any sets _allow_any attribute on function."""

        @allow_any_decorator
        def my_view(request):
            return JsonResponse({"ok": True})

        assert my_view._allow_any is True

    def test_function_still_callable(self):
        """Decorated function is still callable."""

        @allow_any_decorator
        def my_view(request):
            return JsonResponse({"ok": True})

        rf = RequestFactory()
        resp = my_view(rf.get("/test/"))
        assert resp.status_code == 200


class TestRequiresPermissionDecorator:
    """Tests for the @requires_permission decorator."""

    def test_user_with_perm_allowed(self):
        """User with required perm passes."""

        @requires_permission("app.view_model")
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(perms=["app.view_model"])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_user_without_perm_denied(self):
        """User without required perm is denied."""

        @requires_permission("app.delete_model")
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(perms=[])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 403

    def test_anonymous_denied(self):
        """Anonymous user denied by @requires_permission."""

        @requires_permission("app.view")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        resp = my_view(request)
        assert resp.status_code == 403


class TestRequiresPermissionsDecorator:
    """Tests for the @requires_permissions decorator."""

    def test_require_all_passes(self):
        """User with all perms passes when require_all=True."""

        @requires_permissions("a.view", "a.edit", require_all=True)
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(perms=["a.view", "a.edit"])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_require_all_fails_missing_one(self):
        """User missing one perm is denied when require_all=True."""

        @requires_permissions("a.view", "a.edit", require_all=True)
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(perms=["a.view"])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 403


class TestRequiresRoleDecorator:
    """Tests for the @requires_role decorator."""

    def test_user_with_role_allowed(self):
        """User with matching group passes @requires_role."""

        @requires_role("editor")
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(groups=["editor"])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_user_without_role_denied(self):
        """User without matching group is denied."""

        @requires_role("admin")
        def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(groups=["viewer"])
        request = _make_request(user=user)
        resp = my_view(request)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_async_role_check(self):
        """@requires_role works on async functions."""

        @requires_role("manager")
        async def my_view(request):
            return JsonResponse({"ok": True})

        user = _make_user(groups=["manager"])
        request = _make_request(user=user)
        resp = await my_view(request)
        assert resp.status_code == 200


class TestWithPermissionsDecorator:
    """Tests for the @with_permissions decorator."""

    def test_all_permissions_pass(self):
        """All permission classes must pass."""

        @with_permissions(AllowAny)
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()
        resp = my_view(request)
        assert resp.status_code == 200

    def test_one_permission_fails(self):
        """If any permission class denies, access is denied."""

        @with_permissions(AllowAny, IsAuthenticated)
        def my_view(request):
            return JsonResponse({"ok": True})

        request = _make_request()  # Anonymous
        resp = my_view(request)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Combined permissions
# ---------------------------------------------------------------------------


class TestCombinedPermissions:
    """Tests combining multiple permission classes."""

    def test_authenticated_and_admin(self):
        """Both IsAuthenticated and IsAdmin must pass."""
        perms = [IsAuthenticated(), IsAdmin()]
        user = _make_user(is_staff=True)
        request = _make_request(user=user)
        allowed, _, _ = check_permissions(request, perms)
        assert allowed is True

    def test_authenticated_passes_admin_fails(self):
        """Authenticated but non-admin user is denied."""
        perms = [IsAuthenticated(), IsAdmin()]
        user = _make_user(is_staff=False)
        request = _make_request(user=user)
        allowed, msg, code = check_permissions(request, perms)
        assert allowed is False
        assert code == 403  # IsAdmin denies with 403

    def test_authenticated_owner_combo(self):
        """IsAuthenticated + IsOwner checks both levels."""
        perms = [IsAuthenticated(), IsOwner()]
        user = _make_user(pk=5)
        request = _make_request(user=user)

        # View-level: both pass
        allowed, _, _ = check_permissions(request, perms)
        assert allowed is True

        # Object-level: owner match
        obj = SimpleNamespace(user=MagicMock(pk=5))
        allowed, _, _ = check_permissions(request, perms, obj=obj)
        assert allowed is True

        # Object-level: not owner
        obj2 = SimpleNamespace(user=MagicMock(pk=99))
        allowed, _, _ = check_permissions(request, perms, obj=obj2)
        assert allowed is False
