"""
Tests for the lifecycle hooks system in django_matt.views.

Tests cover:
- HookManager registration and execution
- Class-based hooks on ViewSets
- Decorator-based hooks
- Global hooks
- Hook priority ordering
- Conditional hooks
- Error handling hooks
- Hook chaining and composition
- Async hook support
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from django.db import models
from django.http import HttpRequest
from django.test import RequestFactory

import pytest
from pydantic import BaseModel

from django_matt.views.decorators import (
    catch_and_continue,
    compose_hooks,
    hook_method,
    log_hook,
    priority,
    retry,
    timed_hook,
    unless,
    when,
    with_hooks,
)

# Import the hooks system
from django_matt.views.hooks import (
    HookContext,
    HookManager,
    HooksMixin,
    HookType,
    RegisteredHook,
    StopHookChain,
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
    create_hook_context,
    hook_manager,
    on_error,
    register_global_hook,
    register_hook,
    run_hooks,
)

# ============================================================================
# Test fixtures and helpers
# ============================================================================


class MockModel:
    """Mock Django model for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.name = kwargs.get("name", "Test")
        for key, value in kwargs.items():
            setattr(self, key, value)

    class _meta:
        fields = []


class MockViewSet:
    """Mock ViewSet for testing hooks."""

    model = MockModel

    def __init__(self):
        self.hook_calls = []


class MockRequest:
    """Mock HTTP request for testing."""

    def __init__(self):
        self.user = MagicMock()
        self.user.id = 1
        self.user.is_authenticated = True
        self.user.is_staff = False


@pytest.fixture
def hook_mgr():
    """Create a fresh HookManager for each test."""
    manager = HookManager()
    yield manager
    manager.clear()


@pytest.fixture
def mock_request():
    """Create a mock request."""
    return MockRequest()


@pytest.fixture
def mock_viewset():
    """Create a mock viewset."""
    return MockViewSet()


@pytest.fixture
def mock_context(mock_request, mock_viewset):
    """Create a mock HookContext."""
    return HookContext(
        request=mock_request,
        view_class=type(mock_viewset),
        viewset=mock_viewset,
        hook_type=HookType.BEFORE_CREATE,
    )


# ============================================================================
# HookManager tests
# ============================================================================


