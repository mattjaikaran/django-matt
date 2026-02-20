# WebSocket Subscriptions

Django Matt provides real-time GraphQL subscriptions using WebSockets, allowing clients to receive live updates when data changes.

## Overview

Subscriptions enable real-time, event-driven communication:

```graphql
subscription {
  postCreated {
    id
    title
    author {
      name
    }
  }
}
```

When a new post is created, all subscribed clients immediately receive the data.

## Configuration

Enable subscriptions in your settings:

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "SUBSCRIPTIONS_ENABLED": True,
    "SUBSCRIPTION_KEEPALIVE": 30,  # Seconds between keepalive messages
}
```

## SubscriptionGenerator

The `SubscriptionGenerator` creates subscription resolvers for Django models:

```python
from django_matt.graphql import SubscriptionGenerator, create_type_from_model
from myapp.models import Post

PostType = create_type_from_model(Post)
generator = SubscriptionGenerator(Post, PostType)
```

## Event Subscriptions

### Created Events

Subscribe to new objects:

```python
import strawberry
from django_matt.graphql import SubscriptionGenerator

generator = SubscriptionGenerator(Post, PostType)

@strawberry.type
class Subscription:
    post_created = generator.created_subscription()
```

```graphql
subscription {
  postCreated {
    id
    title
    content
    createdAt
  }
}
```

### Updated Events

Subscribe to object updates:

```python
@strawberry.type
class Subscription:
    post_updated = generator.updated_subscription()
```

```graphql
subscription {
  postUpdated {
    id
    title
    content
    updatedAt
  }
}
```

### Deleted Events

Subscribe to deletions:

```python
@strawberry.type
class Subscription:
    post_deleted = generator.deleted_subscription()
```

```graphql
subscription {
  postDeleted {
    id
    modelName
  }
}
```

### All Events

Subscribe to all changes (create, update, delete):

```python
@strawberry.type
class Subscription:
    post_events = generator.all_events_subscription()
```

```graphql
subscription {
  postEvents {
    event    # "created", "updated", or "deleted"
    data {
      id
      title
    }
    timestamp
  }
}
```

## SubscriptionManager

The `SubscriptionManager` handles subscription registration and broadcasting:

### Registering Models

```python
from django_matt.graphql import SubscriptionManager, SubscriptionEvent

manager = SubscriptionManager()

# Register for all events
manager.register(Post, PostType)

# Register for specific events
manager.register(
    Comment,
    CommentType,
    events=[SubscriptionEvent.CREATED, SubscriptionEvent.DELETED],
)
```

### Custom Subscriptions

```python
from django_matt.graphql import get_subscription_manager
from typing import AsyncGenerator

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def my_posts_updates(
        self,
        info: Info,
    ) -> AsyncGenerator[PostType, None]:
        """Subscribe to updates for current user's posts."""
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            return

        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Post"):
            # Filter to only user's posts
            if message.data.author_id == user.id:
                yield message.data
```

## Subscription Events

### Event Types

```python
from django_matt.graphql import SubscriptionEvent

