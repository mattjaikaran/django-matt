# Hybrid Properties

Computed properties that work both in Python and at the database level — inspired by SQLAlchemy's `hybrid_property`.

## What Are Hybrid Properties?

A hybrid property is a descriptor that behaves differently depending on how it's accessed:

- **On an instance** (`user.full_name`) — runs Python code
- **On the class / in a query** (`User.objects.filter_hybrid(full_name="John Doe")`) — generates a SQL expression

This means you write the logic once and it works everywhere: in your Python code, in Django ORM queries, and in database-level filtering and ordering.

## SQLAlchemy vs django-matt

### SQLAlchemy

```python
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, String, select

class User(Base):
    __tablename__ = "users"
    first_name = Column(String)
    last_name = Column(String)

    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @full_name.expression
    def full_name(cls):
        return cls.first_name + " " + cls.last_name

# Query
session.query(User).filter(User.full_name == "John Doe")
```

### django-matt

```python
from django.db import models
from django.db.models import Value
from django.db.models.functions import Concat
from django_matt.db.hybrid import hybrid_property, HybridManager

class User(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    objects = HybridManager()

    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @full_name.expression
    def full_name(cls):
        return Concat("first_name", Value(" "), "last_name")

# Query
User.objects.filter_hybrid(full_name="John Doe")
User.objects.order_by_hybrid("full_name")
```

The API is nearly identical. The main differences:
- django-matt uses Django ORM expressions (`Concat`, `F`, `Value`, `Case`) instead of SQLAlchemy column operations
- QuerySet methods are `filter_hybrid()` / `order_by_hybrid()` instead of standard `filter()` / `order_by()`
- You need `HybridManager` on your model (or `HybridQuerySet` as a custom manager)

## Complete Example

```python
from django.db import models
from django.db.models import Case, F, Value, When
from django.db.models.functions import Concat, Now
from django_matt.db.hybrid import hybrid_property, hybrid_method, HybridManager


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = HybridManager()

    @hybrid_property
    def discounted_price(self):
        """Works on instances: product.discounted_price"""
        return self.price * (1 - self.discount_percent / 100)

    @discounted_price.expression
    def discounted_price(cls):
        """Works in queries: Product.objects.filter_hybrid(discounted_price__lt=50)"""
        return F("price") * (1 - F("discount_percent") / 100.0)

    @hybrid_property
    def price_tier(self):
        if self.price >= 100:
            return "premium"
        elif self.price >= 20:
            return "standard"
        return "budget"

    @price_tier.expression
    def price_tier(cls):
        return Case(
            When(price__gte=100, then=Value("premium")),
            When(price__gte=20, then=Value("standard")),
            default=Value("budget"),
        )


# Instance usage
product = Product.objects.first()
print(product.discounted_price)  # Python calculation
print(product.price_tier)        # Python calculation

# QuerySet usage
cheap = Product.objects.filter_hybrid(discounted_price__lt=50)
premium = Product.objects.filter_hybrid(price_tier="premium")
sorted_products = Product.objects.order_by_hybrid("-discounted_price")

# Annotate for use in values()
annotated = Product.objects.annotate_hybrid("discounted_price", "price_tier")
annotated.values("name", "discounted_price", "price_tier")
```

## hybrid_method

For properties that need arguments:

```python
class Location(models.Model):
    latitude = models.FloatField()
    longitude = models.FloatField()

    objects = HybridManager()

    @hybrid_method
    def within_radius(self, lat, lon, radius_km):
        """Instance check."""
        from math import radians, sin, cos, sqrt, atan2
        # Haversine formula
        ...
        return distance <= radius_km

    @within_radius.expression
    def within_radius(cls, lat, lon, radius_km):
        """SQL expression for filtering."""
        # Use database math functions
        ...

# Query
nearby = Location.objects.filter(Location.within_radius(40.7128, -74.0060, 10))
```

## Setup

Add `HybridManager` to any model that uses hybrid properties:

```python
class MyModel(models.Model):
    objects = HybridManager()  # enables filter_hybrid, order_by_hybrid, annotate_hybrid
```

Or use `HybridQuerySet` as a custom manager:

```python
class MyModel(models.Model):
    objects = models.Manager.from_queryset(HybridQuerySet)()
```

## When to Use

| Approach | Use When |
|----------|----------|
| **Hybrid property** | Same logic needed in Python AND queries |
| **Model method** | Logic only used in Python (not in queries) |
| **QuerySet annotation** | Logic only used in queries (not on instances) |
| **Database view** | Complex logic shared across multiple models |

## Performance Notes

- Hybrid expressions are resolved at query time — no extra queries
- The SQL expression runs in the database, so it benefits from indexes
- `annotate_hybrid()` adds the expression as a SQL annotation — use it when you need the value in `values()` or `order_by()`
- For filtering, `filter_hybrid()` generates a `WHERE` clause — the database does the work

## API Reference

- `django_matt.db.hybrid.hybrid_property` — descriptor for computed properties
- `django_matt.db.hybrid.hybrid_method` — descriptor for computed methods with arguments
- `django_matt.db.hybrid.HybridQuerySet` — QuerySet with `filter_hybrid()`, `order_by_hybrid()`, `annotate_hybrid()`
- `django_matt.db.hybrid.HybridManager` — Manager that returns `HybridQuerySet`