class TestHookManager:
    """Tests for HookManager class."""

    def test_register_global_hook(self, hook_mgr):
        """Test registering a global hook."""

        async def my_hook(context, value):
            return value

        hook = hook_mgr.register(HookType.BEFORE_CREATE, my_hook)

        assert hook.func == my_hook
        assert hook.hook_type == HookType.BEFORE_CREATE
        assert hook.viewset_class is None
        assert hook.priority == 0

    def test_register_viewset_hook(self, hook_mgr):
        """Test registering a viewset-specific hook."""

        async def my_hook(context, value):
            return value

        hook = hook_mgr.register(HookType.AFTER_CREATE, my_hook, viewset_class=MockViewSet)

        assert hook.func == my_hook
        assert hook.viewset_class == MockViewSet

    def test_register_with_priority(self, hook_mgr):
        """Test registering hooks with different priorities."""
        calls = []

        async def hook1(context, value):
            calls.append(1)
            return value

        async def hook2(context, value):
            calls.append(2)
            return value

        async def hook3(context, value):
            calls.append(3)
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, hook1, priority=10)
        hook_mgr.register(HookType.BEFORE_CREATE, hook2, priority=0)
        hook_mgr.register(HookType.BEFORE_CREATE, hook3, priority=5)

        hooks = hook_mgr.get_hooks(HookType.BEFORE_CREATE)
        # Should be ordered by priority (0, 5, 10)
        assert hooks[0].priority == 0
        assert hooks[1].priority == 5
        assert hooks[2].priority == 10

    def test_unregister_hook(self, hook_mgr):
        """Test unregistering a hook."""

        async def my_hook(context, value):
            return value

        hook = hook_mgr.register(HookType.BEFORE_CREATE, my_hook)
        assert len(hook_mgr.get_hooks(HookType.BEFORE_CREATE)) == 1

        result = hook_mgr.unregister(hook)
        assert result is True
        assert len(hook_mgr.get_hooks(HookType.BEFORE_CREATE)) == 0

    def test_get_hooks_includes_global_and_viewset(self, hook_mgr):
        """Test that get_hooks returns both global and viewset hooks."""

        async def global_hook(context, value):
            return value

        async def viewset_hook(context, value):
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, global_hook)
        hook_mgr.register(HookType.BEFORE_CREATE, viewset_hook, viewset_class=MockViewSet)

        # Without viewset_class, only global hooks
        hooks = hook_mgr.get_hooks(HookType.BEFORE_CREATE)
        assert len(hooks) == 1

        # With viewset_class, both global and viewset hooks
        hooks = hook_mgr.get_hooks(HookType.BEFORE_CREATE, viewset_class=MockViewSet)
        assert len(hooks) == 2

    @pytest.mark.asyncio
    async def test_execute_hooks(self, hook_mgr, mock_context):
        """Test executing hooks."""
        calls = []

        async def hook1(context, value):
            calls.append(("hook1", value))
            return {"modified": True, **value}

        async def hook2(context, value):
            calls.append(("hook2", value))
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, hook1)
        hook_mgr.register(HookType.BEFORE_CREATE, hook2)

        result = await hook_mgr.execute(HookType.BEFORE_CREATE, mock_context, {"original": True})

        assert calls[0] == ("hook1", {"original": True})
        assert calls[1] == ("hook2", {"modified": True, "original": True})
        assert result["modified"] is True

    @pytest.mark.asyncio
    async def test_execute_with_condition(self, hook_mgr, mock_context):
        """Test conditional hook execution."""
        calls = []

        async def should_run_hook(context, value):
            calls.append("should_run")
            return value

        async def should_not_run_hook(context, value):
            calls.append("should_not_run")
            return value

        hook_mgr.register(
            HookType.BEFORE_CREATE,
            should_run_hook,
            condition=lambda ctx: True,
        )
        hook_mgr.register(
            HookType.BEFORE_CREATE,
            should_not_run_hook,
            condition=lambda ctx: False,
        )

        await hook_mgr.execute(HookType.BEFORE_CREATE, mock_context, {})

        assert "should_run" in calls
        assert "should_not_run" not in calls

    @pytest.mark.asyncio
    async def test_execute_stops_on_stop_hook_chain(self, hook_mgr, mock_context):
        """Test that StopHookChain stops hook execution."""
        calls = []

        async def hook1(context, value):
            calls.append("hook1")
            raise StopHookChain({"stopped": True})

        async def hook2(context, value):
            calls.append("hook2")
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, hook1)
        hook_mgr.register(HookType.BEFORE_CREATE, hook2, priority=10)

        await hook_mgr.execute(HookType.BEFORE_CREATE, mock_context, {})

        assert "hook1" in calls
        assert "hook2" not in calls

    def test_clear_all_hooks(self, hook_mgr):
        """Test clearing all hooks."""

        async def hook(context, value):
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, hook)
        hook_mgr.register(HookType.AFTER_CREATE, hook)
        hook_mgr.register(HookType.BEFORE_CREATE, hook, viewset_class=MockViewSet)

        hook_mgr.clear()

        assert len(hook_mgr.get_hooks(HookType.BEFORE_CREATE)) == 0
        assert len(hook_mgr.get_hooks(HookType.AFTER_CREATE)) == 0
        assert len(hook_mgr.get_hooks(HookType.BEFORE_CREATE, MockViewSet)) == 0

    def test_clear_viewset_hooks_only(self, hook_mgr):
        """Test clearing only viewset-specific hooks."""

        async def hook(context, value):
            return value

        hook_mgr.register(HookType.BEFORE_CREATE, hook)  # Global
        hook_mgr.register(HookType.BEFORE_CREATE, hook, viewset_class=MockViewSet)  # Viewset

        hook_mgr.clear(viewset_class=MockViewSet)

        # Global hook should remain
        assert len(hook_mgr.get_hooks(HookType.BEFORE_CREATE)) == 1
        # Viewset hook should be cleared
        hooks_with_viewset = hook_mgr.get_hooks(HookType.BEFORE_CREATE, viewset_class=MockViewSet)
        # Only global hook should be returned
        assert len(hooks_with_viewset) == 1


