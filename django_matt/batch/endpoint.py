"""Facebook Graph API-style HTTP batch endpoint."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory
from django.urls import resolve

import orjson
from pydantic import ValidationError

from django_matt.batch.request import BatchPayload, BatchRequest, BatchResponse
from django_matt.batch.resolver import (
    CyclicDependencyError,
    MissingDependencyError,
    interpolate_value,
    topological_sort,
)

if TYPE_CHECKING:
    from django_matt.api import DjangoMattAPI

logger = logging.getLogger("django_matt.batch")

_factory = RequestFactory()


class BatchEndpoint:
    """Facebook-style HTTP batch request handler.

    Accepts an array of sub-requests, resolves dependencies topologically,
    executes independent requests in parallel via ``asyncio.gather``, and
    returns all responses in order.

    Usage::

        from django_matt.batch import BatchEndpoint

        api = DjangoMattAPI()
        batch = BatchEndpoint(api, path="/batch", max_requests=50)
        api.register_batch(batch)
    """

    def __init__(
        self,
        api: DjangoMattAPI,
        path: str = "/batch",
        max_requests: int = 50,
        timeout_per_request: float = 30.0,
        allow_dependencies: bool = True,
    ):
        self.api = api
        self.path = path.rstrip("/")
        self.max_requests = max_requests
        self.timeout_per_request = timeout_per_request
        self.allow_dependencies = allow_dependencies

    async def handle(self, request: HttpRequest) -> JsonResponse:
        """Handle an incoming batch request."""
        if request.method != "POST":
            return JsonResponse({"detail": "Batch endpoint only accepts POST"}, status=405)

        # Parse payload
        try:
            raw = orjson.loads(request.body)
        except (orjson.JSONDecodeError, ValueError):
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        # Accept both {requests: [...]} and bare [...]
        if isinstance(raw, list):
            raw = {"requests": raw}

        try:
            payload = BatchPayload(**raw)
        except ValidationError as e:
            return JsonResponse({"detail": "Validation error", "errors": e.errors()}, status=422)

        if len(payload.requests) > self.max_requests:
            return JsonResponse(
                {
                    "detail": f"Too many requests (max {self.max_requests})",
                },
                status=400,
            )

        # Check dependencies enabled
        has_deps = any(r.depends_on for r in payload.requests)
        if has_deps and not self.allow_dependencies:
            return JsonResponse(
                {"detail": "Dependencies are disabled on this batch endpoint"},
                status=400,
            )

        # Resolve execution order
        try:
            waves = topological_sort(payload.requests)
        except CyclicDependencyError as e:
            return JsonResponse({"detail": str(e)}, status=400)
        except MissingDependencyError as e:
            return JsonResponse({"detail": str(e)}, status=400)

        # Execute waves
        results: dict[str, Any] = {}  # name -> response body
        responses: list[BatchResponse | None] = [None] * len(payload.requests)

        if payload.atomic:
            from django.db import transaction

            async with transaction.atomic():
                await self._execute_waves(waves, payload.requests, request, results, responses)
        else:
            await self._execute_waves(waves, payload.requests, request, results, responses)

        # Build ordered response list
        output = []
        for resp in responses:
            if resp is None:
                output.append(
                    BatchResponse(status=500, error="Request was not executed").model_dump()
                )
            else:
                output.append(resp.model_dump(exclude_none=True))

        return JsonResponse(output, safe=False)

    async def _execute_waves(
        self,
        waves: list[list[int]],
        requests: list[BatchRequest],
        parent_request: HttpRequest,
        results: dict[str, Any],
        responses: list[BatchResponse | None],
    ) -> None:
        """Execute request waves sequentially, requests within a wave in parallel."""
        for wave in waves:
            if len(wave) == 1:
                idx = wave[0]
                responses[idx] = await self._execute_one(
                    idx, requests[idx], parent_request, results
                )
            else:
                wave_results = await asyncio.gather(
                    *(
                        self._execute_one(idx, requests[idx], parent_request, results)
                        for idx in wave
                    ),
                    return_exceptions=True,
                )
                for idx, result in zip(wave, wave_results):
                    if isinstance(result, BaseException):
                        responses[idx] = BatchResponse(
                            status=500,
                            error=str(result),
                            name=requests[idx].name,
                        )
                    else:
                        responses[idx] = result

            # After each wave, store named results for dependency interpolation
            for idx in wave:
                resp = responses[idx]
                if resp and requests[idx].name and resp.status < 400:
                    results[requests[idx].name] = resp.body

    async def _execute_one(
        self,
        idx: int,
        batch_req: BatchRequest,
        parent_request: HttpRequest,
        results: dict[str, Any],
    ) -> BatchResponse:
        """Execute a single sub-request."""
        try:
            # Interpolate dependencies into path and body
            path = interpolate_value(batch_req.path, results)
            body = (
                interpolate_value(batch_req.body, results) if batch_req.body is not None else None
            )

            # Build internal Django request
            sub_request = self._build_request(
                batch_req.method, path, body, batch_req.headers, parent_request
            )

            # Resolve URL and dispatch
            match = resolve(path)
            view = match.func
            kwargs = match.kwargs

            response = await self._call_view(view, sub_request, **kwargs)

            # Extract response data
            status = response.status_code
            resp_body: Any = None
            if hasattr(response, "content") and response.content:
                try:
                    resp_body = orjson.loads(response.content)
                except (orjson.JSONDecodeError, ValueError):
                    resp_body = response.content.decode("utf-8", errors="replace")

            resp_headers = dict(response.items())

            return BatchResponse(
                status=status,
                body=resp_body,
                headers=resp_headers,
                name=batch_req.name,
            )

        except Exception as e:
            logger.exception("Batch sub-request %d failed: %s", idx, e)
            return BatchResponse(
                status=500,
                error=str(e),
                name=batch_req.name,
            )

    @staticmethod
    def _build_request(
        method: str,
        path: str,
        body: Any,
        headers: dict[str, str],
        parent_request: HttpRequest,
    ) -> HttpRequest:
        """Build a Django HttpRequest for an internal sub-request."""
        method_lower = method.lower()
        factory_method = getattr(_factory, method_lower, _factory.get)

        kwargs: dict[str, Any] = {}
        if body is not None and method_lower in ("post", "put", "patch"):
            kwargs["data"] = orjson.dumps(body)
            kwargs["content_type"] = "application/json"

        sub_request = factory_method(path, **kwargs)

        # Carry over auth from parent request
        if hasattr(parent_request, "user"):
            sub_request.user = parent_request.user
        if hasattr(parent_request, "auth"):
            sub_request.auth = parent_request.auth

        # Apply custom headers (HTTP_ prefix convention)
        for key, value in headers.items():
            header_key = f"HTTP_{key.upper().replace('-', '_')}"
            sub_request.META[header_key] = value

        return sub_request

    @staticmethod
    async def _call_view(view: Any, request: HttpRequest, **kwargs: Any) -> Any:
        """Call a view function, handling both sync and async views."""
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(view):
            return await view(request, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: view(request, **kwargs))
