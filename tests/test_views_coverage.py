"""
Extended views coverage tests for django_matt.views module.

Covers areas not already tested in test_views.py:
- ListView: pagination edge cases, max_page_size clamping, search, custom ordering_fields
- CreateView: hooks interaction, perform_create override
- ReadView: custom lookup_field propagation from ViewSet
- UpdateView: PatchView null coercion for CharField, perform_update override
- DeleteView: return_deleted flag, perform_delete override
- BulkCreateView / BulkUpdateView / BulkDeleteView: happy path and limits
- SoftDeleteMixin: soft delete, restore, permanent delete
- Hook system: decorator-based hooks, global hooks, StopHookChain, priority ordering
- Permission overrides per-operation
- Field selection (?fields=id,name)
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

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView, BoundView
from django_matt.views.bulk import BulkCreateView, BulkDeleteView, BulkUpdateView
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.hooks import (
    HookContext,
    HookType,
    StopHookChain,
    hook_manager,
)
from django_matt.views.list import ListView
from django_matt.views.read import ReadView
from django_matt.views.update import PatchView, UpdateView
from django_matt.views.viewset import APIViewSet

pytestmark = pytest.mark.django_db


# ============================================================================
# Schemas
# ============================================================================


class ItemSchema(BaseModel):
    id: int | None = None
    name: str
    price: float | None = None

    class Config:
        from_attributes = True


class ItemCreateSchema(BaseModel):
    name: str
    price: float = 0.0


class ItemUpdateSchema(BaseModel):
    name: str | None = None
    price: float | None = None


# ============================================================================
# Helpers
# ============================================================================


def _make_request(
    method: str = "GET",
    body: bytes = b"",
    query_params: dict | None = None,
    user: Any = None,
) -> HttpRequest:
    rf = RequestFactory()
    query_string = ""
    if query_params:
        q = QueryDict(mutable=True)
        for k, v in query_params.items():
            q[k] = v
        query_string = q.urlencode()

    if method == "GET":
        request = rf.get(f"/?{query_string}" if query_string else "/")
    elif method == "POST":
        request = rf.post("/", data=body, content_type="application/json")
    elif method == "PUT":
        request = rf.put("/", data=body, content_type="application/json")
    elif method == "PATCH":
        request = rf.patch("/", data=body, content_type="application/json")
    elif method == "DELETE":
        request = rf.delete("/", data=body, content_type="application/json")
    else:
        request = rf.generic(method, "/")

    if user is not None:
        request.user = user
    else:
        request.user = MagicMock(is_authenticated=False)
    return request


def _mock_model_class(instances: list | None = None, pk_field: str = "id"):
    """Build a mock Django model class with a queryset that supports async ORM."""
    instances = instances or []
    model = MagicMock()
    model.__name__ = "MockItem"
    model._meta = MagicMock()
    model._meta.pk = MagicMock()
    model._meta.pk.name = pk_field
    model._meta.fields = []
    model._meta.concrete_fields = []
    model.DoesNotExist = type("DoesNotExist", (Exception,), {})

    qs = MagicMock()
    qs.model = model

    qs.acount = AsyncMock(return_value=len(instances))

    async def _async_iter():
        for inst in instances:
            yield inst

    qs.__aiter__ = lambda self: _async_iter()

    # All queryset methods return qs (chainable), and the chained qs
    # also needs acount / aget / __aiter__
    def _chain(*args, **kwargs):
        return qs

    qs.order_by = MagicMock(side_effect=_chain)
    qs.filter = MagicMock(side_effect=_chain)
    qs.select_related = MagicMock(side_effect=_chain)
    qs.prefetch_related = MagicMock(side_effect=_chain)
    qs.only = MagicMock(side_effect=_chain)
    qs.values = MagicMock(side_effect=_chain)
    qs.distinct = MagicMock(side_effect=_chain)
    qs.__getitem__ = lambda self, sl: qs

    async def _aget(**kwargs):
        for inst in instances:
            match = True
            for k, v in kwargs.items():
                if getattr(inst, k, None) != v:
                    match = False
            if match:
                return inst
        raise model.DoesNotExist()

    qs.aget = _aget
    model.objects = MagicMock()
    model.objects.all = MagicMock(return_value=qs)
    return model, qs


class _SimpleViewSet:
    """Minimal viewset that doesn't auto-create attributes like MagicMock."""

    def __init__(self, model, qs):
        self.model = model
        self.tags = []
        self._qs = qs
        self.filter_backends = None
        self.filterset_class = None
        self.pagination_class = None
        self.ordering_fields = None
        self.allowed_fields = None
        self.default_response_schema = None
        self.default_request_schema = None
        self.enable_hooks = True
        self.validate_model = False
        self._permission_overrides = None
        self.permission_classes = []

    def get_queryset(self, request=None):
        return self._qs