# ============================================================================
# HookContext tests
# ============================================================================


class TestHookContext:
    """Tests for HookContext class."""

    def test_context_properties(self, mock_request, mock_viewset):
        """Test HookContext properties."""
        context = HookContext(
            request=mock_request,
            view_class=type(mock_viewset),
            viewset=mock_viewset,
            hook_type=HookType.BEFORE_CREATE,
        )

        assert context.user == mock_request.user
        assert context.model == MockModel
        assert context.hook_type == HookType.BEFORE_CREATE

    def test_context_with_instance(self, mock_request, mock_viewset):
        """Test HookContext with model instance."""
        instance = MockModel(id=42, name="Test Instance")
        context = HookContext(
            request=mock_request,
            view_class=type(mock_viewset),
            viewset=mock_viewset,
            hook_type=HookType.AFTER_CREATE,
            instance=instance,
        )

        assert context.instance.id == 42
        assert context.instance.name == "Test Instance"

    def test_context_with_data(self, mock_request, mock_viewset):
        """Test HookContext with request data."""
        data = {"name": "New Product", "price": 99.99}
        context = HookContext(
            request=mock_request,
            view_class=type(mock_viewset),
            viewset=mock_viewset,
            hook_type=HookType.BEFORE_CREATE,
            data=data,
        )

        assert context.data["name"] == "New Product"
        assert context.data["price"] == 99.99

    def test_context_extra_data(self, mock_request, mock_viewset):
        """Test HookContext with extra data."""
        context = HookContext(
            request=mock_request,
            view_class=type(mock_viewset),
            viewset=mock_viewset,
            hook_type=HookType.BEFORE_CREATE,
            extra={"custom_key": "custom_value"},
        )

        assert context.extra["custom_key"] == "custom_value"


# ============================================================================
# Decorator tests
# ============================================================================


class TestHookDecorators:
    """Tests for hook decorators."""

    def test_before_create_decorator_with_viewset(self, hook_mgr):
        """Test @before_create with viewset class."""
        # Clear global hook_manager first
        hook_manager.clear()

        @before_create(MockViewSet)
        async def validate_data(context, data):
            return data

        hooks = hook_manager.get_hooks(HookType.BEFORE_CREATE, MockViewSet)
        assert len(hooks) == 1
        assert hooks[0].func == validate_data

        # Cleanup
        hook_manager.clear()

    def test_before_create_decorator_global(self, hook_mgr):
        """Test @before_create as global hook."""
        hook_manager.clear()

        @before_create
        async def global_validate(context, data):
            return data

        hooks = hook_manager.get_hooks(HookType.BEFORE_CREATE)
        assert len(hooks) == 1

        hook_manager.clear()

    def test_after_create_decorator(self, hook_mgr):
        """Test @after_create decorator."""
        hook_manager.clear()

        @after_create(MockViewSet)
        async def log_creation(context, instance):
            return instance

        hooks = hook_manager.get_hooks(HookType.AFTER_CREATE, MockViewSet)
        assert len(hooks) == 1

        hook_manager.clear()

    def test_register_global_hook_decorator(self, hook_mgr):
        """Test @register_global_hook decorator."""
        hook_manager.clear()

        @register_global_hook("after_create")
        async def track_creation(context, instance):
            return instance

        hooks = hook_manager.get_hooks(HookType.AFTER_CREATE)
        assert len(hooks) == 1

        hook_manager.clear()

    def test_register_hook_decorator(self, hook_mgr):
        """Test @register_hook decorator."""
        hook_manager.clear()

        @register_hook("before_update", MockViewSet)
        async def validate_update(context, data):
            return data

        hooks = hook_manager.get_hooks(HookType.BEFORE_UPDATE, MockViewSet)
        assert len(hooks) == 1

        hook_manager.clear()


