# Filtering

Django-matt provides a powerful filtering system with filter backends, declarative FilterSets, and search capabilities.

## Overview

Filtering can be configured in three ways:

1. **Simple filtering**: Using `filter_fields` on ListView
2. **Filter backends**: Pluggable backends for filtering, search, and ordering
3. **FilterSet classes**: Declarative filter definitions

## Quick Start

```python
from django_matt.views import ListView
from django_matt.filtering import DjangoFilterBackend, SearchBackend, OrderingBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [DjangoFilterBackend(), SearchBackend(), OrderingBackend()]
    filter_fields = ["category", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = "-created_at"

    list_products = ListView()
```

Query examples:
```
GET /api/products?category=electronics&is_active=true
GET /api/products?search=laptop
GET /api/products?ordering=-price
```

---

## Simple Filtering

The simplest approach using `filter_fields`:

```python
class ProductViewSet(APIViewSet):
    model = Product

    list_products = ListView(
        filter_fields=["category", "is_active", "brand"],
        search_fields=["name", "description"],
        ordering="-created_at",
    )
```

### Supported Lookups

Standard Django ORM lookups are supported:

| Query Param | Lookup | Example |
|-------------|--------|---------|
| `field` | Exact match | `?category=electronics` |
| `field__icontains` | Case-insensitive contains | `?name__icontains=laptop` |
| `field__gte` | Greater than or equal | `?price__gte=100` |
| `field__lte` | Less than or equal | `?price__lte=500` |
| `field__in` | In list | `?status__in=active,pending` |
| `field__isnull` | Is null | `?deleted_at__isnull=true` |

---

## Filter Backends

### DjangoFilterBackend

Filters based on query parameters:

```python
from django_matt.filtering import DjangoFilterBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [DjangoFilterBackend()]
    filter_fields = ["category", "brand", "is_active"]

    list_products = ListView()
```

Reserved parameters (not treated as filters):
- `page`, `page_size`
- `limit`, `offset`
- `cursor`
- `ordering`, `order_by`
- `search`, `q`
- `format`

### SearchBackend

Full-text search across multiple fields:

```python
from django_matt.filtering import SearchBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [SearchBackend()]
    search_fields = ["name", "description", "sku"]

    list_products = ListView()
```

Query: `GET /api/products?search=laptop keyboard`

#### Search Field Prefixes

| Prefix | Lookup | Example |
|--------|--------|---------|
| (none) | `icontains` | `"name"` - case-insensitive contains |
| `^` | `istartswith` | `"^name"` - starts with |
| `=` | `iexact` | `"=sku"` - exact match |
| `@` | `search` | `"@description"` - PostgreSQL full-text |
| `$` | `iregex` | `"$pattern"` - regex match |

```python
search_fields = [
    "name",           # icontains
    "^title",         # istartswith
    "=sku",           # exact match
    "@description",   # PostgreSQL full-text search
]
```

### OrderingBackend

Sortable fields:

```python
from django_matt.filtering import OrderingBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [OrderingBackend()]
    ordering_fields = ["name", "price", "created_at"]
    ordering = "-created_at"  # Default ordering

    list_products = ListView()
```

Query examples:
```
GET /api/products?ordering=price          # Ascending
GET /api/products?ordering=-price         # Descending
GET /api/products?ordering=-created_at,name  # Multiple fields
```

### Combining Backends

```python
from django_matt.filtering import (
    DjangoFilterBackend,
    SearchBackend,
    OrderingBackend,
)

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [
        DjangoFilterBackend(),
        SearchBackend(),
        OrderingBackend(),
    ]
    filter_fields = ["category", "brand", "price__gte", "price__lte"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = "-created_at"

    list_products = ListView()
```

Combined query:
```
GET /api/products?category=electronics&search=laptop&ordering=-price
```

---

## FilterSet Classes

For complex filtering, use declarative FilterSet classes:

### Basic FilterSet

