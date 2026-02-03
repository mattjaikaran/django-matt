# Database Optimization

Django Matt provides tools for analyzing and optimizing database queries, including N+1 detection and automatic query optimization.

## Query Analyzer

The `QueryAnalyzer` class analyzes querysets and provides optimization suggestions.

### Analyzing a Queryset

```python
from django_matt.utils.performance import query_analyzer

# Analyze a queryset
analysis = query_analyzer.analyze_queryset(Order.objects.all())

print(f"Model: {analysis['model']}")
print(f"Foreign keys: {analysis['relations']['foreign_keys']}")
print(f"Many-to-many: {analysis['relations']['many_to_many']}")

for suggestion in analysis['suggestions']:
    print(f"\n{suggestion['type']}: {suggestion['fields']}")
    print(f"  Reason: {suggestion['reason']}")
    print(f"  Fix: {suggestion['fix']}")
```

### Sample Analysis Output

```python
{
    "model": "Order",
    "current_optimizations": {
        "select_related": [],
        "prefetch_related": []
    },
    "relations": {
        "foreign_keys": ["customer", "product"],
        "many_to_many": ["tags"],
        "reverse_relations": ["order_items", "payments"]
    },
    "suggestions": [
        {
            "type": "select_related",
            "fields": ["customer", "product"],
            "reason": "Foreign key fields not using select_related may cause N+1 queries",
            "fix": ".select_related('customer', 'product')"
        },
        {
            "type": "prefetch_related",
            "fields": ["tags"],
            "reason": "Many-to-many fields should use prefetch_related",
            "fix": ".prefetch_related('tags')"
        }
    ],
    "query_count_estimate": {
        "without_optimization": 201,  # 1 + 100*2 for foreign keys
        "with_optimization": 2,        # 1 base + 1 prefetch
        "potential_savings": 199
    }
}
```

## Automatic Query Optimization

### Using optimize_queryset

Automatically add `select_related` and `prefetch_related`:

```python
from django_matt.utils.performance import optimize_queryset

# Before: May cause N+1 queries
orders = Order.objects.all()

# After: Optimized with relations
orders = optimize_queryset(Order.objects.all())

# Equivalent to:
# Order.objects.select_related('customer', 'product').prefetch_related('tags')
```

### Include Reverse Relations

```python
# Include reverse relations in prefetch
orders = optimize_queryset(
    Order.objects.all(),
    include_reverse=True
)

# Adds prefetch_related for: order_items, payments, etc.
```

## N+1 Query Detection

### QueryLoggingMiddleware

Enable query logging to detect N+1 patterns:

```python
# settings.py
MIDDLEWARE = [
    # ...
    "django_matt.utils.QueryLoggingMiddleware",
]

DJANGO_MATT_QUERY_ANALYSIS_ENABLED = True  # Only in development!
```

### Viewing Query Reports

```python
from django_matt.utils.performance import query_analyzer

# After request processing
report = query_analyzer.get_report()

print(f"Total queries: {report['total_queries']}")
print(f"Total time: {report['total_time_ms']:.2f}ms")
print(f"Slow queries: {report['slow_queries']}")
print(f"Potential N+1: {report['potential_n_plus_1']}")

# View duplicate queries (N+1 indicators)
for sql, count in report['duplicates'].items():
    if count > 5:
        print(f"Query executed {count} times: {sql[:100]}...")
```

### Finding Slow Queries

```python
# Get queries exceeding threshold
slow_queries = query_analyzer.get_slow_queries(threshold_ms=100)

for query in slow_queries:
    print(f"Duration: {query['duration_ms']:.2f}ms")
    print(f"SQL: {query['sql'][:200]}...")
```

### Finding Duplicate Queries

```python
# Find repeated queries (N+1 pattern)
duplicates = query_analyzer.get_duplicate_queries()

for sql, count in duplicates.items():
    print(f"Executed {count} times: {sql}")
```

## Common N+1 Patterns

### Pattern 1: Accessing Foreign Keys

```python
# Bad: N+1 queries
orders = Order.objects.all()
for order in orders:
    print(order.customer.name)  # Query per order!

# Good: Single query
orders = Order.objects.select_related('customer')
for order in orders:
    print(order.customer.name)  # No additional queries
```

### Pattern 2: Accessing Many-to-Many

```python
# Bad: N+1 queries
products = Product.objects.all()
for product in products:
    print(product.categories.all())  # Query per product!

# Good: Two queries total
products = Product.objects.prefetch_related('categories')
for product in products:
    print(product.categories.all())  # No additional queries
```

### Pattern 3: Reverse Relations

```python
# Bad: N+1 queries
users = User.objects.all()
for user in users:
    print(user.orders.count())  # Query per user!

# Good: Annotate counts
from django.db.models import Count

users = User.objects.annotate(order_count=Count('orders'))
for user in users:
    print(user.order_count)  # No additional queries
```

### Pattern 4: Nested Relations

```python
# Bad: Multiple N+1 levels
orders = Order.objects.all()
for order in orders:
    for item in order.items.all():  # N queries
        print(item.product.name)     # N*M queries!

# Good: Prefetch with nested
from django.db.models import Prefetch

orders = Order.objects.prefetch_related(
    Prefetch(
        'items',
        queryset=OrderItem.objects.select_related('product')
    )
)
```