# ============================================================================
# Conditional decorator tests
# ============================================================================


class TestConditionalDecorators:
    """Tests for conditional hook decorators."""

    @pytest.mark.asyncio
    async def test_when_decorator(self, mock_context):
        """Test @when conditional decorator."""
        calls = []

        @when(lambda ctx: ctx.user.is_staff)
        async def staff_only_hook(context, value):
            calls.append("staff_hook")
            return value

        # User is not staff
        mock_context.request.user.is_staff = False
        # The condition is stored but we need to check it manually
        assert hasattr(staff_only_hook, "_hook_condition")
        assert staff_only_hook._hook_condition(mock_context) is False

        mock_context.request.user.is_staff = True
        assert staff_only_hook._hook_condition(mock_context) is True

    @pytest.mark.asyncio
    async def test_unless_decorator(self, mock_context):
        """Test @unless conditional decorator."""

        @unless(lambda ctx: ctx.user.is_anonymous)
        async def authenticated_only_hook(context, value):
            return value

        mock_context.request.user.is_anonymous = False
        assert hasattr(authenticated_only_hook, "_hook_condition")
        assert authenticated_only_hook._hook_condition(mock_context) is True

        mock_context.request.user.is_anonymous = True
        assert authenticated_only_hook._hook_condition(mock_context) is False


# ============================================================================
# Composition decorator tests
# ============================================================================


class TestCompositionDecorators:
    """Tests for hook composition decorators."""

    def test_priority_decorator(self):
        """Test @priority decorator."""

        @priority(10)
        async def low_priority_hook(context, value):
            return value

        assert hasattr(low_priority_hook, "_hook_priority")
        assert low_priority_hook._hook_priority == 10

    @pytest.mark.asyncio
    async def test_compose_hooks_decorator(self, mock_context):
        """Test @compose_hooks decorator."""
        calls = []

        async def hook1(context, value):
            calls.append("hook1")
            return {**value, "hook1": True}

        async def hook2(context, value):
            calls.append("hook2")
            return {**value, "hook2": True}

        @compose_hooks(hook1, hook2)
        async def final_hook(context, value):
            calls.append("final")
            return {**value, "final": True}

        result = await final_hook(mock_context, {})

        assert calls == ["hook1", "hook2", "final"]
        assert result == {"hook1": True, "hook2": True, "final": True}


# ============================================================================
# Error handling decorator tests
# ============================================================================


class TestErrorHandlingDecorators:
    """Tests for error handling decorators."""

    @pytest.mark.asyncio
    async def test_catch_and_continue(self, mock_context):
        """Test @catch_and_continue decorator."""

        @catch_and_continue(ValueError, default={"error": "caught"})
        async def failing_hook(context, value):
            raise ValueError("Something went wrong")

        result = await failing_hook(mock_context, {})
        assert result == {"error": "caught"}

    @pytest.mark.asyncio
    async def test_catch_and_continue_preserves_value(self, mock_context):
        """Test @catch_and_continue preserves original value when no default."""

        @catch_and_continue(ValueError)
        async def failing_hook(context, value):
            raise ValueError("Something went wrong")

        original = {"original": True}
        result = await failing_hook(mock_context, original)
        assert result == original

    @pytest.mark.asyncio
    async def test_retry_decorator(self, mock_context):
        """Test @retry decorator."""
        attempts = []

        @retry(times=3, delay=0.01)
        async def flaky_hook(context, value):
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("Connection failed")
            return {"success": True}

        result = await flaky_hook(mock_context, {})
        assert len(attempts) == 3
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self, mock_context):
        """Test @retry raises after max attempts."""

        @retry(times=2, delay=0.01)
        async def always_fails(context, value):
            raise ConnectionError("Connection failed")

        with pytest.raises(ConnectionError):
            await always_fails(mock_context, {})


# ============================================================================
# Debugging decorator tests
# ============================================================================


