# Schema Generation

Django Matt provides powerful tools for generating GraphQL schemas from Django models, with options ranging from fully automatic to completely manual control.

## Automatic Schema Generation

The simplest approach uses `generate_schema()` to create a complete schema:

```python
from django_matt.graphql import generate_schema
from myapp.models import User, Post, Comment

schema = generate_schema(
    models=[User, Post, Comment],
    auto_mutations=True,
    auto_subscriptions=False,
)
```

This generates:

- **Queries**: `users`, `user`, `users_connection` for each model
- **Mutations**: `createUser`, `updateUser`, `deleteUser` for each model
- **Types**: GraphQL types matching model fields
- **Inputs**: Input types for create/update operations
- **Filters**: Filter inputs for list queries

## GraphQLSchema Builder

For more control, use the `GraphQLSchema` builder:

```python
from django_matt.graphql import GraphQLSchema
from myapp.models import User, Post

schema_builder = GraphQLSchema(
    auto_generate_queries=True,
    auto_generate_mutations=True,
    auto_generate_subscriptions=False,
)

# Add models with configuration
schema_builder.add_model(
    User,
    include_queries=True,
    include_mutations=True,
    permissions=[IsAuthenticated],
)

schema_builder.add_model(
    Post,
    include_queries=True,
    include_mutations=True,
    soft_delete=True,  # Use soft delete for delete mutations
)

schema = schema_builder.build()
```

## Custom Type Classes

Provide your own type classes for full control over field exposure:

```python
from django_matt.graphql import GraphQLSchema, create_type_from_model, graphql_type
from myapp.models import User, Post

# Auto-generated type with field selection
UserType = create_type_from_model(
    User,
    fields=["id", "email", "username", "first_name", "last_name"],
    exclude=["password"],
)

# Custom type with computed fields
@graphql_type
class PostType:
    id: int
    title: str
    content: str
    author: UserType
    published_at: datetime | None
    is_published: bool

    @strawberry.field
    def summary(self) -> str:
        """First 100 characters of content."""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content

    @strawberry.field
    def word_count(self) -> int:
        return len(self.content.split())

# Build schema with custom types
schema_builder = GraphQLSchema()
schema_builder.add_model(User, type_class=UserType)
schema_builder.add_model(Post, type_class=PostType)
schema = schema_builder.build()
```

## Custom Input Types

Define custom input types for create and update operations:

```python
from django_matt.graphql import (
    GraphQLSchema,
    create_input_from_model,
    graphql_input,
)

# Auto-generated input
UserCreateInput = create_input_from_model(
    User,
    name="CreateUserInput",
    exclude=["id", "created_at", "updated_at"],
)

# Custom input with validation
@graphql_input
class CreatePostInput:
    title: str
    content: str
    is_published: bool = False

    def validate(self):
        if len(self.title) < 5:
            raise ValueError("Title must be at least 5 characters")

@graphql_input
class UpdatePostInput:
    title: str | None = None
    content: str | None = None
    is_published: bool | None = None

# Use custom inputs
schema_builder = GraphQLSchema()
schema_builder.add_model(
    Post,
    type_class=PostType,
    create_input_class=CreatePostInput,
    update_input_class=UpdatePostInput,
)
```

## Custom Filter Types

Create custom filter inputs for advanced filtering:

```python
from django_matt.graphql import create_filter_input_from_model, graphql_input
from strawberry import UNSET

# Auto-generated filter with all operators
PostFilter = create_filter_input_from_model(
    Post,
    fields=["title", "is_published", "created_at"],
)
# Generates: title, title_contains, title_icontains, title_startswith, etc.

# Custom filter
@graphql_input
class CustomPostFilter:
    # Exact matches
    author_id: int | None = UNSET
    is_published: bool | None = UNSET

    # String filters
    title_contains: str | None = UNSET
    content_search: str | None = UNSET

    # Date filters
    created_after: datetime | None = UNSET
    created_before: datetime | None = UNSET

    # Range filters
    view_count_min: int | None = UNSET
    view_count_max: int | None = UNSET

schema_builder.add_model(
    Post,
    filter_class=CustomPostFilter,
)
```

## Adding Custom Queries

Add custom query fields alongside generated ones:

```python
from django_matt.graphql import GraphQLSchema
import strawberry

schema_builder = GraphQLSchema()
schema_builder.add_model(Post)

# Add custom queries
@strawberry.field
def featured_posts(limit: int = 5) -> list[PostType]:
    """Get featured posts."""
    return Post.objects.filter(
        is_featured=True,
        is_published=True,
    ).order_by("-published_at")[:limit]

@strawberry.field
def search_posts(query: str) -> list[PostType]:
    """Full-text search posts."""
    return Post.objects.filter(
        Q(title__icontains=query) |
        Q(content__icontains=query)
    )

schema_builder.add_query("featured_posts", featured_posts)
schema_builder.add_query("search_posts", search_posts)

schema = schema_builder.build()
```

## Adding Custom Mutations

Add custom mutations:

```python
@strawberry.mutation
def publish_post(id: strawberry.ID) -> PostType:
    """Publish a post."""
    post = Post.objects.get(id=id)
    post.is_published = True
    post.published_at = timezone.now()
    post.save()
    return PostType.from_orm(post)

@strawberry.mutation
def bulk_archive_posts(ids: list[strawberry.ID]) -> int:
    """Archive multiple posts."""
    count = Post.objects.filter(id__in=ids).update(is_archived=True)
    return count

schema_builder.add_mutation("publish_post", publish_post)
schema_builder.add_mutation("bulk_archive_posts", bulk_archive_posts)
```

