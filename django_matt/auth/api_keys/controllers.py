# file-length-max: 550
"""
API Key management controllers.

Provides endpoints for:
- Creating, listing, updating, deleting API keys
- Rotating keys
- Usage analytics
- Data export
"""

import csv
import io
from datetime import timedelta

from django.http import HttpResponse, JsonResponse
from django.utils import timezone

import orjson

from django_matt.core.controller import APIController
from django_matt.core.router import delete, get, post, put

from .schemas import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyUpdateRequest,
    ExportRequest,
    UsageRecord,
    UsageResponse,
    UsageSummary,
)
from .utils import acreate_api_key, arotate_api_key


class APIKeyController(APIController):
    """
    Controller for managing API keys.

    Provides full CRUD operations plus:
    - Key rotation
    - Usage analytics
    - Data export

    All endpoints require JWT authentication (user must be logged in
    to manage their API keys).

    Usage:
        from django_matt.auth.api_keys import APIKeyController

        api.register_controller(APIKeyController, prefix="/api/keys")
    """

    prefix = ""
    tags = ["API Keys"]

    @post("")
    async def create_key(self, request) -> JsonResponse:
        """
        Create a new API key.

        The full key is only returned once - save it securely!
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = APIKeyCreateRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        # Create the key
        api_key, raw_key = await acreate_api_key(
            user=request.user,
            name=data.name,
            is_test=data.is_test,
            scopes=data.scopes,
            expires_at=data.expires_at,
            allowed_ips=data.allowed_ips,
        )

        # Return with full key (only time it's shown)
        response_data = APIKeyCreatedResponse(
            id=api_key.pk,
            name=api_key.name,
            prefix=api_key.prefix,
            key=raw_key,
            is_test=api_key.is_test,
            is_active=api_key.is_active,
            plan=api_key.plan,
            scopes=api_key.scopes,
            rate_limit=api_key.rate_limit,
            rate_limit_period=api_key.rate_limit_period,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            total_requests=api_key.total_requests,
            allowed_ips=api_key.allowed_ips,
        )

        return JsonResponse(response_data.model_dump(mode="json"), status=201)

    @get("")
    async def list_keys(self, request) -> JsonResponse:
        """List all API keys for the current user."""
        from .models import APIKey

        keys = APIKey.objects.filter(user=request.user).order_by("-created_at")
        items = []

        async for key in keys:
            items.append(
                APIKeyResponse(
                    id=key.pk,
                    name=key.name,
                    prefix=key.prefix,
                    is_test=key.is_test,
                    is_active=key.is_active,
                    plan=key.plan,
                    scopes=key.scopes,
                    rate_limit=key.rate_limit,
                    rate_limit_period=key.rate_limit_period,
                    expires_at=key.expires_at,
                    created_at=key.created_at,
                    last_used_at=key.last_used_at,
                    total_requests=key.total_requests,
                    allowed_ips=key.allowed_ips,
                )
            )

        response = APIKeyListResponse(items=items, total=len(items))
        return JsonResponse(response.model_dump(mode="json"))

    @get("{key_id}")
    async def get_key(self, request, key_id: int) -> JsonResponse:
        """Get details of a specific API key."""
        from .models import APIKey

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        response = APIKeyResponse(
            id=api_key.pk,
            name=api_key.name,
            prefix=api_key.prefix,
            is_test=api_key.is_test,
            is_active=api_key.is_active,
            plan=api_key.plan,
            scopes=api_key.scopes,
            rate_limit=api_key.rate_limit,
            rate_limit_period=api_key.rate_limit_period,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            total_requests=api_key.total_requests,
            allowed_ips=api_key.allowed_ips,
        )

        return JsonResponse(response.model_dump(mode="json"))

    @put("{key_id}")
    async def update_key(self, request, key_id: int) -> JsonResponse:
        """Update an API key."""
        from .models import APIKey

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        try:
            body = orjson.loads(request.body) if request.body else {}
            data = APIKeyUpdateRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        # Update fields
        if data.name is not None:
            api_key.name = data.name
        if data.scopes is not None:
            api_key.scopes = data.scopes
        if data.expires_at is not None:
            api_key.expires_at = data.expires_at
        if data.allowed_ips is not None:
            api_key.allowed_ips = data.allowed_ips
        if data.is_active is not None:
            api_key.is_active = data.is_active

        await api_key.asave()

        response = APIKeyResponse(
            id=api_key.pk,
            name=api_key.name,
            prefix=api_key.prefix,
            is_test=api_key.is_test,
            is_active=api_key.is_active,
            plan=api_key.plan,
            scopes=api_key.scopes,
            rate_limit=api_key.rate_limit,
            rate_limit_period=api_key.rate_limit_period,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            total_requests=api_key.total_requests,
            allowed_ips=api_key.allowed_ips,
        )

        return JsonResponse(response.model_dump(mode="json"))

    @delete("{key_id}")
    async def delete_key(self, request, key_id: int) -> JsonResponse:
        """Delete (revoke) an API key."""
        from .models import APIKey

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        await api_key.adelete()

        return JsonResponse({"detail": "API key deleted"})

    @post("{key_id}/rotate")
    async def rotate_key(self, request, key_id: int) -> JsonResponse:
        """
        Rotate an API key.

        Creates a new key with the same settings and revokes the old one.
        The new full key is returned only once - save it securely!
        """
        from .models import APIKey

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        # Rotate the key
        new_key, raw_key = await arotate_api_key(api_key)

        response = APIKeyCreatedResponse(
            id=new_key.pk,
            name=new_key.name,
            prefix=new_key.prefix,
            key=raw_key,
            is_test=new_key.is_test,
            is_active=new_key.is_active,
            plan=new_key.plan,
            scopes=new_key.scopes,
            rate_limit=new_key.rate_limit,
            rate_limit_period=new_key.rate_limit_period,
            expires_at=new_key.expires_at,
            created_at=new_key.created_at,
            last_used_at=new_key.last_used_at,
            total_requests=new_key.total_requests,
            allowed_ips=new_key.allowed_ips,
        )

        return JsonResponse(response.model_dump(mode="json"), status=201)

    @post("{key_id}/revoke")
    async def revoke_key(self, request, key_id: int) -> JsonResponse:
        """Revoke an API key (soft delete - can be reactivated)."""
        from .models import APIKey

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        await api_key.arevoke()

        return JsonResponse({"detail": "API key revoked"})

    @get("{key_id}/usage")
    async def get_usage(self, request, key_id: int) -> JsonResponse:
        """
        Get usage analytics for an API key.

        Query params:
        - days: Number of days to look back (default: 30)
        """
        from .models import APIKey, APIKeyUsage

        try:
            api_key = await APIKey.objects.aget(pk=key_id, user=request.user)
        except APIKey.DoesNotExist:
            return JsonResponse(
                {"detail": "API key not found", "code": "not_found"},
                status=404,
            )

        # Get time range
        days = int(request.GET.get("days", 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get usage records
        records = []
        total_requests = 0
        total_errors = 0
        total_response_time = 0
        total_bytes_sent = 0
        total_bytes_received = 0
        endpoint_totals = {}

        usage_qs = APIKeyUsage.objects.filter(
            api_key=api_key,
            hour__gte=start_date,
            hour__lte=end_date,
        ).order_by("hour")

        async for usage in usage_qs:
            records.append(
                UsageRecord(
                    hour=usage.hour,
                    request_count=usage.request_count,
                    error_count=usage.error_count,
                    avg_response_time_ms=usage.avg_response_time_ms,
                    max_response_time_ms=usage.max_response_time_ms,
                    bytes_sent=usage.bytes_sent,
                    bytes_received=usage.bytes_received,
                    endpoint_counts=usage.endpoint_counts,
                )
            )
            total_requests += usage.request_count
            total_errors += usage.error_count
            total_response_time += usage.avg_response_time_ms * usage.request_count
            total_bytes_sent += usage.bytes_sent
            total_bytes_received += usage.bytes_received

            for endpoint, count in (usage.endpoint_counts or {}).items():
                endpoint_totals[endpoint] = endpoint_totals.get(endpoint, 0) + count

        # Calculate summary
        avg_response_time = total_response_time / total_requests if total_requests > 0 else 0
        error_rate = total_errors / total_requests if total_requests > 0 else 0

        # Top endpoints
        top_endpoints = sorted(
            [{"endpoint": k, "count": v} for k, v in endpoint_totals.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        # Requests by hour (for charts)
        requests_by_hour = [{"hour": r.hour.isoformat(), "count": r.request_count} for r in records]

        summary = UsageSummary(
            period_start=start_date,
            period_end=end_date,
            total_requests=total_requests,
            total_errors=total_errors,
            error_rate=error_rate,
            avg_response_time_ms=avg_response_time,
            total_bytes_sent=total_bytes_sent,
            total_bytes_received=total_bytes_received,
            top_endpoints=top_endpoints,
            requests_by_hour=requests_by_hour,
        )

        response = UsageResponse(
            api_key_id=api_key.pk,
            api_key_name=api_key.name,
            summary=summary,
            records=records,
        )

        return JsonResponse(response.model_dump(mode="json"))

    @post("export")
    async def export_data(self, request) -> HttpResponse:
        """
        Export API keys and usage data.

        Supports JSON and CSV formats.
        """
        from .models import APIKey, APIKeyUsage

        try:
            body = orjson.loads(request.body) if request.body else {}
            data = ExportRequest.model_validate(body)
        except (orjson.JSONDecodeError, Exception):
            data = ExportRequest()

        # Get all keys for user
        keys = []
        async for key in APIKey.objects.filter(user=request.user):
            key_data = {
                "id": key.pk,
                "name": key.name,
                "prefix": key.prefix,
                "is_test": key.is_test,
                "is_active": key.is_active,
                "plan": key.plan,
                "scopes": key.scopes,
                "rate_limit": key.rate_limit,
                "created_at": key.created_at.isoformat(),
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "total_requests": key.total_requests,
            }

            # Include usage if requested
            if data.include_usage:
                usage_records = []
                usage_qs = APIKeyUsage.objects.filter(api_key=key)

                if data.start_date:
                    usage_qs = usage_qs.filter(hour__gte=data.start_date)
                if data.end_date:
                    usage_qs = usage_qs.filter(hour__lte=data.end_date)

                async for usage in usage_qs.order_by("hour"):
                    usage_records.append(
                        {
                            "hour": usage.hour.isoformat(),
                            "request_count": usage.request_count,
                            "error_count": usage.error_count,
                            "avg_response_time_ms": usage.avg_response_time_ms,
                        }
                    )

                key_data["usage"] = usage_records

            keys.append(key_data)

        # Format response
        if data.format == "csv":
            output = io.StringIO()
            if keys:
                # Flatten for CSV
                writer = csv.writer(output)
                writer.writerow(
                    [
                        "id",
                        "name",
                        "prefix",
                        "is_test",
                        "is_active",
                        "plan",
                        "created_at",
                        "total_requests",
                    ]
                )
                for key in keys:
                    writer.writerow(
                        [
                            key["id"],
                            key["name"],
                            key["prefix"],
                            key["is_test"],
                            key["is_active"],
                            key["plan"],
                            key["created_at"],
                            key["total_requests"],
                        ]
                    )

            response = HttpResponse(output.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="api_keys_export.csv"'
            return response

        # Default to JSON
        export_data = {
            "exported_at": timezone.now().isoformat(),
            "record_count": len(keys),
            "api_keys": keys,
        }

        response = HttpResponse(
            orjson.dumps(export_data, option=orjson.OPT_INDENT_2).decode(),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="api_keys_export.json"'
        return response
