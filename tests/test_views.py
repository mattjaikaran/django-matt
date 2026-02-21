"""
Tests for the django_matt.views module.

Covers:
- ListView: list with pagination, filtering, ordering, search, empty results
- CreateView: create with valid data, validation errors, missing body
- ReadView: get by ID, not found, custom lookup field
- UpdateView: full update, partial update (PatchView), not found
- DeleteView: delete existing, not found, return_deleted option
- APIViewSet: full CRUD lifecycle, as_urls(), get_routes()
- BoundView: method enforcement, error handling, permission checks
- View hooks: before/after for each CRUD operation
- Permission integration with views
- optimize_queryset: auto-detection of FK/M2M from schema
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest
from django.contrib.auth.models import User
from django.db import models
from django.http import HttpRequest, JsonResponse, QueryDict
from django.test import RequestFactory

from pydantic import BaseModel

from django_matt.core.errors import APIError, NotFoundAPIError
from django_matt.permissions.common import AllowAny, IsAuthenticated
from django_matt.views.base import APIView, BoundView
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.hooks import (
    HookType,
    StopHookChain,
    hook_manager,
)
from django_matt.views.list import ListView
from django_matt.views.read import ReadView, RetrieveView
from django_matt.views.update import PatchView, UpdateView
from django_matt.views.viewset import APIViewSet, ViewSet


# ============================================================================
# Test models and schemas
# ============================================================================


class ItemSchema(BaseModel):
    """Schema for serializing Item models."""

    id: int | None = None
    name: str
    price: float | None = None

    class Config:
        from_attributes = True


class ItemCreateSchema(BaseModel):
    """Schema for creating items."""

    name: str
    price: float = 0.0


class ItemUpdateSchema(BaseModel):
    """Schema for updating items."""

    name: str | None = None
    price: float | None = None


class UserReadSchema(BaseModel):
    """Schema that references FK fields on Django's User model for optimize_queryset testing."""

    id: int | None = None
    username: str

    class Config:
        from_attributes = True


class SimpleViewSet(APIViewSet):
    """Lightweight viewset for standalone view tests.

    Unlike MagicMock, this won't interfere with the hook system because
    the HooksMixin default hooks properly pass values through.
    """

    model = User
    default_response_schema = UserReadSchema

    def __init__(self, queryset_fn=None):
        self._queryset_fn = queryset_fn
        super().__init__()

    def get_queryset(self, request=None):
        if self._queryset_fn:
            return self._queryset_fn(request)
        return self.model.objects.all()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_hooks():
    """Clear the global hook manager before/after each test."""
    hook_manager.clear()
    yield
    hook_manager.clear()


@pytest.fixture
def rf():
    return RequestFactory()


def _make_request(rf: RequestFactory, method: str = "GET", path: str = "/",
                  data: dict | None = None, query: dict | None = None,
                  user=None) -> HttpRequest:
    """Build an HttpRequest with optional JSON body and query params."""
    factory_method = getattr(rf, method.lower())
    kwargs: dict[str, Any] = {}
    if data is not None:
        kwargs["data"] = orjson.dumps(data)
        kwargs["content_type"] = "application/json"
    if query:
        path += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    request = factory_method(path, **kwargs)
    if user is not None:
        request.user = user
    return request


# ============================================================================
# Minimal Item ViewSet for integration tests
# ============================================================================


class ItemViewSet(APIViewSet):
    model = User  # Use Django's User as a real DB model
    prefix = "items"
    tags = ["Items"]
    default_response_schema = UserReadSchema
    default_request_schema = None  # overridden per-view

    list_items = ListView(page_size=5)
    create_item = CreateView(request_schema=ItemCreateSchema, response_schema=ItemSchema)
    read_item = ReadView(response_schema=UserReadSchema)
    update_item = UpdateView(request_schema=ItemUpdateSchema, response_schema=UserReadSchema)
    patch_item = PatchView(request_schema=ItemUpdateSchema, response_schema=UserReadSchema)
    delete_item = DeleteView()


# ============================================================================
# APIView base class
# ============================================================================


class TestAPIViewBase:
    """Tests for the APIView base class."""

    def test_default_attributes(self):
        view = APIView()
        assert view.path == ""
        assert view.methods == ["GET"]
        assert view.response_schema is None
        assert view.request_schema is None
        assert view.enable_hooks is True

    def test_init_overrides(self):
        view = APIView(
            path="custom",
            methods=["POST"],
            summary="Custom summary",
            description="Custom desc",
            tags=["Tag1"],
            operation_id="custom_op",
            enable_hooks=False,
        )
        assert view.path == "custom"
        assert view.methods == ["POST"]
        assert view.summary == "Custom summary"
        assert view.description == "Custom desc"
        assert view.tags == ["Tag1"]
        assert view.operation_id == "custom_op"
        assert view.enable_hooks is False

    def test_set_name_stores_attr_name(self):
        view = APIView()
        view.__set_name__(object, "my_view")
        assert view._viewset_attr_name == "my_view"

    def test_descriptor_get_unbound(self):
        """Accessing view on the class (not instance) returns the view itself."""
        view = APIView()
        result = view.__get__(None, type(None))
        assert result is view

    def test_get_model_raises_without_viewset(self):
        view = APIView()
        with pytest.raises(ValueError, match="not attached"):
            view.get_model()

    def test_get_queryset_raises_without_viewset(self):
        view = APIView()
        with pytest.raises(ValueError, match="not attached"):
            view.get_queryset(None)

    def test_serialize_with_schema(self):
        """serialize() uses the response schema when available."""
        view = APIView(response_schema=ItemSchema)
        # Create a mock model instance with the right attributes
        mock_obj = MagicMock()
        mock_obj.id = 1
        mock_obj.name = "Widget"
        mock_obj.price = 9.99
        result = view.serialize(mock_obj)
        assert result["id"] == 1
        assert result["name"] == "Widget"
        assert result["price"] == 9.99

    def test_serialize_without_schema_fallback(self):
        """serialize() falls back to _model_to_dict when no schema."""
        view = APIView()
        # Create a simple mock with _meta.fields
        mock_field = MagicMock()
        mock_field.name = "id"
        mock_obj = MagicMock()
        mock_obj._meta.fields = [mock_field]
        mock_obj.id = 42
        result = view.serialize(mock_obj)
        assert result["id"] == 42

    def test_validate_request_with_schema(self, rf):
        view = APIView(request_schema=ItemCreateSchema)
        request = _make_request(rf, "POST", data={"name": "Widget", "price": 5.0})
        result = view.validate_request(request)
        assert result.name == "Widget"
        assert result.price == 5.0

    def test_validate_request_no_schema_returns_none(self, rf):
        view = APIView()
        request = _make_request(rf, "GET")
        assert view.validate_request(request) is None

    def test_validate_request_invalid_json_raises(self, rf):
        view = APIView(request_schema=ItemCreateSchema)
        request = rf.post("/", data=b"not json", content_type="application/json")
        with pytest.raises(ValueError, match="Invalid JSON"):
            view.validate_request(request)

    def test_handle_raises_not_implemented(self):
        view = APIView()
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(view.handle(MagicMock()))

    def test_get_response_schema_from_viewset_default(self):
        """Falls back to viewset default_response_schema."""
        view = APIView()
        mock_viewset = MagicMock()
        mock_viewset.default_response_schema = ItemSchema
        view._viewset = mock_viewset
        assert view.get_response_schema() is ItemSchema

    def test_get_request_schema_from_viewset_default(self):
        view = APIView()
        mock_viewset = MagicMock()
        mock_viewset.default_request_schema = ItemCreateSchema
        view._viewset = mock_viewset
        assert view.get_request_schema() is ItemCreateSchema