class TestDebuggingDecorators:
    """Tests for debugging decorators."""

    @pytest.mark.asyncio
    async def test_log_hook(self, mock_context):
        """Test @log_hook decorator."""
        logs = []

        @log_hook(logs.append)
        async def my_hook(context, value):
            return {"logged": True}

        result = await my_hook(mock_context, {})

        assert result == {"logged": True}
        assert any("starting" in log.lower() for log in logs)
        assert any("completed" in log.lower() for log in logs)

    @pytest.mark.asyncio
    async def test_timed_hook(self, mock_context):
        """Test @timed_hook decorator."""
        slow_hooks = []

        @timed_hook(max_ms=1, on_slow=lambda name, ms: slow_hooks.append((name, ms)))
        async def slow_hook(context, value):
            await asyncio.sleep(0.01)  # 10ms
            return value

        await slow_hook(mock_context, {})

        assert len(slow_hooks) == 1
        assert slow_hooks[0][0] == "slow_hook"
        assert slow_hooks[0][1] > 1


# ============================================================================
# with_hooks class decorator tests
# ============================================================================


class TestWithHooksDecorator:
    """Tests for @with_hooks class decorator."""

    def test_with_hooks_registers_hooks(self):
        """Test that @with_hooks registers hooks for the class."""
        hook_manager.clear()

        async def custom_before_create(context, data):
            return data

        async def custom_after_create(context, instance):
            return instance

        @with_hooks(
            before_create=custom_before_create,
            after_create=custom_after_create,
        )
        class ProductViewSet(MockViewSet):
            pass

        hooks = hook_manager.get_hooks(HookType.BEFORE_CREATE, ProductViewSet)
        assert len(hooks) == 1

        hooks = hook_manager.get_hooks(HookType.AFTER_CREATE, ProductViewSet)
        assert len(hooks) == 1

        hook_manager.clear()


# ============================================================================
# HooksMixin tests
# ============================================================================


