"""
Decorator-based hooks for Django Matt CRUD views.

Provides convenient decorators for registering lifecycle hooks
on ViewSet classes and individual view methods.

Example:
    from django_matt.views.decorators import (
        before_create, after_create, before_update, after_update,
        before_delete, after_delete, on_error, with_hooks
    )

    # Method decorators for ViewSet methods
    class ProductViewSet(APIViewSet):
        model = Product

        @before_create
        async def validate_price(self, request, data):
            if data.get("price", 0) < 0:
                raise ValidationError("Price must be positive")
            return data

    # Standalone hooks registered to a ViewSet
    @before_create(ProductViewSet)
    async def log_creation(context, data):
        logger.info(f"Creating product: {data}")
        return data

    # Apply hooks via decorator
    @with_hooks(
        before_create=validate_product,
        after_create=send_notification,
    )
    class ProductViewSet(APIViewSet):
        model = Product
"""

from functools import wraps
from typing import Any, Callable, TypeVar, overload

from django.http import HttpRequest

from django_matt.views.hooks import (
    HookContext,
    HookType,
    RegisteredHook,
    hook_manager,
)

F = TypeVar("F", bound=Callable[..., Any])
ViewSetT = TypeVar("ViewSetT")


# ============================================================================
# Re-export from hooks module for convenience
# ============================================================================

from django_matt.views.hooks import (
    after_create,
    after_delete,
    after_list,
    after_read,
    after_update,
    before_create,
    before_delete,
    before_list,
    before_read,
    before_update,
    on_error,
    register_global_hook,
    register_hook,
)


# ============================================================================
# Class decorator for applying multiple hooks
# ============================================================================


def with_hooks(
    before_list: Callable | None = None,
    after_list: Callable | None = None,
    before_create: Callable | None = None,
    after_create: Callable | None = None,
    before_read: Callable | None = None,
    after_read: Callable | None = None,
    before_update: Callable | None = None,
    after_update: Callable | None = None,
    before_delete: Callable | None = None,
    after_delete: Callable | None = None,
    on_error: Callable | None = None,
) -> Callable[[type[ViewSetT]], type[ViewSetT]]:
    """
    Class decorator to apply multiple hooks to a ViewSet.

    Example:
        async def validate_product(context, data):
            if data["price"] < 0:
                raise ValidationError("Price must be positive")
            return data

        async def send_notification(context, instance):
            await notify(f"Product {instance.name} created")
            return instance

        @with_hooks(
            before_create=validate_product,
            after_create=send_notification,
        )
        class ProductViewSet(APIViewSet):
            model = Product
            list_products = ListView()
            create_product = CreateView()
    """
    hooks = {
        HookType.BEFORE_LIST: before_list,
        HookType.AFTER_LIST: after_list,
        HookType.BEFORE_CREATE: before_create,
        HookType.AFTER_CREATE: after_create,
        HookType.BEFORE_READ: before_read,
        HookType.AFTER_READ: after_read,
        HookType.BEFORE_UPDATE: before_update,
        HookType.AFTER_UPDATE: after_update,
        HookType.BEFORE_DELETE: before_delete,
        HookType.AFTER_DELETE: after_delete,
        HookType.ON_ERROR: on_error,
    }

    def decorator(cls: type[ViewSetT]) -> type[ViewSetT]:
        for hook_type, func in hooks.items():
            if func is not None:
                hook_manager.register(
                    hook_type=hook_type,
                    func=func,
                    viewset_class=cls,
                )
        return cls

    return decorator


# ============================================================================
# Conditional hook decorators
# ============================================================================


def when(
    condition: Callable[[HookContext], bool],
) -> Callable[[Callable], Callable]:
    """
    Decorator to make a hook conditional.

    The hook will only run if the condition returns True.

    Example:
        @when(lambda ctx: ctx.user.is_staff)
        @before_delete(ProductViewSet)
        async def staff_only_delete(context, instance):
            await audit_log(f"Staff delete: {instance}")
            return instance
    """

    def decorator(func: Callable) -> Callable:
        # Store condition on function for later use
        func._hook_condition = condition
        return func

    return decorator


def unless(
    condition: Callable[[HookContext], bool],
) -> Callable[[Callable], Callable]:
    """
    Decorator to make a hook run unless condition is True.

    The hook will run if the condition returns False.

    Example:
        @unless(lambda ctx: ctx.user.is_anonymous)
        @after_create(ProductViewSet)
        async def log_user_creation(context, instance):
            await audit_log(f"User {context.user} created {instance}")
            return instance
    """

    def decorator(func: Callable) -> Callable:
        func._hook_condition = lambda ctx: not condition(ctx)
        return func

    return decorator


def priority(level: int) -> Callable[[Callable], Callable]:
    """
    Decorator to set hook priority.

    Lower priority values run first.

    Example:
        @priority(10)  # Runs after default priority (0)
        @after_create(ProductViewSet)
        async def send_notification(context, instance):
            ...
    """

    def decorator(func: Callable) -> Callable:
        func._hook_priority = level
        return func

    return decorator


# ============================================================================
# Hook composition
# ============================================================================


