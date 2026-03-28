"""
Tests for the Django Matt core controller module.

Tests the CRUDController with async ORM support and query optimization.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.test import RequestFactory
from django.urls import path as django_path

import pytest
from pydantic import BaseModel

# Import directly from modules to avoid full package import
from django_matt.core.controller import (
    DJANGO_5_2_PLUS,
    DJANGO_6_0_PLUS,
    DJANGO_VERSION,
    APIController,
    Controller,
    CRUDController,
)
from django_matt.core.errors import ConfigurationError, NotFoundAPIError
from django_matt.core.router import APIRouter
from django_matt.core.router import get as route_get


# Test Schemas using Pydantic BaseModel directly
class UserSchema(BaseModel):
    """Simple user schema."""
    id: int | None = None
    username: str
    email: str

    class Config:
        from_attributes = True


# Test Controllers using Django's built-in User model
class UserController(CRUDController):
    """Controller for User model."""

    model = User
    schema = UserSchema
    lookup_field = "id"


class UserWithGroupsController(CRUDController):
    """Controller with relationships for testing optimization."""

    model = User
    schema = UserSchema
    select_related_fields = []  # User has no direct FK
    prefetch_related_fields = ["groups", "user_permissions"]
    ordering = ["-date_joined"]


class NoOptimizationController(CRUDController):
    """Controller with optimization disabled."""

    model = User
    schema = UserSchema
    auto_optimize = False


class TestDjangoVersionDetection:
    """Test Django version detection."""

    def test_django_version_is_tuple(self):
        """Version should be a tuple of integers."""
        assert isinstance(DJANGO_VERSION, tuple)
        assert len(DJANGO_VERSION) == 2
        assert all(isinstance(v, int) for v in DJANGO_VERSION)

    def test_django_5_2_plus_flag(self):
        """DJANGO_5_2_PLUS should be boolean."""
        assert isinstance(DJANGO_5_2_PLUS, bool)

    def test_django_6_0_plus_flag(self):
        """DJANGO_6_0_PLUS should be boolean."""
        assert isinstance(DJANGO_6_0_PLUS, bool)

    def test_version_consistency(self):
        """Version flags should be consistent with version tuple."""
        if DJANGO_VERSION >= (5, 2):
            assert DJANGO_5_2_PLUS is True
        if DJANGO_VERSION >= (6, 0):
            assert DJANGO_6_0_PLUS is True


class TestControllerBase:
    """Test base Controller class."""

    def test_controller_has_prefix(self):
        """Controller should have a prefix attribute."""
        controller = Controller()
        assert hasattr(controller, "prefix")
        assert controller.prefix == ""

    def test_controller_has_tags(self):
        """Controller should have a tags attribute."""
        controller = Controller()
        assert hasattr(controller, "tags")
        assert controller.tags == []


class TestAPIController:
    """Test APIController class."""

    def test_inherits_from_controller(self):
        """APIController should inherit from Controller."""
        assert issubclass(APIController, Controller)

    def test_has_handle_exception_method(self):
        """APIController should have handle_exception method."""
        controller = APIController()
        assert hasattr(controller, "handle_exception")
        assert callable(controller.handle_exception)


class TestCRUDControllerConfiguration:
    """Test CRUDController configuration options."""

    def test_default_auto_optimize(self):
        """auto_optimize should be True by default."""
        controller = UserController()
        assert controller.auto_optimize is True

    def test_auto_optimize_disabled(self):
        """auto_optimize can be disabled."""
        controller = NoOptimizationController()
        assert controller.auto_optimize is False

    def test_default_lookup_field(self):
        """lookup_field should be 'id' by default."""
        controller = UserController()
        assert controller.lookup_field == "id"

    def test_default_ordering(self):
        """ordering should be None by default."""
        controller = UserController()
        assert controller.ordering is None

    def test_custom_ordering(self):
        """ordering can be customized."""
        controller = UserWithGroupsController()
        assert controller.ordering == ["-date_joined"]

    def test_manual_prefetch_related_fields(self):
        """prefetch_related_fields can be set manually."""
        controller = UserWithGroupsController()
        assert "groups" in controller.prefetch_related_fields


class TestCRUDControllerQueryOptimization:
    """Test query optimization features."""

    def test_get_many_to_many_fields(self):
        """Should detect many-to-many fields."""
        controller = UserController()
        m2m_fields = controller._get_many_to_many_fields()
        assert "groups" in m2m_fields
        assert "user_permissions" in m2m_fields

    def test_get_query_optimization_info(self):
        """Should return optimization info dict."""
        controller = UserController()
        info = controller.get_query_optimization_info()

        assert "auto_optimize" in info
        assert "select_related_fields" in info
        assert "prefetch_related_fields" in info
        assert "include_reverse_relations" in info
        assert "ordering" in info
        assert "lookup_field" in info

    def test_optimization_info_with_manual_settings(self):
        """Optimization info should reflect manual settings."""
        controller = UserWithGroupsController()
        info = controller.get_query_optimization_info()

        assert "groups" in info["prefetch_related_fields"]

    def test_optimization_info_when_disabled(self):
        """Optimization info should show empty lists when disabled."""
        controller = NoOptimizationController()
        info = controller.get_query_optimization_info()

        assert info["auto_optimize"] is False
        assert info["select_related_fields"] == []
        assert info["prefetch_related_fields"] == []


class TestCRUDControllerMethods:
    """Test CRUDController method signatures."""

    def test_list_is_async(self):
        """list method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.list)

    def test_retrieve_is_async(self):
        """retrieve method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.retrieve)

    def test_create_is_async(self):
        """create method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.create)

    def test_update_is_async(self):
        """update method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.update)

    def test_partial_update_is_async(self):
        """partial_update method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.partial_update)

    def test_delete_is_async(self):
        """delete method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.delete)

    def test_bulk_create_is_async(self):
        """bulk_create method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.bulk_create)

    def test_bulk_update_is_async(self):
        """bulk_update method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.bulk_update)

    def test_exists_is_async(self):
        """exists method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.exists)

    def test_count_is_async(self):
        """count method should be async."""
        import asyncio

        controller = UserController()
        assert asyncio.iscoroutinefunction(controller.count)