```python
from django_matt.filtering import FilterSet, CharFilter, BooleanFilter, IntegerFilter

class ProductFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    category = IntegerFilter(field_name='category_id')
    is_active = BooleanFilter()
    min_price = IntegerFilter(field_name='price', lookup_expr='gte')
    max_price = IntegerFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = Product
        fields = ['name', 'category', 'is_active']


class ProductViewSet(APIViewSet):
    model = Product
    filterset_class = ProductFilter

    list_products = ListView()
```

### Auto-Generated Filters

```python
class ProductFilter(FilterSet):
    class Meta:
        model = Product
        fields = '__all__'  # Generate filters for all fields
        exclude = ['description', 'metadata']  # Exclude specific fields
```

### Available Filter Types

| Filter | Description | Example |
|--------|-------------|---------|
| `CharFilter` | String fields | `name = CharFilter(lookup_expr='icontains')` |
| `IntegerFilter` | Integer fields | `quantity = IntegerFilter()` |
| `BooleanFilter` | Boolean fields | `is_active = BooleanFilter()` |
| `DateFilter` | Date fields | `created_at = DateFilter(lookup_expr='gte')` |
| `DateTimeFilter` | DateTime fields | `updated_at = DateTimeFilter()` |
| `UUIDFilter` | UUID fields | `uuid = UUIDFilter()` |
| `ChoiceFilter` | Enum/choice fields | `status = ChoiceFilter(choices=STATUS_CHOICES)` |
| `MultipleChoiceFilter` | Multiple values | `tags = MultipleChoiceFilter()` |
| `InFilter` | IN queries | `ids = InFilter()` |
| `RangeFilter` | Range queries | `price = RangeFilter()` |
| `NumberRangeFilter` | Numeric ranges | `quantity = NumberRangeFilter()` |
| `DateRangeFilter` | Date ranges | `created = DateRangeFilter()` |
| `ModelChoiceFilter` | ForeignKey | `category = ModelChoiceFilter(queryset=...)` |

### Filter Configuration

```python
class ProductFilter(FilterSet):
    # Basic filter
    name = CharFilter()

    # Custom field name
    category = IntegerFilter(field_name='category_id')

    # Custom lookup
    name_contains = CharFilter(field_name='name', lookup_expr='icontains')

    # Required filter
    status = CharFilter(required=True)

    # Exclude instead of filter
    not_category = IntegerFilter(field_name='category_id', exclude=True)

    # Custom method
    has_image = BooleanFilter(method='filter_has_image')

    # With help text
    search = CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Search by name',
        help_text='Case-insensitive search',
    )

    def filter_has_image(self, queryset, field_name, value):
        if value:
            return queryset.exclude(image='')
        return queryset.filter(image='')
```

### Range Filters

```python
from django_matt.filtering import NumberRangeFilter, DateRangeFilter

class ProductFilter(FilterSet):
    price = NumberRangeFilter()  # ?price_min=10&price_max=100
    created = DateRangeFilter(field_name='created_at')

    class Meta:
        model = Product
        fields = []
```

Query: `GET /api/products?price_min=100&price_max=500`

### Multiple Choice Filter

```python
from django_matt.filtering import MultipleChoiceFilter

class ProductFilter(FilterSet):
    status = MultipleChoiceFilter(
        choices=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('archived', 'Archived'),
        ]
    )
```

Query: `GET /api/products?status=draft,published`

---

## Custom Filter Methods

### On FilterSet

```python
class ProductFilter(FilterSet):
    search = CharFilter(method='search_all')
    price_range = CharFilter(method='filter_price_range')

    def search_all(self, queryset, name, value):
        """Search across multiple fields."""
        from django.db.models import Q
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(sku__icontains=value)
        )

    def filter_price_range(self, queryset, name, value):
        """Parse price range like '100-500'."""
        try:
            min_price, max_price = value.split('-')
            return queryset.filter(
                price__gte=int(min_price),
                price__lte=int(max_price),
            )
        except ValueError:
            return queryset

    class Meta:
        model = Product
        fields = []
```

### Custom Filter Backend

