"""
Feature flags REST API controllers.

Provides REST API endpoints for managing feature flags.

Usage:
    from django_matt.flags.controllers import FlagController

    api = MattAPI()
    api.register_controller(FlagController)
"""

import json
from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from django_matt.core.controller import APIController
from django_matt.core.router import delete, get, patch, post, put

from .context import FlagContext
from .schemas import (
    BulkEvaluationRequest,
    BulkEvaluationResponse,
    ErrorResponse,
    FeatureFlagCreate,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    FlagAuditLogListResponse,
    FlagEvaluationRequest,
    FlagEvaluationResponse,
    FlagOverrideCreate,
    FlagOverrideListResponse,
    FlagOverrideResponse,
    FlagStatsResponse,
    MessageResponse,
)


class FlagController(APIController):
    """
    Feature flags management controller.

    Provides CRUD operations for feature flags and overrides.

    Endpoints:
        GET    /flags                    - List all flags
        POST   /flags                    - Create a new flag
        GET    /flags/{key}              - Get flag by key
        PUT    /flags/{key}              - Update flag
        PATCH  /flags/{key}              - Partial update flag
        DELETE /flags/{key}              - Delete flag
        POST   /flags/{key}/enable       - Enable flag
        POST   /flags/{key}/disable      - Disable flag
        GET    /flags/{key}/overrides    - List flag overrides
        POST   /flags/{key}/overrides    - Create override
        DELETE /flags/{key}/overrides/{id} - Delete override
        POST   /flags/evaluate           - Evaluate a flag
        POST   /flags/evaluate/bulk      - Evaluate multiple flags
        GET    /flags/stats              - Get flag statistics
        GET    /flags/{key}/audit-logs   - Get audit logs for flag
    """

    prefix = "flags"
    tags = ["Feature Flags"]

    @get("")
    async def list_flags(self, request: HttpRequest) -> JsonResponse:
        """
        List all feature flags.

        Query params:
            - status: Filter by status (active, inactive, archived)
            - type: Filter by type (boolean, percentage, variant)
            - search: Search by key or name
            - page: Page number (default: 1)
            - page_size: Items per page (default: 20)
        """
        from .models import FeatureFlag

        # Build queryset
        qs = FeatureFlag.objects.all()

        # Filters
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        flag_type = request.GET.get("type")
        if flag_type:
            qs = qs.filter(flag_type=flag_type)

        search = request.GET.get("search")
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(key__icontains=search) | Q(name__icontains=search))

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        page_size = min(page_size, 100)  # Max 100 per page

        total = await qs.acount()
        offset = (page - 1) * page_size
        flags = [f async for f in qs.prefetch_related("overrides")[offset : offset + page_size]]

        # Build response
        items = []
        for flag in flags:
            items.append(
                FeatureFlagResponse(
                    id=str(flag.id),
                    key=flag.key,
                    name=flag.name,
                    description=flag.description,
                    flag_type=flag.flag_type,
                    status=flag.status,
                    enabled_by_default=flag.enabled_by_default,
                    rollout_percentage=flag.rollout_percentage,
                    variants=flag.variants,
                    targeting_rules=flag.targeting_rules,
                    scheduled_enable_at=flag.scheduled_enable_at,
                    scheduled_disable_at=flag.scheduled_disable_at,
                    metadata=flag.metadata,
                    created_at=flag.created_at,
                    updated_at=flag.updated_at,
                    created_by_id=str(flag.created_by_id) if flag.created_by_id else None,
                    is_active=flag.is_active,
                    override_count=await flag.overrides.acount(),
                ).model_dump()
            )

        response = FeatureFlagListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())

    @post("")
    async def create_flag(self, request: HttpRequest) -> JsonResponse:
        """Create a new feature flag."""
        from .models import FeatureFlag, FlagAuditLog

        try:
            body = json.loads(request.body) if request.body else {}
            data = FeatureFlagCreate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        # Check if key already exists
        if await FeatureFlag.objects.filter(key=data.key).aexists():
            return JsonResponse(
                ErrorResponse(
                    detail=f"Flag with key '{data.key}' already exists", code="key_exists"
                ).model_dump(),
                status=400,
            )

        # Create flag
        flag = FeatureFlag(
            key=data.key,
            name=data.name,
            description=data.description,
            flag_type=data.flag_type.value,
            status=data.status.value,
            enabled_by_default=data.enabled_by_default,
            rollout_percentage=data.rollout_percentage,
            variants=data.variants.model_dump() if data.variants else {},
            targeting_rules=[r.model_dump() for r in data.targeting_rules],
            scheduled_enable_at=data.scheduled_enable_at,
            scheduled_disable_at=data.scheduled_disable_at,
            metadata=data.metadata,
            created_by=request.user if request.user.is_authenticated else None,
        )
        await flag.asave()

        # Audit log
        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="create",
            new_values={"status": flag.status, "enabled_by_default": flag.enabled_by_default},
            user=request.user if request.user.is_authenticated else None,
        )

        response = FeatureFlagResponse(
            id=str(flag.id),
            key=flag.key,
            name=flag.name,
            description=flag.description,
            flag_type=flag.flag_type,
            status=flag.status,
            enabled_by_default=flag.enabled_by_default,
            rollout_percentage=flag.rollout_percentage,
            variants=flag.variants,
            targeting_rules=flag.targeting_rules,
            scheduled_enable_at=flag.scheduled_enable_at,
            scheduled_disable_at=flag.scheduled_disable_at,
            metadata=flag.metadata,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by_id=str(flag.created_by_id) if flag.created_by_id else None,
            is_active=flag.is_active,
            override_count=0,
        )
        return JsonResponse(response.model_dump(), status=201)

    @get("{key}")
    async def get_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Get a feature flag by key."""
        from .models import FeatureFlag

        try:
            flag = await FeatureFlag.objects.prefetch_related("overrides").aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        response = FeatureFlagResponse(
            id=str(flag.id),
            key=flag.key,
            name=flag.name,
            description=flag.description,
            flag_type=flag.flag_type,
            status=flag.status,
            enabled_by_default=flag.enabled_by_default,
            rollout_percentage=flag.rollout_percentage,
            variants=flag.variants,
            targeting_rules=flag.targeting_rules,
            scheduled_enable_at=flag.scheduled_enable_at,
            scheduled_disable_at=flag.scheduled_disable_at,
            metadata=flag.metadata,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by_id=str(flag.created_by_id) if flag.created_by_id else None,
            is_active=flag.is_active,
            override_count=await flag.overrides.acount(),
        )
        return JsonResponse(response.model_dump())

    @put("{key}")
    async def update_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Update a feature flag."""
        from .models import FeatureFlag, FlagAuditLog

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        try:
            body = json.loads(request.body) if request.body else {}
            data = FeatureFlagUpdate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        # Track changes
        old_values = {
            "status": flag.status,
            "enabled_by_default": flag.enabled_by_default,
            "rollout_percentage": flag.rollout_percentage,
        }

        # Update fields
        if data.name is not None:
            flag.name = data.name
        if data.description is not None:
            flag.description = data.description
        if data.flag_type is not None:
            flag.flag_type = data.flag_type.value
        if data.status is not None:
            flag.status = data.status.value
        if data.enabled_by_default is not None:
            flag.enabled_by_default = data.enabled_by_default
        if data.rollout_percentage is not None:
            flag.rollout_percentage = data.rollout_percentage
        if data.variants is not None:
            flag.variants = data.variants.model_dump()
        if data.targeting_rules is not None:
            flag.targeting_rules = [r.model_dump() for r in data.targeting_rules]
        if data.scheduled_enable_at is not None:
            flag.scheduled_enable_at = data.scheduled_enable_at
        if data.scheduled_disable_at is not None:
            flag.scheduled_disable_at = data.scheduled_disable_at
        if data.metadata is not None:
            flag.metadata = data.metadata

        await flag.asave()

        # Audit log
        new_values = {
            "status": flag.status,
            "enabled_by_default": flag.enabled_by_default,
            "rollout_percentage": flag.rollout_percentage,
        }
        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="update",
            old_values=old_values,
            new_values=new_values,
            user=request.user if request.user.is_authenticated else None,
        )

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(flag.key)

        response = FeatureFlagResponse(
            id=str(flag.id),
            key=flag.key,
            name=flag.name,
            description=flag.description,
            flag_type=flag.flag_type,
            status=flag.status,
            enabled_by_default=flag.enabled_by_default,
            rollout_percentage=flag.rollout_percentage,
            variants=flag.variants,
            targeting_rules=flag.targeting_rules,
            scheduled_enable_at=flag.scheduled_enable_at,
            scheduled_disable_at=flag.scheduled_disable_at,
            metadata=flag.metadata,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            created_by_id=str(flag.created_by_id) if flag.created_by_id else None,
            is_active=flag.is_active,
            override_count=await flag.overrides.acount(),
        )
        return JsonResponse(response.model_dump())

    @patch("{key}")
    async def patch_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Partial update a feature flag."""
        # Use the same logic as update
        return await self.update_flag(request, key)

    @delete("{key}")
    async def delete_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Delete a feature flag."""
        from .models import FeatureFlag, FlagAuditLog

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        # Audit log before deletion
        await FlagAuditLog.objects.acreate(
            flag=None,  # Flag will be deleted
            flag_key=flag.key,
            action="delete",
            old_values={"status": flag.status, "key": flag.key},
            user=request.user if request.user.is_authenticated else None,
        )

        await flag.adelete()

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(key)

        return JsonResponse(MessageResponse(message=f"Flag '{key}' deleted").model_dump())

    @post("{key}/enable")
    async def enable_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Enable a feature flag."""
        from .models import FeatureFlag, FlagAuditLog, FlagStatus

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        old_status = flag.status
        flag.status = FlagStatus.ACTIVE.value
        flag.enabled_by_default = True
        await flag.asave(update_fields=["status", "enabled_by_default", "updated_at"])

        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="enable",
            old_values={"status": old_status},
            new_values={"status": flag.status},
            user=request.user if request.user.is_authenticated else None,
        )

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(key)

        return JsonResponse(MessageResponse(message=f"Flag '{key}' enabled").model_dump())

    @post("{key}/disable")
    async def disable_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """Disable a feature flag."""
        from .models import FeatureFlag, FlagAuditLog, FlagStatus

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        old_status = flag.status
        flag.status = FlagStatus.INACTIVE.value
        flag.enabled_by_default = False
        await flag.asave(update_fields=["status", "enabled_by_default", "updated_at"])

        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="disable",
            old_values={"status": old_status},
            new_values={"status": flag.status},
            user=request.user if request.user.is_authenticated else None,
        )

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(key)

        return JsonResponse(MessageResponse(message=f"Flag '{key}' disabled").model_dump())

    # =========================================================================
    # Overrides
    # =========================================================================

    @get("{key}/overrides")
    async def list_overrides(self, request: HttpRequest, key: str) -> JsonResponse:
        """List overrides for a feature flag."""
        from .models import FeatureFlag

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        overrides = [o async for o in flag.overrides.all()]

        items = []
        for override in overrides:
            items.append(
                FlagOverrideResponse(
                    id=str(override.id),
                    flag_id=str(flag.id),
                    flag_key=flag.key,
                    override_type=override.override_type,
                    target_id=override.target_id,
                    target_value=override.target_value,
                    enabled=override.enabled,
                    variant=override.variant,
                    expires_at=override.expires_at,
                    created_at=override.created_at,
                    created_by_id=str(override.created_by_id) if override.created_by_id else None,
                    is_active=override.is_active,
                ).model_dump()
            )

        response = FlagOverrideListResponse(items=items, total=len(items))
        return JsonResponse(response.model_dump())

    @post("{key}/overrides")
    async def create_override(self, request: HttpRequest, key: str) -> JsonResponse:
        """Create an override for a feature flag."""
        from .models import FeatureFlag, FlagAuditLog, FlagOverride

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        try:
            body = json.loads(request.body) if request.body else {}
            data = FlagOverrideCreate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        override = FlagOverride(
            flag=flag,
            override_type=data.override_type.value,
            target_id=data.target_id,
            target_value=data.target_value,
            enabled=data.enabled,
            variant=data.variant,
            expires_at=data.expires_at,
            created_by=request.user if request.user.is_authenticated else None,
        )
        await override.asave()

        # Audit log
        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="add_override",
            new_values={
                "override_type": override.override_type,
                "target": override.target_id or override.target_value,
                "enabled": override.enabled,
            },
            user=request.user if request.user.is_authenticated else None,
        )

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(key)

        response = FlagOverrideResponse(
            id=str(override.id),
            flag_id=str(flag.id),
            flag_key=flag.key,
            override_type=override.override_type,
            target_id=override.target_id,
            target_value=override.target_value,
            enabled=override.enabled,
            variant=override.variant,
            expires_at=override.expires_at,
            created_at=override.created_at,
            created_by_id=str(override.created_by_id) if override.created_by_id else None,
            is_active=override.is_active,
        )
        return JsonResponse(response.model_dump(), status=201)

    @delete("{key}/overrides/{override_id}")
    async def delete_override(
        self, request: HttpRequest, key: str, override_id: str
    ) -> JsonResponse:
        """Delete an override."""
        from .models import FeatureFlag, FlagAuditLog, FlagOverride

        try:
            flag = await FeatureFlag.objects.aget(key=key)
        except FeatureFlag.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail=f"Flag '{key}' not found", code="not_found").model_dump(),
                status=404,
            )

        try:
            override = await FlagOverride.objects.aget(id=override_id, flag=flag)
        except FlagOverride.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Override not found", code="not_found").model_dump(),
                status=404,
            )

        # Audit log
        await FlagAuditLog.objects.acreate(
            flag=flag,
            flag_key=flag.key,
            action="remove_override",
            old_values={
                "override_type": override.override_type,
                "target": override.target_id or override.target_value,
            },
            user=request.user if request.user.is_authenticated else None,
        )

        await override.adelete()

        # Invalidate cache
        from .backends import get_backend

        backend = get_backend()
        if hasattr(backend, "invalidate_cache"):
            backend.invalidate_cache(key)

        return JsonResponse(MessageResponse(message="Override deleted").model_dump())

    # =========================================================================
    # Evaluation
    # =========================================================================

    @post("evaluate")
    async def evaluate_flag(self, request: HttpRequest) -> JsonResponse:
        """Evaluate a single feature flag."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = FlagEvaluationRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .backends import get_backend

        backend = get_backend()

        # Build context
        user = None
        organization = None
        if data.context.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.context.user_id)
            except User.DoesNotExist:
                pass

        if data.context.organization_id:
            from django_matt.multitenancy.models import Organization

            try:
                organization = await Organization.objects.aget(pk=data.context.organization_id)
            except Organization.DoesNotExist:
                pass

        attributes = data.context.attributes
        if data.context.email:
            attributes["email"] = data.context.email

        enabled = backend.is_enabled(
            data.flag_key,
            user=user,
            organization=organization,
            attributes=attributes,
            default=data.default,
        )

        variant = backend.get_variant(
            data.flag_key,
            user=user,
            organization=organization,
            attributes=attributes,
        )

        response = FlagEvaluationResponse(
            flag_key=data.flag_key,
            enabled=enabled,
            variant=variant,
        )
        return JsonResponse(response.model_dump())

    @post("evaluate/bulk")
    async def evaluate_bulk(self, request: HttpRequest) -> JsonResponse:
        """Evaluate multiple feature flags."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = BulkEvaluationRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .backends import get_backend

        backend = get_backend()

        # Build context
        user = None
        organization = None
        if data.context.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.context.user_id)
            except User.DoesNotExist:
                pass

        if data.context.organization_id:
            from django_matt.multitenancy.models import Organization

            try:
                organization = await Organization.objects.aget(pk=data.context.organization_id)
            except Organization.DoesNotExist:
                pass

        attributes = data.context.attributes
        if data.context.email:
            attributes["email"] = data.context.email

        if data.include_all:
            flags = backend.get_all_flags(
                user=user, organization=organization, attributes=attributes
            )
        else:
            flags = {}
            for key in data.flag_keys:
                flags[key] = backend.is_enabled(
                    key, user=user, organization=organization, attributes=attributes
                )

        # Get variants for variant-type flags
        variants = {}
        for key in flags:
            variant = backend.get_variant(
                key, user=user, organization=organization, attributes=attributes
            )
            if variant:
                variants[key] = variant

        response = BulkEvaluationResponse(flags=flags, variants=variants)
        return JsonResponse(response.model_dump())

    # =========================================================================
    # Stats and Audit
    # =========================================================================

    @get("stats")
    async def get_stats(self, request: HttpRequest) -> JsonResponse:
        """Get feature flag statistics."""

        from .models import FeatureFlag, FlagAuditLog, FlagOverride, FlagStatus, FlagType

        total = await FeatureFlag.objects.acount()
        active = await FeatureFlag.objects.filter(status=FlagStatus.ACTIVE.value).acount()
        inactive = await FeatureFlag.objects.filter(status=FlagStatus.INACTIVE.value).acount()
        archived = await FeatureFlag.objects.filter(status=FlagStatus.ARCHIVED.value).acount()
        overrides = await FlagOverride.objects.acount()

        # Flags by type
        flags_by_type = {}
        for flag_type in FlagType:
            count = await FeatureFlag.objects.filter(flag_type=flag_type.value).acount()
            flags_by_type[flag_type.value] = count

        # Recent changes
        yesterday = timezone.now() - timedelta(days=1)
        recent = await FlagAuditLog.objects.filter(created_at__gte=yesterday).acount()

        response = FlagStatsResponse(
            total_flags=total,
            active_flags=active,
            inactive_flags=inactive,
            archived_flags=archived,
            total_overrides=overrides,
            flags_by_type=flags_by_type,
            recent_changes=recent,
        )
        return JsonResponse(response.model_dump())

    @get("{key}/audit-logs")
    async def get_audit_logs(self, request: HttpRequest, key: str) -> JsonResponse:
        """Get audit logs for a feature flag."""
        from .models import FlagAuditLog

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        page_size = min(page_size, 100)

        qs = FlagAuditLog.objects.filter(flag_key=key).order_by("-created_at")
        total = await qs.acount()

        offset = (page - 1) * page_size
        logs = [log async for log in qs[offset : offset + page_size]]

        items = []
        for log in logs:
            items.append(
                {
                    "id": str(log.id),
                    "flag_key": log.flag_key,
                    "action": log.action,
                    "changes": log.changes,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "user_id": str(log.user_id) if log.user_id else None,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                }
            )

        response = FlagAuditLogListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
        return JsonResponse(response.model_dump())


class FlagEvaluationController(APIController):
    """
    Lightweight controller for flag evaluation only.

    Use this if you only need evaluation endpoints without management.
    """

    prefix = "flags"
    tags = ["Feature Flags"]

    @get("check/{key}")
    async def check_flag(self, request: HttpRequest, key: str) -> JsonResponse:
        """
        Quick check if a flag is enabled for current user.

        Returns simple boolean response.
        """
        ctx = FlagContext.from_request(request)
        enabled = ctx.is_enabled(key)

        return JsonResponse({"enabled": enabled})

    @get("variant/{key}")
    async def get_variant(self, request: HttpRequest, key: str) -> JsonResponse:
        """
        Get variant assignment for current user.

        Returns variant key or null.
        """
        ctx = FlagContext.from_request(request)
        variant = ctx.get_variant(key)

        return JsonResponse({"variant": variant})

    @get("all")
    async def get_all_flags(self, request: HttpRequest) -> JsonResponse:
        """
        Get all flags and their status for current user.

        Returns dict of flag_key -> enabled.
        """
        ctx = FlagContext.from_request(request)
        flags = ctx.get_all_flags()

        return JsonResponse({"flags": flags})


__all__ = [
    "FlagController",
    "FlagEvaluationController",
]
