# Dependency Injection

Django Matt provides a lightweight, type-safe Dependency Injection (DI) container for building modular, testable applications.

## Overview

```mermaid
flowchart TB
    subgraph "DI Container"
        REG[Service Registration]
        RES[Service Resolution]
        LIFE[Lifetime Management]
    end

    subgraph "Lifetimes"
        SING[Singleton<br/>One instance forever]
        SCOPED[Scoped<br/>One per request]
        TRANS[Transient<br/>New every time]
    end

    subgraph "Built-in Dependencies"
        USER[CurrentUser]
        REQ[CurrentRequest]
        ORG[CurrentOrg]
        DB[DBSession]
        CACHE[Cache]
        LOG[Logger]
    end

    REG --> LIFE
    LIFE --> SING
    LIFE --> SCOPED
    LIFE --> TRANS
    RES --> USER
    RES --> REQ
    RES --> ORG
```

## Quick Start

```python
from django_matt.di import container, Singleton, Scoped, Depends

# 1. Define your services
class EmailService:
    def send(self, to: str, subject: str, body: str):
        # Send email logic
        pass

class UserService:
    def __init__(self, email: EmailService):
        self.email = email

    def send_welcome(self, user_id: int):
        user = User.objects.get(id=user_id)
        self.email.send(user.email, "Welcome!", "Welcome to our app!")

# 2. Register services
container.register(EmailService, lifetime=Singleton)
container.register(UserService, lifetime=Singleton)

# 3. Use in controllers (auto-injected)
class UserController(APIController):
    @post("/send-welcome")
    async def send_welcome(
        self,
        request,
        user_id: int,
        user_service: UserService = Depends(),
    ):
        user_service.send_welcome(user_id)
        return {"status": "sent"}

# 4. Or resolve manually
user_service = container.resolve(UserService)
```

## Service Lifetimes

### Singleton

One instance for the entire application lifetime. Perfect for stateless services, database connections, or expensive-to-create objects.

```python
from django_matt.di import container, Singleton

class DatabaseConnection:
    def __init__(self):
        self.pool = create_pool()

container.register(DatabaseConnection, lifetime=Singleton)

# Same instance everywhere
db1 = container.resolve(DatabaseConnection)
db2 = container.resolve(DatabaseConnection)
assert db1 is db2  # True
```

### Scoped

One instance per request/scope. Useful for request-specific data or per-request caching.

```python
from django_matt.di import container, Scoped

class RequestCache:
    def __init__(self):
        self.data = {}

container.register(RequestCache, lifetime=Scoped)

# Different instance per scope
with container.create_scope() as scope:
    cache1 = scope.resolve(RequestCache)
    cache2 = scope.resolve(RequestCache)
    assert cache1 is cache2  # Same within scope

# New scope = new instance
with container.create_scope() as scope:
    cache3 = scope.resolve(RequestCache)
    assert cache3 is not cache1  # Different across scopes
```

### Transient

New instance every time. For lightweight services or when each consumer needs its own instance.

```python
from django_matt.di import container, Transient

class QueryBuilder:
    def __init__(self):
        self.parts = []

container.register(QueryBuilder, lifetime=Transient)

# Different instance every time
qb1 = container.resolve(QueryBuilder)
qb2 = container.resolve(QueryBuilder)
assert qb1 is not qb2  # Always new
```

## Registration Methods

### Basic Registration

```python
# Register concrete class
container.register(EmailService, lifetime=Singleton)

# Register interface with implementation
container.register(IEmailService, SmtpEmailService, lifetime=Singleton)

# Register with factory function
container.register(
    Config,
    factory=lambda: Config.from_env(),
    lifetime=Singleton
)

# Register existing instance
logger = Logger(level="DEBUG")
container.register_instance(logger, Logger)
```

### Using Decorators

```python
from django_matt.di import injectable, singleton, scoped, transient

@singleton
class ConfigService:
    def __init__(self):
        self.settings = load_settings()

@scoped
class RequestContext:
    def __init__(self):
        self.start_time = time.time()

@transient
class QueryBuilder:
    pass

# Or with the base decorator
@injectable(lifetime=Singleton)
class MyService:
    pass
```

## Dependency Resolution

### Automatic Resolution

Dependencies are automatically resolved based on type hints:

```python
class NotificationService:
    def __init__(self, email: EmailService, sms: SMSService):
        self.email = email
        self.sms = sms

container.register(EmailService, lifetime=Singleton)
container.register(SMSService, lifetime=Singleton)
container.register(NotificationService, lifetime=Singleton)

# Dependencies are automatically injected
notification = container.resolve(NotificationService)
# notification.email is EmailService instance
# notification.sms is SMSService instance
```

### Using Depends() Marker

In controllers, use `Depends()` to mark parameters for injection:

```python
from django_matt.di import Depends

class OrderController(APIController):
    @post("/orders")
    async def create_order(
        self,
        request,
        data: OrderCreate,
        order_service: OrderService = Depends(),
        notification: NotificationService = Depends(),
    ):
        order = order_service.create(data)
        notification.send_order_confirmation(order)
        return order
```

### Manual Resolution

```python
# Resolve a service
service = container.resolve(MyService)

# Try to resolve (returns None if not found)
service = container.try_resolve(MyService)

# Check if registered
if container.is_registered(MyService):
    service = container.resolve(MyService)
```

## Built-in Dependencies

Django Matt provides several built-in dependencies for common needs:

```python
from django_matt.di import (
    CurrentUser,
    CurrentRequest,
    CurrentOrg,
    CurrentTenant,
    DBSession,
    Settings,
    Cache,
    Logger,
    Query,
    Header,
    Path,
)

@api.get("/profile")
async def get_profile(
    request,
    user: User = CurrentUser(),           # Authenticated user
    org: Organization = CurrentOrg(),      # Current organization (multi-tenant)
):
    return {"user": user.email, "org": org.name}

@api.get("/items")
async def list_items(
    request,
    page: int = Query(default=1),          # Query parameter
    api_key: str = Header("X-API-Key"),    # Header value
    logger: logging.Logger = Logger(),     # Logger instance
):
    logger.info(f"Listing items, page {page}")
    return {"page": page}
```

### CurrentUser

Returns the authenticated user or raises 401 if not authenticated.

```python
@api.get("/me")
async def get_me(request, user: User = CurrentUser()):
    return {"id": user.id, "email": user.email}

# Optional user (None if not authenticated)
@api.get("/maybe-me")
async def get_maybe_me(request, user: User = CurrentUser(optional=True)):
    if user:
        return {"user": user.email}
    return {"user": None}
```

### CurrentOrg / CurrentTenant

For multi-tenant applications:

```python
@api.get("/projects")
async def list_projects(
    request,
    org: Organization = CurrentOrg(),
):
    return Project.objects.filter(organization=org)
```

### Query, Header, Path

Extract request parameters:

```python
@api.get("/search")
async def search(
    request,
    q: str = Query(),                      # Required query param
    limit: int = Query(default=10),        # Optional with default
    auth: str = Header("Authorization"),   # Required header
):
    return {"query": q, "limit": limit}

@api.get("/users/{user_id}")
async def get_user(
    request,
    user_id: int = Path(),  # From URL path
):
    return User.objects.get(id=user_id)
```

## Middleware

Enable DI middleware for automatic scope management:

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_matt.di.DependencyInjectionMiddleware',
    # Or for async views:
    # 'django_matt.di.AsyncDependencyInjectionMiddleware',
]
```

This creates a new scope for each request, ensuring scoped services are properly managed.

## Error Handling

### ServiceNotFoundError

Raised when resolving an unregistered service:

```python
from django_matt.di import ServiceNotFoundError

try:
    service = container.resolve(UnknownService)
except ServiceNotFoundError as e:
    print(f"Service not found: {e.service_type}")
```

### CircularDependencyError

Raised when circular dependencies are detected:

```python
from django_matt.di import CircularDependencyError

class ServiceA:
    def __init__(self, b: "ServiceB"): pass

class ServiceB:
    def __init__(self, a: ServiceA): pass

container.register(ServiceA)
container.register(ServiceB)

try:
    container.resolve(ServiceA)
except CircularDependencyError as e:
    print(f"Circular: {e.chain}")
    # Output: Circular: [ServiceA, ServiceB, ServiceA]
```

## Testing

DI makes testing easy by allowing service substitution:

```python
import pytest
from django_matt.di import container

class MockEmailService:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

@pytest.fixture
def mock_email():
    # Save original
    original = container.try_resolve(EmailService)

    # Register mock
    mock = MockEmailService()
    container.register_instance(mock, EmailService)

    yield mock

    # Restore original
    if original:
        container.register_instance(original, EmailService)

def test_send_welcome(mock_email):
    user_service = container.resolve(UserService)
    user_service.send_welcome(1)

    assert len(mock_email.sent) == 1
    assert "Welcome" in mock_email.sent[0][1]
```

## Best Practices

1. **Register services at startup** - Register all services when the application starts (e.g., in `AppConfig.ready()`)

2. **Use interfaces** - Register interfaces with implementations for flexibility:
   ```python
   container.register(IEmailService, SmtpEmailService, lifetime=Singleton)
   ```

3. **Prefer constructor injection** - Let dependencies be injected via constructors:
   ```python
   class OrderService:
       def __init__(self, db: Database, cache: Cache):
           self.db = db
           self.cache = cache
   ```

4. **Keep services stateless** - Singletons should be stateless or thread-safe

5. **Use scoped services for request data** - Request-specific caching or context should be scoped

6. **Test with mocks** - Replace services with mocks in tests for isolation