class TestCRUDControllerGetQueryset:
    """Test get_queryset and get_optimized_queryset methods."""

    def test_get_queryset_returns_all(self):
        """get_queryset should return all objects."""
        controller = UserController()
        qs = controller.get_queryset()
        assert qs.model == User

    def test_get_queryset_raises_without_model(self):
        """get_queryset should raise ConfigurationError if model not set."""
        controller = CRUDController()
        with pytest.raises(ConfigurationError):
            controller.get_queryset()

    def test_get_optimized_queryset_applies_ordering(self):
        """get_optimized_queryset should apply ordering."""
        controller = UserWithGroupsController()
        qs = controller.get_optimized_queryset()
        # Check that ordering is in the query
        assert qs.query.order_by == ("-date_joined",)


class TestCRUDControllerFilterQueryset:
    """Test filter_queryset method."""

    def test_filter_queryset_skips_pagination_params(self, rf):
        """filter_queryset should skip pagination parameters."""
        controller = UserController()
        request = rf.get("/users/?page=1&page_size=10&username=test")
        qs = controller.get_queryset()
        filtered = controller.filter_queryset(qs, request)
        # Should have username filter but not page/page_size
        sql = str(filtered.query)
        assert "username" in sql.lower()

    def test_filter_queryset_handles_lookups(self, rf):
        """filter_queryset should handle field lookups."""
        controller = UserController()
        request = rf.get("/users/?username__icontains=john")
        qs = controller.get_queryset()
        filtered = controller.filter_queryset(qs, request)
        sql = str(filtered.query)
        assert "username" in sql.lower()


class TestCRUDControllerInheritance:
    """Test that CRUDController properly inherits from APIController."""

    def test_inherits_from_api_controller(self):
        """CRUDController should inherit from APIController."""
        assert issubclass(CRUDController, APIController)

    def test_inherits_from_controller(self):
        """CRUDController should inherit from Controller."""
        assert issubclass(CRUDController, Controller)

    def test_has_handle_exception(self):
        """CRUDController should have handle_exception from APIController."""
        controller = UserController()
        assert hasattr(controller, "handle_exception")


