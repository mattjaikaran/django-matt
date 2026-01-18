"""
Pagination module for django-matt.

Provides pluggable pagination classes for API responses.
"""

from .base import BasePagination, PaginationResult
from .cursor import CursorPagination
from .limit_offset import LimitOffsetPagination
from .page_number import PageNumberPagination

__all__ = [
    "BasePagination",
    "CursorPagination",
    "LimitOffsetPagination",
    "PageNumberPagination",
    "PaginationResult",
]
