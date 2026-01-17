"""
Dependency markers for parameter injection.

Provides the Depends() marker for declaring dependencies in function parameters.
"""

import inspect
from typing import Any, Callable, TypeVar, Union, get_type_hints

from .container import container as default_container, Container

T = TypeVar("T")


class DependencyMarker:
    """
    Base class for dependency markers.

    Subclass this to create custom dependency resolution logic.
    """

    def resolve(self, request=None, container: Container = None) -> Any:
        """
        Resolve the dependency.

        Args:
            request: The current HTTP request (if available)
            container: The DI container to use

        Returns:
            The resolved dependency value
        """
        raise NotImplementedError


class Depends(DependencyMarker):
    """
    Marker for declaring a dependency that should be injected.

    Usage:
        from django_matt.di import Depends

        class MyController(APIController):
            @get("users")
            async def list_users(
                self,
                request,
                user_service: UserService = Depends(),
                # Or with explicit type:
                email: EmailService = Depends(EmailService),
                # Or with factory function:
                config: Config = Depends(lambda: Config.load()),
            ):
                ...
    """

    def __init__(
        self,
        dependency: Union[type, Callable[..., T], None] = None,
        *,
        use_cache: bool = True,
    ):
        """
        Create a dependency marker.

        Args:
            dependency: The type or factory to resolve. If None, uses the
                       parameter's type annotation.
            use_cache: Whether to cache the resolved value for this request.
                      Defaults to True.
        """
        self.dependency = dependency
        self.use_cache = use_cache
        self._param_name: str = None
        self._param_type: type = None

    def resolve(self, request=None, container: Container = None) -> Any:
        """Resolve the dependency."""
        container = container or default_container

        # If dependency is a callable factory
        if self.dependency is not None and callable(self.dependency):
            if inspect.isclass(self.dependency):
                # It's a class, resolve from container
                if container.is_registered(self.dependency):
                    return container.resolve(self.dependency)
                # Not registered, try to instantiate with dependencies
                return container._call_with_dependencies(self.dependency)
            else:
                # It's a factory function
                return self._call_factory(self.dependency, request, container)

        # Use parameter type from annotation
        if self._param_type is not None:
            if container.is_registered(self._param_type):
                return container.resolve(self._param_type)
            # Try to instantiate directly
            return container._call_with_dependencies(self._param_type)

        raise ValueError(
            f"Cannot resolve dependency: no type specified and no annotation "
            f"found for parameter '{self._param_name}'"
        )

    def _call_factory(
        self,
        factory: Callable,
        request,
        container: Container,
    ) -> Any:
        """Call a factory function with its dependencies."""
        sig = inspect.signature(factory)
        hints = {}
        try:
            hints = get_type_hints(factory)
        except Exception:
            pass

        kwargs = {}
        for param_name, param in sig.parameters.items():
            # Special handling for 'request'
            if param_name == "request":
                kwargs["request"] = request
                continue

            # Get type
            param_type = hints.get(param_name) or param.annotation
            if param_type is inspect.Parameter.empty:
                continue

            # Resolve from container
            if container.is_registered(param_type):
                kwargs[param_name] = container.resolve(param_type)

        return factory(**kwargs)

    def __repr__(self):
        if self.dependency:
            dep_name = (
                self.dependency.__name__
                if hasattr(self.dependency, "__name__")
                else str(self.dependency)
            )
            return f"Depends({dep_name})"
        return "Depends()"


def resolve_dependencies(
    func: Callable,
    request=None,
    container: Container = None,
    **provided_kwargs,
) -> dict[str, Any]:
    """
    Resolve all dependencies for a function.

    Args:
        func: The function to resolve dependencies for
        request: The current HTTP request
        container: The DI container to use
        **provided_kwargs: Already-provided keyword arguments

    Returns:
        Dictionary of resolved dependencies
    """
    container = container or default_container

    # Get signature and type hints
    sig = inspect.signature(func)
    hints = {}
    try:
        hints = get_type_hints(func)
    except Exception:
        pass

    resolved = {}

    for param_name, param in sig.parameters.items():
        # Skip if already provided
        if param_name in provided_kwargs:
            continue

        # Skip self/cls
        if param_name in ("self", "cls"):
            continue

        # Check for Depends marker in default value
        if isinstance(param.default, DependencyMarker):
            marker = param.default
            # Set param info for resolution
            if hasattr(marker, "_param_name"):
                marker._param_name = param_name
            if hasattr(marker, "_param_type"):
                marker._param_type = hints.get(param_name) or param.annotation
                if marker._param_type is inspect.Parameter.empty:
                    marker._param_type = None

            resolved[param_name] = marker.resolve(request=request, container=container)
            continue

        # Check if type is registered in container
        param_type = hints.get(param_name) or param.annotation
        if param_type is not inspect.Parameter.empty:
            if container.is_registered(param_type):
                resolved[param_name] = container.resolve(param_type)

    return resolved


async def aresolve_dependencies(
    func: Callable,
    request=None,
    container: Container = None,
    **provided_kwargs,
) -> dict[str, Any]:
    """
    Async version of resolve_dependencies.

    Some dependency markers may need async resolution (e.g., database queries).
    """
    container = container or default_container

    # Get signature and type hints
    sig = inspect.signature(func)
    hints = {}
    try:
        hints = get_type_hints(func)
    except Exception:
        pass

    resolved = {}

    for param_name, param in sig.parameters.items():
        # Skip if already provided
        if param_name in provided_kwargs:
            continue

        # Skip self/cls
        if param_name in ("self", "cls"):
            continue

        # Check for Depends marker in default value
        if isinstance(param.default, DependencyMarker):
            marker = param.default
            # Set param info for resolution
            if hasattr(marker, "_param_name"):
                marker._param_name = param_name
            if hasattr(marker, "_param_type"):
                marker._param_type = hints.get(param_name) or param.annotation
                if marker._param_type is inspect.Parameter.empty:
                    marker._param_type = None

            # Check if marker has async resolve
            if hasattr(marker, "aresolve"):
                resolved[param_name] = await marker.aresolve(
                    request=request, container=container
                )
            else:
                resolved[param_name] = marker.resolve(
                    request=request, container=container
                )
            continue

        # Check if type is registered in container
        param_type = hints.get(param_name) or param.annotation
        if param_type is not inspect.Parameter.empty:
            if container.is_registered(param_type):
                resolved[param_name] = container.resolve(param_type)

    return resolved
