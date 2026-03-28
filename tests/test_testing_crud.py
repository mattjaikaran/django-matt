"""
Tests for django_matt.testing.crud — scenario-based CRUD testing.

Covers:
- CRUDScenario dataclass defaults and custom values
- CRUDTestCase.run() with status assertions, body assertions, savepoint isolation
- CRUDTestCase failure messages
- generate_crud_scenarios() for a ViewSet with all CRUD views
- generate_crud_scenarios() for a ViewSet with a subset of views
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import Client

import orjson
import pytest

from django_matt.testing.crud import (
    CRUDScenario,
    CRUDTestCase,
    CRUDTestResult,
    generate_crud_scenarios,
)
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.list import ListView
from django_matt.views.read import ReadView
from django_matt.views.update import PatchView, UpdateView
from django_matt.views.viewset import APIViewSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_response(data: dict | list, status_code: int = 200) -> HttpResponse:
    """Build a minimal HttpResponse with JSON content."""
    resp = HttpResponse(
        content=orjson.dumps(data),
        content_type="application/json",
    )
    resp.status_code = status_code
    return resp


def _empty_response(status_code: int = 204) -> HttpResponse:
    resp = HttpResponse(content=b"", content_type="application/json")
    resp.status_code = status_code
    return resp


# ---------------------------------------------------------------------------
# CRUDScenario dataclass
# ---------------------------------------------------------------------------


class TestCRUDScenario:
    def test_defaults(self):
        s = CRUDScenario(method="GET", url="/api/items/")
        assert s.method == "GET"
        assert s.url == "/api/items/"
        assert s.data is None
        assert s.expected_status == 200
        assert s.expected_body is None
        assert s.user is None
        assert s.headers is None
        assert s.description == ""
        assert s.setup is None

    def test_custom_values(self):
        user = MagicMock()
        setup_fn = MagicMock()
        s = CRUDScenario(
            method="POST",
            url="/api/items/",
            data={"name": "Widget"},
            expected_status=201,
            expected_body={"name": "Widget"},
            user=user,
            headers={"X-Custom": "val"},
            description="create widget",
            setup=setup_fn,
        )
        assert s.method == "POST"
        assert s.data == {"name": "Widget"}
        assert s.expected_status == 201
        assert s.expected_body == {"name": "Widget"}
        assert s.user is user
        assert s.headers == {"X-Custom": "val"}
        assert s.description == "create widget"
        assert s.setup is setup_fn


# ---------------------------------------------------------------------------
# CRUDTestCase — passing scenarios
# ---------------------------------------------------------------------------


class TestCRUDTestCasePass:
    """Scenarios that should pass."""

    def test_status_check_passes(self):
        """A scenario whose expected_status matches the response passes."""
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({"items": []}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/api/items/",
                    expected_status=200,
                    description="list returns 200",
                ),
            ]
        )
        results = case.run(client)
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].status_code == 200

    def test_body_check_passes(self):
        """expected_body keys/values are verified against the response."""
        client = MagicMock(spec=Client)
        client.post.return_value = _json_response(
            {"id": 1, "name": "Widget", "price": 9.99}, 201
        )

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="POST",
                    url="/api/items/",
                    data={"name": "Widget", "price": 9.99},
                    expected_status=201,
                    expected_body={"name": "Widget"},
                    description="create widget",
                ),
            ]
        )
        results = case.run(client)
        assert results[0].passed is True

    def test_multiple_scenarios(self):
        """Multiple scenarios are all executed."""
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response([], 200)
        client.delete.return_value = _empty_response(204)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method="GET", url="/a/", expected_status=200),
                CRUDScenario(method="DELETE", url="/a/1", expected_status=204),
            ]
        )
        results = case.run(client)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_setup_callable_invoked(self):
        """The scenario's setup function is called before the request."""
        setup_fn = MagicMock()
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    setup=setup_fn,
                ),
            ]
        )
        case.run(client)
        setup_fn.assert_called_once()

    def test_user_authentication(self):
        """When scenario has a user, force_authenticate is called."""
        user = MagicMock()
        client = MagicMock(spec=Client)
        client.force_authenticate = MagicMock()
        client.get.return_value = _json_response({}, 200)
        client.logout = MagicMock()

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    user=user,
                ),
            ]
        )
        case.run(client)
        client.force_authenticate.assert_called_once_with(user)

    def test_user_force_login_fallback(self):
        """Without force_authenticate, falls back to force_login."""
        user = MagicMock()
        client = MagicMock(spec=Client)
        # Remove force_authenticate so the fallback branch is taken
        del client.force_authenticate
        client.get.return_value = _json_response({}, 200)
        client.logout = MagicMock()

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method="GET", url="/x/", expected_status=200, user=user),
            ]
        )
        case.run(client)
        client.force_login.assert_called_once_with(user)