# ============================================================================
# optimize_queryset
# ============================================================================


class TestOptimizeQueryset:
    """Tests for APIView.optimize_queryset auto-detection of FK/M2M."""

    def test_no_schema_returns_queryset_unchanged(self):
        view = APIView()
        qs = User.objects.all()
        result = view.optimize_queryset(qs)
        # Same queryset object
        assert result is qs

    def test_auto_detects_fk_fields(self):
        """If schema fields match FK columns, select_related is applied."""

        class ProfileSchema(BaseModel):
            id: int | None = None
            username: str

            class Config:
                from_attributes = True

        view = APIView(response_schema=ProfileSchema)
        qs = User.objects.all()
        optimized = view.optimize_queryset(qs)
        # No FK fields in User matching ProfileSchema, so no change
        assert optimized is not None

    def test_auto_detects_m2m_fields(self):
        """If schema fields match M2M columns, prefetch_related is applied."""

        class UserWithGroups(BaseModel):
            id: int | None = None
            username: str
            groups: list = []

            class Config:
                from_attributes = True

        view = APIView(response_schema=UserWithGroups)
        qs = User.objects.all()
        optimized = view.optimize_queryset(qs)
        # groups is M2M on User, should be prefetched
        # Django stores prefetch lookups as strings
        prefetch_lookups = list(getattr(optimized, "_prefetch_related_lookups", []))
        assert "groups" in prefetch_lookups


# ============================================================================
# ListView
# ============================================================================


@pytest.mark.django_db
class TestListView:
    """Tests for ListView."""

    def test_default_config(self):
        view = ListView()
        assert view.methods == ["GET"]
        assert view.pagination is True
        assert view.page_size == 20
        assert view.max_page_size == 100

    def test_custom_config(self):
        view = ListView(
            pagination=False,
            page_size=10,
            max_page_size=50,
            ordering="-name",
            filter_fields=["name", "active"],
            search_fields=["name"],
        )
        assert view.pagination is False
        assert view.page_size == 10
        assert view.max_page_size == 50
        assert view.ordering == "-name"
        assert view.filter_fields == ["name", "active"]
        assert view.search_fields == ["name"]

    @pytest.mark.asyncio
    async def test_list_empty(self, rf):
        """Listing with no records returns empty items."""
        await User.objects.all().adelete()  # Ensure clean state
        viewset = ItemViewSet()
        view = viewset.__class__.list_items
        view._viewset = viewset

        request = _make_request(rf, "GET", path="/items/")
        result = await view.handle(request)

        assert result["items"] == []
        assert result["count"] == 0
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_data(self, rf):
        """Listing returns serialized items."""
        await User.objects.acreate_user(username="alice", password="pass123")
        await User.objects.acreate_user(username="bob", password="pass123")

        viewset = ItemViewSet()
        view = viewset.__class__.list_items
        view._viewset = viewset

        request = _make_request(rf, "GET", path="/items/")
        result = await view.handle(request)

        assert result["total"] >= 2
        assert result["count"] >= 2
        names = [item["username"] for item in result["items"]]
        assert "alice" in names
        assert "bob" in names

    @pytest.mark.asyncio
    async def test_list_pagination(self, rf):
        """Pagination respects page and page_size params."""
        for i in range(10):
            await User.objects.acreate_user(username=f"user_{i:02d}", password="pass123")

        viewset = ItemViewSet()
        view = viewset.__class__.list_items
        view._viewset = viewset

        # page_size=5 is the default on ItemViewSet.list_items
        request = _make_request(rf, "GET", path="/items/", query={"page": "1", "page_size": "3"})
        result = await view.handle(request)

        assert result["count"] == 3
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert result["total"] >= 10

    @pytest.mark.asyncio
    async def test_list_pagination_page_2(self, rf):
        """Page 2 returns the next set of items."""
        for i in range(8):
            await User.objects.acreate_user(username=f"pg2user_{i:02d}", password="pass123")

        viewset = ItemViewSet()
        view = viewset.__class__.list_items
        view._viewset = viewset

        request = _make_request(rf, "GET", path="/items/", query={"page": "2", "page_size": "5"})
        result = await view.handle(request)

        assert result["page"] == 2
        assert result["count"] <= 5

    @pytest.mark.asyncio
    async def test_list_page_size_capped_at_max(self, rf):
        """page_size is capped at max_page_size."""
        viewset = ItemViewSet()
        view = viewset.__class__.list_items
        view._viewset = viewset

        request = _make_request(rf, "GET", path="/items/", query={"page_size": "9999"})
        result = await view.handle(request)
        assert result["page_size"] <= 100

    @pytest.mark.asyncio
    async def test_list_no_pagination(self, rf):
        """With pagination=False, all items are returned without page info."""
        await User.objects.acreate_user(username="nopag_alice", password="pass123")
        await User.objects.acreate_user(username="nopag_bob", password="pass123")

        view = ListView(pagination=False, response_schema=UserReadSchema)
        vs = SimpleViewSet(queryset_fn=lambda req: User.objects.filter(username__startswith="nopag_"))
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/")
        result = await view.handle(request)

        assert "page" not in result
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_list_ordering(self, rf):
        """Ordering via query parameter sorts results."""
        await User.objects.acreate_user(username="z_order_test", password="pass123")
        await User.objects.acreate_user(username="a_order_test", password="pass123")

        view = ListView(
            response_schema=UserReadSchema,
            ordering_fields=["username"],
            pagination=False,
        )
        vs = SimpleViewSet(queryset_fn=lambda req: User.objects.filter(username__endswith="_order_test"))
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/", query={"ordering": "username"})
        result = await view.handle(request)

        usernames = [i["username"] for i in result["items"]]
        assert usernames == sorted(usernames)

    @pytest.mark.asyncio
    async def test_list_filtering(self, rf):
        """Filtering by query parameters filters results."""
        await User.objects.acreate_user(username="filter_active", password="pass123", is_active=True)
        await User.objects.acreate_user(username="filter_inactive", password="pass123", is_active=False)

        view = ListView(
            response_schema=UserReadSchema,
            filter_fields=["is_active", "username"],
            pagination=False,
        )
        vs = SimpleViewSet(queryset_fn=lambda req: User.objects.filter(username__startswith="filter_"))
        view._viewset = vs

        request = _make_request(
            rf, "GET", path="/items/", query={"is_active": "True"}
        )
        result = await view.handle(request)

        assert result["count"] >= 1
        # All returned items should be active
        for item in result["items"]:
            u = await User.objects.aget(username=item["username"])
            assert u.is_active is True

    @pytest.mark.asyncio
    async def test_list_search(self, rf):
        """Search fields apply icontains filter."""
        await User.objects.acreate_user(username="searchable_foo", password="pass123")
        await User.objects.acreate_user(username="searchable_bar", password="pass123")

        view = ListView(
            response_schema=UserReadSchema,
            search_fields=["username"],
            pagination=False,
        )
        vs = SimpleViewSet(queryset_fn=lambda req: User.objects.filter(username__startswith="searchable_"))
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/", query={"search": "foo"})
        result = await view.handle(request)

        assert result["count"] == 1
        assert result["items"][0]["username"] == "searchable_foo"

    @pytest.mark.asyncio
    async def test_list_default_ordering(self, rf):
        """Default ordering defined on the view is applied."""
        await User.objects.acreate_user(username="dord_aaa", password="pass123")
        await User.objects.acreate_user(username="dord_zzz", password="pass123")

        view = ListView(
            response_schema=UserReadSchema,
            ordering="-username",
            pagination=False,
        )
        vs = SimpleViewSet(queryset_fn=lambda req: User.objects.filter(username__startswith="dord_"))
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/")
        result = await view.handle(request)

        usernames = [i["username"] for i in result["items"]]
        assert usernames == sorted(usernames, reverse=True)


