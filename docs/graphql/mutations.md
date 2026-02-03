# Mutations

Django Matt provides automatic CRUD mutation generation with support for validation, hooks, and custom mutations.

## MutationGenerator

The `MutationGenerator` class creates mutation resolvers for a Django model:

```python
from django_matt.graphql import MutationGenerator, create_type_from_model
from myapp.models import Post

PostType = create_type_from_model(Post)
generator = MutationGenerator(Post, PostType)
```

## Create Mutations

### Basic Create

```python
import strawberry
from django_matt.graphql import MutationGenerator

generator = MutationGenerator(Post, PostType)

@strawberry.type
class Mutation:
    create_post = generator.create_mutation()
```

GraphQL usage:

```graphql
mutation {
  createPost(input: {
    title: "My First Post"
    content: "Hello, World!"
    isPublished: false
  }) {
    id
    title
    content
    createdAt
  }
}
```

### With Custom Input

```python
from django_matt.graphql import graphql_input

@graphql_input
class CreatePostInput:
    title: str
    content: str
    is_published: bool = False
    category_id: strawberry.ID | None = None

generator = MutationGenerator(
    Post,
    PostType,
    create_input_class=CreatePostInput,
)

@strawberry.type
class Mutation:
    create_post = generator.create_mutation()
```

### With Hooks

```python
def pre_create_post(info, data):
    """Called before creating the post."""
    # Add the current user as author
    user = info.context.get("user")
    if user and user.is_authenticated:
        data["author_id"] = user.id
    return data

def post_create_post(info, instance):
    """Called after creating the post."""
    # Send notification
    notify_followers(instance.author, f"New post: {instance.title}")
    # Update search index
    index_post(instance)

@strawberry.type
class Mutation:
    create_post = generator.create_mutation(
        pre_save_hook=pre_create_post,
        post_save_hook=post_create_post,
    )
```

## Update Mutations

### Basic Update

```python
@strawberry.type
class Mutation:
    update_post = generator.update_mutation()
```

```graphql
mutation {
  updatePost(
    id: "1"
    input: {
      title: "Updated Title"
      content: "Updated content"
    }
  ) {
    id
    title
    content
    updatedAt
  }
}
```

### Partial Updates

Only provided fields are updated:

```graphql
mutation {
  updatePost(
    id: "1"
    input: { isPublished: true }
  ) {
    id
    isPublished
  }
}
```

### With Custom Input

```python
from strawberry import UNSET

@graphql_input
class UpdatePostInput:
    title: str | None = UNSET
    content: str | None = UNSET
    is_published: bool | None = UNSET
    category_id: strawberry.ID | None = UNSET

generator = MutationGenerator(
    Post,
    PostType,
    update_input_class=UpdatePostInput,
)
```

### With Hooks

```python
def pre_update_post(info, instance, data):
    """Called before updating."""
    # Check ownership
    user = info.context.get("user")
    if instance.author_id != user.id and not user.is_staff:
        raise PermissionError("You can only edit your own posts")
    return data

def post_update_post(info, instance):
    """Called after updating."""
    # Clear cache
    cache.delete(f"post:{instance.id}")
    # Reindex
    index_post(instance)

@strawberry.type
class Mutation:
    update_post = generator.update_mutation(
        pre_save_hook=pre_update_post,
        post_save_hook=post_update_post,
    )
```

## Delete Mutations

### Basic Delete

```python
@strawberry.type
class Mutation:
    delete_post = generator.delete_mutation()
```

```graphql
mutation {
  deletePost(id: "1") {
    success
    deletedId
    message
  }
}
```

### Soft Delete

```python
@strawberry.type
class Mutation:
    delete_post = generator.delete_mutation(
        soft_delete=True,
        soft_delete_field="is_deleted",
    )
```

This sets `is_deleted=True` instead of actually deleting.

### With Hooks

```python
def pre_delete_post(info, instance):
    """Called before deleting."""
    # Check if post has comments
    if instance.comments.exists():
        raise Exception("Cannot delete post with comments")

def post_delete_post(info, deleted_id):
    """Called after deleting."""
    # Clear cache
    cache.delete(f"post:{deleted_id}")
    # Remove from search index
    remove_from_index("post", deleted_id)

@strawberry.type
class Mutation:
    delete_post = generator.delete_mutation(
        pre_delete_hook=pre_delete_post,
        post_delete_hook=post_delete_post,
    )
```

## Bulk Mutations

### Bulk Create

```python
@strawberry.type
class Mutation:
    bulk_create_posts = generator.bulk_create_mutation(max_items=100)
```

```graphql
mutation {
  bulkCreatePosts(inputs: [
    { title: "Post 1", content: "Content 1" },
    { title: "Post 2", content: "Content 2" },
    { title: "Post 3", content: "Content 3" }
  ]) {
    id
    title
  }
}
```

