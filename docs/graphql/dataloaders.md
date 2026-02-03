# DataLoaders

DataLoaders solve the N+1 query problem in GraphQL by batching and caching database queries. Django Matt provides built-in DataLoader support optimized for Django models.

## The N+1 Problem

Consider this query:

```graphql
query {
  posts {
    id
    title
    author {       # Without DataLoader: 1 query per post!
      name
      email
    }
  }
}
```

Without batching, fetching 100 posts would execute 101 queries (1 for posts + 100 for authors). With DataLoaders, this becomes just 2 queries.

## ModelDataLoader

The `ModelDataLoader` batches queries for Django models by primary key:

```python
from django_matt.graphql import ModelDataLoader
from myapp.models import User

# Create loader
user_loader = ModelDataLoader(User)

# Load single user (batched with other loads in the same tick)
user = await user_loader.load(1)

# Load multiple users (single query)
users = await user_loader.load_many([1, 2, 3])
```

### Configuration Options

```python
user_loader = ModelDataLoader(
    model=User,
    type_class=UserType,        # Auto-convert to GraphQL type
    lookup_field="pk",          # Field to look up by
    select_related=["profile"], # Eager load relations
    prefetch_related=["roles"], # Prefetch many-to-many
    cache=True,                 # Enable caching (default)
)
```

### Using in Resolvers

```python
@graphql_type
class PostType:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self, info: Info) -> UserType | None:
        # Get loader from context
        loader = info.context["dataloaders"].get_loader(User)
        return await loader.load(self.author_id)
```

## RelatedDataLoader

Load related objects (one-to-many, many-to-many):

```python
from django_matt.graphql import RelatedDataLoader
from myapp.models import Post, Comment

# Load posts by author
posts_loader = RelatedDataLoader(
    model=Post,
    related_field="author_id",
    type_class=PostType,
)

# Get all posts by user
user_posts = await posts_loader.load(user_id)

# Load comments for posts
comments_loader = RelatedDataLoader(
    model=Comment,
    related_field="post_id",
    type_class=CommentType,
    order_by=["-created_at"],  # Order results
)

comments = await comments_loader.load(post_id)
```

### Using for Relations

```python
@graphql_type
class UserType:
    id: int
    name: str

    @strawberry.field
    async def posts(self, info: Info) -> list[PostType]:
        registry = info.context["dataloaders"]
        loader = registry.get_related_loader(Post, "author_id")
        return await loader.load(self.id)

@graphql_type
class PostType:
    id: int
    title: str

    @strawberry.field
    async def comments(self, info: Info) -> list[CommentType]:
        registry = info.context["dataloaders"]
        loader = registry.get_related_loader(Comment, "post_id")
        return await loader.load(self.id)
```

## DataLoaderRegistry

The `DataLoaderRegistry` manages multiple loaders per request:

```python
from django_matt.graphql import DataLoaderRegistry

# Create registry
registry = DataLoaderRegistry()

# Register model loaders
registry.register_model(
    User,
    type_class=UserType,
    select_related=["profile"],
)

registry.register_model(
    Post,
    type_class=PostType,
    select_related=["author", "category"],
)

# Register related loaders
registry.register_related(
    Post,
    related_field="author_id",
    type_class=PostType,
    order_by=["-created_at"],
)

registry.register_related(
    Comment,
    related_field="post_id",
    type_class=CommentType,
)
```

### Automatic Registry Setup

```python
from django_matt.graphql import create_dataloaders

# Create registry with loaders for all models
registry = create_dataloaders(
    models=[User, Post, Comment, Category],
    type_map={
        User: UserType,
        Post: PostType,
        Comment: CommentType,
        Category: CategoryType,
    },
)
```

## Context Integration

DataLoaders are typically added to the GraphQL context:

### In GraphQL Views

```python
from django_matt.graphql import GraphQLView, DataLoaderRegistry

class CustomGraphQLView(GraphQLView):
    def get_context(self, request, response) -> dict:
        context = super().get_context(request, response)

        # Create fresh registry for each request
        registry = DataLoaderRegistry()
        registry.register_model(User, UserType)
        registry.register_model(Post, PostType)
        registry.register_related(Post, "author_id", PostType)

        context["dataloaders"] = registry
        return context
```

### Using Helper Function

```python
from django_matt.graphql import get_loader

@graphql_type
class PostType:
    id: int
    author_id: int

    @strawberry.field
    async def author(self, info: Info) -> UserType | None:
        loader = get_loader(info, User)
        if loader:
            return await loader.load(self.author_id)
        # Fallback without loader
        return User.objects.filter(id=self.author_id).first()
```

## Custom Loaders

