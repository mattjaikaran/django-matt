"""
Filtering module for django-matt.

Provides pluggable filtering backends and filter classes for API queries.
"""

from .base import BaseFilterBackend
from .backends import DjangoFilterBackend, SearchBackend, OrderingBackend
from .filterset import FilterSet, FilterSetMeta
from .filters import (
    Filter,
    CharFilter,
    IntegerFilter,
    BooleanFilter,
    DateFilter,
    DateTimeFilter,
    UUIDFilter,
    ChoiceFilter,
    MultipleChoiceFilter,
    RangeFilter,
    NumberRangeFilter,
    DateRangeFilter,
    InFilter,
    ModelChoiceFilter,
)
from .search import (
    BaseSearchEngine,
    PostgresSearchBackend,
    ElasticsearchEngine,
    MeilisearchEngine,
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
