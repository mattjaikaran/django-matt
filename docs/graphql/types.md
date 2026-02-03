# Type Definitions

Django Matt provides utilities for creating GraphQL types from Django models, with automatic field mapping and support for custom types.

## Creating Types from Models

### Basic Usage

The `create_type_from_model()` function generates a Strawberry type from a Django model:

```python
from django_matt.graphql import create_type_from_model
from myapp.models import User

# Create type with all fields
UserType = create_type_from_model(User)
```

### Field Selection

Control which fields are included:

```python
# Include only specific fields
UserType = create_type_from_model(
    User,
    fields=["id", "email", "username", "first_name", "last_name"],
)

# Exclude sensitive fields
UserType = create_type_from_model(
    User,
    exclude=["password", "last_login", "is_superuser"],
)
```

### Custom Names and Descriptions

```python
PublicUserType = create_type_from_model(
    User,
    name="PublicUser",
    description="Public user information (no sensitive data)",
    fields=["id", "username", "first_name"],
)
```

## Manual Type Definition

Use the `@graphql_type` decorator for complete control:

```python
from django_matt.graphql import graphql_type
import strawberry

@graphql_type
class UserType:
    id: int
    email: str
    username: str
    first_name: str | None
    last_name: str | None

    @strawberry.field
    def full_name(self) -> str:
        """User's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)

    @strawberry.field
    def initials(self) -> str:
        """User's initials."""
        return "".join(
            name[0].upper()
            for name in [self.first_name, self.last_name]
            if name
        )
```

### With Descriptions

```python
@graphql_type(name="User", description="Application user")
class UserType:
    id: int = strawberry.field(description="Unique identifier")
    email: str = strawberry.field(description="Email address")
    username: str = strawberry.field(description="Display name")
```

## Field Type Mapping

Django Matt automatically maps Django fields to GraphQL types:

| Django Field | GraphQL Type | Python Type |
|--------------|--------------|-------------|
| `AutoField`, `BigAutoField` | `Int` | `int` |
| `IntegerField`, `SmallIntegerField` | `Int` | `int` |
| `FloatField` | `Float` | `float` |
| `DecimalField` | `Decimal` | `Decimal` |
| `CharField`, `TextField` | `String` | `str` |
| `EmailField`, `URLField`, `SlugField` | `String` | `str` |
| `BooleanField` | `Boolean` | `bool` |
| `DateField` | `Date` | `datetime.date` |
| `DateTimeField` | `DateTime` | `datetime.datetime` |
| `TimeField` | `Time` | `datetime.time` |
| `UUIDField` | `UUID` | `uuid.UUID` |
| `JSONField` | `JSON` | `strawberry.scalars.JSON` |
| `ForeignKey` | `ID` | `strawberry.ID` |
| `ManyToManyField` | `[ID]` | `list[strawberry.ID]` |
| `FileField`, `ImageField` | `String` | `str` (URL) |

## Nullable Fields

Nullable fields are automatically handled:

```python
# Django model
class Post(models.Model):
    title = models.CharField(max_length=200)  # Required
    subtitle = models.CharField(max_length=200, null=True)  # Nullable
    published_at = models.DateTimeField(null=True, blank=True)  # Nullable

# Generated type has correct nullability
@graphql_type
class PostType:
    title: str          # Required
    subtitle: str | None  # Nullable
    published_at: datetime | None  # Nullable
```

## Input Types

### Auto-Generated Inputs

```python
from django_matt.graphql import create_input_from_model

# Create input (excludes id by default)
CreateUserInput = create_input_from_model(
    User,
    name="CreateUserInput",
    exclude=["id", "created_at", "updated_at"],
)

# Update input (all fields optional)
UpdateUserInput = create_input_from_model(
    User,
    name="UpdateUserInput",
    exclude=["id", "created_at"],
    optional_fields=["email", "username", "first_name", "last_name"],
)
```

### Manual Input Definition

```python
from django_matt.graphql import graphql_input
from strawberry import UNSET

@graphql_input
class CreateUserInput:
    email: str
    username: str
    password: str
    first_name: str | None = None
    last_name: str | None = None

@graphql_input
class UpdateUserInput:
    email: str | None = UNSET
    username: str | None = UNSET
    first_name: str | None = UNSET
    last_name: str | None = UNSET
```

!!! note "UNSET vs None"
    Use `UNSET` for optional update fields to distinguish between "not provided" and "set to null".

    ```python
    # Client sends: {"email": null}
    # email = None (explicitly set to null)

    # Client sends: {}
    # email = UNSET (not provided, don't update)
    ```

## Filter Types

### Auto-Generated Filters

```python
from django_matt.graphql import create_filter_input_from_model

PostFilter = create_filter_input_from_model(
    Post,
    fields=["title", "is_published", "created_at", "author_id"],
)
```

This generates filter fields with operators:

```graphql
input PostFilter {
  # Exact match
  title: String
  is_published: Boolean
  author_id: ID

  # String operators
  title_contains: String
  title_icontains: String
  title_startswith: String
  title_endswith: String

  # Numeric/Date operators
  created_at: DateTime
  created_at_gt: DateTime
  created_at_gte: DateTime
  created_at_lt: DateTime
  created_at_lte: DateTime

  # List operators
  title_in: [String]
  author_id_in: [ID]

  # Combinators
  AND: [PostFilter]
  OR: [PostFilter]
}
```

### Manual Filter Definition

