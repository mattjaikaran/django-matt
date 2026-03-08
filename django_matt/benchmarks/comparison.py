"""
Framework Comparison Benchmark Scenario.

Compares Django Matt against DRF, django-ninja, FastAPI, and Starlette
on list serialization and create validation scenarios.

If a framework is not installed, results include metadata indicating
the skip reason rather than silently omitting the row.

Usage:
    from django_matt.benchmarks.comparison import FrameworkComparisonScenario
    scenario = FrameworkComparisonScenario()
    results = scenario.run()
"""

from __future__ import annotations

from typing import Any

import orjson
from pydantic import BaseModel

from django_matt.benchmarks.runner import BenchmarkResult, BenchmarkScenario

# ---------------------------------------------------------------------------
# Sample data shared by all framework benchmarks
# ---------------------------------------------------------------------------

_SAMPLE_ITEM: dict[str, Any] = {
    "id": 1,
    "name": "Test User",
    "email": "test@example.com",
    "active": True,
    "score": 98.6,
}

_SAMPLE_LIST: list[dict[str, Any]] = [
    {
        "id": i,
        "name": f"User {i}",
        "email": f"user{i}@example.com",
        "active": i % 2 == 0,
        "score": float(i) * 1.5,
    }
    for i in range(20)
]


# ---------------------------------------------------------------------------
# Pydantic model used by django-matt and FastAPI scenarios
# ---------------------------------------------------------------------------


class _UserSchema(BaseModel):
    """Pydantic schema used by django-matt (and FastAPI internally)."""

    id: int
    name: str
    email: str
    active: bool = True
    score: float = 0.0


def _make_skipped_result(
    name: str,
    framework: str,
    reason: str = "not installed",
) -> BenchmarkResult:
    """Create a placeholder BenchmarkResult indicating a framework is skipped."""
    return BenchmarkResult(
        name=name,
        scenario="framework_comparison",
        iterations=0,
        total_time_ms=0.0,
        mean_time_ms=0.0,
        median_time_ms=0.0,
        min_time_ms=0.0,
        max_time_ms=0.0,
        std_dev_ms=0.0,
        ops_per_second=0.0,
        metadata={
            "framework": framework,
            "skipped": True,
            "reason": (
                f"{reason} — run `uv add --dev djangorestframework "
                "django-ninja fastapi` to enable"
            ),
        },
    )


