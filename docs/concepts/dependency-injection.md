# Dependency Injection

django-matt includes a lightweight, type-safe DI container with support for singleton, scoped, and transient lifetimes. Dependencies are resolved automatically based on type hints.

## Quick Start

```python
from django_matt.di import container, Singleton, Depends

# 1. Define services
class EmailService:
    def send(self, to: str, subject: str, body: str): ...

class UserService:
    def __init__(self, email: EmailService):
        self.email = email

# 2. Register
container.register(EmailService, lifetime=Singleton)
container.register(UserService, lifetime=Singleton)

# 3. Use in controllers (auto-injected via Depends)
class UserController(APIController):
    @post("send-welcome")
    async def send_welcome(
        self,
        request,
        user_id: int,
        user_service: UserService = Depends(),
    ):
        user_service.send_welcome_email(user_id)
```

## The Container

The global container instance is `django_matt.di.container`. It manages service registration and resolution.

### Registration

```python
from django_matt.di import container, Singleton, Scoped, Transient

# Concrete class
container.register(EmailService, lifetime=Singleton)

# Interface -> Implementation
container.register(IUserRepository, SqlUserRepository, lifetime=Singleton)

# Factory function
container.register(Config, factory=lambda: Config.from_env(), lifetime=Singleton)

# Pre-existing instance
container.register_instance(my_logger, Logger)

# Factory with dependencies (auto-resolved)
container.register_factory(
    DatabasePool,
    factory=lambda config: DatabasePool(config.db_url),
    lifetime=Singleton,
)
```

All `register*` methods return `self` for chaining:

```python
container.register(ServiceA, lifetime=Singleton).register(ServiceB, lifetime=Scoped)
```

### Resolution

```python
# Explicit resolution
email_service = container.resolve(EmailService)

# Safe resolution (returns None if not found)
maybe_service = container.try_resolve(SomeOptionalService)

# Check registration
if container.is_registered(EmailService):
    ...
```

## Service Lifetimes

| Lifetime | Behavior |
|----------|----------|
| `Singleton` | One instance for the entire application. Created on first resolve, cached forever. Thread-safe. |
| `Scoped` | One instance per request scope. Created on first resolve within a scope, shared for that scope's duration. |
| `Transient` | New instance every time `resolve()` is called. |

### Scoped Dependencies

Scoped services require a scope context. The `DependencyInjectionMiddleware` creates one per request:

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.di.DependencyInjectionMiddleware",
]
```

Or create scopes manually:

```python
with container.create_scope() as scope:
    # Within this block, scoped services are cached per-scope
    service = scope.resolve(RequestContext)
    same_service = scope.resolve(RequestContext)  # same instance
```

Outside a scope, scoped services behave as transient (new instance each time).

## Depends()

`Depends()` is a marker that tells the DI system to inject a dependency. Use it as a default parameter value:

```python
from django_matt.di import Depends

@api.get("/orders")
async def list_orders(
    self,
    request,
    order_service: OrderService = Depends(),
    email_service: EmailService = Depends(),
):
    orders = await order_service.list_all()
    return orders
```

The DI system inspects the type hint to determine what to resolve from the container.

## Built-in Dependencies

django-matt provides built-in dependency markers for common needs:

```python
from django_matt.di import CurrentUser, CurrentRequest, CurrentOrg, DBSession, Settings, Cache, Logger

@api.get("/profile")
async def get_profile(
    self,
    request,
    user: User = CurrentUser(),       # authenticated user
    org: Organization = CurrentOrg(),  # current tenant (multi-tenant)
):
    return {"user": user.email, "org": org.name}

@api.get("/config")
async def get_config(
    self,
    request,
    settings: dict = Settings(),       # Django settings as dict
    cache: Cache = Cache(),            # cache backend
    logger: Logger = Logger(),         # configured logger
):
    ...
```

### Parameter Extraction

```python
from django_matt.di import Query, Header, Path

@api.get("/search")
async def search(
    self,
    request,
    q: str = Query(),                  # from ?q=...
    api_key: str = Header("X-API-Key"),
):
    ...