class SubscriptionEvent(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
```

### Subscription Message

```python
from django_matt.graphql import SubscriptionMessage

@dataclass
class SubscriptionMessage:
    event: SubscriptionEvent  # Type of event
    data: T                   # The object data
    model_name: str           # Name of the model
    timestamp: float          # Unix timestamp
```

## Using the Decorator

The `@subscribe_to_model` decorator simplifies subscription creation:

```python
from django_matt.graphql import subscribe_to_model, SubscriptionEvent
from typing import AsyncGenerator

@strawberry.type
class Subscription:
    @subscribe_to_model(Post, PostType)
    async def post_updates(self) -> AsyncGenerator[PostType, None]:
        """Subscribe to all post updates."""
        pass  # Implementation provided by decorator

    @subscribe_to_model(Post, PostType, events=[SubscriptionEvent.CREATED])
    async def new_posts(self) -> AsyncGenerator[PostType, None]:
        """Subscribe to new posts only."""
        pass
```

## Filtering Subscriptions

### By Field Value

```python
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def posts_by_category(
        self,
        category_id: strawberry.ID,
    ) -> AsyncGenerator[PostType, None]:
        """Subscribe to posts in a specific category."""
        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Post"):
            if (
                message.event == SubscriptionEvent.CREATED
                and str(message.data.category_id) == category_id
            ):
                yield message.data
```

### By User

```python
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def my_notifications(
        self,
        info: Info,
    ) -> AsyncGenerator[NotificationType, None]:
        """Subscribe to current user's notifications."""
        user = info.context.get("user")
        if not user:
            return

        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Notification"):
            if message.data.user_id == user.id:
                yield message.data
```

## Custom Event Types

Define custom event payloads:

```python
@graphql_type
class PostEventPayload:
    event: str
    post: PostType | None
    previous_values: dict | None = None
    changed_fields: list[str] | None = None

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def post_changes(self) -> AsyncGenerator[PostEventPayload, None]:
        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Post"):
            yield PostEventPayload(
                event=message.event.value,
                post=message.data if message.event != SubscriptionEvent.DELETED else None,
                changed_fields=getattr(message.data, "_changed_fields", None),
            )
```

## Broadcasting Custom Events

Manually broadcast events:

```python
from django_matt.graphql import get_subscription_manager, SubscriptionEvent, SubscriptionMessage

def publish_announcement(title: str, content: str):
    """Broadcast a custom announcement to subscribers."""
    manager = get_subscription_manager()

    # Create custom message
    message = SubscriptionMessage(
        event=SubscriptionEvent.CREATED,
        data={"title": title, "content": content},
        model_name="Announcement",
    )

    # Broadcast to subscribers
    for queue in manager._subscribers["Announcement"]:
        queue.put_nowait(message)
```

## ASGI Setup

Subscriptions require an ASGI server. Here's a complete setup:

### 1. Install Dependencies

```bash
uv add strawberry-graphql[django] uvicorn channels
```

### 2. Configure ASGI

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application
from strawberry.channels import GraphQLWSConsumer
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from myapp.graphql import schema

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("graphql/", GraphQLWSConsumer.as_asgi(schema=schema)),
    ]),
})
```

### 3. Run with Uvicorn

```bash
uvicorn myproject.asgi:application --reload
```

## Client Integration

### JavaScript/TypeScript

```typescript
import { createClient } from "graphql-ws";

const client = createClient({
  url: "ws://localhost:8000/graphql/",
  connectionParams: {
    authorization: `Bearer ${token}`,
  },
});

// Subscribe to events
const unsubscribe = client.subscribe(
  {
    query: `
      subscription {
        postCreated {
          id
          title
          author {
            name
          }
        }
      }
    `,
  },
  {
    next: (data) => {
      console.log("New post:", data.data.postCreated);
    },
    error: (err) => {
      console.error("Subscription error:", err);
    },
    complete: () => {
      console.log("Subscription complete");
    },
  }
);

// Unsubscribe when done
unsubscribe();
```

### React with urql

```typescript
import { useSubscription } from "urql";

const POST_SUBSCRIPTION = `
  subscription PostCreated {
    postCreated {
      id
      title
    }
  }
`;

function PostFeed() {
  const [result] = useSubscription({ query: POST_SUBSCRIPTION });

  useEffect(() => {
    if (result.data?.postCreated) {
      // Handle new post
      addPost(result.data.postCreated);
    }
  }, [result.data]);

  return <PostList posts={posts} />;
}
```

### React with Apollo

```typescript
import { useSubscription, gql } from "@apollo/client";

const POST_SUBSCRIPTION = gql`
  subscription PostCreated {
    postCreated {
      id
      title
    }
  }
`;

function PostFeed() {
  const { data, loading, error } = useSubscription(POST_SUBSCRIPTION);

  if (loading) return <p>Listening...</p>;
  if (error) return <p>Error: {error.message}</p>;

  return <NewPost post={data.postCreated} />;
}
```

## Complete Example

```python
# graphql/subscriptions.py
import strawberry
from typing import AsyncGenerator
from django_matt.graphql import (
    SubscriptionGenerator,
    SubscriptionManager,
    SubscriptionEvent,
    get_subscription_manager,
    create_type_from_model,
)
from myapp.models import Post, Comment, Notification

PostType = create_type_from_model(Post)
CommentType = create_type_from_model(Comment)
NotificationType = create_type_from_model(Notification)

# Create generators
post_subs = SubscriptionGenerator(Post, PostType)
comment_subs = SubscriptionGenerator(Comment, CommentType)

@strawberry.type
class Subscription:
    # Auto-generated subscriptions
    post_created = post_subs.created_subscription()
    post_updated = post_subs.updated_subscription()
    post_deleted = post_subs.deleted_subscription()
    post_events = post_subs.all_events_subscription()

    comment_created = comment_subs.created_subscription()

    # Custom filtered subscription
    @strawberry.subscription
    async def comments_on_post(
        self,
        post_id: strawberry.ID,
    ) -> AsyncGenerator[CommentType, None]:
        """Subscribe to comments on a specific post."""
        manager = get_subscription_manager()
        async for message in manager.subscribe_to("Comment"):
            if (
                message.event == SubscriptionEvent.CREATED
                and str(message.data.post_id) == post_id
            ):
                yield message.data

    # User-specific subscription
    @strawberry.subscription
    async def my_notifications(
        self,
        info: strawberry.Info,
    ) -> AsyncGenerator[NotificationType, None]:
        """Subscribe to notifications for the current user."""
        user = info.context.get("user")
        if not user or not user.is_authenticated:
            raise PermissionError("Authentication required")

        manager = get_subscription_manager()
        manager.register(Notification, NotificationType)

        async for message in manager.subscribe_to("Notification"):
            if message.data.user_id == user.id:
                yield message.data

    # Presence/typing indicator
    @strawberry.subscription
    async def user_typing(
        self,
        conversation_id: strawberry.ID,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to typing indicators in a conversation."""
        manager = get_subscription_manager()
        async for message in manager.subscribe_to(f"typing_{conversation_id}"):
            yield message.data  # Username of typing user
```

## Reference

### SubscriptionManager

```python
class SubscriptionManager:
    def register(
        self,
        model: type[Model],
        type_class: type,
        events: list[SubscriptionEvent] | None = None,
    ) -> None:
        """Register a model for subscriptions."""

    async def subscribe_to(
        self,
        model_name: str,
        events: list[SubscriptionEvent] | None = None,
    ) -> AsyncGenerator[SubscriptionMessage, None]:
        """Subscribe to events for a model."""

    async def subscribe_to_model(
        self,
        model: type[Model],
        events: list[SubscriptionEvent] | None = None,
    ) -> AsyncGenerator[SubscriptionMessage, None]:
        """Subscribe to events for a model by class."""
```

### SubscriptionGenerator

```python
class SubscriptionGenerator:
    def __init__(
        self,
        model: type[Model],
        type_class: type,
        manager: SubscriptionManager | None = None,
    ):
        ...

    def created_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        ...

    def updated_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        ...

    def deleted_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        ...

    def all_events_subscription(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> strawberry.subscription:
        ...
```

### Helper Functions

```python
def get_subscription_manager() -> SubscriptionManager:
    """Get the global subscription manager instance."""

def generate_subscription(
    model: type[Model],
    type_class: type,
    events: list[SubscriptionEvent] | None = None,
    name: str | None = None,
    description: str | None = None,
) -> strawberry.subscription:
    """Generate a subscription for a model."""

def subscribe_to_model(
    model: type[Model],
    type_class: type,
    events: list[SubscriptionEvent] | None = None,
) -> Callable:
    """Decorator to create a subscription for a model."""
```
