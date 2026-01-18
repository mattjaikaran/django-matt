# Query Optimization

Automatic query optimization and N+1 detection.

## Auto Optimization

```python
from django_matt import CRUDController

class ProductController(CRUDController):
    model = Product
    auto_optimize = True  # Auto-detect relations
```

## Manual Optimization

```python
from django_matt.utils import optimize_queryset

users = optimize_queryset(User.objects.all())
# Automatically adds select_related/prefetch_related
```

## N+1 Detection

```python
# settings.py
MIDDLEWARE = [
    "django_matt.utils.QueryLoggingMiddleware",
]

DJANGO_MATT = {
    "N1_DETECTION_ENABLED": True,
}
```
