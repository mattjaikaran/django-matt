"""
Experiments REST API controllers.

Provides REST API endpoints for managing experiments.

Usage:
    from django_matt.experiments.controllers import ExperimentController

    api = MattAPI()
    api.register_controller(ExperimentController)
"""

import json

from django.http import HttpRequest, JsonResponse

from django_matt.core.controller import APIController
from django_matt.core.router import delete, get, patch, post, put

from .context import ExperimentContext
from .schemas import (
    AssignmentRequest,
    AssignmentResponse,
    AuditLogListResponse,
    BulkAssignmentRequest,
    BulkAssignmentResponse,
    ConversionEvent,
    ErrorResponse,
    EventResponse,
    ExperimentAnalysisResponse,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentStatsResponse,
    ExperimentUpdate,
    MessageResponse,
    RevenueEvent,
    VariantCreate,
    VariantResponse,
)


class ExperimentController(APIController):
    """
    Experiments management controller.

    Provides CRUD operations for experiments, variants, and assignments.

    Endpoints:
        GET    /experiments                     - List all experiments
        POST   /experiments                     - Create a new experiment
        GET    /experiments/{key}               - Get experiment by key
        PUT    /experiments/{key}               - Update experiment
        PATCH  /experiments/{key}               - Partial update experiment
        DELETE /experiments/{key}               - Delete experiment
        POST   /experiments/{key}/start         - Start experiment
        POST   /experiments/{key}/pause         - Pause experiment
        POST   /experiments/{key}/resume        - Resume experiment
        POST   /experiments/{key}/complete      - Complete experiment
        GET    /experiments/{key}/variants      - List variants
        POST   /experiments/{key}/variants      - Create variant
        PUT    /experiments/{key}/variants/{id} - Update variant
        DELETE /experiments/{key}/variants/{id} - Delete variant
        GET    /experiments/{key}/analysis      - Get statistical analysis
        POST   /experiments/assign              - Get/create assignment
        POST   /experiments/assign/bulk         - Bulk assignment
        POST   /experiments/track/conversion    - Track conversion
        POST   /experiments/track/revenue       - Track revenue
        GET    /experiments/stats               - Get experiment statistics
        GET    /experiments/{key}/audit-logs    - Get audit logs
    """

    prefix = "experiments"
    tags = ["Experiments"]

    # =========================================================================
    # Experiment CRUD
    # =========================================================================

    @get("")
    async def list_experiments(self, request: HttpRequest) -> JsonResponse:
        """
        List all experiments.

        Query params:
            - status: Filter by status (draft, running, paused, completed, archived)
            - strategy: Filter by strategy
            - search: Search by key or name
            - page: Page number (default: 1)
            - page_size: Items per page (default: 20)
        """
        from .models import Experiment

        qs = Experiment.objects.prefetch_related("variants").all()

        # Filters
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        strategy = request.GET.get("strategy")
        if strategy:
            qs = qs.filter(strategy=strategy)

        search = request.GET.get("search")
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(key__icontains=search) | Q(name__icontains=search))

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        page_size = min(page_size, 100)

        total = await qs.acount()
        offset = (page - 1) * page_size
        experiments = [e async for e in qs[offset : offset + page_size]]

        # Build response
        items = []
        for exp in experiments:
            variants = [
                VariantResponse(
                    id=str(v.id),
                    key=v.key,
                    name=v.name,
                    description=v.description,
                    is_control=v.is_control,
                    weight=v.weight,
                    payload=v.payload,
                    assignment_count=v.assignment_count,
                    conversion_count=v.conversion_count,
                    conversion_rate=v.conversion_rate,
                ).model_dump()
                for v in exp.variants.all()
            ]

            items.append(
                ExperimentResponse(
                    id=str(exp.id),
                    key=exp.key,
                    name=exp.name,
                    description=exp.description,
                    status=exp.status,
                    strategy=exp.strategy,
                    min_sample_size=exp.min_sample_size,
                    target_confidence=exp.target_confidence,
                    primary_metric=exp.primary_metric,
                    secondary_metrics=exp.secondary_metrics,
                    exclusion_group=exp.exclusion_group,
                    holdout_percentage=exp.holdout_percentage,
                    targeting_rules=exp.targeting_rules,
                    epsilon=exp.epsilon,
                    exploration_weight=exp.exploration_weight,
                    feature_flag_key=exp.feature_flag_key,
                    metadata=exp.metadata,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    winner_variant_id=str(exp.winner_variant_id) if exp.winner_variant_id else None,
                    winner_confidence=exp.winner_confidence,
                    winner_detected_at=exp.winner_detected_at,
                    created_at=exp.created_at,
                    updated_at=exp.updated_at,
                    created_by_id=str(exp.created_by_id) if exp.created_by_id else None,
                    variants=variants,
                    total_participants=exp.total_participants,
                    is_running=exp.is_running,
                    has_winner=exp.has_winner,
                ).model_dump()
            )

        response = ExperimentListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())

    @post("")
    async def create_experiment(self, request: HttpRequest) -> JsonResponse:
        """Create a new experiment."""
        from .models import Experiment, ExperimentAuditLog, Variant

        try:
            body = json.loads(request.body) if request.body else {}
            data = ExperimentCreate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        # Check if key already exists
        if await Experiment.objects.filter(key=data.key).aexists():
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment with key '{data.key}' already exists", code="key_exists"
                ).model_dump(),
                status=400,
            )

        # Create experiment
        experiment = Experiment(
            key=data.key,
            name=data.name,
            description=data.description,
            strategy=data.strategy.value,
            min_sample_size=data.min_sample_size,
            target_confidence=data.target_confidence,
            primary_metric=data.primary_metric,
            secondary_metrics=data.secondary_metrics,
            exclusion_group=data.exclusion_group,
            holdout_percentage=data.holdout_percentage,
            targeting_rules=[r.model_dump() for r in data.targeting_rules],
            epsilon=data.epsilon,
            exploration_weight=data.exploration_weight,
            feature_flag_key=data.feature_flag_key,
            metadata=data.metadata,
            created_by=request.user if request.user.is_authenticated else None,
        )
        await experiment.asave()

        # Create variants
        for variant_data in data.variants:
            variant = Variant(
                experiment=experiment,
                key=variant_data.key,
                name=variant_data.name,
                description=variant_data.description,
                is_control=variant_data.is_control,
                weight=variant_data.weight,
                payload=variant_data.payload,
            )
            await variant.asave()

        # Audit log
        await ExperimentAuditLog.objects.acreate(
            experiment=experiment,
            experiment_key=experiment.key,
            action="create",
            new_values={"status": experiment.status},
            user=request.user if request.user.is_authenticated else None,
        )

        # Build response
        variants = [
            VariantResponse(
                id=str(v.id),
                key=v.key,
                name=v.name,
                description=v.description,
                is_control=v.is_control,
                weight=v.weight,
                payload=v.payload,
            ).model_dump()
            async for v in experiment.variants.all()
        ]

        response = ExperimentResponse(
            id=str(experiment.id),
            key=experiment.key,
            name=experiment.name,
            description=experiment.description,
            status=experiment.status,
            strategy=experiment.strategy,
            min_sample_size=experiment.min_sample_size,
            target_confidence=experiment.target_confidence,
            primary_metric=experiment.primary_metric,
            secondary_metrics=experiment.secondary_metrics,
            exclusion_group=experiment.exclusion_group,
            holdout_percentage=experiment.holdout_percentage,
            targeting_rules=experiment.targeting_rules,
            epsilon=experiment.epsilon,
            exploration_weight=experiment.exploration_weight,
            feature_flag_key=experiment.feature_flag_key,
            metadata=experiment.metadata,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            variants=variants,
        )
        return JsonResponse(response.model_dump(), status=201)

    @get("{key}")
    async def get_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Get an experiment by key."""
        from .models import Experiment

        try:
            experiment = await Experiment.objects.prefetch_related("variants").aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        variants = [
            VariantResponse(
                id=str(v.id),
                key=v.key,
                name=v.name,
                description=v.description,
                is_control=v.is_control,
                weight=v.weight,
                payload=v.payload,
                assignment_count=v.assignment_count,
                conversion_count=v.conversion_count,
                conversion_rate=v.conversion_rate,
            ).model_dump()
            for v in experiment.variants.all()
        ]

        response = ExperimentResponse(
            id=str(experiment.id),
            key=experiment.key,
            name=experiment.name,
            description=experiment.description,
            status=experiment.status,
            strategy=experiment.strategy,
            min_sample_size=experiment.min_sample_size,
            target_confidence=experiment.target_confidence,
            primary_metric=experiment.primary_metric,
            secondary_metrics=experiment.secondary_metrics,
            exclusion_group=experiment.exclusion_group,
            holdout_percentage=experiment.holdout_percentage,
            targeting_rules=experiment.targeting_rules,
            epsilon=experiment.epsilon,
            exploration_weight=experiment.exploration_weight,
            feature_flag_key=experiment.feature_flag_key,
            metadata=experiment.metadata,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            winner_variant_id=str(experiment.winner_variant_id)
            if experiment.winner_variant_id
            else None,
            winner_confidence=experiment.winner_confidence,
            winner_detected_at=experiment.winner_detected_at,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            created_by_id=str(experiment.created_by_id) if experiment.created_by_id else None,
            variants=variants,
            total_participants=experiment.total_participants,
            is_running=experiment.is_running,
            has_winner=experiment.has_winner,
        )
        return JsonResponse(response.model_dump())

    @put("{key}")
    async def update_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Update an experiment."""
        from .models import Experiment, ExperimentAuditLog

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            body = json.loads(request.body) if request.body else {}
            data = ExperimentUpdate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        # Track changes
        old_values = {"status": experiment.status}

        # Update fields
        if data.name is not None:
            experiment.name = data.name
        if data.description is not None:
            experiment.description = data.description
        if data.strategy is not None:
            experiment.strategy = data.strategy.value
        if data.min_sample_size is not None:
            experiment.min_sample_size = data.min_sample_size
        if data.target_confidence is not None:
            experiment.target_confidence = data.target_confidence
        if data.primary_metric is not None:
            experiment.primary_metric = data.primary_metric
        if data.secondary_metrics is not None:
            experiment.secondary_metrics = data.secondary_metrics
        if data.exclusion_group is not None:
            experiment.exclusion_group = data.exclusion_group
        if data.holdout_percentage is not None:
            experiment.holdout_percentage = data.holdout_percentage
        if data.targeting_rules is not None:
            experiment.targeting_rules = [r.model_dump() for r in data.targeting_rules]
        if data.epsilon is not None:
            experiment.epsilon = data.epsilon
        if data.exploration_weight is not None:
            experiment.exploration_weight = data.exploration_weight
        if data.feature_flag_key is not None:
            experiment.feature_flag_key = data.feature_flag_key
        if data.metadata is not None:
            experiment.metadata = data.metadata

        await experiment.asave()

        # Audit log
        await ExperimentAuditLog.objects.acreate(
            experiment=experiment,
            experiment_key=experiment.key,
            action="update",
            old_values=old_values,
            new_values={"status": experiment.status},
            user=request.user if request.user.is_authenticated else None,
        )

        return await self.get_experiment(request, key)

    @patch("{key}")
    async def patch_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Partial update an experiment."""
        return await self.update_experiment(request, key)

    @delete("{key}")
    async def delete_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Delete an experiment."""
        from .models import Experiment, ExperimentAuditLog

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        # Audit log before deletion
        await ExperimentAuditLog.objects.acreate(
            experiment=None,
            experiment_key=experiment.key,
            action="delete",
            old_values={"status": experiment.status, "key": experiment.key},
            user=request.user if request.user.is_authenticated else None,
        )

        await experiment.adelete()
        return JsonResponse(MessageResponse(message=f"Experiment '{key}' deleted").model_dump())

    # =========================================================================
    # Experiment Lifecycle
    # =========================================================================

    @post("{key}/start")
    async def start_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Start an experiment."""
        from .models import Experiment, ExperimentAuditLog

        try:
            experiment = await Experiment.objects.prefetch_related("variants").aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            old_status = experiment.status
            experiment.start()

            await ExperimentAuditLog.objects.acreate(
                experiment=experiment,
                experiment_key=experiment.key,
                action="start",
                old_values={"status": old_status},
                new_values={"status": experiment.status},
                user=request.user if request.user.is_authenticated else None,
            )

            return JsonResponse(MessageResponse(message=f"Experiment '{key}' started").model_dump())
        except ValueError as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="invalid_state").model_dump(), status=400
            )

    @post("{key}/pause")
    async def pause_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Pause an experiment."""
        from .models import Experiment, ExperimentAuditLog

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            old_status = experiment.status
            experiment.pause()

            await ExperimentAuditLog.objects.acreate(
                experiment=experiment,
                experiment_key=experiment.key,
                action="pause",
                old_values={"status": old_status},
                new_values={"status": experiment.status},
                user=request.user if request.user.is_authenticated else None,
            )

            return JsonResponse(MessageResponse(message=f"Experiment '{key}' paused").model_dump())
        except ValueError as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="invalid_state").model_dump(), status=400
            )

    @post("{key}/resume")
    async def resume_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Resume a paused experiment."""
        from .models import Experiment, ExperimentAuditLog

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            old_status = experiment.status
            experiment.resume()

            await ExperimentAuditLog.objects.acreate(
                experiment=experiment,
                experiment_key=experiment.key,
                action="resume",
                old_values={"status": old_status},
                new_values={"status": experiment.status},
                user=request.user if request.user.is_authenticated else None,
            )

            return JsonResponse(MessageResponse(message=f"Experiment '{key}' resumed").model_dump())
        except ValueError as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="invalid_state").model_dump(), status=400
            )

    @post("{key}/complete")
    async def complete_experiment(self, request: HttpRequest, key: str) -> JsonResponse:
        """Complete an experiment."""
        from .models import Experiment, ExperimentAuditLog, Variant

        try:
            experiment = await Experiment.objects.prefetch_related("variants").aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            body = {}

        winner_variant = None
        winner_variant_key = body.get("winner_variant_key")
        if winner_variant_key:
            try:
                winner_variant = await Variant.objects.aget(
                    experiment=experiment, key=winner_variant_key
                )
            except Variant.DoesNotExist:
                return JsonResponse(
                    ErrorResponse(
                        detail=f"Variant '{winner_variant_key}' not found", code="not_found"
                    ).model_dump(),
                    status=404,
                )

        confidence = body.get("confidence")

        old_status = experiment.status
        experiment.complete(winner_variant=winner_variant, confidence=confidence)

        await ExperimentAuditLog.objects.acreate(
            experiment=experiment,
            experiment_key=experiment.key,
            action="complete",
            old_values={"status": old_status},
            new_values={
                "status": experiment.status,
                "winner_variant_key": winner_variant_key,
                "confidence": confidence,
            },
            user=request.user if request.user.is_authenticated else None,
        )

        return JsonResponse(MessageResponse(message=f"Experiment '{key}' completed").model_dump())

    # =========================================================================
    # Variants
    # =========================================================================

    @get("{key}/variants")
    async def list_variants(self, request: HttpRequest, key: str) -> JsonResponse:
        """List variants for an experiment."""
        from .models import Experiment

        try:
            experiment = await Experiment.objects.prefetch_related("variants").aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        variants = [
            VariantResponse(
                id=str(v.id),
                key=v.key,
                name=v.name,
                description=v.description,
                is_control=v.is_control,
                weight=v.weight,
                payload=v.payload,
                assignment_count=v.assignment_count,
                conversion_count=v.conversion_count,
                conversion_rate=v.conversion_rate,
            ).model_dump()
            for v in experiment.variants.all()
        ]

        return JsonResponse({"items": variants, "total": len(variants)})

    @post("{key}/variants")
    async def create_variant(self, request: HttpRequest, key: str) -> JsonResponse:
        """Create a new variant for an experiment."""
        from .models import Experiment, ExperimentAuditLog, Variant

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            body = json.loads(request.body) if request.body else {}
            data = VariantCreate.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        # Check if variant key exists
        if await Variant.objects.filter(experiment=experiment, key=data.key).aexists():
            return JsonResponse(
                ErrorResponse(
                    detail=f"Variant '{data.key}' already exists", code="key_exists"
                ).model_dump(),
                status=400,
            )

        variant = Variant(
            experiment=experiment,
            key=data.key,
            name=data.name,
            description=data.description,
            is_control=data.is_control,
            weight=data.weight,
            payload=data.payload,
        )
        await variant.asave()

        # Audit log
        await ExperimentAuditLog.objects.acreate(
            experiment=experiment,
            experiment_key=experiment.key,
            action="add_variant",
            new_values={"variant_key": variant.key},
            user=request.user if request.user.is_authenticated else None,
        )

        response = VariantResponse(
            id=str(variant.id),
            key=variant.key,
            name=variant.name,
            description=variant.description,
            is_control=variant.is_control,
            weight=variant.weight,
            payload=variant.payload,
        )
        return JsonResponse(response.model_dump(), status=201)

    @delete("{key}/variants/{variant_id}")
    async def delete_variant(self, request: HttpRequest, key: str, variant_id: str) -> JsonResponse:
        """Delete a variant."""
        from .models import Experiment, ExperimentAuditLog, Variant

        try:
            experiment = await Experiment.objects.aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        try:
            variant = await Variant.objects.aget(id=variant_id, experiment=experiment)
        except Variant.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Variant not found", code="not_found").model_dump(),
                status=404,
            )

        # Audit log
        await ExperimentAuditLog.objects.acreate(
            experiment=experiment,
            experiment_key=experiment.key,
            action="remove_variant",
            old_values={"variant_key": variant.key},
            user=request.user if request.user.is_authenticated else None,
        )

        await variant.adelete()
        return JsonResponse(MessageResponse(message="Variant deleted").model_dump())

    # =========================================================================
    # Analysis
    # =========================================================================

    @get("{key}/analysis")
    async def get_analysis(self, request: HttpRequest, key: str) -> JsonResponse:
        """Get statistical analysis for an experiment."""
        from .analysis import analyze_experiment
        from .models import Experiment

        try:
            experiment = await Experiment.objects.prefetch_related("variants").aget(key=key)
        except Experiment.DoesNotExist:
            return JsonResponse(
                ErrorResponse(
                    detail=f"Experiment '{key}' not found", code="not_found"
                ).model_dump(),
                status=404,
            )

        metric_name = request.GET.get("metric", experiment.primary_metric)
        confidence_level = float(request.GET.get("confidence", experiment.target_confidence))

        analysis = analyze_experiment(experiment, metric_name, confidence_level)

        response = ExperimentAnalysisResponse(
            experiment_id=analysis.experiment_id,
            experiment_key=analysis.experiment_key,
            status=analysis.status,
            total_participants=analysis.total_participants,
            total_conversions=analysis.total_conversions,
            overall_conversion_rate=analysis.overall_conversion_rate,
            variant_stats=[v.__dict__ for v in analysis.variant_stats],
            comparisons=[c.__dict__ for c in analysis.comparisons],
            has_winner=analysis.has_winner,
            winner_variant_id=analysis.winner_variant_id,
            winner_variant_key=analysis.winner_variant_key,
            winner_confidence=analysis.winner_confidence,
            winner_reason=analysis.winner_reason,
            should_continue=analysis.should_continue,
            recommendation=analysis.recommendation,
            analysis_timestamp=analysis.analysis_timestamp,
            confidence_level=analysis.confidence_level,
        )
        return JsonResponse(response.model_dump())

    # =========================================================================
    # Assignment & Tracking
    # =========================================================================

    @post("assign")
    async def get_assignment(self, request: HttpRequest) -> JsonResponse:
        """Get or create an experiment assignment."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = AssignmentRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .manager import get_manager

        manager = get_manager()

        # Get user if user_id provided
        user = None
        if data.context.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.context.user_id)
            except User.DoesNotExist:
                pass

        assignment = manager.get_assignment(
            experiment_key=data.experiment_key,
            user=user,
            anonymous_id=data.context.anonymous_id,
            create=data.create,
            context=data.context.attributes,
        )

        if not assignment:
            return JsonResponse(
                AssignmentResponse(
                    experiment_key=data.experiment_key,
                    variant_key=None,
                    variant_id=None,
                    is_holdout=False,
                ).model_dump()
            )

        response = AssignmentResponse(
            experiment_key=data.experiment_key,
            variant_key=assignment.variant.key if assignment.variant else None,
            variant_id=str(assignment.variant.id) if assignment.variant else None,
            is_holdout=assignment.is_holdout,
            assigned_at=assignment.assigned_at,
            payload=assignment.variant.payload if assignment.variant else {},
        )
        return JsonResponse(response.model_dump())

    @post("assign/bulk")
    async def bulk_assignment(self, request: HttpRequest) -> JsonResponse:
        """Get assignments for multiple experiments."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = BulkAssignmentRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .manager import get_manager
        from .models import Experiment, ExperimentStatus

        manager = get_manager()

        # Get user if user_id provided
        user = None
        if data.context.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.context.user_id)
            except User.DoesNotExist:
                pass

        experiment_keys = data.experiment_keys
        if data.include_all_running:
            running_keys = [
                e.key
                async for e in Experiment.objects.filter(status=ExperimentStatus.RUNNING.value)
            ]
            experiment_keys = list(set(experiment_keys + running_keys))

        assignments = {}
        for exp_key in experiment_keys:
            assignment = manager.get_assignment(
                experiment_key=exp_key,
                user=user,
                anonymous_id=data.context.anonymous_id,
                create=True,
                context=data.context.attributes,
            )

            assignments[exp_key] = AssignmentResponse(
                experiment_key=exp_key,
                variant_key=assignment.variant.key if assignment and assignment.variant else None,
                variant_id=str(assignment.variant.id)
                if assignment and assignment.variant
                else None,
                is_holdout=assignment.is_holdout if assignment else False,
                assigned_at=assignment.assigned_at if assignment else None,
                payload=assignment.variant.payload if assignment and assignment.variant else {},
            ).model_dump()

        response = BulkAssignmentResponse(assignments=assignments)
        return JsonResponse(response.model_dump())

    @post("track/conversion")
    async def track_conversion(self, request: HttpRequest) -> JsonResponse:
        """Track a conversion event."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = ConversionEvent.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .manager import get_manager

        manager = get_manager()

        # Get user if user_id provided
        user = None
        if data.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.user_id)
            except User.DoesNotExist:
                pass

        success = manager.track_conversion(
            experiment_key=data.experiment_key,
            user=user,
            anonymous_id=data.anonymous_id,
            metric_name=data.metric_name,
            value=data.value,
            metadata=data.metadata,
        )

        return JsonResponse(EventResponse(success=success).model_dump())

    @post("track/revenue")
    async def track_revenue(self, request: HttpRequest) -> JsonResponse:
        """Track a revenue event."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = RevenueEvent.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(), status=400
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(), status=422
            )

        from .manager import get_manager

        manager = get_manager()

        # Get user if user_id provided
        user = None
        if data.user_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = await User.objects.aget(pk=data.user_id)
            except User.DoesNotExist:
                pass

        success = manager.track_revenue(
            experiment_key=data.experiment_key,
            amount=data.amount,
            user=user,
            anonymous_id=data.anonymous_id,
            metric_name=data.metric_name,
            metadata=data.metadata,
        )

        return JsonResponse(EventResponse(success=success).model_dump())

    # =========================================================================
    # Stats & Audit
    # =========================================================================

    @get("stats")
    async def get_stats(self, request: HttpRequest) -> JsonResponse:
        """Get experiment statistics."""
        from .models import (
            AssignmentStrategy,
            Experiment,
            ExperimentAssignment,
            ExperimentResult,
            ExperimentStatus,
        )

        total = await Experiment.objects.acount()
        draft = await Experiment.objects.filter(status=ExperimentStatus.DRAFT.value).acount()
        running = await Experiment.objects.filter(status=ExperimentStatus.RUNNING.value).acount()
        paused = await Experiment.objects.filter(status=ExperimentStatus.PAUSED.value).acount()
        completed = await Experiment.objects.filter(
            status=ExperimentStatus.COMPLETED.value
        ).acount()
        assignments = await ExperimentAssignment.objects.acount()
        conversions = await ExperimentResult.objects.filter(metric_name="conversion").acount()

        # By strategy
        by_strategy = {}
        for strategy in AssignmentStrategy:
            count = await Experiment.objects.filter(strategy=strategy.value).acount()
            by_strategy[strategy.value] = count

        response = ExperimentStatsResponse(
            total_experiments=total,
            draft_experiments=draft,
            running_experiments=running,
            paused_experiments=paused,
            completed_experiments=completed,
            total_assignments=assignments,
            total_conversions=conversions,
            experiments_by_strategy=by_strategy,
        )
        return JsonResponse(response.model_dump())

    @get("{key}/audit-logs")
    async def get_audit_logs(self, request: HttpRequest, key: str) -> JsonResponse:
        """Get audit logs for an experiment."""
        from .models import ExperimentAuditLog

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        page_size = min(page_size, 100)

        qs = ExperimentAuditLog.objects.filter(experiment_key=key).order_by("-created_at")
        total = await qs.acount()

        offset = (page - 1) * page_size
        logs = [log async for log in qs[offset : offset + page_size]]

        items = []
        for log in logs:
            items.append(
                {
                    "id": str(log.id),
                    "experiment_key": log.experiment_key,
                    "action": log.action,
                    "changes": log.changes,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "user_id": str(log.user_id) if log.user_id else None,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                }
            )

        response = AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())


class ExperimentAssignmentController(APIController):
    """
    Lightweight controller for experiment assignment only.

    Use this if you only need assignment endpoints without full management.
    """

    prefix = "experiments"
    tags = ["Experiments"]

    @get("variant/{experiment_key}")
    async def get_variant(self, request: HttpRequest, experiment_key: str) -> JsonResponse:
        """
        Get variant assignment for current user.

        Returns variant key, payload, or null if not in experiment.
        """
        ctx = ExperimentContext.from_request(request)
        variant = ctx.get_variant(experiment_key)
        payload = ctx.get_variant_payload(experiment_key) if variant else {}

        return JsonResponse(
            {
                "variant": variant,
                "payload": payload,
            }
        )

    @get("all")
    async def get_all_experiments(self, request: HttpRequest) -> JsonResponse:
        """
        Get all running experiments and assignments for current user.

        Returns dict of experiment_key -> variant_key.
        """
        ctx = ExperimentContext.from_request(request)
        experiments = ctx.get_all_experiments()

        return JsonResponse({"experiments": experiments})


__all__ = [
    "ExperimentController",
    "ExperimentAssignmentController",
]
