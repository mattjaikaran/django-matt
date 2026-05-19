# Query Optimization

Django Matt provides tools for analyzing Django ORM queries and automatically optimizing them to prevent N+1 query problems.

## QueryAnalyzer

The `QueryAnalyzer` class provides detailed analysis of querysets and generates specific optimization recommendations.

### Basic Analysis

```python
from django_matt.utils.performance import query_analyzer

# Analyze any queryset
analysis = query_analyzer.analyze_queryset(Order.objects.all())

# View results
print(f"Model: {analysis['model']}")
print(f"Current optimizations: {analysis['current_optimizations']}")
print(f"Relations found: {analysis['relations']}")
print(f"Suggestions: {analysis['suggestions']}")
print(f"Query count estimate: {analysis['query_count_estimate']}")
```

### Analysis Output Structure

```python
{
    "model": "Order",
    "current_optimizations": {
        "select_related": [],      # Already applied
        "prefetch_related": []     # Already applied
    },
    "relations": {
        "foreign_keys": ["customer", "product", "shipping_address"],
        "many_to_many": ["tags", "discounts"],
        "reverse_relations": ["items", "payments", "notes"]
    },
    "suggestions": [
        {
            "type": "select_related",
            "fields": ["customer", "product", "shipping_address"],
            "reason": "Foreign key fields not using select_related may cause N+1 queries",
            "fix": ".select_related('customer', 'product', 'shipping_address')"
        },
        {
            "type": "prefetch_related",
            "fields": ["tags", "discounts"],
            "reason": "Many-to-many fields should use prefetch_related",
            "fix": ".prefetch_related('tags', 'discounts')"
        },
        {
            "type": "prefetch_related",
            "fields": ["items", "payments", "notes"],
            "reason": "Reverse relations may benefit from prefetch_related if accessed",
            "fix": ".prefetch_related('items', 'payments', 'notes')",
            "conditional": True  # Only if you access these
        }
    ],
    "query_count_estimate": {
        "without_optimization": 501,  # 1 + N * (FK count + M2M count)
        "with_optimization": 4,       # 1 base + prefetch queries
        "potential_savings": 497
    }
}
```

## optimize_queryset

Automatically apply optimization based on model relations.

### Basic Usage

```python
from django_matt.utils.performance import optimize_queryset

# Before: Unoptimized queryset
orders = Order.objects.all()

# After: Automatically optimized
orders = optimize_queryset(Order.objects.all())
# Equivalent to:
# Order.objects.select_related('customer', 'product', 'shipping_address')
#              .prefetch_related('tags', 'discounts')
```

### With Reverse Relations

```python
# Include reverse relations (be careful with large datasets)
orders = optimize_queryset(
    Order.objects.all(),
    include_reverse=True
)
# Also adds prefetch_related for: items, payments, notes
```

### How It Works

```python
def optimize_queryset(queryset, include_reverse: bool = False):
    """
    Automatically optimize a queryset with select_related and prefetch_related.
    """
    model = queryset.model
    meta = model._meta

    select_fields = []
    prefetch_fields = []

    for field in meta.get_fields():
        if isinstance(field, ForeignKey):
            select_fields.append(field.name)
        elif isinstance(field, ManyToManyField):
            prefetch_fields.append(field.name)
        elif isinstance(field, ManyToOneRel) and include_reverse:
            prefetch_fields.append(field.get_accessor_name())

    if select_fields:
        queryset = queryset.select_related(*select_fields)
    if prefetch_fields:
        queryset = queryset.prefetch_related(*prefetch_fields)

    return queryset
```

## N+1 Detection

### Enable Query Logging

```python
# settings.py
MIDDLEWARE = [
    # ... other middleware
    "django_matt.utils.QueryLoggingMiddleware",
]

# Enable query analysis (development only!)
DJANGO_MATT_QUERY_ANALYSIS_ENABLED = True
```

### Query Logging Middleware

The middleware automatically:

1. Logs all queries during request
2. Adds `X-Django-Matt-Query-Count` header to response
3. Records observations for performance suggestions

### Manual Query Logging

```python
from django_matt.utils.performance import query_analyzer

# Log a query manually
query_analyzer.log_query(
    sql="SELECT * FROM users WHERE id = 1",
    duration=0.005,  # seconds
    params=(1,)
)

# Get logged queries
slow_queries = query_analyzer.get_slow_queries(threshold_ms=100)
duplicates = query_analyzer.get_duplicate_queries()
```

### Query Report

