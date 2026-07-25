"""
Tests for the native task engine core module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from django_matt.tasks_native import (
    NativeTask,
    NativeTaskConfig,
    TaskExecutionError,
    TaskRegistry,
    TaskResult,
    TaskState,
    TaskValidationError,
    get_backend,
    reset,
    set_config,
    task,
    task_registry,
)
from django_matt.tasks_native.backends.sync import SyncNativeBackend


@pytest.fixture(autouse=True)
def reset_task_system():
    """Reset task system before each test."""
    reset()
    task_registry.clear()
    yield
    reset()
    task_registry.clear()


class TestTaskDecorator:
    """Tests for the @task decorator."""

    def test_task_decorator_basic(self):
        """Test basic task decoration."""

        @task
        def simple_task(x: int, y: int) -> int:
            return x + y

        assert isinstance(simple_task, NativeTask)
        assert "simple_task" in simple_task.name
        assert simple_task.options.queue == "default"

    def test_task_decorator_with_options(self):
        """Test task decoration with options."""

        @task(
            name="custom_name",
            queue="high",
            priority=10,
            max_retries=5,
            retry_delay=30.0,
            timeout=600,
        )
        def custom_task() -> str:
            return "done"

        assert custom_task.name == "custom_name"
        assert custom_task.options.queue == "high"
        assert custom_task.options.priority == 10
        assert custom_task.options.max_retries == 5
        assert custom_task.options.retry_delay == 30.0
        assert custom_task.options.timeout == 600

    def test_task_decorator_async(self):
        """Test async task decoration."""

        @task
        async def async_task(x: int) -> int:
            await asyncio.sleep(0)
            return x * 2

        assert async_task.is_async is True

    def test_task_decorator_sync(self):
        """Test sync task detection."""

        @task
        def sync_task(x: int) -> int:
            return x * 2

        assert sync_task.is_async is False

    def test_task_registration(self):
        """Test task is registered in registry."""

        @task
        def registered_task() -> None:
            pass

        # Task name includes full qualified name
        assert registered_task.name in task_registry
        assert task_registry.get(registered_task.name) is registered_task


class TestPydanticValidation:
    """Tests for Pydantic payload validation."""

    def test_payload_type_extraction(self):
        """Test extraction of Pydantic model from signature."""

        class EmailPayload(BaseModel):
            user_id: int
            template: str

        @task
        def send_email(payload: EmailPayload) -> bool:
            return True

        assert send_email.payload_type is EmailPayload

    def test_payload_validation_success(self):
        """Test successful payload validation."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        class UserPayload(BaseModel):
            user_id: int
            name: str

        @task
        def process_user(payload: UserPayload) -> str:
            return f"Processed {payload.name}"

        result = process_user.delay(UserPayload(user_id=1, name="Test"))
        assert result.is_completed
        assert result.result == "Processed Test"

    def test_payload_dict_conversion(self):
        """Test automatic dict to Pydantic model conversion."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        class DataPayload(BaseModel):
            value: int
            label: str

        @task
        def process_data(payload: DataPayload) -> dict:
            return {"value": payload.value, "label": payload.label}

        result = process_data.delay({"value": 42, "label": "test"})
        assert result.is_completed
        assert result.result == {"value": 42, "label": "test"}

    def test_payload_validation_error(self):
        """Test payload validation failure."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=True))

        class StrictPayload(BaseModel):
            required_field: int

        @task
        def strict_task(payload: StrictPayload) -> None:
            pass

        with pytest.raises(TaskValidationError):
            strict_task.delay({"wrong_field": "value"})

    def test_no_payload_type(self):
        """Test task without Pydantic payload."""

        @task
        def simple_task(x: int, y: str) -> str:
            return f"{y}: {x}"

        assert simple_task.payload_type is None


class TestTaskExecution:
    """Tests for task execution."""

    def test_sync_execution_direct_call(self):
        """Test direct synchronous task call."""

        @task
        def add(x: int, y: int) -> int:
            return x + y

        result = add(2, 3)
        assert result == 5

    def test_sync_execution_apply(self):
        """Test synchronous execution via apply()."""

        @task
        def multiply(x: int, y: int) -> int:
            return x * y

        result = multiply.apply(args=(3, 4))
        assert result.is_completed
        assert result.result == 12

    def test_async_execution_direct_call(self):
        """Test direct async task call."""

        @task
        async def async_add(x: int, y: int) -> int:
            await asyncio.sleep(0)
            return x + y

        result = async_add(2, 3)
        assert result == 5

    def test_delay_execution(self):
        """Test delay() method."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @task
        def delayed_task(x: int) -> int:
            return x * 2

        result = delayed_task.delay(5)
        assert isinstance(result, TaskResult)
        assert result.is_completed
        assert result.result == 10

    def test_apply_async_execution(self):
        """Test apply_async() method."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @task
        def async_apply_task(x: int) -> int:
            return x + 100

        result = async_apply_task.apply_async(args=(42,))
        assert isinstance(result, TaskResult)
        assert result.is_completed
        assert result.result == 142

    def test_task_failure(self):
        """Test task failure handling."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @task
        def failing_task() -> None:
            raise ValueError("Task failed!")

        result = failing_task.delay()
        assert result.is_failed
        assert "Task failed!" in result.error

    def test_task_failure_propagation(self):
        """Test task failure propagation."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=True))

        @task
        def failing_task() -> None:
            raise RuntimeError("Critical error!")

        with pytest.raises(TaskExecutionError) as exc_info:
            failing_task.delay()

        assert "Critical error!" in str(exc_info.value)


