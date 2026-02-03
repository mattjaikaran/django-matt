# Pagination

Django-matt provides three pagination styles for handling large datasets efficiently. Each style has different trade-offs between flexibility and performance.

## Overview

| Style | URL Example | Best For |
|-------|-------------|----------|
| Page Number | `?page=2&page_size=25` | Traditional pagination with page controls |
| Limit/Offset | `?limit=25&offset=50` | API clients, infinite scroll |
| Cursor | `?cursor=abc123` | Real-time feeds, large datasets |

## Quick Start

```python
from django_matt.views import ListView
from django_matt.pagination import (
    PageNumberPagination,
    LimitOffsetPagination,
    CursorPagination,
)

class ProductViewSet(APIViewSet):
    model = Product

    # Built-in pagination (page number style)
    list_products = ListView(
        pagination=True,
        page_size=20,
        max_page_size=100,
    )

    # Custom pagination class
    list_with_cursor = ListView(
        path="stream",
        pagination_class=CursorPagination(ordering="-created_at"),
    )
```

---

## Page Number Pagination

Traditional pagination using page numbers.

### Configuration

```python
from django_matt.pagination import PageNumberPagination

pagination = PageNumberPagination(
    page_size=25,              # Default items per page
    max_page_size=100,         # Maximum allowed page size
    page_query_param="page",   # Query param for page number
    page_size_query_param="page_size",  # Query param for page size
)
```

### Usage

```python
class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView(
        pagination_class=PageNumberPagination(page_size=25),
    )
```

### Request

```
GET /api/products?page=2&page_size=25
```

### Response

```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 25,
  "pages": 6,
  "has_next": true,
  "has_previous": true
}
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_size` | `int` | `20` | Default items per page |
| `max_page_size` | `int` | `100` | Maximum allowed page size |
| `page_query_param` | `str` | `"page"` | Query param name for page |
| `page_size_query_param` | `str` | `"page_size"` | Query param name for size |

---

## Limit/Offset Pagination

Simple offset-based pagination, common in SQL-like APIs.

### Configuration

```python
from django_matt.pagination import LimitOffsetPagination

pagination = LimitOffsetPagination(
    default_limit=25,          # Default limit
    max_limit=100,             # Maximum allowed limit
    limit_query_param="limit", # Query param for limit
    offset_query_param="offset",  # Query param for offset
)
```

### Usage

```python
class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView(
        pagination_class=LimitOffsetPagination(default_limit=25),
    )
```

### Request

```
GET /api/products?limit=25&offset=50
```

### Response

```json
{
  "items": [...],
  "total": 150,
  "limit": 25,
  "offset": 50,
  "has_next": true,
  "has_previous": true
}
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `default_limit` | `int` | `20` | Default items to return |
| `max_limit` | `int` | `100` | Maximum allowed limit |
| `limit_query_param` | `str` | `"limit"` | Query param for limit |
| `offset_query_param` | `str` | `"offset"` | Query param for offset |

### Pros and Cons

**Pros:**
- Simple and intuitive
- Can jump to any position
- Familiar to API consumers

**Cons:**
- Less efficient for large offsets (database must scan skipped rows)
- Items can be skipped or duplicated if data changes between requests

---

## Cursor Pagination

Cursor-based pagination for efficient traversal of large or changing datasets.

### Configuration

```python
from django_matt.pagination import CursorPagination

pagination = CursorPagination(
    page_size=25,
    ordering="-created_at",     # Field(s) to order by
    cursor_query_param="cursor",
    cursor_secret="optional-secret",  # For signed cursors
)
```

### Usage

```python
class ProductViewSet(APIViewSet):
    model = Product

    # Real-time feed with cursor pagination
    feed = ListView(
        path="feed",
        pagination_class=CursorPagination(
            ordering="-created_at",
            page_size=50,
        ),
    )

    # Multi-field ordering
    by_price = ListView(
        path="by-price",
        pagination_class=CursorPagination(
            ordering=["price", "-created_at"],
        ),
    )
```

### Request

```
# First page (no cursor)
GET /api/products/feed