```python
report = query_analyzer.get_report()

# {
#     "total_queries": 45,
#     "total_time_ms": 234.5,
#     "avg_time_ms": 5.2,
#     "min_time_ms": 0.5,
#     "max_time_ms": 45.2,
#     "slow_queries": 3,
#     "duplicate_patterns": 2,
#     "potential_n_plus_1": 1,
#     "duplicates": {
#         "SELECT * FROM users WHERE id = ?": 25
#     }
# }
```

## PerformanceSuggester

Get actionable recommendations based on runtime observations.

### Recording Observations

```python
from django_matt.utils.performance import performance_suggester

# Record serialization observation
performance_suggester.observe("serialization", {
    "size": 150000,  # bytes
    "time_ms": 75,
})

# Record query observation
performance_suggester.observe("query", {
    "count": 25,
})

# Record cache observation
performance_suggester.observe("cache", {
    "hit": False,
})
```

### Getting Suggestions

```python
suggestions = performance_suggester.get_suggestions()

for suggestion in suggestions:
    print(f"[{suggestion['priority']}] {suggestion['category']}")
    print(f"  {suggestion['title']}")
    print(f"  {suggestion['description']}")
    for rec in suggestion['recommendations']:
        print(f"    - {rec}")
```

### Example Suggestions

```python
[
    {
        "category": "serialization",
        "priority": "high",
        "title": "Large response payloads detected",
        "description": "Average response size is 150.0KB",
        "recommendations": [
            "Use pagination to limit response size",
            "Consider using StreamingJsonResponse for large datasets",
            "Implement field selection to return only needed fields",
            "Use MessagePack for binary data transfer"
        ]
    },
    {
        "category": "database",
        "priority": "high",
        "title": "High query count per request",
        "description": "Average of 25.0 queries per request",
        "recommendations": [
            "Use select_related() for foreign key relationships",
            "Use prefetch_related() for many-to-many relationships",
            "Consider using optimize_queryset() helper",
            "Review for N+1 query patterns"
        ]
    },
    {
        "category": "dependencies",
        "priority": "low",
        "title": "MessagePack not available",
        "description": "Binary serialization unavailable for internal/service endpoints",
        "recommendations": [
            "Install msgpack for binary serialization: uv add msgpack",
            "Useful for service-to-service communication (~30% smaller payload)"
        ]
    }
    # Note: "No fast JSON library" will never appear — orjson is a base dependency
]
```

### Summary Report

```python
summary = performance_suggester.get_summary()

# {
#     "total_observations": 1500,
#     "categories": {
#         "serialization": 500,
#         "query": 500,
#         "cache": 500
#     },
#     "suggestions": [...],
#     "libraries": {
#         "orjson": True,   # always True — base dependency
#         "msgpack": True   # optional — True if uv add msgpack was run
#     }
# }
```

## Integration Examples

### In Controllers

```python
from django_matt import APIController
from django_matt.utils.performance import optimize_queryset, query_analyzer

@api.controller("/orders")
class OrderController(APIController):

    @api.get("/")
    async def list_orders(self, request):
        # Analyze in development
        if settings.DEBUG:
            analysis = query_analyzer.analyze_queryset(Order.objects.all())
            if analysis['suggestions']:
                print("Optimization suggestions:")
                for s in analysis['suggestions']:
                    print(f"  {s['fix']}")

        # Apply optimizations
        orders = optimize_queryset(Order.objects.all())
        return orders
```

### In CRUD Controllers

```python
from django_matt import CRUDController

class ProductController(CRUDController):
    model = Product
    auto_optimize = True  # Enable automatic query optimization

    # Or specify explicitly
    select_related = ['category', 'brand']
    prefetch_related = ['tags', 'images', 'variants']
```

### In Middleware

```python
class OptimizationLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Clear logs
        query_analyzer.clear_log()

        response = self.get_response(request)

        # Check for issues
        report = query_analyzer.get_report()
        if report['total_queries'] > 20:
            logger.warning(f"High query count: {report['total_queries']}")
        if report['potential_n_plus_1'] > 0:
            logger.warning(f"Potential N+1 detected: {report['duplicates']}")

        return response
```

## Configuration

```python
# settings.py

# Enable query analysis (development only)
DJANGO_MATT_QUERY_ANALYSIS_ENABLED = DEBUG

# Enable performance suggestions
DJANGO_MATT_SUGGESTIONS_ENABLED = DEBUG

# Enable benchmark timing
DJANGO_MATT_BENCHMARK_ENABLED = False
```

## Best Practices

1. **Analyze before optimizing**: Use `analyze_queryset` to understand what's needed
2. **Don't over-optimize**: Only prefetch relations you actually access
3. **Use in development**: Enable logging/suggestions in dev, disable in production
4. **Monitor continuously**: Check query counts in response headers
5. **Set alerts**: Warn when query count exceeds thresholds