class TestStaticBeforeParameterizedOrdering:
    """Test CORE-11: Static routes are matched before parameterized routes.

    Verifies that APIRouter.get_urls() returns URL patterns such that
    static (non-parameterized) paths always appear before parameterized paths,
    regardless of the registration order.
    """

    def _dummy_view(self):
        """Minimal async callable for route registration."""
        async def view(request, *args, **kwargs):
            from django.http import JsonResponse
            return JsonResponse({})
        return view

    def test_static_route_before_parameterized(self):
        """CORE-11: /users/me sorts before /users/<str:id> regardless of registration order."""
        router = APIRouter()
        dummy = self._dummy_view()

        # Register parameterized route FIRST to prove ordering is not based on
        # insertion order.
        router.add_route("users/<str:id>", dummy, methods=["GET"], name="user_detail")
        router.add_route("users/me", dummy, methods=["GET"], name="user_me")

        urls = router.get_urls()
        assert len(urls) == 2

        routes = [getattr(u.pattern, "_route", str(u.pattern)) for u in urls]
        me_idx = next(i for i, r in enumerate(routes) if "me" in r)
        id_idx = next(i for i, r in enumerate(routes) if "<str:id>" in r)

        assert me_idx < id_idx, (
            f"Expected 'users/me' (idx={me_idx}) before 'users/<str:id>' (idx={id_idx}); "
            f"got routes={routes}"
        )

    def test_multiple_static_routes_preserve_declaration_order(self):
        """CORE-11: Multiple static routes appear before parameterized, preserving their own order."""
        router = APIRouter()
        dummy = self._dummy_view()

        # Register mixed order: static, param, static
        router.add_route("items/featured", dummy, methods=["GET"], name="items_featured")
        router.add_route("items/<int:id>", dummy, methods=["GET"], name="item_detail")
        router.add_route("items/popular", dummy, methods=["GET"], name="items_popular")

        urls = router.get_urls()
        assert len(urls) == 3

        routes = [getattr(u.pattern, "_route", str(u.pattern)) for u in urls]
        featured_idx = next(i for i, r in enumerate(routes) if "featured" in r)
        popular_idx = next(i for i, r in enumerate(routes) if "popular" in r)
        param_idx = next(i for i, r in enumerate(routes) if "<int:id>" in r)

        # Both statics must precede the parameterized route
        assert featured_idx < param_idx, (
            f"Expected 'items/featured' (idx={featured_idx}) before 'items/<int:id>' (idx={param_idx})"
        )
        assert popular_idx < param_idx, (
            f"Expected 'items/popular' (idx={popular_idx}) before 'items/<int:id>' (idx={param_idx})"
        )
        # Declaration order within statics is preserved: featured was added before popular
        assert featured_idx < popular_idx, (
            f"Expected 'items/featured' (idx={featured_idx}) before 'items/popular' (idx={popular_idx})"
        )

    def test_is_parameterized_path_static_returns_false(self):
        """_is_parameterized_path returns False for a static URL pattern."""
        pattern = django_path("users/me", lambda r: None, name="users_me")
        assert APIRouter._is_parameterized_path(pattern) is False

    def test_is_parameterized_path_parameterized_returns_true(self):
        """_is_parameterized_path returns True for a parameterized URL pattern."""
        pattern = django_path("users/<str:id>", lambda r: None, name="users_id")
        assert APIRouter._is_parameterized_path(pattern) is True

    def test_is_parameterized_path_int_converter_returns_true(self):
        """_is_parameterized_path returns True for <int:id> converter patterns."""
        pattern = django_path("items/<int:id>", lambda r: None, name="item_detail")
        assert APIRouter._is_parameterized_path(pattern) is True

    def test_is_parameterized_path_nested_param_returns_true(self):
        """_is_parameterized_path returns True for nested parameterized patterns."""
        pattern = django_path("items/<int:id>/reviews/<int:review_id>", lambda r: None, name="review")
        assert APIRouter._is_parameterized_path(pattern) is True

    def test_all_static_routes_no_parameterized(self):
        """All-static routes are returned in declaration order unchanged."""
        router = APIRouter()
        dummy = self._dummy_view()

        router.add_route("alpha", dummy, methods=["GET"], name="alpha")
        router.add_route("beta", dummy, methods=["GET"], name="beta")
        router.add_route("gamma", dummy, methods=["GET"], name="gamma")

        urls = router.get_urls()
        routes = [getattr(u.pattern, "_route", str(u.pattern)) for u in urls]
        assert routes == ["alpha", "beta", "gamma"]

    def test_all_parameterized_routes_no_static(self):
        """All-parameterized routes are returned in declaration order."""
        router = APIRouter()
        dummy = self._dummy_view()

        router.add_route("users/<str:username>", dummy, methods=["GET"], name="user_name")
        router.add_route("items/<int:id>", dummy, methods=["GET"], name="item_id")

        urls = router.get_urls()
        routes = [getattr(u.pattern, "_route", str(u.pattern)) for u in urls]
        assert routes == ["users/<str:username>", "items/<int:id>"]

    def test_decorator_registered_routes_also_sort(self):
        """Routes registered via @router.get() decorator also respect static-first ordering."""
        router = APIRouter()

        @router.get("users/<str:id>")
        async def get_user(request, id: str):
            from django.http import JsonResponse
            return JsonResponse({})

        @router.get("users/me")
        async def get_me(request):
            from django.http import JsonResponse
            return JsonResponse({})

        urls = router.get_urls()
        assert len(urls) == 2

        routes = [getattr(u.pattern, "_route", str(u.pattern)) for u in urls]
        me_idx = next(i for i, r in enumerate(routes) if "me" in r)
        id_idx = next(i for i, r in enumerate(routes) if "<str:id>" in r)
        assert me_idx < id_idx, f"Decorator routes not sorted: {routes}"