# ---------------------------------------------------------------------------
# CRUDTestCase — failing scenarios
# ---------------------------------------------------------------------------


class TestCRUDTestCaseFail:
    """Scenarios that should raise AssertionError."""

    def test_status_mismatch_raises(self):
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({"error": "not found"}, 404)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    description="expect 200",
                ),
            ]
        )
        with pytest.raises(AssertionError, match="Expected status 200, got 404"):
            case.run(client)

    def test_body_key_missing_raises(self):
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({"id": 1}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    expected_body={"name": "Widget"},
                    description="check name",
                ),
            ]
        )
        with pytest.raises(AssertionError, match="Expected key 'name'"):
            case.run(client)

    def test_body_value_mismatch_raises(self):
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({"name": "Gadget"}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    expected_body={"name": "Widget"},
                    description="check name value",
                ),
            ]
        )
        with pytest.raises(AssertionError, match=r"expected 'Widget'.*got 'Gadget'"):
            case.run(client)

    def test_non_dict_body_with_expected_body_raises(self):
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response([1, 2, 3], 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    expected_body={"key": "val"},
                    description="body is list",
                ),
            ]
        )
        with pytest.raises(AssertionError, match="Expected response body to be a dict"):
            case.run(client)


# ---------------------------------------------------------------------------
# CRUDTestCase — HTTP method dispatch
# ---------------------------------------------------------------------------


class TestCRUDTestCaseMethods:
    """Verify that each HTTP method dispatches to the correct client method."""

    @pytest.mark.parametrize(
        "method,client_attr",
        [
            ("GET", "get"),
            ("POST", "post"),
            ("PUT", "put"),
            ("PATCH", "patch"),
            ("DELETE", "delete"),
        ],
    )
    def test_method_dispatch(self, method: str, client_attr: str):
        client = MagicMock(spec=Client)
        getattr(client, client_attr).return_value = _json_response({}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method=method, url="/x/", expected_status=200),
            ]
        )
        case.run(client)
        getattr(client, client_attr).assert_called_once()

    def test_unsupported_method_raises(self):
        client = MagicMock(spec=Client)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method="OPTIONS", url="/x/", expected_status=200),
            ]
        )
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            case.run(client)

    def test_headers_forwarded(self):
        """Custom headers are passed through to the client."""
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(
                    method="GET",
                    url="/x/",
                    expected_status=200,
                    headers={"X-Custom": "hello"},
                ),
            ]
        )
        case.run(client)
        call_kwargs = client.get.call_args
        assert call_kwargs[1].get("HTTP_X_CUSTOM") == "hello"


# ---------------------------------------------------------------------------
# CRUDTestCase — savepoint isolation
# ---------------------------------------------------------------------------


class TestCRUDTestCaseSavepoint:
    """Verify that savepoint isolation is used."""

    @patch("django_matt.testing.crud.transaction")
    def test_savepoint_created_and_rolled_back(self, mock_txn):
        mock_txn.savepoint.return_value = "sp1"
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({}, 200)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method="GET", url="/x/", expected_status=200),
            ]
        )
        case.run(client)

        mock_txn.savepoint.assert_called_once()
        mock_txn.savepoint_rollback.assert_called_once_with("sp1")

    @patch("django_matt.testing.crud.transaction")
    def test_savepoint_rolled_back_on_failure(self, mock_txn):
        """Savepoint is rolled back even when assertion fails."""
        mock_txn.savepoint.return_value = "sp2"
        client = MagicMock(spec=Client)
        client.get.return_value = _json_response({}, 500)

        case = CRUDTestCase(
            scenarios=[
                CRUDScenario(method="GET", url="/x/", expected_status=200),
            ]
        )
        with pytest.raises(AssertionError):
            case.run(client)

        mock_txn.savepoint_rollback.assert_called_once_with("sp2")


# ---------------------------------------------------------------------------
# generate_crud_scenarios
# ---------------------------------------------------------------------------


class _FullViewSet(APIViewSet):
    """ViewSet with all CRUD views for testing generate_crud_scenarios."""

    model = MagicMock()
    prefix = "things"

    list_things = ListView()
    create_thing = CreateView()
    read_thing = ReadView()
    update_thing = UpdateView()
    delete_thing = DeleteView()


class _ListOnlyViewSet(APIViewSet):
    """ViewSet with only a ListView."""

    model = MagicMock()
    prefix = "items"

    list_items = ListView()


