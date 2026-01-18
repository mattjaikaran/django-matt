"""
Dependency Injection Container.

Provides service registration and resolution with different lifetimes.
"""

import inspect
import threading
from contextvars import ContextVar
from enum import Enum
from typing import Any, Callable, TypeVar, Generic, get_type_hints, Union

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Lifetime options for registered services."""

    SINGLETON = "singleton"  # One instance for the entire application
    SCOPED = "scoped"        # One instance per request/scope
    TRANSIENT = "transient"  # New instance every time


# Convenience aliases
Singleton = ServiceLifetime.SINGLETON
Scoped = ServiceLifetime.SCOPED
Transient = ServiceLifetime.TRANSIENT


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not registered."""

    def __init__(self, service_type: type):
        self.service_type = service_type
        super().__init__(f"Service not found: {service_type.__name__}")


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""

    def __init__(self, chain: list[type]):
        self.chain = chain
        chain_str = " -> ".join(t.__name__ for t in chain)
        super().__init__(f"Circular dependency detected: {chain_str}")


class ServiceDescriptor:
    """Describes how to create and manage a service."""

    def __init__(
        self,
        service_type: type,
        implementation: Union[type, Callable, None] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        factory: Callable[..., Any] = None,
        instance: Any = None,
    ):
        self.service_type = service_type
        self.implementation = implementation or service_type
        self.lifetime = lifetime
        self.factory = factory
        self._instance = instance  # For pre-registered instances

    def __repr__(self):
        return (
            f"ServiceDescriptor("
            f"type={self.service_type.__name__}, "
            f"impl={self.implementation.__name__ if isinstance(self.implementation, type) else 'factory'}, "
            f"lifetime={self.lifetime.value})"
        )


# Context variable for scoped instances
_scoped_instances: ContextVar[dict[type, Any]] = ContextVar(
    "scoped_instances", default=None
)


