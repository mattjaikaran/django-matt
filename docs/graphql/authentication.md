# Authentication & Permissions

Django Matt's GraphQL integration provides comprehensive authentication and authorization with JWT support, permission classes, and field-level security.

## Configuration

Enable authentication in your GraphQL settings:

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "AUTH_REQUIRED": False,         # Require auth for all operations
    "AUTH_HEADER_NAME": "Authorization",
    "INTROSPECTION_AUTH_REQUIRED": False,  # Require auth for introspection
}
```

## Authentication Middleware

The `AuthMiddleware` automatically validates JWT tokens and sets the user:

```python
from django_matt.graphql import AuthMiddleware

# Included by default in get_default_extensions()
schema = strawberry.Schema(
    query=Query,
    extensions=[AuthMiddleware],
)
```

### How It Works

1. Extracts JWT from `Authorization: Bearer <token>` header
2. Validates the token using Django Matt's JWT module
3. Sets `request.user` and `context["user"]` to the authenticated user
4. Raises `PermissionError` if auth is required but missing/invalid

## Permission Classes

Django Matt provides Strawberry-compatible permission classes:

### IsAuthenticated

Requires a logged-in user:

```python
from django_matt.graphql import IsAuthenticated

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def me(self, info: Info) -> UserType:
        return info.context["user"]

    @strawberry.field(permission_classes=[IsAuthenticated])
    def my_posts(self, info: Info) -> list[PostType]:
        return Post.objects.filter(author=info.context["user"])
```

### IsAdmin

Requires staff or superuser status:

```python
from django_matt.graphql import IsAdmin

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsAdmin])
    def delete_user(self, id: strawberry.ID) -> bool:
        User.objects.filter(id=id).delete()
        return True
```

### HasPermission

Requires a specific Django permission:

```python
from django_matt.graphql.decorators import HasPermission

@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[HasPermission("blog.delete_post")])
    def delete_post(self, id: strawberry.ID) -> bool:
        Post.objects.filter(id=id).delete()
        return True
```

### HasRole

Requires membership in specific groups:

```python
from django_matt.graphql.decorators import HasRole

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[HasRole("editors", "admins")])
    def draft_posts(self) -> list[PostType]:
        return Post.objects.filter(is_published=False)
```

## Permission Decorators

### @permission_field

Apply multiple permissions to a field:

```python
from django_matt.graphql import permission_field, IsAuthenticated, IsAdmin

@graphql_type
class UserType:
    id: int
    email: str

    @permission_field(IsAuthenticated)
    def private_data(self) -> str:
        return "Only authenticated users can see this"

    @permission_field(IsAuthenticated, IsAdmin)
    def admin_notes(self) -> str:
        return "Only admins can see this"
```

### @authenticated_field

Shorthand for requiring authentication:

```python
from django_matt.graphql import authenticated_field

@graphql_type
class UserType:
    id: int
    username: str  # Public

    @authenticated_field
    def email(self) -> str:
        """Email is only visible to authenticated users."""
        return self._email

    @authenticated_field(description="User's phone number")
    def phone(self) -> str | None:
        return self._phone
```

## Field-Level Permissions

Control access at the field level:

```python
@graphql_type
class UserType:
    id: int
    username: str  # Always visible

    @strawberry.field(permission_classes=[IsAuthenticated])
    def email(self) -> str:
        """Only authenticated users can see email."""
        return self._email

    @strawberry.field(permission_classes=[IsAdmin])
    def last_login(self) -> datetime | None:
        """Only admins can see last login."""
        return self._last_login

    @strawberry.field
    def is_online(self, info: Info) -> bool:
        """Custom logic based on viewer."""
        viewer = info.context.get("user")
        # Only show online status to friends
        if viewer and self._is_friend(viewer):
            return self._is_online
        return False
```

## Custom Permission Classes

Create your own permission classes:

```python
from strawberry.permission import BasePermission
from strawberry.types import Info

class IsOwner(BasePermission):
    """Permission that checks if the user owns the resource."""
    message = "You don't have permission to access this resource"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            return False

        # Check ownership based on source type
        if hasattr(source, "author_id"):
            return source.author_id == user.id
        if hasattr(source, "user_id"):
            return source.user_id == user.id
        if hasattr(source, "owner_id"):
            return source.owner_id == user.id

        return False