class TestControllerPermissionClasses:
    """Verify that Controller.permission_classes is enforced at dispatch time."""

    def _make_request(self, rf, method="get", user=None):
        request = getattr(rf, method)("/")
        request.user = user
        request.content_type = "application/json"
        return request

    @pytest.mark.asyncio
    async def test_permission_classes_blocks_anonymous(self, rf):
        """permission_classes=[IsAuthenticated] must reject anonymous users."""
        from django.contrib.auth.models import AnonymousUser

        from django_matt.permissions.common import IsAuthenticated

        router = APIRouter()

        class ProtectedController(Controller):
            prefix = "/protected"
            permission_classes = [IsAuthenticated]

            @route_get("/")
            async def index(self, request):
                return JsonResponse({"ok": True})

        router.register_controller(ProtectedController)
        urls = router.get_urls()

        request = self._make_request(rf, user=AnonymousUser())
        response = await urls[0].callback(request)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_permission_classes_allows_authenticated(self, rf):
        """permission_classes=[IsAuthenticated] must allow authenticated users."""
        from django_matt.permissions.common import IsAuthenticated

        router = APIRouter()

        class ProtectedController(Controller):
            prefix = "/protected"
            permission_classes = [IsAuthenticated]

            @route_get("/")
            async def index(self, request):
                return JsonResponse({"ok": True})

        router.register_controller(ProtectedController)
        urls = router.get_urls()

        user = User(pk=1, username="test", is_active=True)
        request = self._make_request(rf, user=user)
        response = await urls[0].callback(request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_permission_classes_allows_all(self, rf):
        """No permission_classes means no restriction."""
        router = APIRouter()

        class PublicController(Controller):
            prefix = "/public"

            @route_get("/")
            async def index(self, request):
                return JsonResponse({"ok": True})

        router.register_controller(PublicController)
        urls = router.get_urls()

        from django.contrib.auth.models import AnonymousUser
        request = self._make_request(rf, user=AnonymousUser())
        response = await urls[0].callback(request)
        assert response.status_code == 200

    def test_subclass_does_not_share_permission_classes(self):
        """Each subclass gets its own permission_classes list."""
        from django_matt.permissions.common import IsAuthenticated

        class ParentController(Controller):
            prefix = "/parent"
            permission_classes = [IsAuthenticated]

        class ChildController(ParentController):
            prefix = "/child"

        # Child inherits parent's permissions
        assert len(ChildController.permission_classes) == 1
        # But they are different list objects
        assert ChildController.permission_classes is not ParentController.permission_classes

    @pytest.mark.asyncio
    async def test_guard_overrides_controller_permissions(self, rf):
        """@guard(AllowAny) on a method overrides controller-level IsAuthenticated."""
        from django.contrib.auth.models import AnonymousUser

        from django_matt.permissions.common import AllowAny, IsAuthenticated
        from django_matt.permissions.decorators.guard import guard

        router = APIRouter()

        class MixedController(Controller):
            prefix = "/mixed"
            permission_classes = [IsAuthenticated]

            @route_get("/protected")
            async def protected(self, request):
                return JsonResponse({"ok": True})

            @guard(AllowAny)
            @route_get("/public")
            async def public(self, request):
                return JsonResponse({"public": True})

        router.register_controller(MixedController)
        urls = router.get_urls()

        anon_request = self._make_request(rf, user=AnonymousUser())

        # Find the URLs by name/path
        url_map = {url.pattern._route.strip("/"): url for url in urls}

        # Protected endpoint should block anonymous
        resp = await url_map["mixed/protected"].callback(anon_request)
        assert resp.status_code == 401

        # Public endpoint should allow anonymous via @guard(AllowAny)
        resp = await url_map["mixed/public"].callback(anon_request)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_guard_restricts_to_admin(self, rf):
        """@guard(IsAdmin) on a method restricts beyond controller-level IsAuthenticated."""
        from django_matt.permissions.common import IsAdmin, IsAuthenticated
        from django_matt.permissions.decorators.guard import guard

        router = APIRouter()

        class AdminController(Controller):
            prefix = "/admin-test"
            permission_classes = [IsAuthenticated]

            @guard(IsAdmin)
            @route_get("/admin-only")
            async def admin_only(self, request):
                return JsonResponse({"admin": True})

        router.register_controller(AdminController)
        urls = router.get_urls()

        # Regular authenticated user should be blocked by IsAdmin
        user = User(pk=1, username="regular", is_active=True, is_staff=False)
        request = self._make_request(rf, user=user)
        resp = await urls[0].callback(request)
        assert resp.status_code == 403

        # Admin user should pass
        admin_user = User(pk=2, username="admin", is_active=True, is_staff=True)
        request = self._make_request(rf, user=admin_user)
        resp = await urls[0].callback(request)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_guard_does_not_affect_other_methods(self, rf):
        """@guard on one method does not leak to sibling methods."""
        from django.contrib.auth.models import AnonymousUser

        from django_matt.permissions.common import AllowAny, IsAuthenticated
        from django_matt.permissions.decorators.guard import guard

        router = APIRouter()

        class LeakController(Controller):
            prefix = "/leak"
            permission_classes = [IsAuthenticated]

            @guard(AllowAny)
            @route_get("/open")
            async def open_endpoint(self, request):
                return JsonResponse({"open": True})

            @route_get("/closed")
            async def closed_endpoint(self, request):
                return JsonResponse({"closed": True})

        router.register_controller(LeakController)
        urls = router.get_urls()
        url_map = {url.pattern._route.strip("/"): url for url in urls}

        anon_request = self._make_request(rf, user=AnonymousUser())

        # open should allow anon
        resp = await url_map["leak/open"].callback(anon_request)
        assert resp.status_code == 200

        # closed should still require auth (controller default)
        resp = await url_map["leak/closed"].callback(anon_request)
        assert resp.status_code == 401

    def test_guard_sets_attribute(self):
        """@guard sets _guard_permissions on the decorated function."""
        from django_matt.permissions.common import IsAdmin, IsAuthenticated
        from django_matt.permissions.decorators.guard import guard

        @guard(IsAuthenticated, IsAdmin)
        async def my_method(self, request):
            pass

        assert hasattr(my_method, "_guard_permissions")
        assert my_method._guard_permissions == [IsAuthenticated, IsAdmin]


class TestLoginNotRequired:
    """Tests for Django 5.1+ LoginRequiredMiddleware compatibility."""

    def test_router_view_funcs_have_login_not_required(self):
        """All view functions created by APIRouter should have login_not_required applied."""
        from django_matt.core.router import _login_not_required

        router = APIRouter()

        @router.get("/items")
        async def list_items(request):
            return []

        urls = router.get_urls()
        assert len(urls) >= 1

        view_func = urls[0].callback
        # On Django 5.1+, login_not_required sets login_required=False on the view
        if _login_not_required is not None:
            assert getattr(view_func, "login_required", None) is False
        else:
            # On older Django, attribute may not be present — that's fine
            pass

    def test_controller_view_funcs_have_login_not_required(self):
        """Controller-based view functions should also be exempt."""
        from django_matt.core.router import _login_not_required

        router = APIRouter()

        class ItemController(Controller):
            prefix = "/items"

            @route_get("/")
            async def list_items(self, request):
                return []

        router.register_controller(ItemController)
        urls = router.get_urls()
        assert len(urls) >= 1

        view_func = urls[0].callback
        if _login_not_required is not None:
            assert getattr(view_func, "login_required", None) is False

    def test_dispatch_view_has_login_not_required(self):
        """Merged dispatch views (multiple methods, same path) should be exempt."""
        from django_matt.core.router import _login_not_required

        router = APIRouter()

        @router.get("/things")
        async def list_things(request):
            return []

        @router.post("/things")
        async def create_thing(request, body=None):
            return {"id": 1}

        urls = router.get_urls()
        # Same path merged into one dispatch view
        thing_urls = [u for u in urls if "things" in str(u.pattern)]
        assert len(thing_urls) == 1

        view_func = thing_urls[0].callback
        if _login_not_required is not None:
            assert getattr(view_func, "login_required", None) is False

    def test_matt_api_urls_have_login_not_required(self):
        """MattAPI utility views (docs, openapi) should also be exempt."""
        from django_matt.core.router import _login_not_required

        if _login_not_required is None:
            pytest.skip("Django < 5.1, login_not_required not available")

        from django_matt.api import MattAPI

        api = MattAPI(title="Test API")
        urls = api.urls

        # Find the openapi-schema view
        openapi_urls = [u for u in urls if getattr(u, "name", None) == "openapi-schema"]
        assert len(openapi_urls) == 1
        assert getattr(openapi_urls[0].callback, "login_required", None) is False


@pytest.fixture
def rf():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()
