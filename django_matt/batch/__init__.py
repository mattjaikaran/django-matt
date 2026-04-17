"""Batch & async request handling — HTTP batch, query coalescing, N+1 detection."""

from django_matt.batch.coalescer import QueryCoalescer
from django_matt.batch.endpoint import BatchEndpoint
from django_matt.batch.n_plus_one import NPlusOneMiddleware, QueryPatternTracker
from django_matt.batch.request import BatchPayload, BatchRequest, BatchResponse
from django_matt.batch.resolver import (
    CyclicDependencyError,
    MissingDependencyError,
    interpolate_value,
    jsonpath_extract,
    topological_sort,
)

__all__ = [
    "BatchEndpoint",
    "BatchPayload",
    "BatchRequest",
    "BatchResponse",
    "CyclicDependencyError",
    "MissingDependencyError",
    "interpolate_value",
    "jsonpath_extract",
    "topological_sort",
    "QueryCoalescer",
    "NPlusOneMiddleware",
    "QueryPatternTracker",
]