class IsVerified(BasePermission):
    """Permission that requires email verification."""
    message = "Email verification required"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.get("user")
        return user and user.is_authenticated and user.email_verified

class HasPlan(BasePermission):
    """Permission that requires a specific subscription plan."""
    message = "This feature requires a premium plan"

    def __init__(self, plans: list[str]):
        self.plans = plans

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            return False
        return user.subscription_plan in self.plans
```

Usage:

```python
@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsOwner])
    def update_post(self, id: strawberry.ID, input: UpdatePostInput) -> PostType:
        post = Post.objects.get(id=id)
        # IsOwner already verified ownership
        for field, value in vars(input).items():
            if value is not UNSET:
                setattr(post, field, value)
        post.save()
        return PostType.from_orm(post)

    @strawberry.mutation(permission_classes=[HasPlan(["pro", "enterprise"])])
    def export_analytics(self) -> str:
        return generate_analytics_export()
```

## Query-Level Authorization

### Using Generators

```python
from django_matt.graphql import QueryGenerator, IsAuthenticated

generator = QueryGenerator(Post, PostType)

@strawberry.type
class Query:
    # Public - anyone can view published posts
    posts = generator.list_query()

    # Requires authentication
    drafts = generator.list_query(
        name="myDrafts",
        permission_classes=[IsAuthenticated],
    )
```

### Manual Authorization

```python
@strawberry.type
class Query:
    @strawberry.field
    def posts(
        self,
        info: Info,
        include_private: bool = False,
    ) -> list[PostType]:
        user = info.context.get("user")
        queryset = Post.objects.filter(is_published=True)

        if include_private:
            if not user or not user.is_authenticated:
                raise PermissionError("Authentication required for private posts")
            # Add user's private posts
            queryset = queryset | Post.objects.filter(
                author=user,
                is_published=False,
            )

        return queryset
```

## Mutation Authorization

### Using Generators

```python
from django_matt.graphql import MutationGenerator, IsAuthenticated, IsAdmin

generator = MutationGenerator(Post, PostType)

@strawberry.type
class Mutation:
    # Requires authentication
    create_post = generator.create_mutation(
        permission_classes=[IsAuthenticated],
    )

    # Requires authentication
    update_post = generator.update_mutation(
        permission_classes=[IsAuthenticated],
    )

    # Requires admin
    delete_post = generator.delete_mutation(
        permission_classes=[IsAdmin],
    )
```

### With Hooks

```python
def authorize_update(info, instance, data):
    """Pre-save hook that checks authorization."""
    user = info.context.get("user")

    # Must be owner or admin
    if instance.author_id != user.id and not user.is_staff:
        raise PermissionError("You can only edit your own posts")

    # Non-admins can't publish directly
    if data.get("is_published") and not user.is_staff:
        raise PermissionError("Only admins can publish posts")

    return data

@strawberry.type
class Mutation:
    update_post = generator.update_mutation(
        permission_classes=[IsAuthenticated],
        pre_save_hook=authorize_update,
    )
```

## Subscription Authorization

```python
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def my_notifications(
        self,
        info: Info,
    ) -> AsyncGenerator[NotificationType, None]:
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            raise PermissionError("Authentication required")

        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Notification"):
            # Only yield notifications for this user
            if message.data.user_id == user.id:
                yield message.data
```

## Context Access

Access authentication info from context:

```python
@strawberry.field
def viewer(self, info: Info) -> UserType | None:
    """Get the current authenticated user."""
    user = info.context.get("user")
    if user and user.is_authenticated:
        return UserType.from_orm(user)
    return None

@strawberry.field
def is_authenticated(self, info: Info) -> bool:
    """Check if request is authenticated."""
    user = info.context.get("user")
    return user is not None and user.is_authenticated

@strawberry.mutation
def update_profile(self, info: Info, input: UpdateProfileInput) -> UserType:
    user = info.context.get("user")
    if not user or not user.is_authenticated:
        raise PermissionError("Authentication required")

    for field, value in vars(input).items():
        if value is not UNSET:
            setattr(user, field, value)
    user.save()

    return UserType.from_orm(user)
```

## JWT Integration

### With Django Matt Auth

```python
from django_matt.auth import create_token_pair, verify_access_token

@graphql_input
class LoginInput:
    email: str
    password: str

