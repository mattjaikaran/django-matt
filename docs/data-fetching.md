# Data Fetching

Django Matt provides multiple approaches for fetching data in your API views.

## QuerySet Operations

```python
from django_matt.core import APIController

class ProductController(APIController):
    @api.get("/")
    async def list(self, request):
        # Basic query
        products = [p async for p in Product.objects.all()]

        # Filtering
        products = await Product.objects.filter(is_active=True)

        # Ordering
        products = await Product.objects.order_by("-created_at")

        # Pagination
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 20))
        offset = (page - 1) * limit

        products = [p async for p in Product.objects.all()][offset:offset + limit]

        return products
```

## Query Optimization

### Automatic Optimization

Django Matt can auto-optimize querysets:

```python
from django_matt.utils import optimize_queryset

products = optimize_queryset(Product.objects.all())
# Automatically adds select_related/prefetch_related for foreign keys
```

### Manual Optimization

```python
# Select related (ForeignKey, OneToOne)
products = Product.objects.select_related("category", "brand")

# Prefetch related (ManyToMany, reverse ForeignKey)
products = Product.objects.prefetch_related("tags", "reviews")
```

## Frontend Integration

For frontend data fetching patterns:

- **React** - Use TanStack Query with generated hooks
- **Svelte** - Use generated stores with fetch
- **Axios** - Generated API client

See [Code Generation](./codegen/overview.md) for auto-generated hooks and API clients.

## Related Documentation

- [Views](./features/views.md) - CRUD views and ViewSets
- [Pagination](./features/pagination.md) - Pagination classes
- [Filtering](./features/pagination.md#filtering) - Filter backends
- [Performance](./performance/optimization.md) - Query optimization
- [Code Generation](./codegen/overview.md) - Generated hooks and clients