class Container:
    """
    Dependency Injection Container.

    Manages service registration and resolution with support for
    singleton, scoped, and transient lifetimes.

    Example:
        container = Container()

        # Register a singleton
        container.register(DatabaseConnection, lifetime=Singleton)

        # Register with interface
        container.register(IEmailService, EmailService, lifetime=Singleton)

        # Register with factory
        container.register(
            Config,
            factory=lambda: Config.from_env(),
            lifetime=Singleton
        )

        # Register an existing instance
        container.register_instance(logger, Logger)

        # Resolve
        db = container.resolve(DatabaseConnection)
        email = container.resolve(IEmailService)
    """

    def __init__(self):
        self._services: dict[type, ServiceDescriptor] = {}
        self._singletons: dict[type, Any] = {}
        self._lock = threading.RLock()  # Reentrant lock for nested resolution
        self._resolving: set[type] = set()  # For circular dependency detection

    def register(
        self,
        service_type: type[T],
        implementation: Union[type[T], None] = None,
        *,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        factory: Callable[..., T] = None,
    ) -> "Container":
        """
        Register a service with the container.

        Args:
            service_type: The type to register (interface or concrete class)
            implementation: The concrete implementation (defaults to service_type)
            lifetime: How long instances should live
            factory: Optional factory function to create instances

        Returns:
            self for chaining

        Example:
            container.register(UserService, lifetime=Singleton)
            container.register(IRepository, SqlRepository, lifetime=Scoped)
            container.register(Config, factory=load_config, lifetime=Singleton)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=lifetime,
            factory=factory,
        )
        self._services[service_type] = descriptor
        return self

    def register_instance(
        self,
        instance: T,
        service_type: type[T] = None,
    ) -> "Container":
        """
        Register an existing instance as a singleton.

        Args:
            instance: The instance to register
            service_type: The type to register as (defaults to instance's type)

        Returns:
            self for chaining

        Example:
            logger = Logger(level="DEBUG")
            container.register_instance(logger, Logger)
        """
        service_type = service_type or type(instance)
        descriptor = ServiceDescriptor(
            service_type=service_type,
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance,
        )
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance
        return self

    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "Container":
        """
        Register a factory function for a service.

        Args:
            service_type: The type to register
            factory: Function that creates instances
            lifetime: How long instances should live

        Returns:
            self for chaining
        """
        return self.register(service_type, factory=factory, lifetime=lifetime)

    def resolve(self, service_type: type[T]) -> T:
        """
        Resolve a service from the container.

        Args:
            service_type: The type to resolve

        Returns:
            An instance of the service

        Raises:
            ServiceNotFoundError: If the service is not registered
            CircularDependencyError: If circular dependencies are detected
        """
        # Check for circular dependencies
        if service_type in self._resolving:
            chain = list(self._resolving) + [service_type]
            raise CircularDependencyError(chain)

        # Check if registered
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type)

        descriptor = self._services[service_type]

        # Handle singleton - return cached instance if exists
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

        # Handle scoped - return cached instance if in scope
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            scoped = _scoped_instances.get()
            if scoped is not None and service_type in scoped:
                return scoped[service_type]

        # Track that we're resolving this service (for circular dependency detection)
        self._resolving.add(service_type)
        try:
            # Handle singleton
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                with self._lock:
                    # Double-check after acquiring lock
                    if service_type in self._singletons:
                        return self._singletons[service_type]

                    instance = self._create_instance(descriptor)
                    self._singletons[service_type] = instance
                    return instance

            # Handle scoped
            if descriptor.lifetime == ServiceLifetime.SCOPED:
                scoped = _scoped_instances.get()
                if scoped is None:
                    # No scope, treat as transient
                    return self._create_instance(descriptor)

                if service_type in scoped:
                    return scoped[service_type]

                instance = self._create_instance(descriptor)
                scoped[service_type] = instance
                return instance

            # Transient - always create new
            return self._create_instance(descriptor)
        finally:
            self._resolving.discard(service_type)

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance based on the service descriptor."""
        # Return pre-registered instance if available
        if descriptor._instance is not None:
            return descriptor._instance

        # Use factory if provided
        if descriptor.factory is not None:
            # Check if factory needs dependencies
            sig = inspect.signature(descriptor.factory)
            if sig.parameters:
                return self._call_with_dependencies(descriptor.factory)
            return descriptor.factory()

        # Create instance from implementation
        impl = descriptor.implementation
        if impl is None:
            impl = descriptor.service_type

        return self._call_with_dependencies(impl)

    def _call_with_dependencies(self, callable_obj: Callable) -> Any:
        """Call a callable with its dependencies resolved."""
        # Get type hints for constructor/function
        try:
            if inspect.isclass(callable_obj):
                hints = get_type_hints(callable_obj.__init__)
            else:
                hints = get_type_hints(callable_obj)
        except Exception:
            hints = {}

        # Get signature
        if inspect.isclass(callable_obj):
            sig = inspect.signature(callable_obj.__init__)
        else:
            sig = inspect.signature(callable_obj)

        # Resolve dependencies
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Get type from hints or annotation
            param_type = hints.get(param_name) or param.annotation

            if param_type is inspect.Parameter.empty:
                # No type hint, skip (will use default or raise error)
                continue

            # Check if it's a registered service
            if param_type in self._services:
                kwargs[param_name] = self.resolve(param_type)

        return callable_obj(**kwargs)

    def try_resolve(self, service_type: type[T]) -> Union[T, None]:
        """
        Try to resolve a service, returning None if not found.

        Args:
            service_type: The type to resolve

        Returns:
            An instance of the service, or None if not registered
        """
        try:
            return self.resolve(service_type)
        except ServiceNotFoundError:
            return None

    def is_registered(self, service_type: type) -> bool:
        """Check if a service type is registered."""
        return service_type in self._services

    def get_descriptor(self, service_type: type) -> Union[ServiceDescriptor, None]:
        """Get the service descriptor for a type."""
        return self._services.get(service_type)

    def clear(self):
        """Clear all registrations and cached instances."""
        self._services.clear()
        self._singletons.clear()

    def create_scope(self) -> "ScopedContainer":
        """
        Create a new scope for scoped services.

        Use as a context manager:
            with container.create_scope() as scope:
                service = scope.resolve(MyScopedService)
        """
        return ScopedContainer(self)

    def __contains__(self, service_type: type) -> bool:
        """Check if a service type is registered."""
        return self.is_registered(service_type)

    def __repr__(self):
        return f"Container(services={len(self._services)})"


class ScopedContainer:
    """
    A scoped container that manages per-scope instances.

    Use as a context manager to create a new scope:
        with container.create_scope() as scope:
            service = scope.resolve(MyScopedService)
    """

    def __init__(self, parent: Container):
        self._parent = parent
        self._token = None

    def __enter__(self) -> "ScopedContainer":
        self._token = _scoped_instances.set({})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _scoped_instances.reset(self._token)
        return False

    def resolve(self, service_type: type[T]) -> T:
        """Resolve a service within this scope."""
        return self._parent.resolve(service_type)


# Global container instance
container = Container()
