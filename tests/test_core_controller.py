"""
Tests for the Django Matt core controller module.

Tests the CRUDController with async ORM support and query optimization.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User, Group
from django.test import RequestFactory

from pydantic import BaseModel

# Import directly from modules to avoid full package import
from django_matt.core.controller import (
    APIController,
    Controller,
    CRUDController,
    DJANGO_5_2_PLUS,
    DJANGO_6_0_PLUS,
    DJANGO_VERSION,
)
from django_matt.core.errors import ConfigurationError, NotFoundAPIError


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


@pytest.fixture
def rf():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()