class TestHooksMixin:
    """Tests for HooksMixin class."""

    @pytest.mark.asyncio
    async def test_mixin_default_hooks_return_input(self, mock_request):
        """Test that default mixin hooks return their input unchanged."""

        class TestViewSet(HooksMixin):
            model = MockModel

        viewset = TestViewSet()
        instance = MockModel(id=1)

        # Test various hooks return input unchanged
        result = await viewset.before_create(mock_request, {"test": True})
        assert result == {"test": True}

        result = await viewset.after_create(mock_request, instance)
        assert result == instance

        result = await viewset.before_read(mock_request, 42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_mixin_hooks_can_be_overridden(self, mock_request):
        """Test that mixin hooks can be overridden."""

        class TestViewSet(HooksMixin):
            model = MockModel

            async def before_create(self, request, data):
                return {**data, "modified": True}

        viewset = TestViewSet()
        result = await viewset.before_create(mock_request, {"original": True})

        assert result["original"] is True
        assert result["modified"] is True


# ============================================================================
# StopHookChain tests
# ============================================================================


class TestStopHookChain:
    """Tests for StopHookChain exception."""

    def test_stop_hook_chain_with_value(self):
        """Test StopHookChain stores return value."""
        stop = StopHookChain({"cancelled": True})
        assert stop.value == {"cancelled": True}

    def test_stop_hook_chain_without_value(self):
        """Test StopHookChain with no value."""
        stop = StopHookChain()
        assert stop.value is None


# ============================================================================
# Integration tests
# ============================================================================


class TestHooksIntegration:
    """Integration tests for the hooks system."""

    @pytest.mark.asyncio
    async def test_full_create_hook_chain(self, mock_request):
        """Test complete before/after create hook chain."""
        hook_manager.clear()
        calls = []

        class ProductViewSet(HooksMixin, MockViewSet):
            model = MockModel

            async def before_create(self, request, data):
                calls.append(("class_before", data))
                return {**data, "class_modified": True}

            async def after_create(self, request, instance):
                calls.append(("class_after", instance))
                return instance

        @before_create(ProductViewSet)
        async def decorator_before(context, data):
            calls.append(("decorator_before", data))
            return {**data, "decorator_modified": True}

        @after_create(ProductViewSet)
        async def decorator_after(context, instance):
            calls.append(("decorator_after", instance))
            return instance

        # Create context and run hooks
        viewset = ProductViewSet()
        context = create_hook_context(
            request=mock_request,
            viewset=viewset,
            view_class=ProductViewSet,
            hook_type=HookType.BEFORE_CREATE,
        )

        # Run before_create
        data = {"original": True}
        result = await run_hooks(HookType.BEFORE_CREATE, context, data)

        # Verify call order and data transformation
        assert len([c for c in calls if "before" in c[0]]) == 2
        assert result.get("decorator_modified") is True

        hook_manager.clear()

    @pytest.mark.asyncio
    async def test_error_hook_execution(self, mock_request):
        """Test error hooks are called on exception."""
        hook_manager.clear()
        error_handled = []

        class ErrorViewSet(HooksMixin, MockViewSet):
            model = MockModel

            async def on_error(self, request, error):
                error_handled.append(str(error))

        @on_error(ErrorViewSet)
        async def log_error(context, error):
            error_handled.append(f"logged: {error}")

        viewset = ErrorViewSet()
        context = create_hook_context(
            request=mock_request,
            viewset=viewset,
            view_class=ErrorViewSet,
            hook_type=HookType.ON_ERROR,
        )
        context.error = ValueError("Test error")

        await run_hooks(HookType.ON_ERROR, context, context.error)

        assert len(error_handled) >= 1

        hook_manager.clear()


# ============================================================================
# RegisteredHook tests
# ============================================================================


class TestRegisteredHook:
    """Tests for RegisteredHook dataclass."""

    def test_auto_detect_async(self):
        """Test async detection for hooks."""

        async def async_hook(context, value):
            return value

        def sync_hook(context, value):
            return value

        async_registered = RegisteredHook(func=async_hook, hook_type=HookType.BEFORE_CREATE)
        sync_registered = RegisteredHook(func=sync_hook, hook_type=HookType.BEFORE_CREATE)

        assert async_registered.is_async is True
        assert sync_registered.is_async is False

    def test_should_run_with_viewset_class(self, mock_context):
        """Test should_run checks viewset class."""

        async def my_hook(context, value):
            return value

        hook = RegisteredHook(
            func=my_hook, hook_type=HookType.BEFORE_CREATE, viewset_class=MockViewSet
        )

        assert hook.should_run(mock_context) is True

        # Different viewset class
        class OtherViewSet:
            pass

        mock_context.viewset = OtherViewSet()
        assert hook.should_run(mock_context) is False

    def test_should_run_with_condition(self, mock_context):
        """Test should_run checks custom condition."""

        async def my_hook(context, value):
            return value

        hook = RegisteredHook(
            func=my_hook,
            hook_type=HookType.BEFORE_CREATE,
            condition=lambda ctx: ctx.user.is_staff,
        )

        mock_context.request.user.is_staff = False
        assert hook.should_run(mock_context) is False

        mock_context.request.user.is_staff = True
        assert hook.should_run(mock_context) is True


# ============================================================================
# Hook type string conversion tests
# ============================================================================


class TestHookTypeConversion:
    """Tests for HookType string conversion."""

    def test_hook_type_from_string(self):
        """Test creating HookType from string."""
        assert HookType("before_create") == HookType.BEFORE_CREATE
        assert HookType("after_update") == HookType.AFTER_UPDATE
        assert HookType("on_error") == HookType.ON_ERROR

    def test_hook_type_values(self):
        """Test HookType values."""
        assert HookType.BEFORE_LIST.value == "before_list"
        assert HookType.AFTER_LIST.value == "after_list"
        assert HookType.BEFORE_CREATE.value == "before_create"
        assert HookType.AFTER_CREATE.value == "after_create"
        assert HookType.BEFORE_READ.value == "before_read"
        assert HookType.AFTER_READ.value == "after_read"
        assert HookType.BEFORE_UPDATE.value == "before_update"
        assert HookType.AFTER_UPDATE.value == "after_update"
        assert HookType.BEFORE_DELETE.value == "before_delete"
        assert HookType.AFTER_DELETE.value == "after_delete"
        assert HookType.ON_ERROR.value == "on_error"