## Merging with Custom Classes

Merge generated schema with your own Query/Mutation classes:

```python
import strawberry
from django_matt.graphql import GraphQLSchema

@strawberry.type
class CustomQuery:
    @strawberry.field
    def server_time(self) -> datetime:
        return timezone.now()

    @strawberry.field
    def app_version(self) -> str:
        return "1.0.0"

@strawberry.type
class CustomMutation:
    @strawberry.mutation
    def send_newsletter(self, subject: str, content: str) -> bool:
        send_mass_email(subject, content)
        return True

schema_builder = GraphQLSchema(
    query_class=CustomQuery,      # Merged with generated queries
    mutation_class=CustomMutation,  # Merged with generated mutations
)

schema_builder.add_model(User)
schema_builder.add_model(Post)

schema = schema_builder.build()
```

## Schema Extensions

Add middleware extensions to the schema:

```python
from django_matt.graphql import (
    GraphQLSchema,
    AuthMiddleware,
    RateLimitMiddleware,
    ComplexityMiddleware,
    LoggingMiddleware,
)

schema_builder = GraphQLSchema()
schema_builder.add_model(User)
schema_builder.add_model(Post)

# Custom extensions
extensions = [
    AuthMiddleware,
    RateLimitMiddleware,
    ComplexityMiddleware,
    LoggingMiddleware,
]

schema = schema_builder.build(extensions=extensions)
```

## Multiple Schemas

Create different schemas for different purposes:

```python
from django_matt.graphql import GraphQLSchema

# Public API schema
public_schema_builder = GraphQLSchema()
public_schema_builder.add_model(
    Post,
    include_mutations=False,  # Read-only
)
public_schema = public_schema_builder.build()

# Admin API schema
admin_schema_builder = GraphQLSchema()
admin_schema_builder.add_model(User, permissions=[IsAdmin])
admin_schema_builder.add_model(Post, permissions=[IsAdmin])
admin_schema_builder.add_model(Comment, permissions=[IsAdmin])
admin_schema = admin_schema_builder.build()
```

```python
# urls.py
urlpatterns = [
    path("graphql/", GraphQLView.as_view(schema=public_schema)),
    path("admin/graphql/", GraphQLView.as_view(schema=admin_schema)),
]
```

## Schema Introspection

Access schema information programmatically:

```python
from strawberry.printer import print_schema

# Get SDL (Schema Definition Language)
sdl = print_schema(schema)
print(sdl)

# Save to file
with open("schema.graphql", "w") as f:
    f.write(sdl)
```

## Best Practices

### 1. Separate Schema Files

```
myapp/
  graphql/
    __init__.py
    types.py      # Type definitions
    inputs.py     # Input types
    queries.py    # Custom queries
    mutations.py  # Custom mutations
    schema.py     # Schema assembly
```

### 2. Use Explicit Field Selection

```python
# Good - explicit control
UserType = create_type_from_model(
    User,
    fields=["id", "email", "username"],
)

# Risky - exposes all fields
UserType = create_type_from_model(User)
```

### 3. Version Your Schema

```python
# Track schema changes
SCHEMA_VERSION = "2.0.0"

@strawberry.type
class Query:
    @strawberry.field
    def schema_version(self) -> str:
        return SCHEMA_VERSION
```

### 4. Document Everything

```python
@graphql_type(description="A blog post")
class PostType:
    """A blog post with content and metadata."""

    id: int
    title: str = strawberry.field(description="The post title")
    content: str = strawberry.field(description="Full post content in markdown")
```

## Reference

### generate_schema()

```python
def generate_schema(
    models: list[type[Model]],      # Django model classes
    query: type | None = None,       # Custom Query class to merge
    mutation: type | None = None,    # Custom Mutation class to merge
    subscription: type | None = None, # Custom Subscription class
    extensions: list | None = None,   # Schema extensions
    auto_mutations: bool = True,      # Generate CRUD mutations
    auto_subscriptions: bool = False, # Generate subscriptions
) -> Schema:
```

### GraphQLSchema

```python
class GraphQLSchema:
    def __init__(
        self,
        query_class: type | None = None,
        mutation_class: type | None = None,
        subscription_class: type | None = None,
        auto_generate_queries: bool = True,
        auto_generate_mutations: bool = True,
        auto_generate_subscriptions: bool = False,
    ):
        ...

    def add_model(
        self,
        model: type[Model],
        type_class: type | None = None,
        create_input_class: type | None = None,
        update_input_class: type | None = None,
        filter_class: type | None = None,
        permissions: list | None = None,
        include_queries: bool = True,
        include_mutations: bool = True,
        include_subscriptions: bool = False,
        soft_delete: bool = False,
    ) -> "GraphQLSchema":
        ...

    def add_query(self, name: str, resolver: Callable) -> "GraphQLSchema":
        ...

    def add_mutation(self, name: str, resolver: Callable) -> "GraphQLSchema":
        ...

    def add_subscription(self, name: str, resolver: Callable) -> "GraphQLSchema":
        ...

    def build(self, extensions: list | None = None) -> Schema:
        ...
```