class TestBoundTasks:
    """Tests for bound tasks (bind=True)."""

    def test_bound_task(self):
        """Test task with bind=True receives task instance."""

        @task(bind=True)
        def bound_task(self, x: int) -> str:
            return f"{self.name}: {x}"

        result = bound_task(42)
        assert "bound_task" in result
        assert "42" in result

    def test_bound_async_task(self):
        """Test async bound task."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        @task(bind=True)
        async def async_bound_task(self, x: int) -> str:
            await asyncio.sleep(0)
            return f"{self.name}: {x * 2}"

        result = async_bound_task.delay(21)
        assert result.is_completed
        assert "42" in result.result


class TestTaskHandlers:
    """Tests for task success/failure handlers."""

    def test_on_failure_handler(self):
        """Test on_failure handler is called."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        handler_called = {"called": False, "exception": None}

        @task
        def failing_task_with_handler() -> None:
            raise ValueError("Oops!")

        @failing_task_with_handler.on_failure
        def handle_failure(task, exc, payload):
            handler_called["called"] = True
            handler_called["exception"] = exc

        failing_task_with_handler.delay()

        assert handler_called["called"] is True
        assert isinstance(handler_called["exception"], ValueError)

    def test_on_success_handler(self):
        """Test on_success handler is called."""
        set_config(NativeTaskConfig(always_eager=True, eager_propagate_errors=False))

        handler_called = {"called": False, "result": None}

        @task
        def successful_task_with_handler() -> str:
            return "success"

        @successful_task_with_handler.on_success
        def handle_success(task, result, payload):
            handler_called["called"] = True
            handler_called["result"] = result

        successful_task_with_handler.delay()

        assert handler_called["called"] is True
        assert handler_called["result"] == "success"


class TestTaskRegistry:
    """Tests for TaskRegistry."""

    def test_registry_register(self):
        """Test task registration."""
        registry = TaskRegistry()

        @task
        def test_task_1() -> None:
            pass

        registry.register(test_task_1)
        assert test_task_1.name in registry

    def test_registry_get(self):
        """Test getting task from registry."""
        registry = TaskRegistry()

        @task(name="get_test")
        def test_task_2() -> None:
            pass

        registry.register(test_task_2)
        assert registry.get("get_test") is test_task_2
        assert registry.get("nonexistent") is None

    def test_registry_get_or_raise(self):
        """Test get_or_raise raises KeyError."""
        registry = TaskRegistry()

        with pytest.raises(KeyError):
            registry.get_or_raise("nonexistent")

    def test_registry_unregister(self):
        """Test task unregistration."""
        registry = TaskRegistry()

        @task(name="unregister_test")
        def test_task_3() -> None:
            pass

        registry.register(test_task_3)
        assert "unregister_test" in registry

        registry.unregister("unregister_test")
        assert "unregister_test" not in registry

    def test_registry_all(self):
        """Test getting all tasks."""
        registry = TaskRegistry()

        @task(name="all_test_1")
        def task_a() -> None:
            pass

        @task(name="all_test_2")
        def task_b() -> None:
            pass

        registry.register(task_a)
        registry.register(task_b)

        all_tasks = registry.all()
        assert "all_test_1" in all_tasks
        assert "all_test_2" in all_tasks

    def test_registry_names(self):
        """Test getting task names."""
        registry = TaskRegistry()

        @task(name="names_test")
        def task_c() -> None:
            pass

        registry.register(task_c)
        assert "names_test" in registry.names()

    def test_registry_len(self):
        """Test registry length."""
        registry = TaskRegistry()
        assert len(registry) == 0

        @task(name="len_test")
        def task_d() -> None:
            pass

        registry.register(task_d)
        assert len(registry) == 1

    def test_registry_iter(self):
        """Test iterating over registry."""
        registry = TaskRegistry()

        @task(name="iter_test")
        def task_e() -> None:
            pass

        registry.register(task_e)

        tasks = list(registry)
        assert task_e in tasks