### Custom Batch Function

```python
from strawberry.dataloader import DataLoader

async def load_user_stats(user_ids: list[int]) -> list[dict]:
    """Custom batch function for user statistics."""
    # Single aggregation query for all users
    stats = UserStats.objects.filter(
        user_id__in=user_ids
    ).values("user_id", "post_count", "comment_count", "follower_count")

    stats_map = {s["user_id"]: s for s in stats}
    return [stats_map.get(uid, {}) for uid in user_ids]

# Register custom loader
registry.register_custom("user_stats", load_user_stats)

# Use in resolver
@strawberry.field
async def stats(self, info: Info) -> UserStats:
    loader = info.context["dataloaders"].get_custom_loader("user_stats")
    return await loader.load(self.id)
```

### Loader with Transformations

```python
async def load_user_with_permissions(user_ids: list[int]) -> list[UserWithPermissions]:
    """Load users with their computed permissions."""
    users = User.objects.filter(id__in=user_ids).prefetch_related(
        "groups__permissions",
        "user_permissions",
    )

    user_map = {}
    for user in users:
        permissions = set()
        for group in user.groups.all():
            permissions.update(p.codename for p in group.permissions.all())
        permissions.update(p.codename for p in user.user_permissions.all())

        user_map[user.id] = UserWithPermissions(
            id=user.id,
            email=user.email,
            permissions=list(permissions),
        )

    return [user_map.get(uid) for uid in user_ids]
```

## Caching

### Request-Level Caching

By default, DataLoaders cache results for the duration of a request:

```python
# First call - queries database
user1 = await loader.load(1)

# Second call - returns cached result
user1_again = await loader.load(1)  # No query!
```

### Priming the Cache

Pre-populate the cache with known values:

```python
# Prime cache with user from another query
user = User.objects.get(id=1)
loader.prime(1, UserType.from_orm(user))

# Later load returns cached value
cached_user = await loader.load(1)
```

### Clearing Cache

```python
# Clear specific key
loader.clear(1)

# Clear all cached values
loader.clear()

# Clear all loaders in registry
registry.clear_all()
```

### Disabling Cache

```python
# Create loader without caching
loader = ModelDataLoader(User, cache=False)
```

## Query Optimization

### Select Related

Include related objects in the batch query:

```python
user_loader = ModelDataLoader(
    User,
    select_related=["profile", "organization"],
)

# Single query fetches user + profile + organization
user = await user_loader.load(1)
# user.profile and user.organization are already loaded
```

### Prefetch Related

Prefetch many-to-many and reverse relations:

```python
user_loader = ModelDataLoader(
    User,
    prefetch_related=["groups", "posts"],
)

# Efficient batch loading of relations
user = await user_loader.load(1)
# user.groups.all() and user.posts.all() are prefetched
```

## Best Practices

### 1. Create Loaders Per Request

```python
# Good - fresh loaders per request
def get_context(request, response):
    return {
        "dataloaders": DataLoaderRegistry(),
    }

# Bad - shared loaders across requests (stale data)
global_registry = DataLoaderRegistry()  # Don't do this!
```

### 2. Use Type Classes

```python
# Good - auto-converts to GraphQL types
loader = ModelDataLoader(User, type_class=UserType)
user_type = await loader.load(1)  # Returns UserType

# Okay - returns Django model
loader = ModelDataLoader(User)
user_model = await loader.load(1)  # Returns User model
```

### 3. Optimize Related Queries

```python
# Good - single query for users with profiles
loader = ModelDataLoader(
    User,
    select_related=["profile"],
)

# Bad - N+1 for profiles
@strawberry.field
async def profile(self) -> ProfileType:
    return self.profile  # Additional query per user!
```

### 4. Handle Missing Data

```python
@strawberry.field
async def author(self, info: Info) -> UserType | None:
    loader = get_loader(info, User)
    if not loader:
        return None
    user = await loader.load(self.author_id)
    return user  # May be None if user doesn't exist
```

## Complete Example

```python
# graphql/loaders.py
from django_matt.graphql import (
    DataLoaderRegistry,
    ModelDataLoader,
    RelatedDataLoader,
    create_type_from_model,
)
from myapp.models import User, Post, Comment, Category

# Create types
UserType = create_type_from_model(User, exclude=["password"])
PostType = create_type_from_model(Post)
CommentType = create_type_from_model(Comment)
CategoryType = create_type_from_model(Category)

def create_loaders() -> DataLoaderRegistry:
    """Create a fresh DataLoader registry for a request."""
    registry = DataLoaderRegistry()

    # Model loaders (load by ID)
    registry.register_model(
        User,
        type_class=UserType,
        select_related=["profile"],
    )

    registry.register_model(
        Post,
        type_class=PostType,
        select_related=["author", "category"],
    )

    registry.register_model(
        Comment,
        type_class=CommentType,
        select_related=["author"],
    )

    registry.register_model(Category, type_class=CategoryType)

    # Related loaders (load by foreign key)
    registry.register_related(
        Post,
        related_field="author_id",
        type_class=PostType,
        order_by=["-created_at"],
    )

    registry.register_related(
        Post,
        related_field="category_id",
        type_class=PostType,
    )

    registry.register_related(
        Comment,
        related_field="post_id",
        type_class=CommentType,
        order_by=["created_at"],
    )

    return registry
```