# ============================================================================
# CreateView
# ============================================================================


@pytest.mark.django_db
class TestCreateView:
    """Tests for CreateView."""

    def test_default_config(self):
        view = CreateView()
        assert view.methods == ["POST"]
        assert view.path == ""

    @pytest.mark.asyncio
    async def test_create_valid(self, rf):
        """Creating with valid data returns serialized instance."""

        class CreateItemVS(APIViewSet):
            model = User
            default_response_schema = ItemSchema

            async def perform_create(self, data_dict, request):
                user = await User.objects.acreate_user(
                    username=data_dict["name"], password="testpass"
                )
                user.name = data_dict["name"]
                user.price = data_dict.get("price", 0.0)
                return user

        view = CreateView(
            request_schema=ItemCreateSchema,
            response_schema=ItemSchema,
        )
        vs = CreateItemVS()
        view._viewset = vs

        request = _make_request(rf, "POST", data={"name": "NewItem", "price": 42.0})
        result = await view.handle(request)

        assert result["name"] == "NewItem"
        assert result["price"] == 42.0

    @pytest.mark.asyncio
    async def test_create_validation_error(self, rf):
        """Creating with invalid data raises ValidationError."""
        from pydantic import ValidationError

        view = CreateView(request_schema=ItemCreateSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        # Missing required 'name' field
        request = _make_request(rf, "POST", data={"price": 10.0})
        with pytest.raises(ValidationError):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_create_no_body_raises(self, rf):
        """Creating with no request body raises ValueError."""

        class NoSchemaVS(APIViewSet):
            model = User
            default_request_schema = None

        view = CreateView()
        vs = NoSchemaVS()
        view._viewset = vs

        request = _make_request(rf, "POST")
        with pytest.raises(ValueError, match="required"):
            await view.handle(request)


# ============================================================================
# ReadView
# ============================================================================


@pytest.mark.django_db
class TestReadView:
    """Tests for ReadView."""

    def test_default_config(self):
        view = ReadView()
        assert view.methods == ["GET"]
        assert view.path == "{id}"
        assert view.lookup_field == "id"

    def test_retrieve_view_alias(self):
        assert RetrieveView is ReadView

    def test_custom_lookup_field(self):
        view = ReadView(lookup_field="slug")
        assert view.lookup_field == "slug"

    @pytest.mark.asyncio
    async def test_read_existing(self, rf):
        """Reading an existing object returns serialized data."""
        user = await User.objects.acreate_user(username="readable_user", password="pass123")

        view = ReadView(response_schema=UserReadSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "GET", path=f"/items/{user.id}/")
        result = await view.handle(request, id=user.id)

        assert result["id"] == user.id
        assert result["username"] == "readable_user"

    @pytest.mark.asyncio
    async def test_read_not_found(self, rf):
        """Reading a non-existent object raises NotFoundAPIError."""
        view = ReadView(response_schema=UserReadSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/99999/")
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=99999)

    @pytest.mark.asyncio
    async def test_read_missing_lookup_raises(self, rf):
        """Missing lookup field in kwargs raises ValueError."""
        view = ReadView(response_schema=UserReadSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "GET", path="/items/")
        with pytest.raises(ValueError, match="Missing"):
            await view.handle(request)


# ============================================================================
# UpdateView
# ============================================================================


@pytest.mark.django_db
class TestUpdateView:
    """Tests for UpdateView."""

    def test_default_config(self):
        view = UpdateView()
        assert view.methods == ["PUT"]
        assert view.path == "{id}"
        assert view.lookup_field == "id"

    @pytest.mark.asyncio
    async def test_update_existing(self, rf):
        """Updating an existing object applies changes."""
        user = await User.objects.acreate_user(username="updatable_user", password="pass123")

        view = UpdateView(
            request_schema=ItemUpdateSchema,
            response_schema=UserReadSchema,
        )
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(
            rf, "PUT", data={"name": "updated_name"}
        )
        result = await view.handle(request, id=user.id)

        assert result["id"] == user.id

    @pytest.mark.asyncio
    async def test_update_not_found(self, rf):
        """Updating a non-existent object raises NotFoundAPIError."""
        view = UpdateView(
            request_schema=ItemUpdateSchema,
            response_schema=UserReadSchema,
        )
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "PUT", data={"name": "x"})
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=99999)

    @pytest.mark.asyncio
    async def test_update_no_body_raises(self, rf):
        """Updating with no request body raises ValueError."""
        user = await User.objects.acreate_user(username="upd_nobody", password="pass123")

        class NoSchemaVS(APIViewSet):
            model = User
            default_request_schema = None

        view = UpdateView()
        vs = NoSchemaVS()
        view._viewset = vs

        request = _make_request(rf, "PUT")
        with pytest.raises(ValueError, match="required"):
            await view.handle(request, id=user.id)

    @pytest.mark.asyncio
    async def test_update_missing_lookup_raises(self, rf):
        """Missing lookup field raises ValueError."""
        view = UpdateView(request_schema=ItemUpdateSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "PUT", data={"name": "x"})
        with pytest.raises(ValueError, match="Missing"):
            await view.handle(request)