class FrameworkComparisonScenario(BenchmarkScenario):
    """
    Cross-framework benchmark comparison.

    Benchmarks list serialization (20 items) and single-item create
    validation for each supported framework.  Missing frameworks are
    represented as skipped rows rather than silently omitted.
    """

    name: str = "framework_comparison"
    description: str = "Cross-framework benchmark comparison"

    # ------------------------------------------------------------------
    # Django Matt
    # ------------------------------------------------------------------

    def _run_django_matt(self) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []

        # List serialization — uses model_construct() (from_orm_fast pattern)
        user_instances = [_UserSchema.model_construct(**item) for item in _SAMPLE_LIST]

        def dm_list_serialize() -> bytes:
            return orjson.dumps([u.model_dump() for u in user_instances])

        bench_list = self.create_benchmark(
            "django-matt list (20)",
            metadata={"framework": "django-matt"},
        )
        results.append(bench_list.run(dm_list_serialize))
        results[-1].metadata["framework"] = "django-matt"

        # Create validation — standard Pydantic validation for incoming data
        def dm_create_validate() -> _UserSchema:
            return _UserSchema.model_validate(_SAMPLE_ITEM)

        bench_create = self.create_benchmark(
            "django-matt create",
            metadata={"framework": "django-matt"},
        )
        results.append(bench_create.run(dm_create_validate))
        results[-1].metadata["framework"] = "django-matt"

        return results

    # ------------------------------------------------------------------
    # DRF
    # ------------------------------------------------------------------

    def _run_drf(self) -> list[BenchmarkResult]:
        try:
            from rest_framework import serializers
        except ImportError:
            return [
                _make_skipped_result("DRF list (20)", "DRF", "not installed"),
                _make_skipped_result("DRF create", "DRF", "not installed"),
            ]

        class _UserSerializer(serializers.Serializer):  # type: ignore[misc]
            id = serializers.IntegerField()
            name = serializers.CharField()
            email = serializers.EmailField()
            active = serializers.BooleanField(default=True)
            score = serializers.FloatField(default=0.0)

        # List serialization
        def drf_list_serialize() -> Any:
            s = _UserSerializer(_SAMPLE_LIST, many=True)
            return s.data

        bench_list = self.create_benchmark(
            "DRF list (20)",
            metadata={"framework": "DRF"},
        )
        result_list = bench_list.run(drf_list_serialize)
        result_list.metadata["framework"] = "DRF"

        # Create validation
        def drf_create_validate() -> Any:
            s = _UserSerializer(data=_SAMPLE_ITEM)
            s.is_valid()
            return s.validated_data

        bench_create = self.create_benchmark(
            "DRF create",
            metadata={"framework": "DRF"},
        )
        result_create = bench_create.run(drf_create_validate)
        result_create.metadata["framework"] = "DRF"

        return [result_list, result_create]

    # ------------------------------------------------------------------
    # django-ninja
    # ------------------------------------------------------------------

    def _run_django_ninja(self) -> list[BenchmarkResult]:
        try:
            from ninja import Schema as NinjaSchema
        except ImportError:
            return [
                _make_skipped_result("django-ninja list (20)", "django-ninja", "not installed"),
                _make_skipped_result("django-ninja create", "django-ninja", "not installed"),
            ]

        class _NinjaUserSchema(NinjaSchema):  # type: ignore[misc]
            id: int
            name: str
            email: str
            active: bool = True
            score: float = 0.0

        ninja_instances = [_NinjaUserSchema.model_construct(**item) for item in _SAMPLE_LIST]

        # List serialization
        def ninja_list_serialize() -> bytes:
            return orjson.dumps([u.model_dump() for u in ninja_instances])

        bench_list = self.create_benchmark(
            "django-ninja list (20)",
            metadata={"framework": "django-ninja"},
        )
        result_list = bench_list.run(ninja_list_serialize)
        result_list.metadata["framework"] = "django-ninja"

        # Create validation
        def ninja_create_validate() -> Any:
            return _NinjaUserSchema.model_validate(_SAMPLE_ITEM)

        bench_create = self.create_benchmark(
            "django-ninja create",
            metadata={"framework": "django-ninja"},
        )
        result_create = bench_create.run(ninja_create_validate)
        result_create.metadata["framework"] = "django-ninja"

        return [result_list, result_create]

    # ------------------------------------------------------------------
    # FastAPI
    # ------------------------------------------------------------------

    def _run_fastapi(self) -> list[BenchmarkResult]:
        try:
            import fastapi  # noqa: F401
            from pydantic import BaseModel as _FM
        except ImportError:
            return [
                _make_skipped_result("FastAPI list (20)", "FastAPI", "not installed"),
                _make_skipped_result("FastAPI create", "FastAPI", "not installed"),
            ]

        class _FastAPIUserModel(_FM):
            id: int
            name: str
            email: str
            active: bool = True
            score: float = 0.0

            model_config = {"from_attributes": True}

        fa_instances = [_FastAPIUserModel.model_construct(**item) for item in _SAMPLE_LIST]

        # List serialization (FastAPI delegates to Pydantic internally)
        def fastapi_list_serialize() -> bytes:
            return orjson.dumps([u.model_dump() for u in fa_instances])

        bench_list = self.create_benchmark(
            "FastAPI list (20)",
            metadata={"framework": "FastAPI"},
        )
        result_list = bench_list.run(fastapi_list_serialize)
        result_list.metadata["framework"] = "FastAPI"

        # Create validation
        def fastapi_create_validate() -> Any:
            return _FastAPIUserModel.model_validate(_SAMPLE_ITEM)

        bench_create = self.create_benchmark(
            "FastAPI create",
            metadata={"framework": "FastAPI"},
        )
        result_create = bench_create.run(fastapi_create_validate)
        result_create.metadata["framework"] = "FastAPI"

        return [result_list, result_create]

    # ------------------------------------------------------------------
    # Starlette (raw ASGI baseline — no schema layer)
    # ------------------------------------------------------------------

    def _run_starlette(self) -> list[BenchmarkResult]:
        try:
            import starlette  # noqa: F401
        except ImportError:
            return [
                _make_skipped_result("Starlette list (20)", "Starlette", "not installed"),
                _make_skipped_result("Starlette create", "Starlette", "not installed"),
            ]

        # Starlette raw ASGI: just orjson serialization of plain dicts
        def starlette_list_serialize() -> bytes:
            return orjson.dumps(_SAMPLE_LIST)

        bench_list = self.create_benchmark(
            "Starlette list (20)",
            metadata={"framework": "Starlette"},
        )
        result_list = bench_list.run(starlette_list_serialize)
        result_list.metadata["framework"] = "Starlette"

        # "Create" for Starlette = raw dict construction (no schema validation)
        def starlette_create() -> bytes:
            return orjson.dumps(_SAMPLE_ITEM)

        bench_create = self.create_benchmark(
            "Starlette create",
            metadata={"framework": "Starlette"},
        )
        result_create = bench_create.run(starlette_create)
        result_create.metadata["framework"] = "Starlette"

        return [result_list, result_create]

    # ------------------------------------------------------------------
    # Main run()
    # ------------------------------------------------------------------

    def run(self) -> list[BenchmarkResult]:
        """
        Run cross-framework benchmarks.

        Each framework runs list-serialize (20 items) and create-validate
        sub-benchmarks.  Frameworks not installed produce skipped rows.
        """
        results: list[BenchmarkResult] = []

        results.extend(self._run_django_matt())
        results.extend(self._run_drf())
        results.extend(self._run_django_ninja())
        results.extend(self._run_fastapi())
        results.extend(self._run_starlette())

        return results