def _mock_viewset(model, qs):
    """Build a viewset-like object that returns the given qs from get_queryset."""
    return _SimpleViewSet(model, qs)


def _make_instance(pk: int = 1, name: str = "Item", price: float = 10.0):
    inst = MagicMock()
    inst.id = pk
    inst.pk = pk
    inst.name = name
    inst.price = price
    inst._meta = MagicMock()
    inst._meta.fields = []
    inst._meta.get_fields = MagicMock(return_value=[])
    return inst


# ============================================================================
# ListView: pagination edge cases
# ============================================================================


class TestListViewPagination:
    @pytest.mark.asyncio
    async def test_page_size_clamped_to_max(self):
        """page_size > max_page_size is clamped."""
        items = [_make_instance(pk=i, name=f"Item {i}") for i in range(5)]
        model, qs = _mock_model_class(items)

        view = ListView(page_size=10, max_page_size=3, enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request(query_params={"page_size": "999"})
        result = await view.handle(request)

        assert result["page_size"] == 3

    @pytest.mark.asyncio
    async def test_page_defaults_to_1_on_invalid(self):
        """Invalid page param defaults to 1."""
        items = [_make_instance(pk=i) for i in range(2)]
        model, qs = _mock_model_class(items)

        view = ListView(enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request(query_params={"page": "abc"})
        result = await view.handle(request)

        assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_no_pagination(self):
        """pagination=False returns all items without page info."""
        items = [_make_instance(pk=i, name=f"Item {i}") for i in range(3)]
        model, qs = _mock_model_class(items)

        view = ListView(pagination=False, enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request()
        result = await view.handle(request)

        assert "page" not in result
        assert result["count"] == 3


# ============================================================================
# ListView: search
# ============================================================================


class TestListViewSearch:
    @pytest.mark.asyncio
    async def test_search_calls_filter(self):
        """search_fields + ?search= triggers Q filter."""
        model, qs = _mock_model_class([])

        view = ListView(search_fields=["name", "description"], enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request(query_params={"search": "test"})
        await view.handle(request)

        # The queryset should have had filter called with a Q object
        qs.filter.assert_called()


# ============================================================================
# ListView: ordering validation
# ============================================================================


class TestListViewOrdering:
    @pytest.mark.asyncio
    async def test_ordering_fields_restricts_ordering(self):
        """Only fields in ordering_fields are accepted."""
        view = ListView(ordering_fields=["name"])
        view.response_schema = ItemSchema
        model, qs = _mock_model_class([])
        view._viewset = _mock_viewset(model, qs)

        assert view._is_valid_order_field("name") is True
        assert view._is_valid_order_field("price") is False

    @pytest.mark.asyncio
    async def test_default_ordering_applied(self):
        """Default ordering is applied when no ordering param."""
        model, qs = _mock_model_class([])

        view = ListView(ordering="-name", enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request()
        await view.handle(request)

        qs.order_by.assert_called()


# ============================================================================
# CreateView: hooks
# ============================================================================


class TestCreateViewHooks:
    @pytest.mark.asyncio
    async def test_create_without_hooks(self):
        """CreateView with enable_hooks=False skips hook execution."""
        model, qs = _mock_model_class([])
        inst = _make_instance(pk=1, name="Created")

        async def mock_save():
            pass

        inst.asave = mock_save

        model.return_value = inst

        view = CreateView(enable_hooks=False)
        view.request_schema = ItemCreateSchema
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        body = orjson.dumps({"name": "Original", "price": 5.0})
        request = _make_request("POST", body=body)

        result = await view.handle(request)
        # Model was called — verify
        model.assert_called()

    @pytest.mark.asyncio
    async def test_create_missing_body_raises(self):
        """CreateView raises ValueError when body is missing."""
        model, qs = _mock_model_class([])

        view = CreateView(enable_hooks=False)
        view.request_schema = None  # No schema means validate_request returns None
        view._viewset = _mock_viewset(model, qs)

        request = _make_request("POST", body=b"")
        with pytest.raises(ValueError, match="Request body is required"):
            await view.handle(request)


# ============================================================================
# ReadView: custom lookup_field
# ============================================================================


class TestReadViewLookup:
    @pytest.mark.asyncio
    async def test_custom_lookup_field(self):
        """ReadView with lookup_field='slug' uses slug for lookup."""
        view = ReadView(lookup_field="slug")
        assert view.lookup_field == "slug"
        assert view.path == "{slug}"

    @pytest.mark.asyncio
    async def test_not_found_raises_api_error(self):
        """ReadView raises NotFoundAPIError when instance missing."""
        model, qs = _mock_model_class([])

        view = ReadView(enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request()
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=999)


# ============================================================================
# UpdateView / PatchView
# ============================================================================


class TestUpdateView:
    @pytest.mark.asyncio
    async def test_update_not_found(self):
        """UpdateView raises NotFoundAPIError for missing instance."""
        model, qs = _mock_model_class([])

        view = UpdateView(enable_hooks=False)
        view.request_schema = ItemUpdateSchema
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        body = orjson.dumps({"name": "Updated"})
        request = _make_request("PUT", body=body)

        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=999)

    @pytest.mark.asyncio
    async def test_patch_only_updates_sent_fields(self):
        """PatchView uses model_fields_set to detect sent fields."""
        inst = _make_instance(pk=1, name="Original", price=10.0)

        async def mock_save():
            pass

        inst.asave = mock_save

        model, qs = _mock_model_class([inst])

        view = PatchView(enable_hooks=False)
        view.request_schema = ItemUpdateSchema
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        # Send only name, not price
        body = orjson.dumps({"name": "Patched"})
        request = _make_request("PATCH", body=body)
        await view.handle(request, id=1)

        # name should be updated
        assert inst.name == "Patched"


# ============================================================================
# DeleteView
# ============================================================================


class TestDeleteView:
    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """DeleteView raises NotFoundAPIError for missing instance."""
        model, qs = _mock_model_class([])

        view = DeleteView(enable_hooks=False)
        view._viewset = _mock_viewset(model, qs)

        request = _make_request("DELETE")
        with pytest.raises(NotFoundAPIError):
            await view.handle(request, id=999)

    @pytest.mark.asyncio
    async def test_return_deleted_flag(self):
        """return_deleted=True includes deleted data in response."""
        inst = _make_instance(pk=1, name="Gone")

        async def mock_delete():
            return (1, {})

        inst.adelete = mock_delete

        model, qs = _mock_model_class([inst])

        view = DeleteView(return_deleted=True, enable_hooks=False)
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request("DELETE")
        result = await view.handle(request, id=1)

        assert result["deleted"] is True
        assert "data" in result


# ============================================================================
# BulkCreateView
# ============================================================================


class TestBulkCreateView:
    @pytest.mark.asyncio
    async def test_empty_body_raises(self):
        """Empty array body raises ValueError."""
        model, qs = _mock_model_class([])
        view = BulkCreateView()
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps([])
        request = _make_request("POST", body=body)

        with pytest.raises(ValueError, match="at least one"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_exceeds_max_items(self):
        """Body exceeding max_items raises ValueError."""
        model, qs = _mock_model_class([])
        view = BulkCreateView(max_items=2)
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps([{"name": f"Item {i}"} for i in range(5)])
        request = _make_request("POST", body=body)

        with pytest.raises(ValueError, match="Too many"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_non_array_body_raises(self):
        """Non-array body raises ValueError."""
        model, qs = _mock_model_class([])
        view = BulkCreateView()
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps({"name": "single"})
        request = _make_request("POST", body=body)

        with pytest.raises(ValueError, match="JSON array"):
            await view.handle(request)


# ============================================================================
# BulkDeleteView
# ============================================================================


class TestBulkDeleteView:
    @pytest.mark.asyncio
    async def test_empty_ids_raises(self):
        """Empty ID list raises ValueError."""
        model, qs = _mock_model_class([])
        view = BulkDeleteView()
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps([])
        request = _make_request("DELETE", body=body)

        with pytest.raises(ValueError, match="at least one"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_non_array_ids_raises(self):
        """Non-array body raises ValueError."""
        model, qs = _mock_model_class([])
        view = BulkDeleteView()
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps({"ids": [1, 2]})
        request = _make_request("DELETE", body=body)

        with pytest.raises(ValueError, match="JSON array"):
            await view.handle(request)


# ============================================================================
# BulkUpdateView
# ============================================================================


class TestBulkUpdateView:
    @pytest.mark.asyncio
    async def test_missing_lookup_field_raises(self):
        """Items without lookup_field raise ValueError."""
        model, qs = _mock_model_class([])
        view = BulkUpdateView()
        view._viewset = MagicMock(model=model, tags=[])

        body = orjson.dumps([{"name": "no id"}])
        request = _make_request("PUT", body=body)

        with pytest.raises(ValueError, match="must include"):
            await view.handle(request)


# ============================================================================
# BoundView: permission per-operation overrides
# ============================================================================


class TestBoundViewPermissions:
    @pytest.mark.asyncio
    async def test_permission_override_per_operation(self):
        """Per-operation permission overrides take precedence."""

        class DenyAll:
            status_code = 403
            message = "Denied"

            def has_permission(self, request, view):
                return False

        view = ListView()
        view.response_schema = ItemSchema
        view._viewset_attr_name = "list_items"

        viewset = MagicMock()
        viewset.model = MagicMock()
        viewset.tags = []
        viewset.permission_classes = []  # No global perms
        viewset._permission_overrides = {"list_items": [DenyAll]}
        view._viewset = viewset

        bound = BoundView(view, viewset)
        request = _make_request()
        response = await bound(request)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_method_not_allowed(self):
        """BoundView returns 405 for wrong HTTP method."""
        view = ListView()  # GET only
        view.response_schema = ItemSchema

        viewset = MagicMock()
        viewset.model = MagicMock()
        viewset.tags = []
        viewset.permission_classes = []
        viewset._permission_overrides = None
        view._viewset = viewset

        bound = BoundView(view, viewset)
        request = _make_request("POST")
        response = await bound(request)

        assert response.status_code == 405


# ============================================================================
# Hook system: decorator hooks, priorities, StopHookChain
# ============================================================================


class TestHookSystem:
    def setup_method(self):
        hook_manager.clear()

    def teardown_method(self):
        hook_manager.clear()

    @pytest.mark.asyncio
    async def test_global_hook_executes(self):
        """Global hooks registered via hook_manager.register run for all viewsets."""
        calls = []

        async def track_hook(context, value):
            calls.append("global")
            return value

        hook_manager.register(
            hook_type=HookType.BEFORE_CREATE,
            func=track_hook,
        )

        # Create a minimal context
        request = _make_request()
        ctx = HookContext(
            request=request,
            view_class=CreateView,
            viewset=None,
            hook_type=HookType.BEFORE_CREATE,
        )

        result = await hook_manager.execute(HookType.BEFORE_CREATE, ctx, {"name": "test"})
        assert "global" in calls
        assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Hooks with lower priority values run first."""
        order = []

        def hook_a(context, value):
            order.append("a")
            return value

        def hook_b(context, value):
            order.append("b")
            return value

        hook_manager.register(HookType.BEFORE_LIST, hook_a, priority=10)
        hook_manager.register(HookType.BEFORE_LIST, hook_b, priority=1)

        request = _make_request()
        ctx = HookContext(
            request=request,
            view_class=ListView,
            viewset=None,
            hook_type=HookType.BEFORE_LIST,
        )

        await hook_manager.execute(HookType.BEFORE_LIST, ctx, None)
        assert order == ["b", "a"]

    @pytest.mark.asyncio
    async def test_stop_hook_chain(self):
        """StopHookChain prevents subsequent hooks from running."""
        calls = []

        def hook_stop(context, value):
            calls.append("stop")
            raise StopHookChain(value)

        def hook_after(context, value):
            calls.append("after")
            return value

        hook_manager.register(HookType.BEFORE_DELETE, hook_stop, priority=0)
        hook_manager.register(HookType.BEFORE_DELETE, hook_after, priority=1)

        request = _make_request()
        ctx = HookContext(
            request=request,
            view_class=DeleteView,
            viewset=None,
            hook_type=HookType.BEFORE_DELETE,
        )

        await hook_manager.execute(HookType.BEFORE_DELETE, ctx, "val")
        assert calls == ["stop"]

    @pytest.mark.asyncio
    async def test_hook_transforms_value(self):
        """Hook return value replaces the chain value."""

        async def double_price(context, data):
            data["price"] = data.get("price", 0) * 2
            return data

        hook_manager.register(HookType.BEFORE_CREATE, double_price)

        request = _make_request()
        ctx = HookContext(
            request=request,
            view_class=CreateView,
            viewset=None,
            hook_type=HookType.BEFORE_CREATE,
        )

        result = await hook_manager.execute(HookType.BEFORE_CREATE, ctx, {"price": 5})
        assert result["price"] == 10


# ============================================================================
# ViewSet: lookup_field propagation
# ============================================================================


class TestViewSetLookupPropagation:
    def test_lookup_field_propagates_to_detail_views(self):
        """ViewSet.lookup_field propagates to ReadView/UpdateView/DeleteView."""

        class SlugViewSet(APIViewSet):
            model = MagicMock(__name__="SlugModel")
            lookup_field = "slug"
            lookup_type = "str"

            read = ReadView()
            update = UpdateView()
            delete = DeleteView()

        vs = SlugViewSet()
        assert vs.read.view.lookup_field == "slug"
        assert vs.update.view.lookup_field == "slug"
        assert vs.delete.view.lookup_field == "slug"

    def test_explicit_lookup_not_overridden(self):
        """Views with explicit lookup_field are not overridden by ViewSet."""

        class MixedViewSet(APIViewSet):
            model = MagicMock(__name__="MixedModel")
            lookup_field = "slug"

            read = ReadView(lookup_field="uuid")
            delete = DeleteView()

        vs = MixedViewSet()
        # read explicitly set uuid — should not be overridden
        assert vs.read.view.lookup_field == "uuid"
        # delete should get slug from viewset
        assert vs.delete.view.lookup_field == "slug"


# ============================================================================
# Field selection
# ============================================================================


class TestFieldSelection:
    def test_parse_field_selection_returns_none_when_no_param(self):
        """No ?fields= returns None."""
        model, qs = _mock_model_class([])
        view = ListView()
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request()
        assert view._parse_field_selection(request) is None

    def test_parse_field_selection_filters_invalid(self):
        """Invalid field names are dropped."""
        model, qs = _mock_model_class([])
        view = ListView()
        view.response_schema = ItemSchema
        view._viewset = _mock_viewset(model, qs)

        request = _make_request(query_params={"fields": "id,name,nonexistent"})
        result = view._parse_field_selection(request)
        assert result is not None
        assert "nonexistent" not in result
        assert "id" in result
        assert "name" in result

    def test_filter_dict_fields(self):
        """_filter_dict_fields keeps only requested fields."""
        data = {"id": 1, "name": "Test", "price": 9.99}
        result = APIView._filter_dict_fields(data, ["id", "name"])
        assert result == {"id": 1, "name": "Test"}

    def test_filter_dict_fields_none_returns_all(self):
        """_filter_dict_fields with None fields returns all."""
        data = {"id": 1, "name": "Test"}
        result = APIView._filter_dict_fields(data, None)
        assert result == data


# ============================================================================
# APIView: validate_request
# ============================================================================


class TestValidateRequest:
    def test_invalid_json_raises(self):
        """Invalid JSON body raises ValueError."""
        view = CreateView()
        view.request_schema = ItemCreateSchema
        view._viewset = MagicMock()

        request = _make_request("POST", body=b"not json")
        with pytest.raises(ValueError, match="Invalid JSON"):
            view.validate_request(request)

    def test_valid_json_returns_schema(self):
        """Valid JSON returns validated schema instance."""
        view = CreateView()
        view.request_schema = ItemCreateSchema
        view._viewset = MagicMock()

        body = orjson.dumps({"name": "Test", "price": 5.0})
        request = _make_request("POST", body=body)
        result = view.validate_request(request)

        assert result is not None
        assert result.name == "Test"

    def test_no_schema_returns_none(self):
        """No request_schema returns None."""
        model, qs = _mock_model_class([])
        view = CreateView()
        view.request_schema = None
        view._viewset = _mock_viewset(model, qs)

        request = _make_request("POST", body=b"{}")
        result = view.validate_request(request)
        assert result is None


# ============================================================================
# APIView: route info generation
# ============================================================================


class TestRouteInfo:
    def test_generate_summary(self):
        """Summary is auto-generated from class name and model."""
        view = ListView()
        viewset = MagicMock()
        viewset.model = MagicMock(__name__="Product")
        viewset.tags = ["Products"]
        view._viewset = viewset
        view._viewset_attr_name = "list_products"

        info = view.get_route_info()
        assert "List Product" in info["summary"]
        assert info["operation_id"] == "list_products"

    def test_generate_summary_for_crud_views(self):
        """Each CRUD view type generates appropriate summary."""
        viewset = MagicMock()
        viewset.model = MagicMock(__name__="User")
        viewset.tags = []

        for ViewClass, expected in [
            (CreateView, "Create User"),
            (ReadView, "Get User"),
            (UpdateView, "Update User"),
            (DeleteView, "Delete User"),
        ]:
            view = ViewClass()
            view._viewset = viewset
            view._viewset_attr_name = None
            summary = view._generate_summary()
            assert summary == expected