def compose_hooks(*hooks: Callable) -> Callable:
    """
    Compose multiple hook functions into a single hook.

    Hooks are executed in order, with each hook receiving the result
    of the previous hook.

    Example:
        @compose_hooks(
            validate_price,
            normalize_name,
            add_metadata,
        )
        @before_create(ProductViewSet)
        async def process_product(context, data):
            # This runs after all composed hooks
            return data
    """

    def composed(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: HookContext, value: Any) -> Any:
            import asyncio

            result = value

            # Run each hook in sequence
            for hook in hooks:
                if asyncio.iscoroutinefunction(hook):
                    hook_result = await hook(context, result)
                else:
                    hook_result = hook(context, result)
                    if asyncio.iscoroutine(hook_result):
                        hook_result = await hook_result

                if hook_result is not None:
                    result = hook_result

            # Run the decorated function last
            if asyncio.iscoroutinefunction(func):
                final_result = await func(context, result)
            else:
                final_result = func(context, result)
                if asyncio.iscoroutine(final_result):
                    final_result = await final_result

            return final_result if final_result is not None else result

        return wrapper

    return composed


# ============================================================================
# Method-level hook markers
# ============================================================================


def hook_method(hook_type: HookType | str) -> Callable[[F], F]:
    """
    Mark a ViewSet method as a hook of a specific type.

    This is useful when you want to name your hook methods differently
    from the default names (before_create, after_create, etc.).

    Example:
        class ProductViewSet(APIViewSet):
            @hook_method("before_create")
            async def validate_and_prepare(self, request, data):
                # Custom validation
                return data
    """
    if isinstance(hook_type, str):
        hook_type = HookType(hook_type)

    def decorator(func: F) -> F:
        func._hook_type = hook_type
        return func

    return decorator


# ============================================================================
# Error handling decorators
# ============================================================================


def catch_and_continue(
    *exception_types: type[Exception],
    default: Any = None,
) -> Callable[[Callable], Callable]:
    """
    Wrap a hook to catch exceptions and continue the hook chain.

    Example:
        @catch_and_continue(ConnectionError, default=None)
        @after_create(ProductViewSet)
        async def send_notification(context, instance):
            await external_service.notify(instance)
            return instance
    """
    if not exception_types:
        exception_types = (Exception,)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: HookContext, value: Any) -> Any:
            import asyncio

            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(context, value)
                result = func(context, value)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except exception_types:
                return default if default is not None else value

        return wrapper

    return decorator


def retry(
    times: int = 3,
    delay: float = 0.1,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable], Callable]:
    """
    Retry a hook function on failure.

    Example:
        @retry(times=3, delay=0.5)
        @after_create(ProductViewSet)
        async def sync_to_external_service(context, instance):
            await external_api.sync(instance)
            return instance
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: HookContext, value: Any) -> Any:
            import asyncio

            last_exception = None
            for attempt in range(times):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(context, value)
                    result = func(context, value)
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                except exceptions as e:
                    last_exception = e
                    if attempt < times - 1:
                        await asyncio.sleep(delay * (attempt + 1))

            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# Timing and debugging decorators
# ============================================================================


def log_hook(
    logger_func: Callable[[str], None] | None = None,
) -> Callable[[Callable], Callable]:
    """
    Log hook execution for debugging.

    Example:
        import logging
        logger = logging.getLogger(__name__)

        @log_hook(logger.debug)
        @before_create(ProductViewSet)
        async def my_hook(context, data):
            return data
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: HookContext, value: Any) -> Any:
            import asyncio
            import time

            hook_name = getattr(func, "__name__", str(func))
            log = logger_func or print

            log(f"Hook '{hook_name}' starting for {context.hook_type.value}")
            start = time.time()

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(context, value)
                else:
                    result = func(context, value)
                    if asyncio.iscoroutine(result):
                        result = await result

                elapsed = (time.time() - start) * 1000
                log(f"Hook '{hook_name}' completed in {elapsed:.2f}ms")
                return result

            except Exception as e:
                elapsed = (time.time() - start) * 1000
                log(f"Hook '{hook_name}' failed after {elapsed:.2f}ms: {e}")
                raise

        return wrapper

    return decorator


def timed_hook(
    max_ms: float | None = None,
    on_slow: Callable[[str, float], None] | None = None,
) -> Callable[[Callable], Callable]:
    """
    Track hook execution time and optionally warn on slow hooks.

    Example:
        @timed_hook(max_ms=100, on_slow=lambda name, ms: logger.warning(f"Slow hook: {name} ({ms}ms)"))
        @after_create(ProductViewSet)
        async def complex_processing(context, instance):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(context: HookContext, value: Any) -> Any:
            import asyncio
            import time

            start = time.time()

            if asyncio.iscoroutinefunction(func):
                result = await func(context, value)
            else:
                result = func(context, value)
                if asyncio.iscoroutine(result):
                    result = await result

            elapsed_ms = (time.time() - start) * 1000

            if max_ms is not None and elapsed_ms > max_ms and on_slow is not None:
                hook_name = getattr(func, "__name__", str(func))
                on_slow(hook_name, elapsed_ms)

            return result

        return wrapper

    return decorator


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Basic hook decorators (re-exported from hooks module)
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
    # Class decorator
    "with_hooks",
    # Conditional decorators
    "when",
    "unless",
    "priority",
    # Composition
    "compose_hooks",
    # Method markers
    "hook_method",
    # Error handling
    "catch_and_continue",
    "retry",
    # Debugging
    "log_hook",
    "timed_hook",
]