```python
@graphql_input
class PostFilter:
    # Basic filters
    author_id: strawberry.ID | None = UNSET
    is_published: bool | None = UNSET

    # String search
    title_contains: str | None = UNSET
    content_search: str | None = UNSET

    # Date range
    created_after: datetime | None = UNSET
    created_before: datetime | None = UNSET

    # Custom filters
    has_comments: bool | None = UNSET
    min_word_count: int | None = UNSET
```

## Relay Types

Django Matt includes Relay-compatible types for cursor-based pagination:

### Node Interface

```python
from django_matt.graphql import NodeInterface

@graphql_type
class PostType(NodeInterface):
    """Implements Relay Node interface."""
    id: strawberry.ID
    title: str
    content: str
```

### Connection and Edge Types

```python
from django_matt.graphql import ConnectionType, EdgeType, PageInfoType

# These are generic types
# ConnectionType[PostType] -> PostConnection
# EdgeType[PostType] -> PostEdge
```

Usage in queries:

```graphql
query {
  posts(first: 10, after: "cursor123") {
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

### Creating Connections from Querysets

```python
from django_matt.graphql import ConnectionType

def resolve_posts(
    first: int | None = None,
    after: str | None = None,
) -> ConnectionType[PostType]:
    queryset = Post.objects.all()
    return ConnectionType.from_queryset(
        queryset,
        PostType,
        first=first,
        after=after,
    )
```

## Enums

### From Python Enums

```python
from enum import Enum
from django_matt.graphql import graphql_enum

@graphql_enum
class PostStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

@graphql_type
class PostType:
    id: int
    title: str
    status: PostStatus
```

### From Django Choices

```python
from django.db import models
from django_matt.graphql import graphql_enum

class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

# Convert Django choices to GraphQL enum
PostStatusEnum = graphql_enum(Post.Status)
```

## Interfaces

Define shared fields across types:

```python
from django_matt.graphql import graphql_interface

@graphql_interface
class Timestamped:
    created_at: datetime
    updated_at: datetime

@graphql_type
class PostType(Timestamped):
    id: int
    title: str

@graphql_type
class CommentType(Timestamped):
    id: int
    content: str
```

## DjangoModelType Base Class

For more control, extend `DjangoModelType`:

```python
from django_matt.graphql import DjangoModelType
import strawberry

@strawberry.type
class UserType(DjangoModelType):
    """User type with ORM conversion support."""

    class Meta:
        model = User
        fields = ["id", "email", "username"]
        exclude = ["password"]

    # DjangoModelType provides:
    # - from_orm(obj) - Convert Django model to type
    # - from_django(obj) - Alias for from_orm
    # - from_queryset(qs) - Convert queryset to list of types
```

Usage:

```python
# Convert single object
user = User.objects.get(id=1)
user_type = UserType.from_orm(user)

# Convert queryset
users = User.objects.all()
user_types = UserType.from_queryset(users)
```

## Custom Scalars

Define custom scalar types:

```python
import strawberry
from decimal import Decimal

@strawberry.scalar(
    description="Monetary value with 2 decimal places",
    serialize=lambda v: float(v),
    parse_value=lambda v: Decimal(str(v)).quantize(Decimal("0.01")),
)
class Money(Decimal):
    pass

@graphql_type
class ProductType:
    id: int
    name: str
    price: Money  # Uses custom scalar
```

## Union Types

```python
import strawberry

@graphql_type
class TextPost:
    id: int
    title: str
    content: str

@graphql_type
class ImagePost:
    id: int
    title: str
    image_url: str

PostUnion = strawberry.union("Post", types=[TextPost, ImagePost])

@graphql_type
class Query:
    @strawberry.field
    def posts(self) -> list[PostUnion]:
        # Return mixed post types
        ...
```

## Type References

Handle circular references with string annotations:

```python
from __future__ import annotations

@graphql_type
class UserType:
    id: int
    email: str
    posts: list["PostType"]  # Forward reference

@graphql_type
class PostType:
    id: int
    title: str
    author: UserType  # Regular reference
```

## Best Practices

### 1. Explicit Field Selection

```python
# Good - explicit control over exposed fields
UserType = create_type_from_model(
    User,
    fields=["id", "email", "username"],
)

# Bad - might expose sensitive fields
UserType = create_type_from_model(User)
```

### 2. Separate Public and Internal Types

```python
# Public type for API consumers
@graphql_type
class PublicUserType:
    id: int
    username: str
    avatar_url: str | None

# Admin type with more fields
@graphql_type
class AdminUserType:
    id: int
    username: str
    email: str
    is_active: bool
    last_login: datetime | None
```

### 3. Document Types Thoroughly

```python
@graphql_type(description="Blog post with author and content")
class PostType:
    """
    Represents a blog post.

    Posts can be in draft or published state.
    Only published posts are visible to regular users.
    """
    id: int = strawberry.field(description="Unique post identifier")
    title: str = strawberry.field(description="Post title (max 200 chars)")
    content: str = strawberry.field(description="Post content in Markdown")
```

### 4. Use Type Aliases for Clarity

```python
from typing import TypeAlias

PostList: TypeAlias = list[PostType]
UserOrNone: TypeAlias = UserType | None

@graphql_type
class Query:
    @strawberry.field
    def posts(self) -> PostList:
        ...

    @strawberry.field
    def current_user(self, info: Info) -> UserOrNone:
        ...
```
