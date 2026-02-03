# Database Recipes

This cookbook covers common database patterns and optimizations for django-matt.

## Query Optimization

### Avoiding N+1 Queries

```python
from django_matt.utils.performance import optimize_queryset, QueryAnalyzer

# Automatic optimization
@api.get("/posts")
async def list_posts(request):
    # optimize_queryset adds select_related/prefetch_related automatically
    posts = optimize_queryset(
        Post.objects.all(),
        select_related=['author', 'category'],
        prefetch_related=['tags', 'comments'],
    )
    return [PostSchema.from_orm(p) async for p in posts]


# Manual optimization
@api.get("/users/{user_id}/orders")
async def get_user_orders(request, user_id: int):
    orders = (
        Order.objects
        .filter(user_id=user_id)
        .select_related('user', 'shipping_address')
        .prefetch_related(
            'items',
            'items__product',
            'items__product__category',
        )
        .order_by('-created_at')
    )
    return [OrderSchema.from_orm(o) async for o in orders]


# Analyze queries for optimization suggestions
@api.get("/debug/analyze-posts")
@admin_required
async def analyze_posts_query(request):
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze_queryset(Post.objects.all())
    return {
        "suggestions": analysis["suggestions"],
        "missing_indexes": analysis["missing_indexes"],
        "n_plus_one_risks": analysis["n_plus_one_risks"],
    }
```

### Using `only()` and `defer()`

```python
# Only load specific fields
@api.get("/users/list")
async def list_users_minimal(request):
    users = User.objects.only('id', 'email', 'username')
    return [
        {"id": u.id, "email": u.email, "username": u.username}
        async for u in users
    ]


# Defer heavy fields
@api.get("/posts")
async def list_posts(request):
    # Defer the content field for listing
    posts = Post.objects.defer('content', 'html_content')
    return [PostListSchema.from_orm(p) async for p in posts]
```

### Aggregations

```python
from django.db.models import Count, Sum, Avg, F, Q

@api.get("/stats/orders")
async def get_order_stats(request):
    stats = await Order.objects.aaggregate(
        total_orders=Count('id'),
        total_revenue=Sum('total'),
        avg_order_value=Avg('total'),
    )
    return stats


@api.get("/products/popular")
async def get_popular_products(request, limit: int = 10):
    products = (
        Product.objects
        .annotate(order_count=Count('orderitem'))
        .order_by('-order_count')
        [:limit]
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "order_count": p.order_count,
        }
        async for p in products
    ]
```

## Transactions

### Atomic Operations

```python
from django.db import transaction

@api.post("/orders")
@jwt_required
async def create_order(request, data: OrderCreateSchema):
    async with transaction.atomic():
        # Create order
        order = await Order.objects.acreate(
            user=request.user,
            status='pending',
        )

        # Create order items
        total = 0
        for item in data.items:
            product = await Product.objects.aget(id=item.product_id)

            # Check stock
            if product.stock < item.quantity:
                raise ValidationError(f"Insufficient stock for {product.name}")

            # Create item
            await OrderItem.objects.acreate(
                order=order,
                product=product,
                quantity=item.quantity,
                price=product.price,
            )

            # Update stock
            product.stock -= item.quantity
            await product.asave()

            total += product.price * item.quantity

        # Update order total
        order.total = total
        await order.asave()

    return OrderSchema.from_orm(order)
```

### Savepoints

```python
@api.post("/batch-import")
@jwt_required
async def batch_import(request, data: BatchImportSchema):
    results = {"success": 0, "failed": 0, "errors": []}

    async with transaction.atomic():
        for idx, item in enumerate(data.items):
            try:
                # Create savepoint for each item
                sid = transaction.savepoint()

                await process_import_item(item)

                transaction.savepoint_commit(sid)
                results["success"] += 1
            except Exception as e:
                # Rollback just this item
                transaction.savepoint_rollback(sid)
                results["failed"] += 1
                results["errors"].append({
                    "index": idx,
                    "error": str(e),
                })

    return results
```

## Soft Deletes

### Soft Delete Mixin

```python
from django.db import models
from django.utils import timezone

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        return super().get_queryset()

    def deleted_only(self):
        return super().get_queryset().filter(deleted_at__isnull=False)


class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])


# Usage in model
class Post(SoftDeleteMixin, models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
```

```python
# In controller
@api.delete("/posts/{post_id}")
@jwt_required
async def delete_post(request, post_id: int):
    post = await Post.objects.aget(id=post_id, author=request.user)
    await post.adelete()  # Soft delete
    return {"deleted": True}


@api.post("/posts/{post_id}/restore")
@admin_required
async def restore_post(request, post_id: int):
    post = await Post.all_objects.aget(id=post_id)
    await post.arestore()
    return PostSchema.from_orm(post)


@api.get("/admin/posts/deleted")
@admin_required
async def list_deleted_posts(request):
    posts = Post.objects.deleted_only()
    return [PostSchema.from_orm(p) async for p in posts]
```

## Audit Logging

### Automatic Audit Trail

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user', 'created_at']),
        ]


