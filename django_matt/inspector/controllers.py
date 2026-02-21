"""
REST API controllers for the Request Inspector.

Provides programmatic access to captured requests.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.http import HttpRequest, JsonResponse

import orjson

from django_matt.core.controller import APIController
from django_matt.core.router import delete, get, post

from .export import export_request
from .schemas import (
    CapturedRequestListSchema,
    CapturedRequestSchema,
    CaptureStatusSchema,
    ErrorResponseSchema,
    ExportResponseSchema,
    InspectorStatsSchema,
    MessageResponseSchema,
)
from .storage import CapturedRequest, MemoryStorage, RedisStorage, get_storage

if TYPE_CHECKING:
    pass


def _request_to_schema(request: CapturedRequest) -> dict:
    """Convert a CapturedRequest to a schema dict."""
    return CapturedRequestSchema(
        id=request.id,
        timestamp=request.timestamp,
        timestamp_formatted=datetime.fromtimestamp(request.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
        method=request.method,
        path=request.path,
        full_url=request.full_url,
        query_string=request.query_string,
        request_headers=request.request_headers,
        request_body=request.request_body,
        request_content_type=request.request_content_type,
        response_status=request.response_status,
        response_headers=request.response_headers,
        response_body=request.response_body,
        response_content_type=request.response_content_type,
        duration_ms=request.duration_ms,
        client_ip=request.client_ip,
        user_id=request.user_id,
        user_email=request.user_email,
        exception=request.exception,
        traceback=request.traceback,
        status_category=request.status_category,
        is_success=request.is_success,
        is_error=request.is_client_error or request.is_server_error,
    ).model_dump()


class InspectorController(APIController):
    """
    Request Inspector API controller.

    Provides REST endpoints for accessing and managing captured requests.

    Endpoints:
        GET    /inspector/requests              - List captured requests
        GET    /inspector/requests/{id}         - Get request detail
        DELETE /inspector/requests/{id}         - Delete a request (not supported by storage)
        DELETE /inspector/requests              - Clear all requests
        POST   /inspector/requests/{id}/export  - Export request in various formats
        GET    /inspector/stats                 - Get inspector statistics
        GET    /inspector/status                - Get capture status
        POST   /inspector/pause                 - Pause request capture
        POST   /inspector/resume                - Resume request capture
    """

    prefix = "inspector"
    tags = ["Request Inspector"]

    @get("")
    async def list_requests(self, request: HttpRequest) -> JsonResponse:
        """
        List captured requests with filtering and pagination.

        Query params:
            - page: Page number (default: 1)
            - page_size: Items per page (default: 50, max: 100)
            - method: Filter by HTTP method (GET, POST, etc.)
            - status: Filter by exact status code
            - status_min: Filter by minimum status code
            - status_max: Filter by maximum status code (exclusive)
            - path: Filter by path contains
            - since: Filter by timestamp >= (unix timestamp)
            - until: Filter by timestamp <= (unix timestamp)
        """
        storage = get_storage()

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = min(int(request.GET.get("page_size", 50)), 100)
        offset = (page - 1) * page_size

        # Filters
        method = request.GET.get("method")
        status = request.GET.get("status")
        status_min = request.GET.get("status_min")
        status_max = request.GET.get("status_max")
        path_contains = request.GET.get("path")
        since = request.GET.get("since")
        until = request.GET.get("until")

        # Convert filter values
        if status:
            status = int(status)
        if status_min:
            status_min = int(status_min)
        if status_max:
            status_max = int(status_max)
        if since:
            since = float(since)
        if until:
            until = float(until)

        # Get requests
        requests_list = storage.list(
            limit=page_size + 1,  # Get one extra to check if there's a next page
            offset=offset,
            method=method,
            status=status,
            status_min=status_min,
            status_max=status_max,
            path_contains=path_contains,
            since=since,
            until=until,
        )

        # Check for next page
        has_next = len(requests_list) > page_size
        if has_next:
            requests_list = requests_list[:page_size]

        total = storage.count()

        response = CapturedRequestListSchema(
            items=[_request_to_schema(r) for r in requests_list],
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
            has_prev=page > 1,
        )

        return JsonResponse(response.model_dump())

    @get("{request_id}")
    async def get_request(self, request: HttpRequest, request_id: str) -> JsonResponse:
        """Get a specific captured request by ID."""
        storage = get_storage()
        captured = storage.get(request_id)

        if not captured:
            return JsonResponse(
                ErrorResponseSchema(detail="Request not found", code="not_found").model_dump(),
                status=404,
            )

        return JsonResponse(_request_to_schema(captured))

    @delete("{request_id}")
    async def delete_request(self, request: HttpRequest, request_id: str) -> JsonResponse:
        """
        Delete a specific captured request.

        Note: Individual deletion may not be supported by all storage backends.
        """
        storage = get_storage()
        captured = storage.get(request_id)

        if not captured:
            return JsonResponse(
                ErrorResponseSchema(detail="Request not found", code="not_found").model_dump(),
                status=404,
            )

        # Note: Current storage implementations don't support individual deletion
        # This would need to be added to the storage interface
        return JsonResponse(
            ErrorResponseSchema(
                detail="Individual deletion not supported. Use DELETE /inspector to clear all.",
                code="not_supported",
            ).model_dump(),
            status=501,
        )

    @delete("")
    async def clear_requests(self, request: HttpRequest) -> JsonResponse:
        """Clear all captured requests."""
        storage = get_storage()
        count = storage.clear()

        return JsonResponse(
            MessageResponseSchema(message=f"Cleared {count} requests", success=True).model_dump()
        )

    @post("{request_id}/export")
    async def export_request_endpoint(self, request: HttpRequest, request_id: str) -> JsonResponse:
        """
        Export a captured request in various formats.

        Body:
            - format: Export format (curl, httpie, python, fetch)
            - include_response: Whether to include expected response as comment
        """
        storage = get_storage()
        captured = storage.get(request_id)

        if not captured:
            return JsonResponse(
                ErrorResponseSchema(detail="Request not found", code="not_found").model_dump(),
                status=404,
            )

        # Parse body
        try:
            body = orjson.loads(request.body) if request.body else {}
        except orjson.JSONDecodeError:
            body = {}

        export_format = body.get("format", "curl")
        include_response = body.get("include_response", False)

        try:
            content = export_request(
                captured, format=export_format, include_response=include_response
            )
        except ValueError as e:
            return JsonResponse(
                ErrorResponseSchema(detail=str(e), code="invalid_format").model_dump(),
                status=400,
            )

        # Determine content type based on format
        content_types = {
            "curl": "text/x-shellscript",
            "httpie": "text/x-shellscript",
            "python": "text/x-python",
            "fetch": "text/javascript",
        }

        response = ExportResponseSchema(
            format=export_format,
            content=content,
            content_type=content_types.get(export_format, "text/plain"),
        )

        return JsonResponse(response.model_dump())

    @get("stats")
    async def get_stats(self, request: HttpRequest) -> JsonResponse:
        """Get inspector statistics."""
        storage = get_storage()

        # Get all requests for stats calculation
        all_requests = storage.list(limit=1000)

        total = len(all_requests)
        success_count = sum(1 for r in all_requests if r.is_success)
        error_count = sum(1 for r in all_requests if r.is_client_error or r.is_server_error)

        durations = [r.duration_ms for r in all_requests if r.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0

        # Count methods
        methods: dict[str, int] = {}
        for r in all_requests:
            methods[r.method] = methods.get(r.method, 0) + 1

        # Count status codes
        status_codes: dict[str, int] = {}
        for r in all_requests:
            code = str(r.response_status)
            status_codes[code] = status_codes.get(code, 0) + 1

        response = InspectorStatsSchema(
            total_requests=total,
            success_count=success_count,
            error_count=error_count,
            avg_duration_ms=round(avg_duration, 2),
            max_duration_ms=round(max_duration, 2),
            methods=methods,
            status_codes=status_codes,
            is_capturing=storage.is_capturing(),
        )

        return JsonResponse(response.model_dump())

    @get("status")
    async def get_status(self, request: HttpRequest) -> JsonResponse:
        """Get capture status and storage info."""
        storage = get_storage()

        # Determine storage type
        if isinstance(storage, RedisStorage):
            storage_type = "redis"
        elif isinstance(storage, MemoryStorage):
            storage_type = "memory"
        else:
            storage_type = "unknown"

        response = CaptureStatusSchema(
            is_capturing=storage.is_capturing(),
            storage_type=storage_type,
            request_count=storage.count(),
            max_requests=getattr(storage, "max_requests", 100),
        )

        return JsonResponse(response.model_dump())

    @post("pause")
    async def pause_capture(self, request: HttpRequest) -> JsonResponse:
        """Pause request capture."""
        storage = get_storage()
        storage.pause_capture()

        return JsonResponse(
            MessageResponseSchema(message="Request capture paused", success=True).model_dump()
        )

    @post("resume")
    async def resume_capture(self, request: HttpRequest) -> JsonResponse:
        """Resume request capture."""
        storage = get_storage()
        storage.resume_capture()

        return JsonResponse(
            MessageResponseSchema(message="Request capture resumed", success=True).model_dump()
        )


__all__ = ["InspectorController"]