```python
# graphql/types.py
import strawberry
from django_matt.graphql import graphql_type, get_loader

@graphql_type
class UserType:
    id: int
    email: str
    username: str

    @strawberry.field
    async def posts(self, info: strawberry.Info) -> list["PostType"]:
        """User's posts (efficiently loaded)."""
        registry = info.context["dataloaders"]
        loader = registry.get_related_loader(Post, "author_id")
        return await loader.load(self.id)

    @strawberry.field
    async def post_count(self, info: strawberry.Info) -> int:
        """Number of posts by this user."""
        posts = await self.posts(info)
        return len(posts)

@graphql_type
class PostType:
    id: int
    title: str
    content: str
    author_id: int
    category_id: int | None

    @strawberry.field
    async def author(self, info: strawberry.Info) -> UserType | None:
        """Post author (efficiently loaded)."""
        loader = get_loader(info, User)
        return await loader.load(self.author_id) if loader else None

    @strawberry.field
    async def category(self, info: strawberry.Info) -> "CategoryType | None":
        """Post category (efficiently loaded)."""
        if not self.category_id:
            return None
        loader = get_loader(info, Category)
        return await loader.load(self.category_id) if loader else None

    @strawberry.field
    async def comments(self, info: strawberry.Info) -> list["CommentType"]:
        """Post comments (efficiently loaded)."""
        registry = info.context["dataloaders"]
        loader = registry.get_related_loader(Comment, "post_id")
        return await loader.load(self.id)

@graphql_type
class CommentType:
    id: int
    content: str
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.Info) -> UserType | None:
        loader = get_loader(info, User)
        return await loader.load(self.author_id) if loader else None
```

```python
# graphql/views.py
from django_matt.graphql import AsyncGraphQLView
from .loaders import create_loaders

class OptimizedGraphQLView(AsyncGraphQLView):
    async def get_context(self, request, response) -> dict:
        context = await super().get_context(request, response)
        context["dataloaders"] = create_loaders()
        return context
```

## Reference

### ModelDataLoader

```python
class ModelDataLoader:
    def __init__(
        self,
        model: type[Model],
        type_class: type | None = None,
        lookup_field: str = "pk",
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        cache: bool = True,
    ):
        ...

    async def load(self, key: Any) -> T | None:
        """Load a single item by key."""

    async def load_many(self, keys: list[Any]) -> list[T | None]:
        """Load multiple items by keys."""

    def prime(self, key: Any, value: T) -> None:
        """Prime the cache with a value."""

    def clear(self, key: Any | None = None) -> None:
        """Clear the cache (specific key or all)."""
```

### RelatedDataLoader

```python
class RelatedDataLoader:
    def __init__(
        self,
        model: type[Model],
        related_field: str,
        type_class: type | None = None,
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        order_by: list[str] | None = None,
        cache: bool = True,
    ):
        ...

    async def load(self, key: Any) -> list[T]:
        """Load related objects for a key."""

    async def load_many(self, keys: list[Any]) -> list[list[T]]:
        """Load related objects for multiple keys."""
```

### DataLoaderRegistry

```python
class DataLoaderRegistry:
    def register_model(
        self,
        model: type[Model],
        type_class: type | None = None,
        lookup_field: str = "pk",
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
    ) -> ModelDataLoader:
        ...

    def register_related(
        self,
        model: type[Model],
        related_field: str,
        type_class: type | None = None,
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        order_by: list[str] | None = None,
    ) -> RelatedDataLoader:
        ...

    def register_custom(
        self,
        name: str,
        load_fn: Callable[[list], list],
    ) -> DataLoader:
        ...

    def get_loader(self, model: type[Model]) -> ModelDataLoader | None:
        ...

    def get_related_loader(
        self,
        model: type[Model],
        related_field: str,
    ) -> RelatedDataLoader | None:
        ...

    def get_custom_loader(self, name: str) -> DataLoader | None:
        ...

    def clear_all(self) -> None:
        """Clear all loader caches."""
```
