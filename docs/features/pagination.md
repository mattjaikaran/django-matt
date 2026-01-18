# Pagination & Filtering

Built-in support for pagination, filtering, searching, and ordering.

## Pagination

### PageNumberPagination

Standard page-based pagination:

```python
from django_matt.pagination import PageNumberPagination

class ProductViewSet(APIViewSet):
    pagination_class = PageNumberPagination

    list = ListView()

# Request: GET /products?page=2&page_size=20
# Response:
{
    "items": [...],
    "total": 150,
    "page": 2,
    "page_size": 20,
    "pages": 8
}
```

### LimitOffsetPagination

Offset-based pagination:

```python
from django_matt.pagination import LimitOffsetPagination

class ProductViewSet(APIViewSet):
    pagination_class = LimitOffsetPagination

    list = ListView()

# Request: GET /products?limit=20&offset=40
# Response:
{
    "items": [...],
    "total": 150,
    "limit": 20,
    "offset": 40
}
```

### CursorPagination

Efficient cursor-based pagination for large datasets:

```python
from django_matt.pagination import CursorPagination

class ProductViewSet(APIViewSet):
    pagination_class = CursorPagination
    ordering = "-created_at"

    list = ListView()

# Request: GET /products?cursor=cD0yMDIzLTAxLTAx
# Response:
{
    "items": [...],
    "next_cursor": "cD0yMDIzLTAxLTAy",
    "previous_cursor": null
}
```

## Filtering

### Basic Filtering

```python
from django_matt.filtering import DjangoFilterBackend

class ProductViewSet(APIViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "is_active", "brand"]

    list = ListView()

# Request: GET /products?category=1&is_active=true
```

### FilterSet

Declarative filter definitions:

```python
from django_matt.filtering import FilterSet, CharFilter, IntegerFilter, BooleanFilter

class ProductFilter(FilterSet):
    name = CharFilter(lookup_expr="icontains")
    min_price = IntegerFilter(field_name="price", lookup_expr="gte")
    max_price = IntegerFilter(field_name="price", lookup_expr="lte")
    in_stock = BooleanFilter(field_name="stock", lookup_expr="gt", value=0)

    class Meta:
        model = Product
        fields = ["category", "brand"]

class ProductViewSet(APIViewSet):
    filterset_class = ProductFilter
    list = ListView()

# Request: GET /products?name=shirt&min_price=10&max_price=50
```

### Filter Types

```python
from django_matt.filtering import (
    CharFilter,        # Text fields
    IntegerFilter,     # Integer fields
    BooleanFilter,     # Boolean fields
    DateFilter,        # Date fields
    DateTimeFilter,    # DateTime fields
    InFilter,          # IN queries (?ids=1,2,3)
    RangeFilter,       # Range queries
)

class ProductFilter(FilterSet):
    name = CharFilter(lookup_expr="icontains")
    price = RangeFilter()  # ?price_min=10&price_max=50
    categories = InFilter(field_name="category_id")  # ?categories=1,2,3
    created_after = DateFilter(field_name="created_at", lookup_expr="gte")
```

## Searching

### Basic Search

```python
from django_matt.filtering import SearchBackend

class ProductViewSet(APIViewSet):
    filter_backends = [SearchBackend]
    search_fields = ["name", "description"]

    list = ListView()

# Request: GET /products?search=wireless headphones
```

### Search Prefixes

```python
search_fields = [
    "^name",        # Starts with
    "=sku",         # Exact match
    "@description", # Full-text search (PostgreSQL)
    "category__name",  # Related field
]
```

### PostgreSQL Full-Text Search

```python
from django_matt.filtering import PostgresSearchBackend

class ProductViewSet(APIViewSet):
    filter_backends = [PostgresSearchBackend]
    search_fields = ["name", "description"]
    search_vector_field = "search_vector"  # Pre-computed SearchVector

    list = ListView()
```

## Ordering

```python
from django_matt.filtering import OrderingBackend

class ProductViewSet(APIViewSet):
    filter_backends = [OrderingBackend]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]  # Default ordering

    list = ListView()

# Request: GET /products?ordering=-price,name
```

## Combined Example

```python
from django_matt.views import APIViewSet, ListView
from django_matt.pagination import PageNumberPagination
from django_matt.filtering import (
    DjangoFilterBackend,
    SearchBackend,
    OrderingBackend,
    FilterSet,
    CharFilter,
    IntegerFilter,
)

class ProductFilter(FilterSet):
    name = CharFilter(lookup_expr="icontains")
    min_price = IntegerFilter(field_name="price", lookup_expr="gte")
    max_price = IntegerFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ["category", "brand", "is_active"]

class ProductViewSet(APIViewSet):
    model = Product
    pagination_class = PageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchBackend, OrderingBackend]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]

    list = ListView()

# Combined request:
# GET /products?category=1&min_price=10&search=wireless&ordering=-price&page=2
```