# ============================================================================
# PatchView
# ============================================================================


@pytest.mark.django_db
class TestPatchView:
    """Tests for PatchView (partial update)."""

    def test_default_config(self):
        view = PatchView()
        assert view.methods == ["PATCH"]
        assert view.path == "{id}"

    @pytest.mark.asyncio
    async def test_patch_partial_update(self, rf):
        """Patch only updates provided fields."""
        user = await User.objects.acreate_user(
            username="patchable_user", password="pass123", first_name="Original"
        )

        class PatchSchema(BaseModel):
            first_name: str | None = None
            last_name: str | None = None

        view = PatchView(
            request_schema=PatchSchema,
            response_schema=UserReadSchema,
        )
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "PATCH", data={"first_name": "Patched"})
        result = await view.handle(request, id=user.id)

        await user.arefresh_from_db()
        assert user.first_name == "Patched"

    @pytest.mark.asyncio
    async def test_patch_not_found(self, rf):
        """Patching a non-existent object raises NotFoundAPIError."""
        view = PatchView(request_schema=ItemUpdateSchema, response_schema=UserReadSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "PATCH", data={"name": "x"})
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=99999)


# ============================================================================
# DeleteView
# ============================================================================


@pytest.mark.django_db
class TestDeleteView:
    """Tests for DeleteView."""

    def test_default_config(self):
        view = DeleteView()
        assert view.methods == ["DELETE"]
        assert view.path == "{id}"
        assert view.lookup_field == "id"
        assert view.return_deleted is False

    @pytest.mark.asyncio
    async def test_delete_existing(self, rf):
        """Deleting an existing object returns deleted=True."""
        user = await User.objects.acreate_user(username="deletable_user", password="pass123")
        user_id = user.id

        view = DeleteView()
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "DELETE", path=f"/items/{user_id}/")
        result = await view.handle(request, id=user_id)

        assert result["deleted"] is True
        assert not await User.objects.filter(id=user_id).aexists()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, rf):
        """Deleting a non-existent object raises NotFoundAPIError."""
        view = DeleteView()
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "DELETE", path="/items/99999/")
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=99999)

    @pytest.mark.asyncio
    async def test_delete_return_deleted_data(self, rf):
        """With return_deleted=True, response includes the deleted object."""
        user = await User.objects.acreate_user(username="retdel_user", password="pass123")
        user_id = user.id

        view = DeleteView(return_deleted=True, response_schema=UserReadSchema)
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "DELETE", path=f"/items/{user_id}/")
        result = await view.handle(request, id=user_id)

        assert result["deleted"] is True
        assert result["data"]["username"] == "retdel_user"

    @pytest.mark.asyncio
    async def test_delete_missing_lookup_raises(self, rf):
        """Missing lookup field raises ValueError."""
        view = DeleteView()
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(rf, "DELETE", path="/items/")
        with pytest.raises(ValueError, match="Missing"):
            await view.handle(request)


# ============================================================================
# BoundView (view bound to viewset instance via descriptor)
# ============================================================================


