"""
Tests for django_matt.services — BaseService, CRUDService, BaseThirdPartyService.

Uses Django's in-memory test models via conftest. All ORM calls are mocked
so tests run without a real database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Service exceptions
# ---------------------------------------------------------------------------


class TestServiceExceptions:
    def test_not_found_error(self):
        from django_matt.services import NotFoundError, ServiceError

        err = NotFoundError("Widget 99 not found")
        assert err.code == "not_found"
        assert "99" in err.message
        assert isinstance(err, ServiceError)

    def test_validation_error(self):
        from django_matt.services import ValidationError

        err = ValidationError("Title is required", field="title")
        assert err.code == "validation_error"
        assert err.field == "title"

    def test_conflict_error(self):
        from django_matt.services import ConflictError

        err = ConflictError("Already exists")
        assert err.code == "conflict"

    def test_service_error_base(self):
        from django_matt.services import ServiceError

        err = ServiceError("oops", code="custom")
        assert str(err) == "oops"
        assert err.code == "custom"


# ---------------------------------------------------------------------------
# Helpers — lightweight fake model & service
# ---------------------------------------------------------------------------


def _make_mock_model(name: str = "Widget"):
    """Return a MagicMock that looks like a Django model class."""
    model = MagicMock()
    model.__name__ = name
    model._meta = MagicMock()
    model._meta.fields = []
    # objects queryset mock
    model.objects = MagicMock()
    return model


def _make_service(model_mock=None):
    from django_matt.services import CRUDService

    class WidgetService(CRUDService):
        model = model_mock or _make_mock_model()

    return WidgetService()


# ---------------------------------------------------------------------------
# BaseService read helpers
# ---------------------------------------------------------------------------


class TestBaseServiceReadHelpers:
    @pytest.mark.asyncio
    async def test_get_returns_instance(self):
        from django_matt.services.base import BaseService

        model = _make_mock_model()
        instance = MagicMock()
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(BaseService):
            pass

        S.model = model
        svc = S()
        result = await svc.get(1)
        assert result is instance

    @pytest.mark.asyncio
    async def test_get_raises_not_found(self):
        from django.core.exceptions import ObjectDoesNotExist

        from django_matt.services.base import BaseService, NotFoundError

        model = _make_mock_model()
        model.objects.all.return_value.aget = AsyncMock(side_effect=ObjectDoesNotExist)

        class S(BaseService):
            pass

        S.model = model
        svc = S()

        with pytest.raises(NotFoundError):
            await svc.get(999)

    @pytest.mark.asyncio
    async def test_get_or_none_returns_none(self):
        from django.core.exceptions import ObjectDoesNotExist

        from django_matt.services.base import BaseService

        model = _make_mock_model()
        model.objects.all.return_value.aget = AsyncMock(side_effect=ObjectDoesNotExist)

        class S(BaseService):
            pass

        S.model = model
        svc = S()
        assert await svc.get_or_none(999) is None

    @pytest.mark.asyncio
    async def test_exists(self):
        from django_matt.services.base import BaseService

        model = _make_mock_model()
        model.objects.all.return_value.filter.return_value.aexists = AsyncMock(return_value=True)

        class S(BaseService):
            pass

        S.model = model
        svc = S()
        assert await svc.exists(pk=1) is True

    @pytest.mark.asyncio
    async def test_count(self):
        from django_matt.services.base import BaseService

        model = _make_mock_model()
        model.objects.all.return_value.filter.return_value.acount = AsyncMock(return_value=42)

        class S(BaseService):
            pass

        S.model = model
        svc = S()
        assert await svc.count() == 42


# ---------------------------------------------------------------------------
# CRUDService.list
# ---------------------------------------------------------------------------


def _async_iter(items):
    """Return an async iterable from a regular list."""

    async def _gen():
        for item in items:
            yield item

    return _gen()


def _make_qs(items=None, count=None):
    """Build a queryset mock that supports async for and acount."""
    items = items or []
    qs = MagicMock()
    qs.acount = AsyncMock(return_value=count if count is not None else len(items))
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    # __getitem__ returns another qs (slicing); __aiter__ yields items
    sliced = MagicMock()

    async def _aiter():
        for item in items:
            yield item

    sliced.__aiter__ = lambda self: _aiter()
    qs.__getitem__ = MagicMock(return_value=sliced)
    return qs


class TestCRUDServiceList:
    @pytest.mark.asyncio
    async def test_list_returns_items_and_total(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        fake_items = [MagicMock(), MagicMock()]
        qs = _make_qs(fake_items)
        model.objects.all.return_value = qs

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        items, total = await svc.list()
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_with_filters_skips_none(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        qs = _make_qs()
        model.objects.all.return_value = qs

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        # None values should not be passed to filter
        await svc.list(status=None, active=True)
        call_kwargs = qs.filter.call_args[1]
        assert "status" not in call_kwargs
        assert call_kwargs.get("active") is True

    @pytest.mark.asyncio
    async def test_list_with_ordering(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        qs = _make_qs()
        model.objects.all.return_value = qs

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        await svc.list(ordering="-created_at")
        qs.order_by.assert_called_once_with("-created_at")


# ---------------------------------------------------------------------------
# CRUDService.create
# ---------------------------------------------------------------------------


class TestCRUDServiceCreate:
    @pytest.mark.asyncio
    async def test_create_basic(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        instance = MagicMock()
        instance.pk = 1
        instance.aclean_fields = AsyncMock()
        instance.asave = AsyncMock()
        model.return_value = instance  # model(**data) → instance

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        with patch("django_matt.services.base.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_atomic.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.create({"title": "Test"})

        assert result is instance
        instance.asave.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_adds_created_by(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        # Signal model supports created_by
        model.created_by = None
        captured: dict[str, Any] = {}

        instance = MagicMock()
        instance.pk = 1
        instance.aclean_fields = AsyncMock()
        instance.asave = AsyncMock()

        def capture(**kwargs):
            captured.update(kwargs)
            return instance

        model.side_effect = capture

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        user = MagicMock()
        with patch("django_matt.services.base.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_atomic.return_value.__aexit__ = AsyncMock(return_value=False)
            await svc.create({"title": "Test"}, user=user)

        assert captured.get("created_by") is user


# ---------------------------------------------------------------------------
# CRUDService.update
# ---------------------------------------------------------------------------


class TestCRUDServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_sets_fields(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        instance = MagicMock()
        instance.pk = 1
        instance.title = "old"
        instance.asave = AsyncMock()
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        with patch("django_matt.services.base.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_atomic.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.update(1, {"title": "new"})

        assert result.title == "new"
        instance.asave.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_update_skips_none(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        recorded: dict = {}

        class FakeInstance:
            pk = 1
            title = "old"
            description = "old description"

            def __setattr__(self, key, value):
                if not key.startswith("_"):
                    recorded[key] = value
                super().__setattr__(key, value)

            async def asave(self):
                pass

        instance = FakeInstance()
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        with patch("django_matt.services.base.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_atomic.return_value.__aexit__ = AsyncMock(return_value=False)
            await svc.update(1, {"title": "new", "description": None}, partial=True)

        # description=None should not be set on the instance
        assert "description" not in recorded
        assert recorded.get("title") == "new"

    @pytest.mark.asyncio
    async def test_update_fields_convenience(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        instance = MagicMock()
        instance.pk = 1
        instance.asave = AsyncMock()
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(CRUDService):
            pass

        S.model = model
        svc = S()

        with patch("django_matt.services.base.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_atomic.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.update_fields(1, completed=True)

        assert result is instance


# ---------------------------------------------------------------------------
# CRUDService.delete
# ---------------------------------------------------------------------------


class TestCRUDServiceDelete:
    @pytest.mark.asyncio
    async def test_hard_delete(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        instance = MagicMock()
        instance.adelete = AsyncMock(return_value=(1, {}))
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        result = await svc.delete(1, hard=True)
        assert result is True
        instance.adelete.assert_called_once()

    @pytest.mark.asyncio
    async def test_soft_delete_calls_soft_delete(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        soft_called: list = []

        class FakeInstance:
            pk = 1

            def soft_delete(self, user=None):
                soft_called.append(user)

            async def adelete(self):
                raise AssertionError("adelete should not be called on soft-delete")

        instance = FakeInstance()
        model.objects.all.return_value.aget = AsyncMock(return_value=instance)

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        result = await svc.delete(1)
        assert result is True
        assert len(soft_called) == 1


# ---------------------------------------------------------------------------
# CRUDService.bulk_delete
# ---------------------------------------------------------------------------


class TestCRUDServiceBulkDelete:
    @pytest.mark.asyncio
    async def test_bulk_delete_hard(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        qs = MagicMock()
        qs.adelete = AsyncMock(return_value=(3, {}))
        qs.filter.return_value = qs
        model.objects.all.return_value = qs

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        count = await svc.bulk_delete([1, 2, 3], hard=True)
        assert count == 3

    @pytest.mark.asyncio
    async def test_bulk_delete_soft(self):
        from django_matt.services import CRUDService

        model = _make_mock_model()
        model.is_active = True  # signal soft-delete support
        qs = MagicMock()
        qs.aupdate = AsyncMock(return_value=2)
        qs.filter.return_value = qs
        model.objects.all.return_value = qs

        class S(CRUDService):
            pass

        S.model = model
        svc = S()
        count = await svc.bulk_delete([1, 2])
        assert count == 2
        qs.aupdate.assert_called_once_with(is_active=False)


# ---------------------------------------------------------------------------
# BaseThirdPartyService
# ---------------------------------------------------------------------------


httpx_mod = pytest.importorskip("httpx")


class TestBaseThirdPartyService:
    def _make_resp(self, data: dict, status: int = 200) -> MagicMock:
        import orjson

        resp = MagicMock()
        resp.content = orjson.dumps(data)
        resp.is_success = status < 400
        resp.status_code = status
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_get(self):
        from django_matt.services import BaseThirdPartyService

        class GithubService(BaseThirdPartyService):
            base_url = "https://api.github.com"

        svc = GithubService()
        resp = self._make_resp({"login": "octocat"})

        with patch.object(svc._get_client(), "request", AsyncMock(return_value=resp)):
            result = await svc._get("/users/octocat")
        assert result["login"] == "octocat"

    @pytest.mark.asyncio
    async def test_post(self):
        from django_matt.services import BaseThirdPartyService

        class MyService(BaseThirdPartyService):
            base_url = "https://api.example.com"

        svc = MyService()
        resp = self._make_resp({"id": 42})

        with patch.object(svc._get_client(), "request", AsyncMock(return_value=resp)):
            result = await svc._post("/items", {"name": "Widget"})
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_error_raises_third_party_error(self):
        from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError

        class MyService(BaseThirdPartyService):
            base_url = "https://api.example.com"

        svc = MyService()
        resp = self._make_resp({"message": "Not found"}, status=404)

        with (
            patch.object(svc._get_client(), "request", AsyncMock(return_value=resp)),
            pytest.raises(ThirdPartyServiceError) as exc_info,
        ):
            await svc._get("/missing")

        assert exc_info.value.status == 404

    @pytest.mark.asyncio
    async def test_custom_auth_headers(self):
        from django_matt.services import BaseThirdPartyService

        class MyService(BaseThirdPartyService):
            base_url = "https://api.example.com"

            def _auth_headers(self):
                return {"Authorization": "Bearer test-key"}

        svc = MyService()
        client = svc._get_client()
        assert "Bearer test-key" in client.headers.get("authorization", "")

    @pytest.mark.asyncio
    async def test_context_manager(self):
        from django_matt.services import BaseThirdPartyService

        class MyService(BaseThirdPartyService):
            base_url = "https://api.example.com"

        async with MyService() as svc:
            assert svc._http is None or not svc._http.is_closed
        # After exit, client should be closed
        assert svc._http is None or svc._http.is_closed

    @pytest.mark.asyncio
    async def test_custom_on_error(self):
        from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError

        class StrictService(BaseThirdPartyService):
            base_url = "https://api.example.com"

            def _on_error(self, status: int, body: dict) -> None:
                raise ThirdPartyServiceError(status, body.get("error", "bad"), body)

        svc = StrictService()
        resp = self._make_resp({"error": "rate limited"}, status=429)

        with (
            patch.object(svc._get_client(), "request", AsyncMock(return_value=resp)),
            pytest.raises(ThirdPartyServiceError) as exc_info,
        ):
            await svc._post("/items", {})

        assert "rate limited" in exc_info.value.message


# ---------------------------------------------------------------------------
# CLI template generators
# ---------------------------------------------------------------------------


class TestCLITemplateGenerators:
    def test_generate_service_template(self):
        from django_matt.cli.templates.service import generate_service_template

        code = generate_service_template("Product")
        assert "class ProductService(CRUDService" in code
        assert "model = Product" in code
        assert "from django_matt.services import CRUDService" in code
        assert "get_queryset" in code

    def test_generate_third_party_service_template(self):
        from django_matt.cli.templates.service import generate_third_party_service_template

        code = generate_third_party_service_template("Stripe", "https://api.stripe.com/v1")
        assert "class StripeService(BaseThirdPartyService)" in code
        assert "https://api.stripe.com/v1" in code
        assert "_auth_headers" in code
        assert "from django_matt.services import BaseThirdPartyService" in code