### Bulk Update

```python
@strawberry.type
class Mutation:
    bulk_update_posts = generator.bulk_update_mutation(max_items=100)
```

```graphql
mutation {
  bulkUpdatePosts(inputs: [
    { id: "1", data: { isPublished: true } },
    { id: "2", data: { isPublished: true } },
    { id: "3", data: { isPublished: false } }
  ]) {
    id
    isPublished
  }
}
```

### Bulk Delete

```python
@strawberry.type
class Mutation:
    bulk_delete_posts = generator.bulk_delete_mutation(
        max_items=100,
        soft_delete=True,
    )
```

```graphql
mutation {
  bulkDeletePosts(ids: ["1", "2", "3"]) {
    success
    deletedCount
    deletedIds
    message
  }
}
```

## Convenience Functions

Quick mutation generation without creating a MutationGenerator:

```python
from django_matt.graphql import (
    generate_create_mutation,
    generate_update_mutation,
    generate_delete_mutation,
    generate_bulk_create_mutation,
    generate_bulk_update_mutation,
    generate_bulk_delete_mutation,
)

@strawberry.type
class Mutation:
    create_post = generate_create_mutation(Post, PostType)
    update_post = generate_update_mutation(Post, PostType)
    delete_post = generate_delete_mutation(Post, PostType)

    bulk_create_posts = generate_bulk_create_mutation(Post, PostType)
    bulk_update_posts = generate_bulk_update_mutation(Post, PostType)
    bulk_delete_posts = generate_bulk_delete_mutation(Post, PostType)
```

## Custom Mutations

### Basic Custom Mutation

```python
from django_matt.graphql import mutation

@strawberry.type
class Mutation:
    @mutation
    def publish_post(self, id: strawberry.ID) -> PostType:
        post = Post.objects.get(id=id)
        post.is_published = True
        post.published_at = timezone.now()
        post.save()
        return PostType.from_orm(post)
```

### With Input Type

```python
@graphql_input
class PublishPostInput:
    id: strawberry.ID
    notify_followers: bool = True
    schedule_at: datetime | None = None

@strawberry.type
class Mutation:
    @strawberry.mutation
    def publish_post(self, input: PublishPostInput) -> PostType:
        post = Post.objects.get(id=input.id)

        if input.schedule_at:
            schedule_publish(post, input.schedule_at)
        else:
            post.is_published = True
            post.published_at = timezone.now()
            post.save()

        if input.notify_followers:
            notify_followers(post.author, post)

        return PostType.from_orm(post)
```

### With Custom Result Type

```python
@graphql_type
class PublishResult:
    success: bool
    post: PostType | None
    message: str
    notified_count: int = 0

@strawberry.type
class Mutation:
    @strawberry.mutation
    def publish_post(self, id: strawberry.ID) -> PublishResult:
        try:
            post = Post.objects.get(id=id)
            post.is_published = True
            post.published_at = timezone.now()
            post.save()

            notified = notify_followers(post.author, post)

            return PublishResult(
                success=True,
                post=PostType.from_orm(post),
                message="Post published successfully",
                notified_count=notified,
            )
        except Post.DoesNotExist:
            return PublishResult(
                success=False,
                post=None,
                message="Post not found",
            )
```

## Result Types

Django Matt provides standard result types:

### MutationResult

```python
from django_matt.graphql.mutations import MutationResult

@strawberry.type
class MutationResult:
    success: bool
    message: str | None = None
    errors: list[str] | None = None
```

### DeleteResult

```python
from django_matt.graphql.mutations import DeleteResult

@strawberry.type
class DeleteResult:
    success: bool
    deleted_id: strawberry.ID | None = None
    message: str | None = None
```

### BulkDeleteResult

```python
from django_matt.graphql.mutations import BulkDeleteResult

@strawberry.type
class BulkDeleteResult:
    success: bool
    deleted_count: int = 0
    deleted_ids: list[strawberry.ID] | None = None
    message: str | None = None
```

## Validation

### Input Validation

```python
@graphql_input
class CreatePostInput:
    title: str
    content: str
    category_id: strawberry.ID | None = None

    def validate(self):
        errors = []
        if len(self.title) < 5:
            errors.append("Title must be at least 5 characters")
        if len(self.content) < 100:
            errors.append("Content must be at least 100 characters")
        if errors:
            raise ValueError("; ".join(errors))

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> PostType:
        input.validate()  # Raises if invalid
        post = Post.objects.create(**vars(input))
        return PostType.from_orm(post)
```

### Model Validation

```python
from django.core.exceptions import ValidationError

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> PostType:
        post = Post(**vars(input))
        try:
            post.full_clean()  # Django model validation
        except ValidationError as e:
            raise Exception(str(e))
        post.save()
        return PostType.from_orm(post)
```