class AuditableMixin(models.Model):
    """Mixin that automatically logs changes."""

    class Meta:
        abstract = True

    def save(self, *args, user=None, request=None, **kwargs):
        is_new = self.pk is None
        old_values = {}

        if not is_new:
            old_instance = type(self).objects.get(pk=self.pk)
            for field in self._meta.fields:
                old_value = getattr(old_instance, field.name)
                new_value = getattr(self, field.name)
                if old_value != new_value:
                    old_values[field.name] = {
                        'old': str(old_value),
                        'new': str(new_value),
                    }

        super().save(*args, **kwargs)

        # Create audit log
        if user or request:
            AuditLog.objects.create(
                user=user or (request.user if request else None),
                action='create' if is_new else 'update',
                content_type=ContentType.objects.get_for_model(self),
                object_id=self.pk,
                changes=old_values,
                ip_address=get_client_ip(request) if request else None,
                user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            )
```

```python
# Usage in controller
@api.put("/products/{product_id}")
@jwt_required
async def update_product(request, product_id: int, data: ProductUpdateSchema):
    product = await Product.objects.aget(id=product_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    # Pass request for audit logging
    await product.asave(request=request)

    return ProductSchema.from_orm(product)


# Query audit logs
@api.get("/admin/audit/{content_type}/{object_id}")
@admin_required
async def get_audit_log(request, content_type: str, object_id: int):
    ct = await ContentType.objects.aget(model=content_type)
    logs = AuditLog.objects.filter(
        content_type=ct,
        object_id=object_id,
    ).select_related('user')

    return [
        {
            "action": log.action,
            "user": log.user.email if log.user else None,
            "changes": log.changes,
            "created_at": log.created_at,
        }
        async for log in logs
    ]
```

## Bulk Operations

### Bulk Create

```python
@api.post("/products/bulk")
@admin_required
async def bulk_create_products(request, data: BulkProductSchema):
    products = [
        Product(
            name=item.name,
            price=item.price,
            description=item.description,
        )
        for item in data.products
    ]

    created = await Product.objects.abulk_create(products)
    return {"created": len(created)}
```

### Bulk Update

```python
@api.patch("/products/bulk-price")
@admin_required
async def bulk_update_prices(request, data: BulkPriceUpdateSchema):
    # Update using F expressions
    await Product.objects.filter(
        id__in=data.product_ids
    ).aupdate(
        price=F('price') * data.multiplier
    )

    return {"updated": len(data.product_ids)}


# Or with individual updates
@api.patch("/products/bulk")
@admin_required
async def bulk_update_products(request, data: list[ProductUpdateSchema]):
    products = []
    for item in data:
        product = await Product.objects.aget(id=item.id)
        for field, value in item.model_dump(exclude_unset=True, exclude={'id'}).items():
            setattr(product, field, value)
        products.append(product)

    await Product.objects.abulk_update(products, ['name', 'price', 'description'])
    return {"updated": len(products)}
```

## Database-Specific Features

### PostgreSQL Full-Text Search

```python
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)

@api.get("/search/products")
async def search_products(request, q: str):
    """Full-text search with ranking."""
    search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
    search_query = SearchQuery(q, config='english')

    products = (
        Product.objects
        .annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query),
        )
        .filter(search=search_query)
        .order_by('-rank')
        [:20]
    )

    return [ProductSchema.from_orm(p) async for p in products]


@api.get("/search/similar")
async def find_similar(request, name: str):
    """Fuzzy matching with trigram similarity."""
    products = (
        Product.objects
        .annotate(similarity=TrigramSimilarity('name', name))
        .filter(similarity__gt=0.3)
        .order_by('-similarity')
        [:10]
    )

    return [
        {"product": ProductSchema.from_orm(p), "similarity": p.similarity}
        async for p in products
    ]
```

### PostgreSQL JSON Fields

```python
from django.db.models import JSONField
from django.db.models.functions import Cast
from django.contrib.postgres.fields import ArrayField

class Product(models.Model):
    name = models.CharField(max_length=200)
    metadata = JSONField(default=dict)
    tags = ArrayField(models.CharField(max_length=50), default=list)


# Query JSON fields
@api.get("/products/by-brand")
async def get_products_by_brand(request, brand: str):
    products = Product.objects.filter(
        metadata__brand=brand  # Access nested JSON field
    )
    return [ProductSchema.from_orm(p) async for p in products]


# Query array fields
@api.get("/products/by-tag")
async def get_products_by_tag(request, tag: str):
    products = Product.objects.filter(tags__contains=[tag])
    return [ProductSchema.from_orm(p) async for p in products]
```

## Connection Pooling

```python
# settings.py - Django 5.2+ connection pooling
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mydb",
        "USER": "user",
        "PASSWORD": "password",
        "HOST": "localhost",
        "PORT": "5432",
        # Connection pooling (Django 5.2+)
        "CONN_MAX_AGE": 600,  # Keep connections for 10 minutes
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "pool": {
                "min_size": 2,
                "max_size": 10,
            }
        }
    }
}
```