```

## Decorators

### @injectable

Register a class with the container at definition time:

```python
from django_matt.di import injectable, Singleton

@injectable(lifetime=Singleton)
class DatabaseConnection:
    def __init__(self):
        self.connect()

# Register as an interface implementation
@injectable(as_type=IUserRepository, lifetime=Singleton)
class SqlUserRepository(IUserRepository):
    ...

# Default (transient) lifetime
@injectable
class TemporaryWorker:
    ...
```

### @singleton, @scoped, @transient

Shorthand decorators:

```python
from django_matt.di import singleton, scoped, transient

@singleton
class AppConfig:
    def __init__(self):
        self.load()

@scoped
class RequestContext:
    pass

@transient
class EmailMessage:
    pass
```

### @inject

Decorator that resolves dependencies for a standalone function (not just controller methods):

```python
from django_matt.di import inject, Depends

@inject
async def process_order(
    order_id: int,
    order_service: OrderService = Depends(),
    email_service: EmailService = Depends(),
):
    order = await order_service.get(order_id)
    await email_service.send_confirmation(order)

# Call it — dependencies are auto-resolved
await process_order(order_id=42)
```

Works with both sync and async functions, standalone functions and class methods.

### @provides

Register a factory function for a service:

```python
from django_matt.di import provides, Singleton

@provides(DatabaseConnection, lifetime=Singleton)
def create_database_connection():
    return DatabaseConnection(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )

# Return type can be inferred from annotation
@provides(lifetime=Singleton)
def create_config() -> Config:
    return Config.from_env()
```

## Auto-Wiring

The container inspects constructor type hints to resolve dependencies automatically:

```python
class NotificationService:
    def __init__(self, email: EmailService, sms: SMSService):
        self.email = email
        self.sms = sms

# Both EmailService and SMSService are resolved from the container
container.register(EmailService, lifetime=Singleton)
container.register(SMSService, lifetime=Singleton)
container.register(NotificationService, lifetime=Singleton)

# Dependencies are resolved recursively
notification = container.resolve(NotificationService)
# notification.email is the singleton EmailService
# notification.sms is the singleton SMSService
```

### Circular Dependency Detection

The container detects circular dependencies at resolution time and raises `CircularDependencyError`:

```python
# A depends on B, B depends on A
container.register(ServiceA)  # __init__(self, b: ServiceB)
container.register(ServiceB)  # __init__(self, a: ServiceA)

container.resolve(ServiceA)
# CircularDependencyError: Circular dependency detected: ServiceA -> ServiceB -> ServiceA
```

## InjectableMeta

A metaclass that auto-injects dependencies when a class is instantiated:

```python
from django_matt.di import InjectableMeta, Depends

class UserService(metaclass=InjectableMeta):
    def __init__(
        self,
        repository: UserRepository = Depends(),
        email: EmailService = Depends(),
    ):
        self.repository = repository
        self.email = email

# Dependencies are auto-resolved on instantiation
service = UserService()
service.repository  # resolved UserRepository instance
```

## Testing with DI

### Override Services

Replace real services with test doubles:

```python
class MockEmailService:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

@pytest.fixture
def mock_email():
    mock = MockEmailService()
    container.register_instance(mock, EmailService)
    yield mock
    # Clean up
    container.register(EmailService, lifetime=Singleton)
```

### Scoped Testing

Use `create_scope()` to isolate scoped services in tests:

```python
async def test_scoped_service():
    with container.create_scope() as scope:
        ctx1 = scope.resolve(RequestContext)
        ctx2 = scope.resolve(RequestContext)
        assert ctx1 is ctx2  # same instance within scope

    with container.create_scope() as scope:
        ctx3 = scope.resolve(RequestContext)
        assert ctx3 is not ctx1  # different scope, different instance
```

### Clear Container

Reset the container between tests:

```python
@pytest.fixture(autouse=True)
def clean_container():
    yield
    container.clear()
```
