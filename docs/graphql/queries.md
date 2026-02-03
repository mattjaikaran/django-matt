# Query Resolvers

Django Matt provides tools for generating and customizing GraphQL query resolvers with built-in filtering, pagination, and ordering.

## QueryGenerator

The `QueryGenerator` class creates query resolvers for a Django model:

```python
from django_matt.graphql import QueryGenerator, create_type_from_model
from myapp.models import Post

PostType = create_type_from_model(Post)
generator = QueryGenerator(Post, PostType)
```

## List Queries

### Basic List Query

```python
import strawberry
from django_matt.graphql import QueryGenerator

generator = QueryGenerator(Post, PostType)

@strawberry.type
class Query:
    posts = generator.list_query()
```

GraphQL usage:

```graphql
query {
  posts {
    id
    title
    content
  }
}
```

### With Filtering

```python
@strawberry.type
class Query:
    posts = generator.list_query(filterable=True)
```

```graphql
query {
  posts(filter: { is_published: true, author_id: "1" }) {
    id
    title
  }
}
```

### With Ordering

```python
@strawberry.type
class Query:
    posts = generator.list_query(orderable=True)
```

```graphql
query {
  posts(orderBy: ["-created_at", "title"]) {
    id
    title
    createdAt
  }
}
```

### With Pagination

```python
@strawberry.type
class Query:
    posts = generator.list_query(
        paginated=True,
        default_limit=20,
        max_limit=100,
    )
```

```graphql
query {
  posts(limit: 10, offset: 20) {
    id
    title
  }
}
```

### Full Configuration

```python
@strawberry.type
class Query:
    posts = generator.list_query(
        name="allPosts",              # Custom field name
        description="Get all posts",  # Field description
        permission_classes=[IsAuthenticated],
        filterable=True,
        orderable=True,
        paginated=True,
        default_limit=20,
        max_limit=100,
    )
```

## Detail Queries

### Basic Detail Query

```python
@strawberry.type
class Query:
    post = generator.detail_query()
```

```graphql
query {
  post(id: "1") {
    id
    title
    content
    author {
      name
    }
  }
}
```

### Custom Lookup Field

```python
@strawberry.type
class Query:
    post = generator.detail_query(lookup_field="slug")
```

```graphql
query {
  post(id: "my-post-slug") {
    id
    title
  }
}
```

## Connection Queries (Relay-style)

For cursor-based pagination:

```python
@strawberry.type
class Query:
    posts_connection = generator.connection_query()
```

```graphql
query {
  postsConnection(first: 10, after: "cursor123") {
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
      totalCount
    }
    edges {
      cursor
      node {
        id
        title
      }
    }
    totalCount
  }
}
```

### Backward Pagination

```graphql
query {
  postsConnection(last: 10, before: "cursor456") {
    pageInfo {
      hasPreviousPage
      startCursor
    }
    edges {
      cursor
      node {
        id
        title
      }
    }
  }
}
```

## Convenience Functions

For quick query generation without creating a QueryGenerator:

```python
from django_matt.graphql import (
    generate_list_query,
    generate_detail_query,
    generate_connection_query,
)

@strawberry.type
class Query:
    posts = generate_list_query(Post, PostType)
    post = generate_detail_query(Post, PostType)
    posts_connection = generate_connection_query(Post, PostType)
```

## Custom Filter Logic

### Using apply_filters

The `apply_filters` function handles filter-to-queryset conversion:

```python
from django_matt.graphql.queries import apply_filters

@strawberry.field
def posts(
    filter: PostFilter | None = None,
) -> list[PostType]:
    queryset = Post.objects.all()

    if filter:
        queryset = apply_filters(queryset, filter)

    return [PostType.from_orm(p) for p in queryset]
```

### Custom Filter Implementation

For complex filtering logic:

```python
@strawberry.field
def search_posts(
    query: str,
    category: str | None = None,
    min_views: int | None = None,
) -> list[PostType]:
    queryset = Post.objects.filter(is_published=True)

    # Full-text search
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    # Category filter
    if category:
        queryset = queryset.filter(category__slug=category)

    # Minimum views filter
    if min_views:
        queryset = queryset.filter(view_count__gte=min_views)

    return [PostType.from_orm(p) for p in queryset]
```

## Advanced Filtering

### Filter Operators

The auto-generated filters support these operators:

| Operator | Example | Django Equivalent |
|----------|---------|-------------------|
| Exact | `title: "Hello"` | `title="Hello"` |
| Contains | `title_contains: "ell"` | `title__contains="ell"` |
| Case-insensitive contains | `title_icontains: "ell"` | `title__icontains="ell"` |
| Starts with | `title_startswith: "Hel"` | `title__startswith="Hel"` |
| Ends with | `title_endswith: "lo"` | `title__endswith="lo"` |
| Greater than | `created_at_gt: "2024-01-01"` | `created_at__gt=...` |
| Greater than or equal | `created_at_gte: "2024-01-01"` | `created_at__gte=...` |
| Less than | `created_at_lt: "2024-01-01"` | `created_at__lt=...` |
| Less than or equal | `created_at_lte: "2024-01-01"` | `created_at__lte=...` |
| In list | `id_in: ["1", "2", "3"]` | `id__in=[1, 2, 3]` |