# Next page (with cursor from previous response)
GET /api/products/feed?cursor=eyJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNSJ9
```

### Response

```json
{
  "items": [...],
  "page_size": 50,
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNSJ9",
  "previous_cursor": null,
  "has_next": true,
  "has_previous": false
}
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_size` | `int` | `20` | Items per page |
| `ordering` | `str \| list` | `"pk"` | Ordering field(s) |
| `cursor_query_param` | `str` | `"cursor"` | Query param name |
| `cursor_secret` | `str` | `None` | Secret for signed cursors |

### How It Works

1. Results are ordered by the specified field(s)
2. The cursor encodes the position (last seen value)
3. Next page fetches items after that position
4. Works efficiently with database indexes

### Pros and Cons

**Pros:**
- Consistent performance regardless of position
- Handles insertions/deletions without skipping items
- Perfect for real-time feeds and infinite scroll
- Secure (doesn't expose raw IDs)

**Cons:**
- Cannot jump to arbitrary pages
- Requires consistent ordering
- More complex implementation

---

## Using with Views

### Built-in Pagination

ListView has built-in simple pagination:

```python
class ProductViewSet(APIViewSet):
    model = Product

    # Use built-in pagination
    list_products = ListView(
        pagination=True,        # Enable pagination
        page_size=20,           # Default page size
        max_page_size=100,      # Maximum allowed
    )

    # Disable pagination for small datasets
    list_categories = ListView(
        path="categories",
        pagination=False,
    )
```

### Custom Pagination Class

Use a specific pagination class:

```python
from django_matt.pagination import CursorPagination

class ProductViewSet(APIViewSet):
    model = Product

    # Define pagination at viewset level
    pagination_class = CursorPagination(ordering="-created_at")

    # All ListViews will use cursor pagination
    list_products = ListView()
    list_featured = ListView(path="featured")

    # Override for specific view
    list_by_price = ListView(
        path="by-price",
        pagination_class=PageNumberPagination(page_size=50),
    )
```

---

## Custom Pagination

Create custom pagination by extending `BasePagination`:

```python
from django_matt.pagination import BasePagination
from django.db.models import QuerySet
from django.http import HttpRequest

class KeysetPagination(BasePagination):
    """
    Keyset pagination using explicit ID markers.
    """

    page_size = 25
    id_param = "after_id"

    def paginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        self._request = request
        self._page_size = self.get_page_size(request)

        after_id = request.GET.get(self.id_param)
        if after_id:
            queryset = queryset.filter(id__gt=after_id)

        # Fetch one extra to check for next page
        results = list(queryset[:self._page_size + 1])
        self._has_next = len(results) > self._page_size
        self._results = results[:self._page_size]

        if self._results:
            self._last_id = self._results[-1].id
        else:
            self._last_id = None

        return self._results

    def get_paginated_response(self, data: list) -> dict:
        return {
            "items": data,
            "page_size": self._page_size,
            "after_id": self._last_id,
            "has_next": self._has_next,
        }
```

---

## Async Pagination

All pagination classes support async operations:

```python
class CursorPagination(BasePagination):
    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> list:
        """Async pagination for cursor-based traversal."""
        # Cursor pagination already evaluates queryset
        return self.paginate_queryset(queryset, request)

class PageNumberPagination(BasePagination):
    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """Async version with async count."""
        self._request = request
        self._count = await self.aget_count(queryset)  # Async count
        self._page = self.get_page_number(request)
        self._page_size = self.get_page_size(request)

        # ... rest of logic

        offset = (self._page - 1) * self._page_size
        return queryset[offset : offset + self._page_size]
```

---

## Best Practices

### Choose the Right Style

| Use Case | Recommended Style |
|----------|-------------------|
| Admin interfaces | Page Number |
| Traditional websites | Page Number |
| Mobile apps | Limit/Offset or Cursor |
| Infinite scroll | Cursor |
| Real-time feeds | Cursor |
| Large datasets (100k+) | Cursor |
| Need random access | Page Number or Limit/Offset |

### Optimize for Performance

```python
# Add index on ordering field
class Product(models.Model):
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at', 'id']),
        ]

# Use cursor pagination for large tables
pagination = CursorPagination(
    ordering=["-created_at", "id"],  # Unique ordering
    page_size=50,
)
```

### Handle Edge Cases

```python
class ProductViewSet(APIViewSet):
    list_products = ListView(
        pagination=True,
        page_size=25,
        max_page_size=100,  # Prevent abuse
    )

    def get_queryset(self, request=None):
        # Always order for consistent pagination
        return self.model.objects.all().order_by("-created_at", "id")
```

### Security

```python
# Use signed cursors in production
pagination = CursorPagination(
    ordering="-created_at",
    cursor_secret=settings.SECRET_KEY,
)
```

---

## Response Schemas

Define Pydantic schemas for paginated responses:

```python
from pydantic import BaseModel, Generic
from typing import TypeVar

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int | None = None
    page_size: int | None = None
    pages: int | None = None
    has_next: bool = False
    has_previous: bool = False

# Usage
class ProductList(PaginatedResponse[ProductSchema]):
    pass
```