class _PatchViewSet(APIViewSet):
    """ViewSet with a PatchView instead of UpdateView."""

    model = MagicMock()
    prefix = "stuff"

    patch_stuff = PatchView()


class TestGenerateCRUDScenarios:
    def test_full_viewset_generates_all_scenarios(self):
        scenarios = generate_crud_scenarios(
            _FullViewSet,
            base_url="/api/things",
            create_data={"name": "Thing"},
            update_data={"name": "Updated"},
        )
        # list(1) + create(2) + read(2) + update(2) + delete(2) = 9
        assert len(scenarios) == 9

        descriptions = [s.description for s in scenarios]

        # Check that each view type produced scenarios
        assert any("list returns 200" in d for d in descriptions)
        assert any("create returns 201" in d for d in descriptions)
        assert any("create empty body returns 422" in d for d in descriptions)
        assert any("read returns 200" in d for d in descriptions)
        assert any("read non-existent returns 404" in d for d in descriptions)
        assert any("update returns 200" in d for d in descriptions)
        assert any("update non-existent returns 404" in d for d in descriptions)
        assert any("delete returns 204" in d for d in descriptions)
        assert any("delete non-existent returns 404" in d for d in descriptions)

    def test_list_only_viewset(self):
        scenarios = generate_crud_scenarios(
            _ListOnlyViewSet,
            base_url="/api/items",
        )
        assert len(scenarios) == 1
        assert scenarios[0].method == "GET"
        assert scenarios[0].expected_status == 200

    def test_create_without_data_skips_happy_path(self):
        """When create_data is None, the 201 scenario is skipped."""
        scenarios = generate_crud_scenarios(
            _FullViewSet,
            base_url="/api/things",
            # No create_data
        )
        descriptions = [s.description for s in scenarios]
        assert not any("create returns 201" in d for d in descriptions)
        # But the 422 scenario is still generated
        assert any("create empty body returns 422" in d for d in descriptions)

    def test_patch_viewset_uses_patch_method(self):
        scenarios = generate_crud_scenarios(
            _PatchViewSet,
            base_url="/api/stuff",
            update_data={"name": "New"},
        )
        patch_scenarios = [s for s in scenarios if s.method == "PATCH"]
        assert len(patch_scenarios) >= 1

    def test_urls_default_correctly(self):
        scenarios = generate_crud_scenarios(
            _FullViewSet,
            base_url="/api/things",
            create_data={"name": "X"},
        )
        list_scenario = next(s for s in scenarios if "list" in s.description)
        assert list_scenario.url == "/api/things/"

        read_scenario = next(s for s in scenarios if "read returns" in s.description)
        assert read_scenario.url == "/api/things/1"

    def test_custom_urls_override(self):
        scenarios = generate_crud_scenarios(
            _ListOnlyViewSet,
            base_url="/api/items",
            list_url="/custom/list/",
        )
        assert scenarios[0].url == "/custom/list/"

    def test_user_propagated(self):
        user = MagicMock()
        scenarios = generate_crud_scenarios(
            _ListOnlyViewSet,
            base_url="/api/items",
            user=user,
        )
        assert scenarios[0].user is user

    def test_setup_propagated(self):
        setup_fn = MagicMock()
        scenarios = generate_crud_scenarios(
            _ListOnlyViewSet,
            base_url="/api/items",
            setup=setup_fn,
        )
        assert scenarios[0].setup is setup_fn


# ---------------------------------------------------------------------------
# CRUDTestResult
# ---------------------------------------------------------------------------


class TestCRUDTestResult:
    def test_default_values(self):
        s = CRUDScenario(method="GET", url="/x/")
        r = CRUDTestResult(scenario=s, passed=True)
        assert r.passed is True
        assert r.status_code is None
        assert r.response_body is None
        assert r.error is None

    def test_failure_result(self):
        s = CRUDScenario(method="GET", url="/x/")
        r = CRUDTestResult(
            scenario=s,
            passed=False,
            status_code=500,
            response_body={"error": "oops"},
            error="Expected 200, got 500",
        )
        assert r.passed is False
        assert r.status_code == 500
        assert r.error == "Expected 200, got 500"


# ---------------------------------------------------------------------------
# Import from testing __init__
# ---------------------------------------------------------------------------


class TestExports:
    def test_importable_from_testing_package(self):
        from django_matt.testing import (
            CRUDScenario,
            CRUDTestCase,
            CRUDTestResult,
            generate_crud_scenarios,
        )

        assert CRUDScenario is not None
        assert CRUDTestCase is not None
        assert CRUDTestResult is not None
        assert generate_crud_scenarios is not None
