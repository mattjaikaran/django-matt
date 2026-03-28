"""
Scenario-based CRUD testing for Django Matt ViewSets.

Provides CRUDScenario (a declarative test scenario) and CRUDTestCase
(a runner that executes scenarios as sub-tests with savepoint isolation).

Also provides generate_crud_scenarios() to auto-generate happy-path and
error scenarios for a given ViewSet class.

Example:
    from django_matt.testing.crud import CRUDScenario, CRUDTestCase

    scenarios = [
        CRUDScenario(
            method="GET",
            url="/api/items/",
            expected_status=200,
            description="list items returns 200",
        ),
        CRUDScenario(
            method="POST",
            url="/api/items/",
            data={"name": "Widget"},
            expected_status=201,
            expected_body={"name": "Widget"},
            description="create item returns 201",
        ),
    ]
    CRUDTestCase(scenarios=scenarios).run(client)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from django.test import Client

import orjson

from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.list import ListView
from django_matt.views.read import ReadView
from django_matt.views.update import PatchView, UpdateView
from django_matt.views.viewset import APIViewSet


@dataclass
class CRUDScenario:
    """A single declarative test scenario for a CRUD endpoint.

    Attributes:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: Request URL path.
        data: Optional request body (will be JSON-encoded).
        expected_status: Expected HTTP status code.
        expected_body: Optional dict of key/value pairs that must appear in
            the JSON response.  Only listed keys are checked; extra keys in
            the response are ignored.
        user: Optional user to authenticate as before the request.
        headers: Optional extra HTTP headers.
        description: Human-readable label shown in sub-test output.
        setup: Optional callable invoked before the request (e.g. to create
            prerequisite data).  Receives no arguments.
    """

    method: str
    url: str
    data: dict[str, Any] | None = None
    expected_status: int = 200
    expected_body: dict[str, Any] | None = None
    user: Any | None = None
    headers: dict[str, str] | None = None
    description: str = ""
    setup: Any | None = None  # callable[[], None] | None


@dataclass
class CRUDTestResult:
    """Result of running a single scenario."""

    scenario: CRUDScenario
    passed: bool
    status_code: int | None = None
    response_body: Any | None = None
    error: str | None = None


class CRUDTestCase:
    """Runs a list of CRUDScenario instances as isolated sub-tests.

    Each scenario is executed inside a database savepoint so that side-effects
    (created/updated/deleted rows) are rolled back before the next scenario.

    Usage with pytest::

        def test_my_viewset(client):
            case = CRUDTestCase(scenarios=[...])
            case.run(client)

    Usage with Django's TestCase (``self.subTest`` support)::

        class MyTest(TestCase):
            def test_crud(self):
                case = CRUDTestCase(scenarios=[...])
                case.run(self.client, test_instance=self)

    Args:
        scenarios: List of CRUDScenario to execute.
    """

    def __init__(self, scenarios: list[CRUDScenario]) -> None:
        self.scenarios = scenarios

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        client: Client,
        *,
        test_instance: Any | None = None,
    ) -> list[CRUDTestResult]:
        """Execute every scenario and return results.

        Raises ``AssertionError`` on the first failing scenario so that
        pytest / unittest can report the failure with a clear message.

        Args:
            client: A Django test ``Client`` (or ``APITestClient``).
            test_instance: Optional ``TestCase`` instance — when provided,
                each scenario is wrapped in ``self.subTest()``.

        Returns:
            List of CRUDTestResult (one per scenario).
        """
        results: list[CRUDTestResult] = []
        for idx, scenario in enumerate(self.scenarios):
            label = scenario.description or f"scenario[{idx}]"
            if test_instance is not None and hasattr(test_instance, "subTest"):
                with test_instance.subTest(scenario=label):
                    result = self._run_one(client, scenario, label)
                    results.append(result)
            else:
                result = self._run_one(client, scenario, label)
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_one(
        self,
        client: Client,
        scenario: CRUDScenario,
        label: str,
    ) -> CRUDTestResult:
        """Run a single scenario inside a savepoint."""
        sid = transaction.savepoint()
        try:
            return self._execute(client, scenario, label)
        finally:
            transaction.savepoint_rollback(sid)

    def _execute(
        self,
        client: Client,
        scenario: CRUDScenario,
        label: str,
    ) -> CRUDTestResult:
        """Execute request, check status and body, return result."""
        # Optional pre-request setup
        if callable(scenario.setup):
            scenario.setup()

        # Authenticate if a user is provided
        if scenario.user is not None:
            if hasattr(client, "force_authenticate"):
                client.force_authenticate(scenario.user)
            else:
                client.force_login(scenario.user)

        response = self._send_request(client, scenario)
        status = response.status_code

        # Parse response body
        body: Any = None
        if response.content:
            try:
                body = orjson.loads(response.content)
            except (orjson.JSONDecodeError, ValueError):
                body = response.content.decode("utf-8", errors="replace")

        # Assert status code
        if status != scenario.expected_status:
            msg = (
                f"[{label}] Expected status {scenario.expected_status}, "
                f"got {status}. Response: {body}"
            )
            return self._fail(scenario, status, body, msg)

        # Assert expected body keys/values
        if scenario.expected_body is not None:
            if not isinstance(body, dict):
                msg = (
                    f"[{label}] Expected response body to be a dict, "
                    f"got {type(body).__name__}: {body}"
                )
                return self._fail(scenario, status, body, msg)

            for key, expected_val in scenario.expected_body.items():
                actual_val = body.get(key, _MISSING)
                if actual_val is _MISSING:
                    msg = (
                        f"[{label}] Expected key '{key}' in response body. "
                        f"Got keys: {list(body.keys())}"
                    )
                    return self._fail(scenario, status, body, msg)
                if actual_val != expected_val:
                    msg = (
                        f"[{label}] body['{key}']: expected {expected_val!r}, "
                        f"got {actual_val!r}"
                    )
                    return self._fail(scenario, status, body, msg)

        # Clear auth for next scenario
        if scenario.user is not None:
            if hasattr(client, "logout"):
                client.logout()

        return CRUDTestResult(
            scenario=scenario,
            passed=True,
            status_code=status,
            response_body=body,
        )

    @staticmethod
    def _send_request(client: Client, scenario: CRUDScenario) -> HttpResponse:
        """Dispatch the HTTP request based on scenario method."""
        method = scenario.method.upper()
        kwargs: dict[str, Any] = {}

        if scenario.headers:
            for key, value in scenario.headers.items():
                header_key = key if key.startswith("HTTP_") else f"HTTP_{key.upper().replace('-', '_')}"
                kwargs[header_key] = value

        if method == "GET":
            return client.get(scenario.url, data=scenario.data, **kwargs)
        if method == "POST":
            body = orjson.dumps(scenario.data).decode() if scenario.data is not None else None
            return client.post(
                scenario.url, data=body, content_type="application/json", **kwargs
            )
        if method == "PUT":
            body = orjson.dumps(scenario.data).decode() if scenario.data is not None else None
            return client.put(
                scenario.url, data=body, content_type="application/json", **kwargs
            )
        if method == "PATCH":
            body = orjson.dumps(scenario.data).decode() if scenario.data is not None else None
            return client.patch(
                scenario.url, data=body, content_type="application/json", **kwargs
            )
        if method == "DELETE":
            return client.delete(scenario.url, **kwargs)
        raise ValueError(f"Unsupported HTTP method: {method}")

    @staticmethod
    def _fail(
        scenario: CRUDScenario,
        status: int | None,
        body: Any,
        message: str,
    ) -> CRUDTestResult:
        """Record failure and raise AssertionError."""
        result = CRUDTestResult(
            scenario=scenario,
            passed=False,
            status_code=status,
            response_body=body,
            error=message,
        )
        raise AssertionError(message)


# Sentinel for missing keys
_MISSING = object()


# ---------------------------------------------------------------------------
# Auto-generation of common CRUD scenarios
# ---------------------------------------------------------------------------


def generate_crud_scenarios(
    viewset_class: type[APIViewSet],
    *,
    base_url: str = "",
    list_url: str | None = None,
    detail_url: str | None = None,
    create_data: dict[str, Any] | None = None,
    update_data: dict[str, Any] | None = None,
    user: Any | None = None,
    setup: Any | None = None,
) -> list[CRUDScenario]:
    """Auto-generate happy-path and error scenarios for a ViewSet.

    Inspects the ViewSet's ``_views`` to determine which CRUD operations are
    declared, then builds standard scenarios for each.

    Args:
        viewset_class: The APIViewSet subclass to inspect.
        base_url: URL prefix for all endpoints (e.g. ``"/api/items"``).
        list_url: Override URL for list/create (defaults to ``base_url + "/"``.
        detail_url: Override URL for read/update/delete (defaults to
            ``base_url + "/1"``).  Should include the lookup value.
        create_data: Request body for create scenarios.
        update_data: Request body for update scenarios.
        user: Default user for authenticated scenarios.
        setup: Default setup callable for all scenarios.

    Returns:
        List of CRUDScenario instances.
    """
    if list_url is None:
        list_url = base_url.rstrip("/") + "/"
    if detail_url is None:
        detail_url = base_url.rstrip("/") + "/1"

    scenarios: list[CRUDScenario] = []

    # Inspect views declared on the viewset
    views = viewset_class._views

    for attr_name, view in views.items():
        if isinstance(view, ListView):
            # Happy path: list returns 200
            scenarios.append(
                CRUDScenario(
                    method="GET",
                    url=list_url,
                    expected_status=200,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: list returns 200",
                )
            )

        elif isinstance(view, CreateView):
            # Happy path: create returns 201
            if create_data is not None:
                scenarios.append(
                    CRUDScenario(
                        method="POST",
                        url=list_url,
                        data=create_data,
                        expected_status=201,
                        user=user,
                        setup=setup,
                        description=f"{attr_name}: create returns 201",
                    )
                )
            # Error: create with empty body returns 422
            scenarios.append(
                CRUDScenario(
                    method="POST",
                    url=list_url,
                    data={},
                    expected_status=422,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: create empty body returns 422",
                )
            )

        elif isinstance(view, ReadView):
            # Happy path: read existing returns 200
            scenarios.append(
                CRUDScenario(
                    method="GET",
                    url=detail_url,
                    expected_status=200,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: read returns 200",
                )
            )
            # Error: read non-existent returns 404
            nonexistent_url = base_url.rstrip("/") + "/999999"
            scenarios.append(
                CRUDScenario(
                    method="GET",
                    url=nonexistent_url,
                    expected_status=404,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: read non-existent returns 404",
                )
            )

        elif isinstance(view, (UpdateView, PatchView)):
            method = "PATCH" if isinstance(view, PatchView) else "PUT"
            if update_data is not None:
                scenarios.append(
                    CRUDScenario(
                        method=method,
                        url=detail_url,
                        data=update_data,
                        expected_status=200,
                        user=user,
                        setup=setup,
                        description=f"{attr_name}: update returns 200",
                    )
                )
            # Error: update non-existent returns 404
            nonexistent_url = base_url.rstrip("/") + "/999999"
            scenarios.append(
                CRUDScenario(
                    method=method,
                    url=nonexistent_url,
                    data=update_data or {},
                    expected_status=404,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: update non-existent returns 404",
                )
            )

        elif isinstance(view, DeleteView):
            # Happy path: delete existing returns 204
            scenarios.append(
                CRUDScenario(
                    method="DELETE",
                    url=detail_url,
                    expected_status=204,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: delete returns 204",
                )
            )
            # Error: delete non-existent returns 404
            nonexistent_url = base_url.rstrip("/") + "/999999"
            scenarios.append(
                CRUDScenario(
                    method="DELETE",
                    url=nonexistent_url,
                    expected_status=404,
                    user=user,
                    setup=setup,
                    description=f"{attr_name}: delete non-existent returns 404",
                )
            )

    return scenarios
