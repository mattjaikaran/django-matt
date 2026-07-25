"""Controllers for {{ project_name }}."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_matt.auth import jwt_required

from .models import AuditEntry, FeatureFlag
from .schemas import (
    AuditEntrySchema,
    FeatureFlagCreate,
    FeatureFlagSchema,
    FeatureFlagUpdate,
)


async def health(request) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
@jwt_required
async def list_audit_entries(request) -> JsonResponse:
    """List audit log entries with optional filtering."""
    action = request.GET.get("action")
    resource_type = request.GET.get("resource_type")

    qs = AuditEntry.objects.all()
    if action:
        qs = qs.filter(action=action)
    if resource_type:
        qs = qs.filter(resource_type=resource_type)

    entries = [
        AuditEntrySchema.model_validate(e).model_dump(mode="json")
        async for e in qs[:100]
    ]
    return JsonResponse({"entries": entries})


@require_http_methods(["GET"])
@jwt_required
async def list_flags(request) -> JsonResponse:
    flags = [
        FeatureFlagSchema.model_validate(f).model_dump(mode="json")
        async for f in FeatureFlag.objects.all()
    ]
    return JsonResponse({"flags": flags})


@require_http_methods(["POST"])
@jwt_required
async def create_flag(request) -> JsonResponse:
    import orjson

    data = FeatureFlagCreate.model_validate(orjson.loads(request.body))
    flag = await FeatureFlag.objects.acreate(
        name=data.name,
        description=data.description,
        enabled=data.enabled,
        rollout_percent=data.rollout_percent,
    )
    return JsonResponse(
        FeatureFlagSchema.model_validate(flag).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["PATCH"])
@jwt_required
async def update_flag(request, flag_id: int) -> JsonResponse:
    import orjson

    try:
        flag = await FeatureFlag.objects.aget(pk=flag_id)
    except FeatureFlag.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    data = FeatureFlagUpdate.model_validate(orjson.loads(request.body))
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(flag, field, value)
    await flag.asave()
    return JsonResponse(
        FeatureFlagSchema.model_validate(flag).model_dump(mode="json"),
    )
