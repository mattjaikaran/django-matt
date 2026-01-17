"""
Dependency Injection for django-matt.

Provides a lightweight, type-safe DI container with:
- Service registration with singleton/scoped/transient lifetimes
- Auto-injection in controllers based on type hints
- Built-in dependencies for common needs (request, user, org)
- Async support

Quick Start:
    # 1. Define your services
    class EmailService:
        def send(self, to: str, subject: str, body: str):
            ...

    class UserService:
        def __init__(self, email: EmailService):
            self.email = email

    # 2. Register services
    from django_matt.di import container, Singleton, Scoped

    container.register(EmailService, lifetime=Singleton)
    container.register(UserService, lifetime=Singleton)

    # 3. Use in controllers (auto-injected)
    from django_matt.di import Depends

    class UserController(APIController):
        @post("send-welcome")
        async def send_welcome(
            self,
            request,
            user_id: int,
            user_service: UserService = Depends(),
        ):
            user_service.send_welcome_email(user_id)

    # 4. Or resolve manually
    user_service = container.resolve(UserService)

Built-in Dependencies:
    from django_matt.di import (
        CurrentUser,      # The authenticated user
        CurrentRequest,   # The current HttpRequest
        CurrentOrg,       # The current organization (multi-tenant)
        DBSession,        # Database session/connection
    )

    @get("profile")
    async def get_profile(
        self,
        request,
        user: User = CurrentUser(),
        org: Organization = CurrentOrg(),
    ):
        return {"user": user.email, "org": org.name}
"""

from .container import (
    Container,
    container,
    ServiceLifetime,
    Singleton,
    Scoped,
    Transient,
    ServiceDescriptor,
    ServiceNotFoundError,
    CircularDependencyError,
)

from .depends import (
    Depends,
    DependencyMarker,
)

from .builtins import (
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

from .middleware import (
    DependencyInjectionMiddleware,
    AsyncDependencyInjectionMiddleware,
    RequestScopeMiddleware,
    AsyncRequestScopeMiddleware,
    inject_dependencies,
    with_scope,
)

from .decorators import (
    injectable,
    inject,
    provides,
    singleton,
    scoped,
    transient,
    InjectableMeta,
)

__all__ = [
    # Container
    "Container",
    "container",
    "ServiceLifetime",
    "Singleton",
    "Scoped",
    "Transient",
    "ServiceDescriptor",
    "ServiceNotFoundError",
    "CircularDependencyError",
    # Depends
    "Depends",
    "DependencyMarker",
    # Built-ins
    "CurrentUser",
    "CurrentRequest",
    "CurrentOrg",
    "CurrentTenant",
    "DBSession",
    "Settings",
    "Cache",
    "Logger",
    # Middleware
    "DependencyInjectionMiddleware",
    "AsyncDependencyInjectionMiddleware",
    "RequestScopeMiddleware",
    "AsyncRequestScopeMiddleware",
    "inject_dependencies",
    "with_scope",
    # Decorators
    "injectable",
    "inject",
    "provides",
    "singleton",
    "scoped",
    "transient",
    "InjectableMeta",
    # Extra builtins
    "Query",
    "Header",
    "Path",
]
