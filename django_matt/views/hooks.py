"""
Lifecycle hooks for Django Matt CRUD views.

Provides a comprehensive hook system for executing custom logic before/after
CRUD operations with support for async, priority ordering, and error handling.

Example:
    from django_matt.views import APIViewSet, ListView, CreateView
    from django_matt.views.hooks import before_create, after_create, on_error

    class ProductViewSet(APIViewSet):
        model = Product

        # Class-based hooks
        async def before_create(self, request, data):
            data["created_by"] = request.user
            return data

        async def after_create(self, request, instance):
            await send_notification(f"Product {instance.name} created")
            return instance

    # Or decorator-based hooks
    @before_create(ProductViewSet)
    async def validate_product(request, data):
        if data["price"] < 0:
            raise ValidationError("Price must be positive")
        return data

    # Global hooks
    @register_global_hook("after_create")
    async def track_all_creates(request, instance, view_class):
        await analytics.track("object_created", {"id": instance.id})
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

from django.db import models
from django.http import HttpRequest

from pydantic import BaseModel

# Type aliases
HookFunction = Callable[..., Any]
AsyncHookFunction = Callable[..., Any]  # Coroutine functions
ViewSetType = TypeVar("ViewSetType")


class HookType(str, Enum):
    """Types of lifecycle hooks available."""

    BEFORE_LIST = "before_list"
    AFTER_LIST = "after_list"
    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"
    BEFORE_READ = "before_read"
    AFTER_READ = "after_read"
    BEFORE_UPDATE = "before_update"
    AFTER_UPDATE = "after_update"
    BEFORE_DELETE = "before_delete"
    AFTER_DELETE = "after_delete"
    BEFORE_BULK_CREATE = "before_bulk_create"
    AFTER_BULK_CREATE = "after_bulk_create"
    BEFORE_BULK_UPDATE = "before_bulk_update"
    AFTER_BULK_UPDATE = "after_bulk_update"
    BEFORE_BULK_DELETE = "before_bulk_delete"
    AFTER_BULK_DELETE = "after_bulk_delete"
    ON_ERROR = "on_error"


@dataclass
class HookContext:
    """
    Context passed to all hook functions.

    Provides access to request, user, instance, and view information.
    """

    request: HttpRequest
    view_class: type
    viewset: Any
    hook_type: HookType
    instance: models.Model | None = None
    data: dict[str, Any] | BaseModel | None = None
    queryset: models.QuerySet | None = None
    error: Exception | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def user(self) -> Any:
        """Get the current user from the request."""
        return getattr(self.request, "user", None)

    @property
    def model(self) -> type[models.Model] | None:
        """Get the model class from the viewset."""
        return getattr(self.viewset, "model", None)


@dataclass
class RegisteredHook:
    """
    A registered hook with metadata.
    """

    func: HookFunction
    hook_type: HookType
    priority: int = 0  # Lower = higher priority (runs first)
    condition: Callable[[HookContext], bool] | None = None  # Optional condition
    is_async: bool = False
    name: str = ""
    viewset_class: type | None = None  # None means global

    def __post_init__(self):
        if not self.name:
            self.name = getattr(self.func, "__name__", str(self.func))
        # Auto-detect async
        import asyncio

        self.is_async = asyncio.iscoroutinefunction(self.func)

    def should_run(self, context: HookContext) -> bool:
        """Check if this hook should run for the given context."""
        # Check viewset class match
        if self.viewset_class is not None:
            if not isinstance(context.viewset, self.viewset_class):
                return False

        # Check custom condition
        if self.condition is not None:
            try:
                return self.condition(context)
            except Exception:
                return False

        return True


class HookManager:
    """
    Central manager for registering and executing lifecycle hooks.

    Supports:
    - Global hooks (apply to all viewsets)
    - ViewSet-specific hooks
    - Priority ordering
    - Conditional execution
    - Async hook support
    - Error handling
    """

    def __init__(self):
        self._global_hooks: dict[HookType, list[RegisteredHook]] = {
            hook_type: [] for hook_type in HookType
        }
        self._viewset_hooks: dict[type, dict[HookType, list[RegisteredHook]]] = {}

    def register(
        self,
        hook_type: HookType | str,
        func: HookFunction,
        viewset_class: type | None = None,
        priority: int = 0,
        condition: Callable[[HookContext], bool] | None = None,
    ) -> RegisteredHook:
        """
        Register a hook function.

        Args:
            hook_type: The type of hook (e.g., "before_create")
            func: The hook function to call
            viewset_class: Optional viewset class to scope the hook
            priority: Lower values run first (default: 0)
            condition: Optional condition function

        Returns:
            The registered hook object
        """
        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)

        hook = RegisteredHook(
            func=func,
            hook_type=hook_type,
            priority=priority,
            condition=condition,
            viewset_class=viewset_class,
        )

        if viewset_class is None:
            # Global hook
            self._global_hooks[hook_type].append(hook)
            self._global_hooks[hook_type].sort(key=lambda h: h.priority)
        else:
            # ViewSet-specific hook
            if viewset_class not in self._viewset_hooks:
                self._viewset_hooks[viewset_class] = {ht: [] for ht in HookType}

            self._viewset_hooks[viewset_class][hook_type].append(hook)
            self._viewset_hooks[viewset_class][hook_type].sort(key=lambda h: h.priority)

        return hook

    def unregister(self, hook: RegisteredHook) -> bool:
        """
        Unregister a previously registered hook.

        Returns:
            True if the hook was found and removed
        """
        if hook.viewset_class is None:
            if hook in self._global_hooks[hook.hook_type]:
                self._global_hooks[hook.hook_type].remove(hook)
                return True
        elif hook.viewset_class in self._viewset_hooks:
            if hook in self._viewset_hooks[hook.viewset_class][hook.hook_type]:
                self._viewset_hooks[hook.viewset_class][hook.hook_type].remove(hook)
                return True
        return False

    def get_hooks(
        self,
        hook_type: HookType | str,
        viewset_class: type | None = None,
    ) -> list[RegisteredHook]:
        """
        Get all hooks for a given type and optional viewset class.

        Returns hooks in priority order (global hooks first, then viewset-specific).
        """
        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)

        hooks: list[RegisteredHook] = []

        # Add global hooks
        hooks.extend(self._global_hooks[hook_type])

        # Add viewset-specific hooks
        if viewset_class is not None and viewset_class in self._viewset_hooks:
            hooks.extend(self._viewset_hooks[viewset_class][hook_type])

        # Sort by priority
        hooks.sort(key=lambda h: h.priority)
        return hooks

    async def execute(
        self,
        hook_type: HookType | str,
        context: HookContext,
        initial_value: Any = None,
    ) -> Any:
        """
        Execute all hooks of a given type.

        Hooks are executed in priority order. Each hook can transform
        the value passed through the chain.

        Args:
            hook_type: The type of hook to execute
            context: The hook context
            initial_value: Initial value to pass through hook chain

        Returns:
            The final value after all hooks have executed
        """
        import asyncio

        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)

        context.hook_type = hook_type
        viewset_class = type(context.viewset) if context.viewset else None

        hooks = self.get_hooks(hook_type, viewset_class)
        value = initial_value

        for hook in hooks:
            if not hook.should_run(context):
                continue

            try:
                if hook.is_async:
                    result = await hook.func(context, value)
                else:
                    result = hook.func(context, value)
                    # Handle sync generators or other iterables
                    if asyncio.iscoroutine(result):
                        result = await result

                # Allow hooks to transform the value
                if result is not None:
                    value = result

            except StopHookChain:
                # Allow hooks to stop the chain early
                break
            except Exception as e:
                # Execute error hooks if this isn't already an error hook
                if hook_type != HookType.ON_ERROR:
                    context.error = e
                    await self.execute(HookType.ON_ERROR, context, e)
                raise

        return value

    async def execute_with_class_hooks(
        self,
        hook_type: HookType | str,
        context: HookContext,
        initial_value: Any = None,
    ) -> Any:
        """
        Execute hooks including class-defined hooks on the viewset.

        This checks for methods on the viewset like `before_create`, `after_create`, etc.
        """
        import asyncio

        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)

        value = initial_value
        viewset = context.viewset

        # Execute class-defined hook first (if exists)
        if viewset is not None:
            method_name = hook_type.value
            class_hook = getattr(viewset, method_name, None)
            if class_hook is not None and callable(class_hook):
                try:
                    if asyncio.iscoroutinefunction(class_hook):
                        result = await class_hook(context.request, value)
                    else:
                        result = class_hook(context.request, value)
                        if asyncio.iscoroutine(result):
                            result = await result

                    if result is not None:
                        value = result
                except StopHookChain:
                    return value
                except Exception as e:
                    if hook_type != HookType.ON_ERROR:
                        context.error = e
                        await self.execute(HookType.ON_ERROR, context, e)
                    raise

        # Then execute registered hooks
        value = await self.execute(hook_type, context, value)

        return value

    def clear(self, viewset_class: type | None = None):
        """
        Clear all registered hooks.

        Args:
            viewset_class: If provided, only clear hooks for that viewset
        """
        if viewset_class is None:
            self._global_hooks = {hook_type: [] for hook_type in HookType}
            self._viewset_hooks = {}
        elif viewset_class in self._viewset_hooks:
            del self._viewset_hooks[viewset_class]


class StopHookChain(Exception):
    """
    Exception to stop hook chain execution early.

    Raise this in a hook to prevent subsequent hooks from running.
    """

    def __init__(self, value: Any = None):
        self.value = value
        super().__init__("Hook chain stopped")


# Global hook manager instance
hook_manager = HookManager()


# ============================================================================
# Decorator-based hook registration
# ============================================================================


def _is_viewset_class(obj: Any) -> bool:
    """
    Check if an object is a ViewSet class (not a function).

    This distinguishes between:
    - @before_create(ProductViewSet) - obj is a class
    - @before_create - obj is a function being decorated
    """
    import inspect

    # If it's not a class, it's not a viewset
    if not inspect.isclass(obj):
        return False

    # Check if it's a coroutine function (async def)
    if inspect.iscoroutinefunction(obj):
        return False

    # Check if it looks like a function being used as decorator
    # Functions don't have __mro__ but classes do
    if not hasattr(obj, "__mro__"):
        return False

    return True


def _create_hook_decorator(hook_type: HookType):
    """Create a decorator factory for a specific hook type."""

    def decorator_factory(
        viewset_class: type | None = None,
        priority: int = 0,
        condition: Callable[[HookContext], bool] | None = None,
    ):
        """
        Decorator to register a hook function.

        Can be used with or without arguments:

            @before_create(ProductViewSet)
            async def my_hook(context, data):
                ...

            @before_create(priority=10)
            async def global_hook(context, data):
                ...

            @before_create
            async def another_global_hook(context, data):
                ...
        """

        def decorator(func: HookFunction) -> HookFunction:
            # Determine the viewset class to use
            actual_viewset_class = None
            if viewset_class is not None and _is_viewset_class(viewset_class):
                actual_viewset_class = viewset_class

            hook_manager.register(
                hook_type=hook_type,
                func=func,
                viewset_class=actual_viewset_class,
                priority=priority,
                condition=condition,
            )
            return func

        # Handle @decorator without parentheses - the first arg is the function
        if viewset_class is not None and not _is_viewset_class(viewset_class):
            # It's a function being decorated directly
            func = viewset_class
            hook_manager.register(
                hook_type=hook_type,
                func=func,
                viewset_class=None,
                priority=priority,
                condition=condition,
            )
            return func

        return decorator

    return decorator_factory


# Create decorator for each hook type
before_list = _create_hook_decorator(HookType.BEFORE_LIST)
after_list = _create_hook_decorator(HookType.AFTER_LIST)
before_create = _create_hook_decorator(HookType.BEFORE_CREATE)
after_create = _create_hook_decorator(HookType.AFTER_CREATE)
before_read = _create_hook_decorator(HookType.BEFORE_READ)
after_read = _create_hook_decorator(HookType.AFTER_READ)
before_update = _create_hook_decorator(HookType.BEFORE_UPDATE)
after_update = _create_hook_decorator(HookType.AFTER_UPDATE)
before_delete = _create_hook_decorator(HookType.BEFORE_DELETE)
after_delete = _create_hook_decorator(HookType.AFTER_DELETE)
on_error = _create_hook_decorator(HookType.ON_ERROR)


def register_global_hook(
    hook_type: HookType | str,
    priority: int = 0,
    condition: Callable[[HookContext], bool] | None = None,
):
    """
    Register a global hook that applies to all viewsets.

    Example:
        @register_global_hook("after_create")
        async def track_all_creates(context, instance):
            await analytics.track("object_created", {
                "model": context.model.__name__,
                "id": instance.id
            })
    """
    if isinstance(hook_type, str):
        hook_type = HookType(hook_type)

    def decorator(func: HookFunction) -> HookFunction:
        hook_manager.register(
            hook_type=hook_type,
            func=func,
            viewset_class=None,
            priority=priority,
            condition=condition,
        )
        return func

    return decorator


def register_hook(
    hook_type: HookType | str,
    viewset_class: type,
    priority: int = 0,
    condition: Callable[[HookContext], bool] | None = None,
):
    """
    Register a hook for a specific viewset class.

    Example:
        @register_hook("before_create", ProductViewSet)
        async def validate_product(context, data):
            if data["price"] < 0:
                raise ValidationError("Price must be positive")
            return data
    """
    if isinstance(hook_type, str):
        hook_type = HookType(hook_type)

    def decorator(func: HookFunction) -> HookFunction:
        hook_manager.register(
            hook_type=hook_type,
            func=func,
            viewset_class=viewset_class,
            priority=priority,
            condition=condition,
        )
        return func

    return decorator


# ============================================================================
# Utility functions
# ============================================================================


def create_hook_context(
    request: HttpRequest,
    viewset: Any,
    view_class: type,
    hook_type: HookType | None = None,
    instance: models.Model | None = None,
    data: dict[str, Any] | BaseModel | None = None,
    queryset: models.QuerySet | None = None,
    **extra: Any,
) -> HookContext:
    """
    Create a HookContext with common parameters.

    This is a utility function for creating contexts in view handlers.
    """
    return HookContext(
        request=request,
        view_class=view_class,
        viewset=viewset,
        hook_type=hook_type or HookType.BEFORE_LIST,
        instance=instance,
        data=data,
        queryset=queryset,
        extra=extra,
    )


async def run_hooks(
    hook_type: HookType | str,
    context: HookContext,
    value: Any = None,
    include_class_hooks: bool = True,
) -> Any:
    """
    Convenience function to run hooks.

    Args:
        hook_type: The hook type to execute
        context: The hook context
        value: Initial value to pass through
        include_class_hooks: Whether to include class-defined hooks

    Returns:
        The transformed value after hooks execute
    """
    if include_class_hooks:
        return await hook_manager.execute_with_class_hooks(hook_type, context, value)
    return await hook_manager.execute(hook_type, context, value)


# ============================================================================
# Mixin for ViewSets
# ============================================================================


class HooksMixin:
    """
    Mixin that adds hook support to ViewSets.

    This mixin provides the infrastructure for class-based hooks.
    Views that support hooks should check for these methods.

    Example:
        class ProductViewSet(HooksMixin, APIViewSet):
            model = Product

            async def before_create(self, request, data):
                data["created_by_id"] = request.user.id
                return data

            async def after_create(self, request, instance):
                await send_notification(f"Product created: {instance.name}")
                return instance

            async def on_error(self, request, error):
                await log_error(error)
                # Re-raise to propagate the error
                raise error
    """

    # Class-based hook methods (override in subclasses)
    # These have the signature: async def hook_name(self, request, value) -> value

    async def before_list(self, request: HttpRequest, queryset: models.QuerySet) -> models.QuerySet:
        """Hook called before listing resources."""
        return queryset

    async def after_list(self, request: HttpRequest, result: dict[str, Any]) -> dict[str, Any]:
        """Hook called after listing resources."""
        return result

    async def before_create(self, request: HttpRequest, data: dict[str, Any]) -> dict[str, Any]:
        """Hook called before creating a resource."""
        return data

    async def after_create(self, request: HttpRequest, instance: models.Model) -> models.Model:
        """Hook called after creating a resource."""
        return instance

    async def before_read(self, request: HttpRequest, lookup_value: Any) -> Any:
        """Hook called before reading a resource."""
        return lookup_value

    async def after_read(self, request: HttpRequest, instance: models.Model) -> models.Model:
        """Hook called after reading a resource."""
        return instance

    async def before_update(
        self, request: HttpRequest, value: Any
    ) -> Any:
        """Hook called before updating a resource.

        The value is a tuple of (instance, data_dict). Returns the same
        tuple (possibly modified).
        """
        return value

    async def after_update(self, request: HttpRequest, instance: models.Model) -> models.Model:
        """Hook called after updating a resource."""
        return instance

    async def before_delete(self, request: HttpRequest, instance: models.Model) -> models.Model:
        """Hook called before deleting a resource."""
        return instance

    async def after_delete(self, request: HttpRequest, instance: models.Model) -> None:
        """Hook called after deleting a resource."""

    async def on_error(self, request: HttpRequest, error: Exception) -> None:
        """Hook called when an error occurs."""


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Types and Enums
    "HookType",
    "HookContext",
    "RegisteredHook",
    # Manager
    "HookManager",
    "hook_manager",
    # Exceptions
    "StopHookChain",
    # Decorators
    "before_list",
    "after_list",
    "before_create",
    "after_create",
    "before_read",
    "after_read",
    "before_update",
    "after_update",
    "before_delete",
    "after_delete",
    "on_error",
    "register_global_hook",
    "register_hook",
    # Utilities
    "create_hook_context",
    "run_hooks",
    # Mixin
    "HooksMixin",
]
