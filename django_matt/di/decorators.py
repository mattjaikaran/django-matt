"""
Dependency Injection Decorators.

Provides decorators for:
- @injectable: Mark a class as injectable (auto-register)
- @inject: Inject dependencies into a function
- @provides: Mark a method as a factory for a service
"""

import inspect
from collections.abc import Callable
from functools import wraps

from .container import (
    Container,
    Scoped,
    ServiceLifetime,
    Singleton,
    Transient,
)
from .container import (
    container as default_container,
)
from .depends import aresolve_dependencies, resolve_dependencies


def injectable[T](
    cls: type[T] = None,
    *,
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    as_type: type = None,
    container: Container = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator that registers a class with the DI container.

    Usage:
        from django_matt.di import injectable, Singleton

        @injectable
        class UserRepository:
            def get_user(self, id: int) -> User:
                ...

        @injectable(lifetime=Singleton)
        class DatabaseConnection:
            def __init__(self):
                self.connect()

        # Register as interface
        @injectable(as_type=IUserRepository, lifetime=Singleton)
        class SqlUserRepository(IUserRepository):
            ...
    """
    container = container or default_container

    def decorator(cls: type[T]) -> type[T]:
        service_type = as_type or cls
        container.register(service_type, cls, lifetime=lifetime)
        return cls

    if cls is not None:
        return decorator(cls)
    return decorator


def inject(
    func: Callable = None,
    *,
    container: Container = None,
) -> Callable:
    """
    Decorator that injects dependencies into a function or method.

    Dependencies are resolved based on:
    1. Parameters with Depends() default values
    2. Parameters with types registered in the container

    Usage:
        from django_matt.di import inject, Depends

        @inject
        def process_order(
            order_id: int,
            order_service: OrderService = Depends(),
            email_service: EmailService = Depends(),
        ):
            order = order_service.get(order_id)
            email_service.send_confirmation(order)

        # Works with async functions
        @inject
        async def process_order_async(
            order_id: int,
            order_service: OrderService = Depends(),
        ):
            order = await order_service.get_async(order_id)
            return order

        # Works with class methods
        class OrderProcessor:
            @inject
            def process(
                self,
                order_id: int,
                order_service: OrderService = Depends(),
            ):
                ...
    """
    container = container or default_container

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                # Extract request from args if present
                request = None
                if args and hasattr(args[0], "META"):
                    request = args[0]
                elif len(args) > 1 and hasattr(args[1], "META"):
                    # Method call: self, request, ...
                    request = args[1]

                # Resolve dependencies
                deps = await aresolve_dependencies(
                    fn,
                    request=request,
                    container=container,
                    **kwargs,
                )
                kwargs.update(deps)
                return await fn(*args, **kwargs)

            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            # Extract request from args if present
            request = None
            if args and hasattr(args[0], "META"):
                request = args[0]
            elif len(args) > 1 and hasattr(args[1], "META"):
                # Method call: self, request, ...
                request = args[1]

            # Resolve dependencies
            deps = resolve_dependencies(
                fn,
                request=request,
                container=container,
                **kwargs,
            )
            kwargs.update(deps)
            return fn(*args, **kwargs)

        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator


def provides[T](
    service_type: type[T] = None,
    *,
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    container: Container = None,
) -> Callable:
    """
    Decorator that marks a function or method as a factory for a service.

    Usage:
        from django_matt.di import provides, Singleton

        @provides(DatabaseConnection, lifetime=Singleton)
        def create_database_connection():
            return DatabaseConnection(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
            )

        # The return type can be inferred
        @provides(lifetime=Singleton)
        def create_config() -> Config:
            return Config.from_env()

        # In a configuration class
        class AppConfig:
            @provides(EmailService, lifetime=Singleton)
            def email_service(self) -> EmailService:
                return EmailService(smtp_host=self.smtp_host)
    """
    container = container or default_container

    def decorator(fn: Callable) -> Callable:
        # Determine service type from annotation or argument
        nonlocal service_type
        if service_type is None:
            hints = {}
            try:
                from typing import get_type_hints

                hints = get_type_hints(fn)
            except Exception:
                pass
            service_type = hints.get("return")

        if service_type is None:
            raise ValueError(
                f"Cannot determine service type for {fn.__name__}. "
                "Provide service_type argument or add return type annotation."
            )

        # Register the factory
        container.register(service_type, factory=fn, lifetime=lifetime)

        return fn

    return decorator


def singleton[T](
    cls: type[T] = None,
    *,
    as_type: type = None,
    container: Container = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Shortcut for @injectable(lifetime=Singleton).

    Usage:
        from django_matt.di import singleton

        @singleton
        class AppConfig:
            def __init__(self):
                self.load_config()
    """
    return injectable(cls, lifetime=Singleton, as_type=as_type, container=container)


def scoped[T](
    cls: type[T] = None,
    *,
    as_type: type = None,
    container: Container = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Shortcut for @injectable(lifetime=Scoped).

    Usage:
        from django_matt.di import scoped

        @scoped
        class RequestContext:
            def __init__(self):
                self.start_time = time.time()
    """
    return injectable(cls, lifetime=Scoped, as_type=as_type, container=container)


def transient[T](
    cls: type[T] = None,
    *,
    as_type: type = None,
    container: Container = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Shortcut for @injectable(lifetime=Transient).

    Usage:
        from django_matt.di import transient

        @transient
        class EmailMessage:
            def __init__(self):
                self.created_at = datetime.now()
    """
    return injectable(cls, lifetime=Transient, as_type=as_type, container=container)


class InjectableMeta(type):
    """
    Metaclass that automatically injects dependencies into __init__.

    Usage:
        from django_matt.di import InjectableMeta, Depends

        class UserService(metaclass=InjectableMeta):
            def __init__(
                self,
                repository: UserRepository = Depends(),
                email: EmailService = Depends(),
            ):
                self.repository = repository
                self.email = email

            def create_user(self, data):
                user = self.repository.create(data)
                self.email.send_welcome(user)
                return user

        # Now when you instantiate, dependencies are auto-resolved:
        service = UserService()  # repository and email are injected
    """

    def __call__(cls, *args, **kwargs):
        # Resolve dependencies for __init__
        deps = resolve_dependencies(
            cls.__init__,
            request=None,
            container=default_container,
            **kwargs,
        )
        kwargs.update(deps)
        return super().__call__(*args, **kwargs)
