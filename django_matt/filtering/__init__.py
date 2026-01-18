"""
Filtering module for django-matt.

Provides pluggable filtering backends and filter classes for API queries.
"""

from .backends import DjangoFilterBackend, OrderingBackend, SearchBackend
from .base import BaseFilterBackend
from .filters import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFilter,
    DateRangeFilter,
    DateTimeFilter,
    Filter,
    InFilter,
    IntegerFilter,
    ModelChoiceFilter,
    MultipleChoiceFilter,
    NumberRangeFilter,
    RangeFilter,
    UUIDFilter,
)
from .filterset import FilterSet, FilterSetMeta
from .search import (
    BaseSearchEngine,
    ElasticsearchEngine,
    MeilisearchEngine,
    PostgresSearchBackend,
    SearchEngineBackend,
)

__all__ = [
    # Backends
    "BaseFilterBackend",
    "DjangoFilterBackend",
    "SearchBackend",
    "OrderingBackend",
    # FilterSet
    "FilterSet",
    "FilterSetMeta",
    # Filters
    "Filter",
    "CharFilter",
    "IntegerFilter",
    "BooleanFilter",
    "DateFilter",
    "DateTimeFilter",
    "UUIDFilter",
    "ChoiceFilter",
    "MultipleChoiceFilter",
    "RangeFilter",
    "NumberRangeFilter",
    "DateRangeFilter",
    "InFilter",
    "ModelChoiceFilter",
    # Search Engines
    "BaseSearchEngine",
    "PostgresSearchBackend",
    "ElasticsearchEngine",
    "MeilisearchEngine",
    "SearchEngineBackend",
]