class TestSyncBackend:
    """Tests for SyncNativeBackend."""

    def test_backend_enqueue(self):
        """Test sync backend enqueue."""
        config = NativeTaskConfig(always_eager=True)
        backend = SyncNativeBackend(config)

        @task
        def backend_test_task(x: int) -> int:
            return x * 3

        from django_matt.tasks_native.types import TaskMeta

        meta = TaskMeta(
            task_id="test-123",
            task_name=backend_test_task.name,
            state=TaskState.PENDING,
        )

        result = backend.enqueue(backend_test_task, args=(7,), kwargs={}, meta=meta)
        assert result.is_completed
        assert result.result == 21

    def test_backend_get_result(self):
        """Test getting result from sync backend."""
        config = NativeTaskConfig(always_eager=True)
        backend = SyncNativeBackend(config)

        @task
        def result_test_task() -> str:
            return "stored"

        from django_matt.tasks_native.types import TaskMeta

        meta = TaskMeta(
            task_id="result-test-123",
            task_name=result_test_task.name,
            state=TaskState.PENDING,
        )

        backend.enqueue(result_test_task, args=(), kwargs={}, meta=meta)

        stored_result = backend.get_result("result-test-123")
        assert stored_result is not None
        assert stored_result.result == "stored"

    def test_backend_health_check(self):
        """Test sync backend health check."""
        config = NativeTaskConfig()
        backend = SyncNativeBackend(config)

        health = backend.health_check()
        assert health["healthy"] is True
        assert health["backend"] == "sync"
        assert health["mode"] == "synchronous"

    def test_backend_queue_operations(self):
        """Test sync backend queue operations (no-op)."""
        config = NativeTaskConfig()
        backend = SyncNativeBackend(config)

        assert backend.get_queue_length() == 0
        assert backend.purge_queue() == 0
        assert backend.revoke("any-id") is False


class TestTaskResult:
    """Tests for TaskResult."""

    def test_result_properties(self):
        """Test TaskResult properties."""
        from django_matt.tasks_native.types import TaskMeta

        meta = TaskMeta(
            task_id="prop-test",
            task_name="test_task",
            state=TaskState.COMPLETED,
            result=42,
        )

        result = TaskResult(task_id="prop-test", meta=meta)

        assert result.task_id == "prop-test"
        assert result.state == TaskState.COMPLETED
        assert result.is_completed is True
        assert result.is_failed is False
        assert result.is_pending is False
        assert result.is_running is False
        assert result.is_terminal is True
        assert result.result == 42

    def test_result_failed_state(self):
        """Test TaskResult failed state."""
        from django_matt.tasks_native.types import TaskMeta

        meta = TaskMeta(
            task_id="fail-test",
            task_name="test_task",
            state=TaskState.FAILED,
            error="Something went wrong",
        )

        result = TaskResult(task_id="fail-test", meta=meta)

        assert result.is_failed is True
        assert result.is_terminal is True
        assert result.error == "Something went wrong"

    def test_result_get_propagates_error(self):
        """Test TaskResult.get() raises on failure."""
        from django_matt.tasks_native.types import TaskMeta

        meta = TaskMeta(
            task_id="get-test",
            task_name="test_task",
            state=TaskState.FAILED,
            error="Get failed",
            traceback="...",
        )

        result = TaskResult(task_id="get-test", meta=meta)

        with pytest.raises(TaskExecutionError):
            result.get()


class TestTaskMeta:
    """Tests for TaskMeta."""

    def test_meta_duration(self):
        """Test TaskMeta duration calculation."""
        from datetime import UTC, datetime, timedelta

        from django_matt.tasks_native.types import TaskMeta

        started = datetime.now(UTC)
        completed = started + timedelta(seconds=5)

        meta = TaskMeta(
            task_id="duration-test",
            task_name="test",
            started_at=started,
            completed_at=completed,
        )

        assert meta.duration_ms == pytest.approx(5000, rel=0.01)

    def test_meta_wait_time(self):
        """Test TaskMeta wait time calculation."""
        from datetime import UTC, datetime, timedelta

        from django_matt.tasks_native.types import TaskMeta

        queued = datetime.now(UTC)
        started = queued + timedelta(seconds=2)

        meta = TaskMeta(
            task_id="wait-test",
            task_name="test",
            queued_at=queued,
            started_at=started,
        )

        assert meta.wait_time_ms == pytest.approx(2000, rel=0.01)

    def test_meta_terminal_states(self):
        """Test TaskMeta terminal state detection."""
        from django_matt.tasks_native.types import TaskMeta

        for state in [
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.DEAD_LETTER,
        ]:
            meta = TaskMeta(task_id="term-test", task_name="test", state=state)
            assert meta.is_terminal is True

        for state in [TaskState.PENDING, TaskState.QUEUED, TaskState.RUNNING, TaskState.RETRYING]:
            meta = TaskMeta(task_id="nonterm-test", task_name="test", state=state)
            assert meta.is_terminal is False