@graphql_type
class AuthPayload:
    access_token: str
    refresh_token: str
    user: UserType

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, input: LoginInput) -> AuthPayload:
        from django.contrib.auth import authenticate

        user = authenticate(email=input.email, password=input.password)
        if not user:
            raise Exception("Invalid credentials")

        tokens = create_token_pair(user)

        return AuthPayload(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=UserType.from_orm(user),
        )

    @strawberry.mutation
    async def refresh_token(self, refresh_token: str) -> AuthPayload:
        from django_matt.auth import refresh_tokens

        tokens = await refresh_tokens(refresh_token)
        user = await verify_access_token(tokens.access_token)

        return AuthPayload(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=UserType.from_orm(user),
        )
```

### Client Usage

```typescript
// Login and get tokens
const { data } = await client.mutate({
  mutation: gql`
    mutation Login($input: LoginInput!) {
      login(input: $input) {
        accessToken
        refreshToken
        user {
          id
          email
        }
      }
    }
  `,
  variables: {
    input: { email: "user@example.com", password: "secret" },
  },
});

// Store tokens
localStorage.setItem("accessToken", data.login.accessToken);
localStorage.setItem("refreshToken", data.login.refreshToken);

// Use in subsequent requests
const authLink = setContext((_, { headers }) => ({
  headers: {
    ...headers,
    authorization: `Bearer ${localStorage.getItem("accessToken")}`,
  },
}));
```

## Error Handling

### Permission Errors

```python
@strawberry.mutation(permission_classes=[IsAuthenticated])
def create_post(self, input: CreatePostInput) -> PostType:
    # If not authenticated, Strawberry raises:
    # "User must be authenticated"
    ...
```

### Custom Error Messages

```python
class IsOwner(BasePermission):
    message = "You don't have permission to modify this resource"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        # When returns False, message is shown to client
        ...
```

### Handling in Client

```typescript
try {
  const result = await client.mutate({ mutation: DELETE_POST, variables: { id } });
} catch (error) {
  if (error.message.includes("permission")) {
    showToast("You don't have permission for this action");
  } else if (error.message.includes("Authentication")) {
    redirectToLogin();
  }
}
```

## Complete Example

```python
# graphql/auth.py
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info
from django_matt.graphql import (
    graphql_type,
    graphql_input,
    IsAuthenticated,
    IsAdmin,
    authenticated_field,
)
from django_matt.auth import create_token_pair
from myapp.models import User

@graphql_input
class RegisterInput:
    email: str
    username: str
    password: str

@graphql_input
class LoginInput:
    email: str
    password: str

@graphql_type
class AuthPayload:
    access_token: str
    refresh_token: str
    user: "UserType"

@graphql_type
class UserType:
    id: int
    username: str

    @authenticated_field
    def email(self) -> str:
        return self._email

    @strawberry.field(permission_classes=[IsAdmin])
    def is_staff(self) -> bool:
        return self._is_staff

@strawberry.type
class Query:
    @strawberry.field
    def me(self, info: Info) -> UserType | None:
        user = info.context.get("user")
        if user and user.is_authenticated:
            return UserType.from_orm(user)
        return None

    @strawberry.field(permission_classes=[IsAdmin])
    def users(self) -> list[UserType]:
        return User.objects.all()

@strawberry.type
class Mutation:
    @strawberry.mutation
    def register(self, input: RegisterInput) -> AuthPayload:
        user = User.objects.create_user(
            email=input.email,
            username=input.username,
            password=input.password,
        )
        tokens = create_token_pair(user)
        return AuthPayload(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=UserType.from_orm(user),
        )

    @strawberry.mutation
    def login(self, input: LoginInput) -> AuthPayload:
        from django.contrib.auth import authenticate

        user = authenticate(email=input.email, password=input.password)
        if not user:
            raise Exception("Invalid email or password")

        tokens = create_token_pair(user)
        return AuthPayload(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=UserType.from_orm(user),
        )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_profile(
        self,
        info: Info,
        username: str | None = None,
    ) -> UserType:
        user = info.context["user"]
        if username:
            user.username = username
        user.save()
        return UserType.from_orm(user)

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def change_password(
        self,
        info: Info,
        current_password: str,
        new_password: str,
    ) -> bool:
        user = info.context["user"]
        if not user.check_password(current_password):
            raise Exception("Current password is incorrect")
        user.set_password(new_password)
        user.save()
        return True
```