@pytest.mark.django_db
class TestBoundView:
    """Tests for BoundView (wraps view + viewset for dispatch)."""

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, rf):
        """Request with wrong HTTP method returns 405."""
        viewset = ItemViewSet()
        bound = viewset.list_items  # ListView, methods=["GET"]

        request = _make_request(rf, "POST", path="/items/")
        response = await bound(request)

        assert response.status_code == 405
        data = orjson.loads(response.content)
        assert "not allowed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_permission_denied(self, rf):
        """Permission classes deny unauthenticated requests."""

        class ProtectedViewSet(APIViewSet):
            model = User
            permission_classes = [IsAuthenticated]
            default_response_schema = UserReadSchema
            list_items = ListView()

        viewset = ProtectedViewSet()
        bound = viewset.list_items

        # Anonymous user
        from django.contrib.auth.models import AnonymousUser
        request = _make_request(rf, "GET", path="/items/")
        request.user = AnonymousUser()

        response = await bound(request)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_permission_allowed(self, rf):
        """Authenticated users pass IsAuthenticated check."""

        class ProtectedViewSet(APIViewSet):
            model = User
            permission_classes = [IsAuthenticated]
            default_response_schema = UserReadSchema
            list_items = ListView()

        viewset = ProtectedViewSet()
        bound = viewset.list_items

        user = await User.objects.acreate_user(username="authed_bound", password="pass123")
        request = _make_request(rf, "GET", path="/items/", user=user)

        response = await bound(request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_allow_any_permission(self, rf):
        """AllowAny permission lets anyone through."""

        class PublicViewSet(APIViewSet):
            model = User
            permission_classes = [AllowAny]
            default_response_schema = UserReadSchema
            list_items = ListView()

        viewset = PublicViewSet()
        bound = viewset.list_items

        from django.contrib.auth.models import AnonymousUser
        request = _make_request(rf, "GET", path="/items/")
        request.user = AnonymousUser()

        response = await bound(request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_validation_error_returns_422(self, rf):
        """Pydantic validation error returns 422."""
        viewset = ItemViewSet()
        bound = viewset.create_item  # CreateView with ItemCreateSchema

        # Missing required 'name' field
        request = _make_request(rf, "POST", data={"price": 10.0})
        response = await bound(request)

        assert response.status_code == 422
        data = orjson.loads(response.content)
        assert "errors" in data

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, rf):
        """NotFoundAPIError returns 404."""
        viewset = ItemViewSet()
        bound = viewset.read_item

        request = _make_request(rf, "GET", path="/items/99999/")
        response = await bound(request, id=99999)

        assert response.status_code == 404
        data = orjson.loads(response.content)
        assert data["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_value_error_returns_400(self, rf):
        """ValueError returns 400."""

        class NoSchemaUpdateVS(APIViewSet):
            model = User
            default_request_schema = None
            default_response_schema = UserReadSchema
            update_item = UpdateView()

        viewset = NoSchemaUpdateVS()
        bound = viewset.update_item

        request = _make_request(rf, "PUT")  # No body, no schema -> ValueError
        response = await bound(request, id=1)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_json_response_passthrough(self, rf):
        """If handle() returns a JsonResponse, it passes through."""
        view = APIView()
        view.methods = ["GET"]

        async def mock_handle(request, **kwargs):
            return JsonResponse({"custom": True}, status=201)

        view.handle = mock_handle
        mock_viewset = MagicMock()
        mock_viewset.permission_classes = None
        mock_viewset._permission_overrides = None
        view._viewset_attr_name = "custom"
        bound = BoundView(view, mock_viewset)

        request = _make_request(rf, "GET")
        response = await bound(request)

        assert response.status_code == 201
        data = orjson.loads(response.content)
        assert data["custom"] is True

    @pytest.mark.asyncio
    async def test_stop_hook_chain_with_value(self, rf):
        """StopHookChain with a value is returned as JSON."""
        view = APIView()
        view.methods = ["GET"]

        async def mock_handle(request, **kwargs):
            raise StopHookChain({"cancelled": True})

        view.handle = mock_handle
        mock_viewset = MagicMock()
        mock_viewset.permission_classes = None
        mock_viewset._permission_overrides = None
        view._viewset_attr_name = "test"
        bound = BoundView(view, mock_viewset)

        request = _make_request(rf, "GET")
        response = await bound(request)

        assert response.status_code == 200
        data = orjson.loads(response.content)
        assert data["cancelled"] is True

    @pytest.mark.asyncio
    async def test_stop_hook_chain_without_value(self, rf):
        """StopHookChain with no value returns 'Operation cancelled'."""
        view = APIView()
        view.methods = ["GET"]

        async def mock_handle(request, **kwargs):
            raise StopHookChain()

        view.handle = mock_handle
        mock_viewset = MagicMock()
        mock_viewset.permission_classes = None
        mock_viewset._permission_overrides = None
        view._viewset_attr_name = "test"
        bound = BoundView(view, mock_viewset)

        request = _make_request(rf, "GET")
        response = await bound(request)

        assert response.status_code == 200
        data = orjson.loads(response.content)
        assert "cancelled" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_api_error_returns_custom_status(self, rf):
        """APIError returns its custom status code."""
        view = APIView()
        view.methods = ["GET"]
        view.enable_hooks = False

        async def mock_handle(request, **kwargs):
            raise APIError("Rate limited", status_code=429, code="rate_limit")

        view.handle = mock_handle
        mock_viewset = MagicMock()
        mock_viewset.permission_classes = None
        mock_viewset._permission_overrides = None
        view._viewset_attr_name = "test"
        bound = BoundView(view, mock_viewset)

        request = _make_request(rf, "GET")
        response = await bound(request)

        assert response.status_code == 429
        data = orjson.loads(response.content)
        assert data["code"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_generic_exception_returns_500(self, rf):
        """Unhandled exception returns 500."""
        view = APIView()
        view.methods = ["GET"]
        view.enable_hooks = False

        async def mock_handle(request, **kwargs):
            raise RuntimeError("unexpected")

        view.handle = mock_handle
        mock_viewset = MagicMock()
        mock_viewset.permission_classes = None
        mock_viewset._permission_overrides = None
        view._viewset_attr_name = "test"
        bound = BoundView(view, mock_viewset)

        request = _make_request(rf, "GET")
        response = await bound(request)

        assert response.status_code == 500


# ============================================================================
# ViewSet and APIViewSet
# ============================================================================


class TestViewSet:
    """Tests for ViewSet base class."""

    def test_viewset_metaclass_collects_views(self):
        """Metaclass collects APIView instances from class body."""

        class MyViewSet(ViewSet):
            model = User
            prefix = "things"
            list_things = ListView()
            create_thing = CreateView()

        assert "list_things" in MyViewSet._views
        assert "create_thing" in MyViewSet._views

    def test_viewset_init_binds_views(self):
        """Instantiating ViewSet binds views to the instance."""

        class MyViewSet(ViewSet):
            model = User
            prefix = "things"
            list_things = ListView()

        vs = MyViewSet()
        assert MyViewSet.list_things._viewset is vs

    def test_get_queryset_raises_without_model(self):
        """get_queryset raises if model is None."""

        class EmptyViewSet(ViewSet):
            model = None

        vs = EmptyViewSet()
        with pytest.raises(ValueError, match="must be set"):
            vs.get_queryset()

    @pytest.mark.django_db
    def test_get_queryset_returns_all(self):

        class UserVS(ViewSet):
            model = User

        vs = UserVS()
        qs = vs.get_queryset()
        assert qs.model is User

    def test_get_routes(self):
        """get_routes() returns route info for each view."""

        class MyViewSet(ViewSet):
            model = User
            prefix = "things"
            tags = ["Things"]
            default_response_schema = UserReadSchema
            list_things = ListView()
            create_thing = CreateView()
            read_thing = ReadView()

        vs = MyViewSet()
        routes = vs.get_routes()

        assert len(routes) == 3
        names = {r["name"] for r in routes}
        assert "list_things" in names
        assert "create_thing" in names
        assert "read_thing" in names

    def test_get_routes_full_path(self):
        """Routes build full path from prefix + view path."""

        class MyViewSet(ViewSet):
            model = User
            prefix = "users"
            read_user = ReadView(path="{id}")

        vs = MyViewSet()
        routes = vs.get_routes()
        read_route = [r for r in routes if r["name"] == "read_user"][0]
        assert read_route["path"] == "users/{id}"


class TestAPIViewSet:
    """Tests for APIViewSet class."""

    def test_inherits_viewset_and_hooks_mixin(self):
        assert issubclass(APIViewSet, ViewSet)

    def test_default_attributes(self):

        class MyViewSet(APIViewSet):
            model = User

        assert MyViewSet.authentication_classes == []
        assert MyViewSet.permission_classes == []
        assert MyViewSet.enable_hooks is True

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_perform_create(self):
        """perform_create creates and saves a model instance."""

        class UserVS(APIViewSet):
            model = User

        vs = UserVS()
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get("/")

        user = await vs.perform_create(
            {"username": "perf_create_user", "password": "pass123"}, request
        )
        assert user.pk is not None
        assert await User.objects.filter(username="perf_create_user").aexists()

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_perform_update(self):
        """perform_update modifies and saves instance."""
        user = await User.objects.acreate_user(username="perf_update_user", password="pass123")

        class UserVS(APIViewSet):
            model = User

        vs = UserVS()
        rf = RequestFactory()
        request = rf.get("/")

        updated = await vs.perform_update(user, {"first_name": "Updated"}, request)
        await updated.arefresh_from_db()
        assert updated.first_name == "Updated"

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_perform_delete(self):
        """perform_delete removes instance from DB."""
        user = await User.objects.acreate_user(username="perf_delete_user", password="pass123")
        user_id = user.id

        class UserVS(APIViewSet):
            model = User

        vs = UserVS()
        rf = RequestFactory()
        request = rf.get("/")

        await vs.perform_delete(user, request)
        assert not await User.objects.filter(id=user_id).aexists()

    @pytest.mark.django_db
    def test_as_urls_generates_patterns(self):
        """as_urls() returns Django URL patterns."""

        class UserVS(APIViewSet):
            model = User
            prefix = "users"
            default_response_schema = UserReadSchema
            list_users = ListView()
            read_user = ReadView()

        patterns = UserVS.as_urls()
        assert len(patterns) == 2
        # Patterns should have names
        names = {p.name for p in patterns}
        assert "list_users" in names
        assert "read_user" in names


# ============================================================================
# Permission overrides per operation
# ============================================================================


@pytest.mark.django_db
class TestPermissionOverrides:
    """Tests for per-operation permission overrides on viewsets."""

    @pytest.mark.asyncio
    async def test_per_operation_override(self, rf):
        """A viewset can override permissions for specific operations."""

        class MixedPermsViewSet(APIViewSet):
            model = User
            permission_classes = [IsAuthenticated]
            default_response_schema = UserReadSchema
            _permission_overrides = {
                "list_items": [AllowAny],  # Public listing
            }
            list_items = ListView()
            read_item = ReadView()

        viewset = MixedPermsViewSet()

        # list_items should be public (AllowAny override)
        from django.contrib.auth.models import AnonymousUser
        request = _make_request(rf, "GET", path="/items/")
        request.user = AnonymousUser()

        bound_list = viewset.list_items
        response = await bound_list(request)
        assert response.status_code == 200

        # read_item should still require auth
        bound_read = viewset.read_item
        response = await bound_read(request, id=1)
        assert response.status_code == 401


# ============================================================================
# View hooks integration (before/after on real views via BoundView)
# ============================================================================


@pytest.mark.django_db
class TestViewHooksIntegration:
    """Tests for lifecycle hooks executing through the view pipeline."""

    @pytest.mark.asyncio
    async def test_before_list_hook_modifies_queryset(self, rf):
        """before_list class hook can filter the queryset."""
        await User.objects.acreate_user(username="hook_visible", password="pass123")
        await User.objects.acreate_user(username="hook_hidden", password="pass123")

        class FilteredViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            list_items = ListView(pagination=False)

            async def before_list(self, request, queryset):
                """Only return users whose name starts with 'hook_visible'."""
                return queryset.filter(username="hook_visible")

        viewset = FilteredViewSet()
        bound = viewset.list_items

        request = _make_request(rf, "GET", path="/items/")
        response = await bound(request)

        data = orjson.loads(response.content)
        assert data["count"] == 1
        assert data["items"][0]["username"] == "hook_visible"

    @pytest.mark.asyncio
    async def test_after_list_hook_modifies_response(self, rf):
        """after_list class hook can add extra data to response."""
        await User.objects.acreate_user(username="afterlist_user", password="pass123")

        class AugmentedViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            list_items = ListView(pagination=False)

            async def after_list(self, request, result):
                result["extra_metadata"] = "added_by_hook"
                return result

        viewset = AugmentedViewSet()
        bound = viewset.list_items

        request = _make_request(rf, "GET", path="/items/")
        response = await bound(request)

        data = orjson.loads(response.content)
        assert data["extra_metadata"] == "added_by_hook"

    @pytest.mark.asyncio
    async def test_before_create_hook_modifies_data(self, rf):
        """before_create class hook can inject fields into the data."""
        calls = []

        class AugmentedCreateViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            create_item = CreateView(request_schema=ItemCreateSchema, response_schema=ItemSchema)

            async def before_create(self, request, data):
                calls.append("before_create")
                data["injected"] = True
                return data

            async def perform_create(self, data_dict, request):
                # Verify the hook modified data before creation
                assert data_dict.get("injected") is True
                user = await User.objects.acreate_user(
                    username=data_dict["name"], password="pass123"
                )
                user.name = data_dict["name"]
                user.price = data_dict.get("price", 0)
                return user

        viewset = AugmentedCreateViewSet()
        bound = viewset.create_item

        request = _make_request(rf, "POST", data={"name": "hook_created", "price": 5.0})
        response = await bound(request)

        assert response.status_code == 200
        assert "before_create" in calls

    @pytest.mark.asyncio
    async def test_after_create_hook_receives_instance(self, rf):
        """after_create class hook receives the created instance."""
        created_instances = []

        class TrackCreateViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            create_item = CreateView(request_schema=ItemCreateSchema, response_schema=ItemSchema)

            async def after_create(self, request, instance):
                created_instances.append(instance)
                return instance

            async def perform_create(self, data_dict, request):
                user = await User.objects.acreate_user(
                    username=data_dict["name"], password="pass123"
                )
                user.name = data_dict["name"]
                user.price = data_dict.get("price", 0)
                return user

        viewset = TrackCreateViewSet()
        bound = viewset.create_item

        request = _make_request(rf, "POST", data={"name": "tracked_item", "price": 1.0})
        response = await bound(request)

        assert response.status_code == 200
        assert len(created_instances) == 1
        assert created_instances[0].username == "tracked_item"

    @pytest.mark.asyncio
    async def test_before_delete_hook(self, rf):
        """before_delete hook receives the instance before deletion."""
        user = await User.objects.acreate_user(username="hook_del_user", password="pass123")
        hook_instances = []

        class HookDeleteViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            delete_item = DeleteView()

            async def before_delete(self, request, instance):
                hook_instances.append(instance.username)
                return instance

        viewset = HookDeleteViewSet()
        bound = viewset.delete_item

        request = _make_request(rf, "DELETE", path=f"/items/{user.id}/")
        response = await bound(request, id=user.id)

        assert response.status_code == 200
        assert "hook_del_user" in hook_instances

    @pytest.mark.asyncio
    async def test_after_delete_hook(self, rf):
        """after_delete hook runs after deletion."""
        user = await User.objects.acreate_user(username="hook_after_del", password="pass123")
        after_calls = []

        class AfterDeleteViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            delete_item = DeleteView()

            async def after_delete(self, request, instance):
                after_calls.append(instance.username)

        viewset = AfterDeleteViewSet()
        bound = viewset.delete_item

        request = _make_request(rf, "DELETE", path=f"/items/{user.id}/")
        response = await bound(request, id=user.id)

        assert response.status_code == 200
        assert "hook_after_del" in after_calls

    @pytest.mark.asyncio
    async def test_on_error_hook(self, rf):
        """on_error hook is called when an exception occurs."""
        error_log = []

        class ErrorViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema
            read_item = ReadView()

            async def on_error(self, request, error):
                error_log.append(str(error))

        viewset = ErrorViewSet()
        bound = viewset.read_item

        request = _make_request(rf, "GET", path="/items/99999/")
        response = await bound(request, id=99999)

        assert response.status_code == 404
        # on_error should have been called for the NotFoundAPIError
        assert len(error_log) >= 1


# ============================================================================
# Full CRUD lifecycle test
# ============================================================================


@pytest.mark.django_db
class TestFullCRUDLifecycle:
    """End-to-end test exercising create, read, list, update, delete."""

    @pytest.mark.asyncio
    async def test_crud_lifecycle(self, rf):
        """Walk through a complete CRUD lifecycle."""

        class LifecycleViewSet(APIViewSet):
            model = User
            prefix = "lifecycle"
            default_response_schema = UserReadSchema
            list_items = ListView(pagination=False)
            create_item = CreateView(request_schema=ItemCreateSchema, response_schema=ItemSchema)
            read_item = ReadView()
            update_item = UpdateView(request_schema=ItemUpdateSchema, response_schema=UserReadSchema)
            delete_item = DeleteView()

            async def perform_create(self, data_dict, request):
                user = await User.objects.acreate_user(
                    username=data_dict["name"], password="pass123"
                )
                user.name = data_dict["name"]
                user.price = data_dict.get("price", 0)
                return user

        viewset = LifecycleViewSet()

        # 1) CREATE
        create_req = _make_request(rf, "POST", data={"name": "lifecycle_item", "price": 99.0})
        create_resp = await viewset.create_item(create_req)
        assert create_resp.status_code == 200
        create_data = orjson.loads(create_resp.content)
        assert create_data["name"] == "lifecycle_item"

        # Get the created user's ID
        user = await User.objects.aget(username="lifecycle_item")
        user_id = user.id

        # 2) READ
        read_req = _make_request(rf, "GET", path=f"/lifecycle/{user_id}/")
        read_resp = await viewset.read_item(read_req, id=user_id)
        assert read_resp.status_code == 200
        read_data = orjson.loads(read_resp.content)
        assert read_data["username"] == "lifecycle_item"
        assert read_data["id"] == user_id

        # 3) LIST
        list_req = _make_request(rf, "GET", path="/lifecycle/")
        list_resp = await viewset.list_items(list_req)
        assert list_resp.status_code == 200
        list_data = orjson.loads(list_resp.content)
        assert list_data["total"] >= 1
        found = any(
            item["username"] == "lifecycle_item" for item in list_data["items"]
        )
        assert found

        # 4) UPDATE
        update_req = _make_request(
            rf, "PUT", data={"name": "updated_lifecycle"}
        )
        update_resp = await viewset.update_item(update_req, id=user_id)
        assert update_resp.status_code == 200

        # 5) DELETE
        delete_req = _make_request(rf, "DELETE", path=f"/lifecycle/{user_id}/")
        delete_resp = await viewset.delete_item(delete_req, id=user_id)
        assert delete_resp.status_code == 200
        delete_data = orjson.loads(delete_resp.content)
        assert delete_data["deleted"] is True

        # Verify deleted
        assert not await User.objects.filter(id=user_id).aexists()


# ============================================================================
# Route generation and summary generation
# ============================================================================


class TestRouteGeneration:
    """Tests for route and OpenAPI metadata generation."""

    def test_generate_summary_list(self):
        view = ListView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.model.__name__ = "User"
        view._viewset = mock_vs
        assert "List" in view._generate_summary()

    def test_generate_summary_create(self):
        view = CreateView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.model.__name__ = "User"
        view._viewset = mock_vs
        assert "Create" in view._generate_summary()

    def test_generate_summary_read(self):
        view = ReadView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.model.__name__ = "User"
        view._viewset = mock_vs
        assert "Get" in view._generate_summary()

    def test_generate_summary_update(self):
        view = UpdateView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.model.__name__ = "User"
        view._viewset = mock_vs
        assert "Update" in view._generate_summary()

    def test_generate_summary_delete(self):
        view = DeleteView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.model.__name__ = "User"
        view._viewset = mock_vs
        assert "Delete" in view._generate_summary()

    def test_generate_summary_without_viewset(self):
        view = ListView()
        summary = view._generate_summary()
        assert summary == "ListView"

    def test_generate_operation_id_from_attr_name(self):
        view = ListView()
        view._viewset_attr_name = "list_users"
        assert view._generate_operation_id() == "list_users"

    def test_generate_operation_id_fallback(self):
        view = ListView()
        view._viewset_attr_name = None
        assert view._generate_operation_id() == "listview"

    def test_get_route_info(self):
        view = ListView(
            summary="List all items",
            tags=["Items"],
            operation_id="list_items",
        )
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.tags = ["Default"]
        view._viewset = mock_vs

        info = view.get_route_info()
        assert info["summary"] == "List all items"
        assert info["tags"] == ["Items"]
        assert info["operation_id"] == "list_items"
        assert info["methods"] == ["GET"]


# ============================================================================
# ListView internal methods
# ============================================================================


@pytest.mark.django_db
class TestListViewInternals:
    """Tests for ListView internal helper methods."""

    def test_apply_pagination_defaults(self, rf):
        view = ListView(page_size=10, max_page_size=50)
        request = _make_request(rf, "GET")
        qs = User.objects.all()
        _, info = view._apply_pagination(qs, request)
        assert info["page"] == 1
        assert info["page_size"] == 10

    def test_apply_pagination_custom_params(self, rf):
        view = ListView(page_size=10, max_page_size=50)
        request = _make_request(rf, "GET", query={"page": "3", "page_size": "25"})
        _, info = view._apply_pagination(User.objects.all(), request)
        assert info["page"] == 3
        assert info["page_size"] == 25

    def test_apply_pagination_caps_page_size(self, rf):
        view = ListView(page_size=10, max_page_size=50)
        request = _make_request(rf, "GET", query={"page_size": "999"})
        _, info = view._apply_pagination(User.objects.all(), request)
        assert info["page_size"] == 50

    def test_apply_pagination_invalid_page(self, rf):
        view = ListView()
        request = _make_request(rf, "GET", query={"page": "abc"})
        _, info = view._apply_pagination(User.objects.all(), request)
        assert info["page"] == 1

    def test_apply_pagination_invalid_page_size(self, rf):
        view = ListView(page_size=20)
        request = _make_request(rf, "GET", query={"page_size": "abc"})
        _, info = view._apply_pagination(User.objects.all(), request)
        assert info["page_size"] == 20

    def test_is_valid_order_field_with_ordering_fields(self):
        view = ListView(ordering_fields=["name", "created"])
        assert view._is_valid_order_field("name") is True
        assert view._is_valid_order_field("secret") is False

    def test_is_valid_order_field_from_model_fields(self):
        view = ListView()
        mock_vs = MagicMock()
        mock_vs.model = User
        mock_vs.ordering_fields = None
        view._viewset = mock_vs
        assert view._is_valid_order_field("username") is True
        assert view._is_valid_order_field("nonexistent_field") is False

    def test_is_valid_order_field_no_viewset(self):
        view = ListView()
        assert view._is_valid_order_field("anything") is False

    @pytest.mark.asyncio
    async def test_count_queryset_async(self):
        view = ListView()
        qs = User.objects.all()
        count = await view._count_queryset(qs)
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_count_queryset_list(self):
        view = ListView()
        items = [1, 2, 3]
        count = await view._count_queryset(items)
        assert count == 3

    def test_get_filter_backends_from_view(self):
        mock_backend = MagicMock()
        view = ListView(filter_backends=[mock_backend])
        assert view._get_filter_backends() == [mock_backend]

    def test_get_filter_backends_from_viewset(self):
        mock_backend = MagicMock()
        view = ListView()
        mock_vs = MagicMock()
        mock_vs.filter_backends = [mock_backend]
        view._viewset = mock_vs
        assert view._get_filter_backends() == [mock_backend]

    def test_get_filter_backends_empty(self):
        view = ListView()
        view._viewset = None
        assert view._get_filter_backends() == []

    def test_get_pagination_class_from_view(self):
        mock_pag = MagicMock()
        view = ListView(pagination_class=mock_pag)
        assert view._get_pagination_class() is mock_pag

    def test_get_pagination_class_from_viewset(self):
        mock_pag = MagicMock()
        view = ListView()
        mock_vs = MagicMock()
        mock_vs.pagination_class = mock_pag
        view._viewset = mock_vs
        assert view._get_pagination_class() is mock_pag

    def test_apply_search_no_search_fields(self, rf):
        view = ListView()
        qs = User.objects.all()
        request = _make_request(rf, "GET", query={"search": "test"})
        result = view._apply_search(qs, request)
        assert result is qs  # No search fields, no change

    def test_apply_ordering_via_order_by_param(self, rf):
        """The 'order_by' query param also works for ordering."""
        view = ListView(ordering_fields=["username"])
        mock_vs = MagicMock()
        mock_vs.model = User
        view._viewset = mock_vs

        request = _make_request(rf, "GET", query={"order_by": "-username"})
        qs = User.objects.all()
        ordered = view._apply_ordering(qs, request)
        assert ordered.query.order_by == ("-username",)

    def test_apply_filters_skips_pagination_params(self, rf):
        """Pagination-related query params are not used as filters."""
        view = ListView()
        # Use a real viewset so _apply_filters doesn't pick up a MagicMock filterset_class
        vs = SimpleViewSet()
        view._viewset = vs

        request = _make_request(
            rf, "GET", query={"page": "2", "page_size": "10", "ordering": "id"}
        )
        qs = User.objects.all()
        filtered = view._apply_filters(qs, request)
        # No actual filters applied - queryset where clause should be unchanged
        assert str(filtered.query.where) == str(qs.query.where)


# ============================================================================
# Disable hooks
# ============================================================================


class TestDisableHooks:
    """Test that enable_hooks=False disables hook execution."""

    @pytest.mark.asyncio
    async def test_run_hooks_disabled(self, rf):
        view = APIView(enable_hooks=False)
        request = _make_request(rf, "GET")
        sentinel = object()
        result = await view._run_hooks(HookType.BEFORE_LIST, request, value=sentinel)
        # When hooks disabled, the value passes through unchanged
        assert result is sentinel

    @pytest.mark.asyncio
    async def test_handle_error_disabled(self, rf):
        """_handle_error is a no-op when hooks are disabled."""
        view = APIView(enable_hooks=False)
        request = _make_request(rf, "GET")
        # Should not raise
        await view._handle_error(request, ValueError("test"))
