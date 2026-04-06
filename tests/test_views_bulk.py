"""
Tests for bulk CRUD views: BulkCreateView, BulkUpdateView, BulkDeleteView.

Covers:
- BulkCreateView: bulk create, validation, max_items limit, empty body, hooks
- BulkUpdateView: bulk update, missing IDs, not-found handling, hooks
- BulkDeleteView: bulk delete, count verification, hooks
- Transaction atomicity: all-or-nothing semantics
- ViewSet integration: bulk views attached to APIViewSet
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth.models import User
from django.db import models
from django.http import HttpRequest
from django.test import RequestFactory

import orjson
import pytest
from pydantic import BaseModel

from django_matt.views.base import BoundView
from django_matt.views.bulk import BulkCreateView, BulkDeleteView, BulkUpdateView
from django_matt.views.hooks import HookType, hook_manager
from django_matt.views.viewset import APIViewSet

# ============================================================================
# Schemas
# ============================================================================


class UserCreateSchema(BaseModel):
    username: str
    email: str = ""

    class Config:
        from_attributes = True


class UserUpdateSchema(BaseModel):
    username: str | None = None
    email: str | None = None

    class Config:
        from_attributes = True


class UserReadSchema(BaseModel):
    id: int | None = None
    username: str
    email: str = ""

    class Config:
        from_attributes = True


# ============================================================================
# ViewSet
# ============================================================================


class BulkUserViewSet(APIViewSet):
    model = User
    default_response_schema = UserReadSchema
    default_request_schema = UserCreateSchema

    bulk_create = BulkCreateView(
        path="bulk",
        request_schema=UserCreateSchema,
        response_schema=UserReadSchema,
    )
    bulk_update = BulkUpdateView(
        path="bulk",
        request_schema=UserUpdateSchema,
        response_schema=UserReadSchema,
    )
    bulk_delete = BulkDeleteView(path="bulk")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_hooks():
    """Clear the global hook manager before/after each test."""
    hook_manager.clear()
    yield
    hook_manager.clear()


@pytest.fixture()
def rf():
    return RequestFactory()


@pytest.fixture()
def viewset():
    return BulkUserViewSet()


def _make_request(rf: RequestFactory, method: str, body: Any) -> HttpRequest:
    """Build a Django HttpRequest with a JSON body."""
    raw = orjson.dumps(body)
    fn = getattr(rf, method.lower())
    request = fn(
        "/api/users/bulk",
        data=raw,
        content_type="application/json",
    )
    request._body = raw
    # Attach a minimal user for permission checks
    request.user = MagicMock()
    request.user.is_authenticated = True
    return request


# ============================================================================
# BulkCreateView
# ============================================================================


@pytest.mark.django_db
class TestBulkCreateView:
    @pytest.mark.asyncio
    async def test_bulk_create_basic(self, rf, viewset):
        """Create multiple users in one request."""
        request = _make_request(rf, "POST", [
            {"username": "bulk_alice", "email": "bulk_alice@example.com"},
            {"username": "bulk_bob", "email": "bulk_bob@example.com"},
        ])

        view = BulkCreateView(
            request_schema=UserCreateSchema,
            response_schema=UserReadSchema,
        )
        view._viewset = viewset

        result = await view.handle(request)

        assert len(result) == 2
        assert result[0]["username"] == "bulk_alice"
        assert result[1]["username"] == "bulk_bob"
        # Verify DB state
        assert await User.objects.filter(username="bulk_alice").aexists()
        assert await User.objects.filter(username="bulk_bob").aexists()

    @pytest.mark.asyncio
    async def test_bulk_create_empty_body(self, rf, viewset):
        """Empty list should raise ValueError."""
        request = _make_request(rf, "POST", [])

        view = BulkCreateView(request_schema=UserCreateSchema)
        view._viewset = viewset

        with pytest.raises(ValueError, match="at least one item"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_create_exceeds_max_items(self, rf, viewset):
        """Exceeding max_items should raise ValueError."""
        items = [{"username": f"user{i}"} for i in range(5)]
        request = _make_request(rf, "POST", items)

        view = BulkCreateView(request_schema=UserCreateSchema, max_items=3)
        view._viewset = viewset

        with pytest.raises(ValueError, match="exceeds maximum of 3"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_create_invalid_json(self, rf, viewset):
        """Non-array body should raise ValueError."""
        request = _make_request(rf, "POST", {"username": "solo"})

        view = BulkCreateView(request_schema=UserCreateSchema)
        view._viewset = viewset

        with pytest.raises(ValueError, match="must be a JSON array"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_create_custom_max_items(self, rf, viewset):
        """Custom max_items is respected."""
        view = BulkCreateView(max_items=5)
        assert view.max_items == 5

    @pytest.mark.asyncio
    async def test_bulk_create_validation_error(self, rf, viewset):
        """Pydantic validation errors bubble up."""
        # username is required, omit it
        request = _make_request(rf, "POST", [{"email": "bad@example.com"}])

        view = BulkCreateView(request_schema=UserCreateSchema)
        view._viewset = viewset

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await view.handle(request)


# ============================================================================
# BulkUpdateView
# ============================================================================


@pytest.mark.django_db
class TestBulkUpdateView:
    @pytest.mark.asyncio
    async def test_bulk_update_basic(self, rf, viewset):
        """Update multiple users in one request."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _create_users():
            u1 = User.objects.create_user("upd_alice", "alice@old.com", "pass")
            u2 = User.objects.create_user("upd_bob", "bob@old.com", "pass")
            return u1.pk, u2.pk

        pk1, pk2 = await _create_users()

        request = _make_request(rf, "PUT", [
            {"id": pk1, "email": "alice@new.com"},
            {"id": pk2, "email": "bob@new.com"},
        ])

        view = BulkUpdateView(
            request_schema=UserUpdateSchema,
            response_schema=UserReadSchema,
        )
        view._viewset = viewset

        result = await view.handle(request)

        assert len(result) == 2
        u1 = await User.objects.aget(pk=pk1)
        assert u1.email == "alice@new.com"
        u2 = await User.objects.aget(pk=pk2)
        assert u2.email == "bob@new.com"

    @pytest.mark.asyncio
    async def test_bulk_update_missing_lookup_field(self, rf, viewset):
        """Items without id should raise ValueError."""
        request = _make_request(rf, "PUT", [{"email": "no-id@example.com"}])

        view = BulkUpdateView(request_schema=UserUpdateSchema)
        view._viewset = viewset

        with pytest.raises(ValueError, match="must include 'id'"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_update_not_found(self, rf, viewset):
        """Non-existent IDs should raise NotFoundAPIError."""
        request = _make_request(rf, "PUT", [{"id": 999999, "email": "x@x.com"}])

        view = BulkUpdateView(request_schema=UserUpdateSchema)
        view._viewset = viewset

        from django_matt.core.errors import NotFoundAPIError

        with pytest.raises(NotFoundAPIError):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_update_empty_body(self, rf, viewset):
        """Empty list should raise ValueError."""
        request = _make_request(rf, "PUT", [])

        view = BulkUpdateView(request_schema=UserUpdateSchema)
        view._viewset = viewset

        with pytest.raises(ValueError, match="at least one item"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_update_exceeds_max_items(self, rf, viewset):
        """Exceeding max_items should raise ValueError."""
        items = [{"id": i, "email": f"u{i}@x.com"} for i in range(10)]
        request = _make_request(rf, "PUT", items)

        view = BulkUpdateView(request_schema=UserUpdateSchema, max_items=5)
        view._viewset = viewset

        with pytest.raises(ValueError, match="exceeds maximum of 5"):
            await view.handle(request)


# ============================================================================
# BulkDeleteView
# ============================================================================


@pytest.mark.django_db
class TestBulkDeleteView:
    @pytest.mark.asyncio
    async def test_bulk_delete_basic(self, rf, viewset):
        """Delete multiple users by ID."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _create_users():
            u1 = User.objects.create_user("del_alice", "da@x.com", "pass")
            u2 = User.objects.create_user("del_bob", "db@x.com", "pass")
            return [u1.pk, u2.pk]

        pks = await _create_users()
        request = _make_request(rf, "DELETE", pks)

        view = BulkDeleteView()
        view._viewset = viewset

        result = await view.handle(request)

        assert result["deleted"] is True
        assert result["count"] == 2
        assert not await User.objects.filter(pk__in=pks).aexists()

    @pytest.mark.asyncio
    async def test_bulk_delete_nonexistent_ids(self, rf, viewset):
        """Deleting non-existent IDs returns count=0, no error."""
        request = _make_request(rf, "DELETE", [999998, 999999])

        view = BulkDeleteView()
        view._viewset = viewset

        result = await view.handle(request)
        assert result["deleted"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_delete_empty_body(self, rf, viewset):
        """Empty list should raise ValueError."""
        request = _make_request(rf, "DELETE", [])

        view = BulkDeleteView()
        view._viewset = viewset

        with pytest.raises(ValueError, match="at least one ID"):
            await view.handle(request)

    @pytest.mark.asyncio
    async def test_bulk_delete_exceeds_max_items(self, rf, viewset):
        """Exceeding max_items should raise ValueError."""
        ids = list(range(20))
        request = _make_request(rf, "DELETE", ids)

        view = BulkDeleteView(max_items=10)
        view._viewset = viewset

        with pytest.raises(ValueError, match="exceeds maximum of 10"):
            await view.handle(request)


# ============================================================================
# BoundView integration (through viewset)
# ============================================================================


@pytest.mark.django_db
class TestBulkViewSetIntegration:
    @pytest.mark.asyncio
    async def test_bulk_create_via_bound_view(self, rf):
        """BulkCreateView works correctly when accessed through a viewset."""
        vs = BulkUserViewSet()
        bound = vs.bulk_create  # triggers __get__ -> BoundView

        request = _make_request(rf, "POST", [
            {"username": "carol", "email": "carol@example.com"},
        ])

        response = await bound(request)
        assert response.status_code == 200

        data = orjson.loads(response.content)
        assert len(data) == 1
        assert data[0]["username"] == "carol"

    @pytest.mark.asyncio
    async def test_bulk_delete_via_bound_view(self, rf):
        """BulkDeleteView works correctly when accessed through a viewset."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _create():
            return User.objects.create_user("delme", "d@x.com", "pass").pk

        pk = await _create()
        vs = BulkUserViewSet()
        bound = vs.bulk_delete

        request = _make_request(rf, "DELETE", [pk])
        response = await bound(request)
        assert response.status_code == 200

        data = orjson.loads(response.content)
        assert data["deleted"] is True
        assert data["count"] == 1


# ============================================================================
# Hooks
# ============================================================================


@pytest.mark.django_db
class TestBulkHooks:
    @pytest.mark.asyncio
    async def test_before_bulk_create_hook(self, rf, viewset):
        """before_bulk_create hook can modify data before creation."""

        class HookedViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema

            bulk_create = BulkCreateView(
                request_schema=UserCreateSchema,
                response_schema=UserReadSchema,
            )

            async def before_bulk_create(self, request, data):
                # Add a suffix to all usernames
                for item in data:
                    item["username"] = item["username"] + "_hooked"
                return data

        vs = HookedViewSet()
        view = BulkCreateView(
            request_schema=UserCreateSchema,
            response_schema=UserReadSchema,
        )
        view._viewset = vs

        request = _make_request(rf, "POST", [{"username": "test"}])
        result = await view.handle(request)

        assert result[0]["username"] == "test_hooked"

    @pytest.mark.asyncio
    async def test_before_bulk_delete_hook(self, rf, viewset):
        """before_bulk_delete hook can filter IDs."""

        class HookedViewSet(APIViewSet):
            model = User
            default_response_schema = UserReadSchema

            bulk_delete = BulkDeleteView()

            async def before_bulk_delete(self, request, data):
                # Only allow deletion of the first ID
                return data[:1]

        from asgiref.sync import sync_to_async

        @sync_to_async
        def _create():
            u1 = User.objects.create_user("keep1", "k1@x.com", "pass")
            u2 = User.objects.create_user("keep2", "k2@x.com", "pass")
            return u1.pk, u2.pk

        pk1, pk2 = await _create()

        vs = HookedViewSet()
        view = BulkDeleteView()
        view._viewset = vs

        request = _make_request(rf, "DELETE", [pk1, pk2])
        result = await view.handle(request)

        assert result["count"] == 1
        # Second user should still exist
        assert await User.objects.filter(pk=pk2).aexists()