### Combining Filters

```graphql
query {
  posts(
    filter: {
      AND: [
        { is_published: true },
        { created_at_gte: "2024-01-01" }
      ]
    }
  ) {
    id
    title
  }
}
```

```graphql
query {
  posts(
    filter: {
      OR: [
        { author_id: "1" },
        { author_id: "2" }
      ]
    }
  ) {
    id
    title
    author {
      name
    }
  }
}
```

## Async Resolvers

The generated queries support async execution:

```python
@strawberry.type
class Query:
    @strawberry.field
    async def posts(self, info: Info) -> list[PostType]:
        # Async database access
        posts = []
        async for post in Post.objects.all():
            posts.append(PostType.from_orm(post))
        return posts
```

## Custom Resolvers

### With DataLoaders

```python
from django_matt.graphql import get_loader

@strawberry.type
class PostType:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self, info: Info) -> UserType | None:
        loader = get_loader(info, User)
        if loader:
            return await loader.load(self.author_id)
        return None
```

### With Permissions

```python
from django_matt.graphql import IsAuthenticated, permission_field

@strawberry.type
class Query:
    @permission_field(IsAuthenticated)
    def my_posts(self, info: Info) -> list[PostType]:
        user = info.context["user"]
        return Post.objects.filter(author=user)
```

## Query Optimization

### Select Related

Automatically include related objects:

```python
@strawberry.field
def posts_with_authors(self) -> list[PostType]:
    return Post.objects.select_related("author").all()
```

### Prefetch Related

For many-to-many and reverse relations:

```python
@strawberry.field
def posts_with_comments(self) -> list[PostType]:
    return Post.objects.prefetch_related(
        "comments",
        "comments__author",
    ).all()
```

### Conditional Selection

Only fetch what's requested:

```python
@strawberry.field
def posts(self, info: Info) -> list[PostType]:
    queryset = Post.objects.all()

    # Check if author is requested
    selections = get_field_selections(info)
    if "author" in selections:
        queryset = queryset.select_related("author")

    if "comments" in selections:
        queryset = queryset.prefetch_related("comments")

    return queryset
```

## Error Handling

### Not Found

```python
@strawberry.field
def post(self, id: strawberry.ID) -> PostType | None:
    try:
        post = Post.objects.get(id=id)
        return PostType.from_orm(post)
    except Post.DoesNotExist:
        return None  # Returns null in GraphQL
```

### Custom Errors

```python
@strawberry.field
def post(self, id: strawberry.ID) -> PostType:
    try:
        post = Post.objects.get(id=id)
        return PostType.from_orm(post)
    except Post.DoesNotExist:
        raise Exception(f"Post with id {id} not found")
```

## Complete Example

```python
import strawberry
from django_matt.graphql import (
    QueryGenerator,
    create_type_from_model,
    create_filter_input_from_model,
    IsAuthenticated,
)
from myapp.models import Post, User

PostType = create_type_from_model(Post)
UserType = create_type_from_model(User)
PostFilter = create_filter_input_from_model(Post)

post_queries = QueryGenerator(Post, PostType)
user_queries = QueryGenerator(User, UserType)

@strawberry.type
class Query:
    # Generated queries
    posts = post_queries.list_query(
        filterable=True,
        orderable=True,
        paginated=True,
        default_limit=20,
    )
    post = post_queries.detail_query()
    posts_connection = post_queries.connection_query()

    users = user_queries.list_query(permission_classes=[IsAuthenticated])
    user = user_queries.detail_query(permission_classes=[IsAuthenticated])

    # Custom queries
    @strawberry.field
    def featured_posts(self, limit: int = 5) -> list[PostType]:
        """Get featured posts."""
        return Post.objects.filter(
            is_featured=True,
            is_published=True,
        ).order_by("-published_at")[:limit]

    @strawberry.field
    def search_posts(self, query: str) -> list[PostType]:
        """Search posts by title and content."""
        return Post.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query),
            is_published=True,
        )

    @strawberry.field
    def my_drafts(self, info: Info) -> list[PostType]:
        """Get current user's draft posts."""
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            return []
        return Post.objects.filter(
            author=user,
            is_published=False,
        )

schema = strawberry.Schema(query=Query)
```

## Reference

### QueryGenerator Methods

```python
class QueryGenerator:
    def __init__(
        self,
        model: type[Model],      # Django model class
        type_class: type,         # Strawberry type class
        input_class: type | None = None,    # Input type (optional)
        filter_class: type | None = None,   # Filter type (optional)
        connection_class: type | None = None,  # Connection type (optional)
    ):
        ...

    def list_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        filterable: bool = True,
        orderable: bool = True,
        paginated: bool = True,
        default_limit: int = 100,
        max_limit: int = 1000,
    ) -> strawberry.field:
        ...

    def detail_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
    ) -> strawberry.field:
        ...

    def connection_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        filterable: bool = True,
        orderable: bool = True,
    ) -> strawberry.field:
        ...
```