## Query Optimization Strategies

### 1. Only Select Needed Fields

```python
# Bad: Select all columns
users = User.objects.all()

# Good: Select only needed columns
users = User.objects.only('id', 'username', 'email')

# Or using values
users = User.objects.values('id', 'username', 'email')
```

### 2. Use Aggregations

```python
# Bad: Fetch all then count in Python
orders = list(Order.objects.all())
total = sum(o.total for o in orders)

# Good: Database aggregation
from django.db.models import Sum

total = Order.objects.aggregate(total=Sum('total'))['total']
```

### 3. Use Bulk Operations

```python
# Bad: Individual inserts
for item in items:
    Product.objects.create(**item)  # N queries

# Good: Bulk insert
Product.objects.bulk_create([
    Product(**item) for item in items
])  # 1 query
```

### 4. Use Database Indexes

```python
# models.py
class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)

    class Meta:
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['status']),
        ]
```

### 5. Use Database-Specific Features

```python
# PostgreSQL: Use DISTINCT ON
orders = Order.objects.order_by('customer_id', '-created_at').distinct('customer_id')

# Use raw SQL for complex queries
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT customer_id, SUM(total)
        FROM orders
        WHERE created_at > %s
        GROUP BY customer_id
        HAVING SUM(total) > %s
    """, [start_date, min_total])
```

## Integration with Controllers

### Auto-Optimization in CRUDController

```python
from django_matt import CRUDController

class ProductController(CRUDController):
    model = Product
    auto_optimize = True  # Automatically optimize queries

    # Customize optimization
    select_related = ['category', 'brand']
    prefetch_related = ['tags', 'images']
```

### Manual Optimization

```python
from django_matt.utils.performance import optimize_queryset

@api.get("/orders")
async def list_orders(request):
    # Analyze first (development)
    analysis = query_analyzer.analyze_queryset(Order.objects.all())
    print(analysis['suggestions'])

    # Apply optimization
    orders = optimize_queryset(Order.objects.all())
    return orders
```

## Performance Benchmarks

Typical query performance improvements:

| Scenario | Without Optimization | With Optimization | Improvement |
|----------|---------------------|-------------------|-------------|
| 100 orders + customer | 101 queries / 500ms | 1 query / 5ms | 100x |
| 100 products + 5 tags each | 501 queries / 2000ms | 2 queries / 10ms | 200x |
| Nested 3-level relations | 1000+ queries | 3-4 queries | 300x+ |

### Run Database Benchmarks

```bash
python manage.py benchmark --scenario database
```

## Best Practices

### 1. Always Profile First

```python
# Enable query logging in development
DJANGO_MATT_QUERY_ANALYSIS_ENABLED = DEBUG

# Check query count after requests
report = query_analyzer.get_report()
if report['total_queries'] > 10:
    print("Warning: High query count")
```

### 2. Use Pagination

```python
# Bad: Load all records
products = Product.objects.all()

# Good: Paginate
@api.get("/products")
async def list_products(request, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    products = Product.objects.all()[offset:offset + limit]
    total = await Product.objects.count()
    return {
        "items": products,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }
```

### 3. Use Caching for Expensive Queries

```python
from django_matt.utils.performance import cache_manager

@cache_manager.cache_result(timeout=300)
async def get_product_stats():
    return await Product.objects.aggregate(
        total=Count('id'),
        avg_price=Avg('price'),
        total_revenue=Sum('sales__total'),
    )
```

### 4. Monitor in Production

```python
# Add timing to responses
MIDDLEWARE = [
    "django_matt.utils.BenchmarkMiddleware",
]

# Response headers include:
# X-Django-Matt-Timing: 45.23ms
# X-Django-Matt-Query-Count: 3
```

### 5. Use Database Connection Pooling

```python
# settings.py (PostgreSQL with pgbouncer)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        'HOST': 'pgbouncer',  # Connection pool
        'PORT': '6432',
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}
```

## Troubleshooting

### High Query Count

1. Enable query logging:
   ```python
   DJANGO_MATT_QUERY_ANALYSIS_ENABLED = True
   ```

2. Check for N+1:
   ```python
   duplicates = query_analyzer.get_duplicate_queries()
   ```

3. Add optimizations:
   ```python
   queryset = optimize_queryset(queryset)
   ```

### Slow Queries

1. Find slow queries:
   ```python
   slow = query_analyzer.get_slow_queries(threshold_ms=100)
   ```

2. Add indexes:
   ```python
   class Meta:
       indexes = [models.Index(fields=['slow_field'])]
   ```

3. Use `EXPLAIN ANALYZE`:
   ```python
   print(queryset.explain(analyze=True))
   ```

### Memory Issues

For large datasets, use iteration:

```python
# Bad: Load all into memory
products = list(Product.objects.all())

# Good: Use iterator
for product in Product.objects.iterator(chunk_size=1000):
    process(product)

# Good: Use pagination
for page in paginate(Product.objects.all(), page_size=1000):
    process_batch(page)
```
