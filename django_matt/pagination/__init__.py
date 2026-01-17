"""
Pagination module for django-matt.

Provides pluggable pagination classes for API responses.
"""

from .base import BasePagination, PaginationResult
from .page_number import PageNumberPagination
from .limit_offset import LimitOffsetPagination
from .cursor import CursorPagination

__all__ = [
    "BasePagination",
    "PaginationResult",
    "PageNumberPagination",
    "LimitOffsetPagination",
    "CursorPagination",
]