```python
from django_matt.filtering import BaseFilterBackend

class TenantFilterBackend(BaseFilterBackend):
    """Filter by current user's organization."""

    def filter_queryset(self, request, queryset, view=None):
        if hasattr(request, 'user') and request.user.is_authenticated:
            org = getattr(request.user, 'organization', None)
            if org:
                return queryset.filter(organization=org)
        return queryset


class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [
        TenantFilterBackend(),  # Always applied first
        DjangoFilterBackend(),
        SearchBackend(),
    ]
```

---

## Advanced Search

### PostgreSQL Full-Text Search

```python
from django_matt.filtering import PostgresSearchBackend

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [PostgresSearchBackend()]
    search_fields = ['name', 'description']

    list_products = ListView()
```

This uses PostgreSQL's `SearchVector` and `SearchQuery` for efficient full-text search.

### Elasticsearch Integration

```python
from django_matt.filtering import ElasticsearchEngine, SearchEngineBackend

# Configure engine
es_engine = ElasticsearchEngine(
    hosts=['localhost:9200'],
    index='products',
)

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [SearchEngineBackend(engine=es_engine)]
    search_fields = ['name', 'description', 'tags']
```

### Meilisearch Integration

```python
from django_matt.filtering import MeilisearchEngine, SearchEngineBackend

meili_engine = MeilisearchEngine(
    host='http://localhost:7700',
    api_key='your-api-key',
    index='products',
)

class ProductViewSet(APIViewSet):
    model = Product
    filter_backends = [SearchEngineBackend(engine=meili_engine)]
```

---

## Complete Example

```python
from django_matt.views import APIViewSet, ListView
from django_matt.filtering import (
    FilterSet,
    CharFilter,
    IntegerFilter,
    BooleanFilter,
    DateFilter,
    ChoiceFilter,
    DjangoFilterBackend,
    SearchBackend,
    OrderingBackend,
)


class ProductFilter(FilterSet):
    """Comprehensive product filtering."""

    # Text search
    name = CharFilter(lookup_expr='icontains')
    sku = CharFilter(lookup_expr='iexact')

    # Category
    category = IntegerFilter(field_name='category_id')
    category_slug = CharFilter(field_name='category__slug')

    # Price range
    min_price = IntegerFilter(field_name='price', lookup_expr='gte')
    max_price = IntegerFilter(field_name='price', lookup_expr='lte')

    # Status
    is_active = BooleanFilter()
    is_featured = BooleanFilter()
    status = ChoiceFilter(choices=[
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ])

    # Dates
    created_after = DateFilter(field_name='created_at', lookup_expr='gte')
    created_before = DateFilter(field_name='created_at', lookup_expr='lte')

    # Custom
    in_stock = BooleanFilter(method='filter_in_stock')
    has_discount = BooleanFilter(method='filter_has_discount')

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock_quantity__gt=0)
        return queryset.filter(stock_quantity=0)

    def filter_has_discount(self, queryset, name, value):
        if value:
            return queryset.filter(discount_percent__gt=0)
        return queryset.filter(discount_percent=0)

    class Meta:
        model = Product
        fields = []


class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"
    tags = ["Products"]

    # Filter configuration
    filter_backends = [
        DjangoFilterBackend(),
        SearchBackend(),
        OrderingBackend(),
    ]
    filterset_class = ProductFilter
    search_fields = [
        "name",
        "description",
        "^sku",  # Starts with
        "@tags__name",  # Full-text on related
    ]
    ordering_fields = ["name", "price", "created_at", "stock_quantity"]
    ordering = "-created_at"

    # Views
    list_products = ListView(
        response_schema=ProductListSchema,
        pagination=True,
        page_size=25,
    )

    # Filtered views
    list_featured = ListView(
        path="featured",
        description="Featured products",
    )

    list_on_sale = ListView(
        path="on-sale",
        description="Products on sale",
    )

    def get_queryset(self, request=None):
        qs = self.model.objects.filter(is_deleted=False)
        return qs.select_related('category').prefetch_related('tags')
```

Example queries:
```bash
# Search with filters
GET /api/products?search=laptop&category=1&min_price=500&max_price=2000

# Sort by price descending
GET /api/products?ordering=-price

# Complex filter
GET /api/products?is_active=true&in_stock=true&status=published&ordering=name

# Featured products
GET /api/products/featured?is_featured=true
```