## Transactions

All generated mutations run in database transactions:

```python
from django.db import transaction

@strawberry.type
class Mutation:
    @strawberry.mutation
    def transfer_ownership(
        self,
        post_id: strawberry.ID,
        new_owner_id: strawberry.ID,
    ) -> PostType:
        with transaction.atomic():
            post = Post.objects.select_for_update().get(id=post_id)
            new_owner = User.objects.get(id=new_owner_id)

            # Create transfer record
            Transfer.objects.create(
                post=post,
                from_user=post.author,
                to_user=new_owner,
            )

            # Update ownership
            post.author = new_owner
            post.save()

            return PostType.from_orm(post)
```

## Permissions

### With Permission Classes

```python
from django_matt.graphql import IsAuthenticated, IsAdmin

@strawberry.type
class Mutation:
    create_post = generator.create_mutation(
        permission_classes=[IsAuthenticated],
    )

    delete_post = generator.delete_mutation(
        permission_classes=[IsAdmin],
    )
```

### Manual Permission Checks

```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    def update_post(
        self,
        info: Info,
        id: strawberry.ID,
        input: UpdatePostInput,
    ) -> PostType:
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            raise PermissionError("Authentication required")

        post = Post.objects.get(id=id)
        if post.author_id != user.id and not user.is_staff:
            raise PermissionError("You can only edit your own posts")

        for field, value in vars(input).items():
            if value is not UNSET:
                setattr(post, field, value)
        post.save()

        return PostType.from_orm(post)
```

## Complete Example

```python
import strawberry
from django_matt.graphql import (
    MutationGenerator,
    create_type_from_model,
    graphql_input,
    IsAuthenticated,
)
from myapp.models import Post

PostType = create_type_from_model(Post)

@graphql_input
class CreatePostInput:
    title: str
    content: str
    is_published: bool = False

@graphql_input
class UpdatePostInput:
    title: str | None = UNSET
    content: str | None = UNSET
    is_published: bool | None = UNSET

generator = MutationGenerator(
    Post,
    PostType,
    create_input_class=CreatePostInput,
    update_input_class=UpdatePostInput,
)

@strawberry.type
class Mutation:
    # Generated CRUD mutations
    create_post = generator.create_mutation(
        permission_classes=[IsAuthenticated],
    )
    update_post = generator.update_mutation(
        permission_classes=[IsAuthenticated],
    )
    delete_post = generator.delete_mutation(
        permission_classes=[IsAuthenticated],
        soft_delete=True,
    )

    # Bulk operations
    bulk_create_posts = generator.bulk_create_mutation(
        permission_classes=[IsAuthenticated],
        max_items=50,
    )
    bulk_delete_posts = generator.bulk_delete_mutation(
        permission_classes=[IsAuthenticated],
        max_items=50,
        soft_delete=True,
    )

    # Custom mutations
    @strawberry.mutation
    def publish_post(self, info: Info, id: strawberry.ID) -> PostType:
        """Publish a draft post."""
        user = info.context.get("user")
        post = Post.objects.get(id=id)

        if post.author_id != user.id:
            raise PermissionError("Not authorized")

        post.is_published = True
        post.published_at = timezone.now()
        post.save()

        return PostType.from_orm(post)

    @strawberry.mutation
    def duplicate_post(self, id: strawberry.ID) -> PostType:
        """Create a copy of a post."""
        original = Post.objects.get(id=id)
        copy = Post.objects.create(
            title=f"Copy of {original.title}",
            content=original.content,
            author=original.author,
            is_published=False,
        )
        return PostType.from_orm(copy)

schema = strawberry.Schema(mutation=Mutation, query=Query)
```

## Reference

### MutationGenerator

```python
class MutationGenerator:
    def __init__(
        self,
        model: type[Model],
        type_class: type,
        create_input_class: type | None = None,
        update_input_class: type | None = None,
    ):
        ...

    def create_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        pre_save_hook: Callable | None = None,
        post_save_hook: Callable | None = None,
    ) -> strawberry.mutation:
        ...

    def update_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
        pre_save_hook: Callable | None = None,
        post_save_hook: Callable | None = None,
    ) -> strawberry.mutation:
        ...

    def delete_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
        soft_delete: bool = False,
        soft_delete_field: str = "is_deleted",
        pre_delete_hook: Callable | None = None,
        post_delete_hook: Callable | None = None,
    ) -> strawberry.mutation:
        ...

    def bulk_create_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
    ) -> strawberry.mutation:
        ...

    def bulk_update_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
    ) -> strawberry.mutation:
        ...

    def bulk_delete_mutation(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        max_items: int = 100,
        soft_delete: bool = False,
        soft_delete_field: str = "is_deleted",
    ) -> strawberry.mutation:
        ...
```
