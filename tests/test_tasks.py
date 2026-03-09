"""
Tests for the background tasks module.

Tests cover:
- TaskStatus enum values
- TaskResult dataclass and properties
- Task class (creation, calling, apply, delay, signatures)
- TaskRegistry (register, get, unregister, iteration)
- @task / @shared_task decorators
- RetryPolicy hierarchy (ExponentialBackoff, LinearBackoff, FixedDelay, etc.)
- Scheduling (crontab, every, IntervalSchedule, CrontabSchedule)
- Primitives (Signature, Group, Chain, Chord)
- SyncBackend execution
- TaskConfig
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from django_matt.tasks.base import (
    Retry,
    Task,
    TaskOptions,
    TaskRegistry,
    TaskResult,
    TaskStatus,
    task_registry,
)
from django_matt.tasks.config import TaskConfig, get_task_config, set_task_config
from django_matt.tasks.decorators import task, shared_task, periodic_task, schedule
from django_matt.tasks.primitives import (
    Chain,
    Chord,
    Group,
    GroupResult,
    Signature,
    chain,
    chord,
    group,
    signature,
)
from django_matt.tasks.retry import (
    CompositeRetryPolicy,
    ExponentialBackoff,
    FixedDelay,
    LinearBackoff,
    NoRetry,
    RetryOnException,
    RetryPolicy,
)
from django_matt.tasks.scheduling import (
    CrontabSchedule,
    IntervalSchedule,
    ScheduleEntry,
    ScheduledTask,
    Scheduler,
    crontab,
    every,
)
from django_matt.tasks.backends.sync import SyncBackend


# ==============================================================================
# TaskStatus
# ==============================================================================


class TestTaskStatus:
    def test_enum_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.STARTED.value == "started"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILURE.value == "failure"
        assert TaskStatus.RETRY.value == "retry"
        assert TaskStatus.REVOKED.value == "revoked"

    def test_all_statuses_present(self):
        names = {s.name for s in TaskStatus}
        assert names == {"PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY", "REVOKED"}


# ==============================================================================
# TaskResult
# ==============================================================================


class TestTaskResult:
    def test_default_values(self):
        result = TaskResult(task_id="abc-123")
        assert result.task_id == "abc-123"
        assert result.status == TaskStatus.PENDING
        assert result.result is None
        assert result.error is None
        assert result.traceback is None
        assert result.started_at is None
        assert result.completed_at is None
        assert result.retries == 0

    def test_is_pending(self):
        result = TaskResult(task_id="t1", status=TaskStatus.PENDING)
        assert result.is_pending is True
        assert result.is_started is False
        assert result.is_success is False
        assert result.is_failure is False
        assert result.is_complete is False

    def test_is_started(self):
        result = TaskResult(task_id="t1", status=TaskStatus.STARTED)
        assert result.is_started is True
        assert result.is_pending is False
        assert result.is_complete is False

    def test_is_success(self):
        result = TaskResult(task_id="t1", status=TaskStatus.SUCCESS, result=42)
        assert result.is_success is True
        assert result.is_complete is True

    def test_is_failure(self):
        result = TaskResult(task_id="t1", status=TaskStatus.FAILURE, error="boom")
        assert result.is_failure is True
        assert result.is_complete is True

    def test_is_complete_for_revoked(self):
        result = TaskResult(task_id="t1", status=TaskStatus.REVOKED)
        assert result.is_complete is True

    def test_get_success(self):
        result = TaskResult(task_id="t1", status=TaskStatus.SUCCESS, result="ok")
        assert result.get() == "ok"

    def test_get_failure_propagate(self):
        result = TaskResult(task_id="t1", status=TaskStatus.FAILURE, error="oops")
        with pytest.raises(Exception, match="oops"):
            result.get(propagate=True)

    def test_get_failure_no_propagate(self):
        result = TaskResult(task_id="t1", status=TaskStatus.FAILURE, error="oops")
        assert result.get(propagate=False) is None


# ==============================================================================
# Task class
# ==============================================================================


class TestTask:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_task_creation(self):
        def add(x, y):
            return x + y
        t = Task(func=add, name="test.add")
        assert t.name == "test.add"
        assert t.func is add
        assert t.bind is False

    def test_task_auto_name(self):
        def my_func():
            pass
        t = Task(func=my_func)
        assert "my_func" in t.name

    def test_task_call(self):
        def add(x, y):
            return x + y
        t = Task(func=add, name="test.task_call_add")
        assert t(2, 3) == 5

    def test_task_bind(self):
        def bound_task(self, x):
            return f"{self.name}:{x}"
        t = Task(func=bound_task, name="test.bound", bind=True)
        result = t(10)
        assert result == "test.bound:10"

    def test_task_apply_success(self):
        def add(x, y):
            return x + y
        t = Task(func=add, name="test.apply_add")
        result = t.apply(args=(3, 4))
        assert result.status == TaskStatus.SUCCESS
        assert result.result == 7
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_task_apply_failure_throw(self):
        def fail():
            raise ValueError("bad")
        t = Task(func=fail, name="test.apply_fail")
        with pytest.raises(ValueError, match="bad"):
            t.apply(throw=True)

    def test_task_apply_failure_no_throw(self):
        def fail():
            raise ValueError("bad")
        t = Task(func=fail, name="test.apply_fail_nothrow")
        result = t.apply(throw=False)
        assert result.status == TaskStatus.FAILURE
        assert "bad" in result.error

    def test_task_options(self):
        t = Task(
            func=lambda: None,
            name="test.opts",
            queue="high",
            priority=5,
            timeout=120,
            retry=3,
            retry_delay=10,
        )
        assert t.options.queue == "high"
        assert t.options.priority == 5
        assert t.options.timeout == 120
        assert t.options.retry == 3
        assert t.options.retry_delay == 10

    def test_task_repr(self):
        t = Task(func=lambda: None, name="test.repr_task")
        assert repr(t) == "Task(test.repr_task)"

    def test_task_registered(self):
        name = f"test.auto_register_{uuid.uuid4().hex[:8]}"
        t = Task(func=lambda: None, name=name)
        assert name in task_registry

    def test_task_signature_s(self):
        t = Task(func=lambda x: x, name="test.sig_s")
        sig = t.s(1, key="val")
        assert isinstance(sig, Signature)
        assert sig.args == (1,)
        assert sig.kwargs == {"key": "val"}

    def test_task_signature_si_immutable(self):
        t = Task(func=lambda x: x, name="test.sig_si")
        sig = t.si(1)
        assert sig.immutable is True

    def test_task_retry_raises(self):
        t = Task(func=lambda: None, name="test.retry_raise")
        with pytest.raises(Retry):
            t.retry(exc=ValueError("err"), countdown=5)

    def test_task_delay_calls_backend(self):
        t = Task(func=lambda x: x * 2, name="test.delay_backend")
        mock_backend = MagicMock()
        mock_backend.send_task.return_value = TaskResult(
            task_id="mock-id", status=TaskStatus.SUCCESS, result=4
        )
        t._backend = mock_backend
        result = t.delay(2)
        mock_backend.send_task.assert_called_once()
        assert result.result == 4


# ==============================================================================
# TaskRegistry
# ==============================================================================


class TestTaskRegistry:
    def test_register_and_get(self):
        reg = TaskRegistry()
        t = MagicMock(spec=Task)
        t.name = "reg.test_task"
        reg.register(t)
        assert reg.get("reg.test_task") is t

    def test_get_missing_returns_none(self):
        reg = TaskRegistry()
        assert reg.get("nonexistent") is None

    def test_unregister(self):
        reg = TaskRegistry()
        t = MagicMock(spec=Task)
        t.name = "reg.remove"
        reg.register(t)
        reg.unregister("reg.remove")
        assert reg.get("reg.remove") is None

    def test_contains(self):
        reg = TaskRegistry()
        t = MagicMock(spec=Task)
        t.name = "reg.contains"
        reg.register(t)
        assert "reg.contains" in reg
        assert "reg.nope" not in reg

    def test_len(self):
        reg = TaskRegistry()
        assert len(reg) == 0
        t = MagicMock(spec=Task)
        t.name = "reg.len"
        reg.register(t)
        assert len(reg) == 1

    def test_iter(self):
        reg = TaskRegistry()
        t1 = MagicMock(spec=Task)
        t1.name = "reg.iter1"
        t2 = MagicMock(spec=Task)
        t2.name = "reg.iter2"
        reg.register(t1)
        reg.register(t2)
        tasks = list(reg)
        assert t1 in tasks
        assert t2 in tasks

    def test_all_returns_copy(self):
        reg = TaskRegistry()
        t = MagicMock(spec=Task)
        t.name = "reg.all"
        reg.register(t)
        all_tasks = reg.all()
        assert "reg.all" in all_tasks
        all_tasks.pop("reg.all")
        assert "reg.all" in reg


# ==============================================================================
# @task decorator
# ==============================================================================


class TestTaskDecorator:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_task_without_parentheses(self):
        @task
        def simple(x):
            return x + 1
        assert isinstance(simple, Task)
        assert simple(5) == 6

    def test_task_with_options(self):
        @task(retry=3, queue="high", timeout=60)
        def configured():
            return "ok"
        assert isinstance(configured, Task)
        assert configured.options.retry == 3
        assert configured.options.queue == "high"
        assert configured.options.timeout == 60

    def test_shared_task_is_alias(self):
        assert shared_task is task

    def test_task_with_bind(self):
        @task(bind=True)
        def bound(self, x):
            return self.name
        assert isinstance(bound, Task)
        result = bound(10)
        assert "bound" in result


# ==============================================================================
# Retry Policies
# ==============================================================================


class TestExponentialBackoff:
    def test_default_delays(self):
        policy = ExponentialBackoff(initial_delay=1.0, multiplier=2.0, jitter=False)
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0

    def test_max_delay_cap(self):
        policy = ExponentialBackoff(
            initial_delay=100.0, multiplier=10.0, max_delay=300.0, jitter=False
        )
        assert policy.get_delay(1) == 100.0
        assert policy.get_delay(2) == 300.0

    def test_jitter_produces_different_values(self):
        policy = ExponentialBackoff(initial_delay=10.0, multiplier=2.0, jitter=True)
        delays = {policy.get_delay(1) for _ in range(20)}
        assert len(delays) > 1

    def test_should_retry_within_limit(self):
        policy = ExponentialBackoff(max_retries=3)
        assert policy.should_retry(1, Exception()) is True
        assert policy.should_retry(3, Exception()) is True
        assert policy.should_retry(4, Exception()) is False

    def test_should_retry_specific_exceptions(self):
        policy = ExponentialBackoff(max_retries=5, retry_on=[ValueError, TypeError])
        assert policy.should_retry(1, ValueError("x")) is True
        assert policy.should_retry(1, TypeError("x")) is True
        assert policy.should_retry(1, RuntimeError("x")) is False


class TestLinearBackoff:
    def test_delays(self):
        policy = LinearBackoff(initial_delay=5.0, increment=5.0)
        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(2) == 10.0
        assert policy.get_delay(3) == 15.0

    def test_max_delay_cap(self):
        policy = LinearBackoff(initial_delay=100.0, increment=200.0, max_delay=250.0)
        assert policy.get_delay(2) == 250.0

    def test_should_retry(self):
        policy = LinearBackoff(max_retries=2)
        assert policy.should_retry(1, Exception()) is True
        assert policy.should_retry(2, Exception()) is True
        assert policy.should_retry(3, Exception()) is False


class TestFixedDelay:
    def test_constant_delay(self):
        policy = FixedDelay(delay=30.0)
        assert policy.get_delay(1) == 30.0
        assert policy.get_delay(5) == 30.0
        assert policy.get_delay(100) == 30.0

    def test_should_retry(self):
        policy = FixedDelay(max_retries=1)
        assert policy.should_retry(1, Exception()) is True
        assert policy.should_retry(2, Exception()) is False


class TestNoRetry:
    def test_no_retry(self):
        policy = NoRetry()
        assert policy.should_retry(1, Exception()) is False
        assert policy.get_delay(1) == 0


class TestRetryOnException:
    def test_only_retries_specified(self):
        policy = RetryOnException(
            exceptions=[ConnectionError, TimeoutError], max_retries=3, delay=5.0
        )
        assert policy.should_retry(1, ConnectionError()) is True
        assert policy.should_retry(1, TimeoutError()) is True
        assert policy.should_retry(1, ValueError()) is False

    def test_exponential_mode(self):
        policy = RetryOnException(
            exceptions=[Exception], delay=2.0, exponential=True, multiplier=3.0
        )
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 6.0
        assert policy.get_delay(3) == 18.0


class TestCompositeRetryPolicy:
    def test_any_policy_allows_retry(self):
        p1 = RetryOnException(exceptions=[ValueError], max_retries=1)
        p2 = RetryOnException(exceptions=[TypeError], max_retries=1)
        composite = CompositeRetryPolicy(policies=[p1, p2])
        assert composite.should_retry(1, ValueError()) is True
        assert composite.should_retry(1, TypeError()) is True
        assert composite.should_retry(1, RuntimeError()) is False


# ==============================================================================
# Scheduling
# ==============================================================================


class TestIntervalSchedule:
    def test_total_seconds(self):
        s = IntervalSchedule(hours=1, minutes=30, seconds=15)
        assert s.total_seconds == 3600 + 1800 + 15

    def test_get_next_run(self):
        s = IntervalSchedule(minutes=5)
        now = datetime(2025, 1, 1, 12, 0, 0)
        next_run = s.get_next_run(now)
        assert next_run == now + timedelta(minutes=5)

    def test_repr(self):
        s = every(hours=2, minutes=30)
        assert "hours=2" in repr(s)
        assert "minutes=30" in repr(s)

    def test_weeks(self):
        s = IntervalSchedule(weeks=2)
        assert s.total_seconds == 2 * 604800


class TestCrontabSchedule:
    def test_parse_field_star(self):
        c = CrontabSchedule()
        result = c._parse_field("*", 0, 59)
        assert result == set(range(0, 60))

    def test_parse_field_integer(self):
        c = CrontabSchedule()
        result = c._parse_field(5, 0, 59)
        assert result == {5}

    def test_parse_field_step(self):
        c = CrontabSchedule()
        result = c._parse_field("*/15", 0, 59)
        assert result == {0, 15, 30, 45}

    def test_parse_field_range(self):
        c = CrontabSchedule()
        result = c._parse_field("1-5", 0, 6)
        assert result == {1, 2, 3, 4, 5}

    def test_get_next_run_midnight(self):
        c = crontab(minute=0, hour=0)
        now = datetime(2025, 6, 15, 10, 30, 0)
        next_run = c.get_next_run(now)
        assert next_run.hour == 0
        assert next_run.minute == 0
        assert next_run.day == 16

    def test_get_next_run_every_15_min(self):
        c = crontab(minute="*/15")
        now = datetime(2025, 6, 15, 10, 1, 0)
        next_run = c.get_next_run(now)
        assert next_run.minute == 15

    def test_repr(self):
        c = crontab(minute=0, hour=12)
        assert "minute=0" in repr(c)
        assert "hour=12" in repr(c)


class TestScheduler:
    def setup_method(self):
        self.scheduler = Scheduler()

    def test_register_and_get(self):
        mock_task = MagicMock()
        mock_task.name = "sched.test"
        self.scheduler.register(mock_task, every(minutes=5))
        st = self.scheduler.get("sched.test")
        assert st is not None
        assert st.task is mock_task
        assert st.enabled is True

    def test_unregister(self):
        mock_task = MagicMock()
        mock_task.name = "sched.unreg"
        self.scheduler.register(mock_task, every(hours=1))
        self.scheduler.unregister("sched.unreg")
        assert self.scheduler.get("sched.unreg") is None

    def test_enable_disable(self):
        mock_task = MagicMock()
        mock_task.name = "sched.toggle"
        self.scheduler.register(mock_task, every(hours=1))
        self.scheduler.disable("sched.toggle")
        assert self.scheduler.get("sched.toggle").enabled is False
        self.scheduler.enable("sched.toggle")
        assert self.scheduler.get("sched.toggle").enabled is True

    def test_get_due_tasks(self):
        mock_task = MagicMock()
        mock_task.name = "sched.due"
        self.scheduler.register(mock_task, every(minutes=5))
        st = self.scheduler.get("sched.due")
        st.next_run = datetime(2020, 1, 1)
        due = self.scheduler.get_due_tasks(datetime(2025, 1, 1))
        assert len(due) == 1
        assert due[0].task is mock_task

    def test_disabled_tasks_not_due(self):
        mock_task = MagicMock()
        mock_task.name = "sched.disabled_due"
        self.scheduler.register(mock_task, every(minutes=5))
        st = self.scheduler.get("sched.disabled_due")
        st.next_run = datetime(2020, 1, 1)
        self.scheduler.disable("sched.disabled_due")
        due = self.scheduler.get_due_tasks(datetime(2025, 1, 1))
        assert len(due) == 0

    def test_mark_run(self):
        mock_task = MagicMock()
        mock_task.name = "sched.mark"
        self.scheduler.register(mock_task, every(minutes=10))
        self.scheduler.mark_run("sched.mark")
        st = self.scheduler.get("sched.mark")
        assert st.last_run is not None

    def test_all_returns_copy(self):
        mock_task = MagicMock()
        mock_task.name = "sched.all"
        self.scheduler.register(mock_task, every(hours=1))
        all_tasks = self.scheduler.all()
        assert "sched.all" in all_tasks
        all_tasks.pop("sched.all")
        assert self.scheduler.get("sched.all") is not None


# ==============================================================================
# Primitives
# ==============================================================================


class TestSignature:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_creation(self):
        t = Task(func=lambda x: x, name="prim.sig_create")
        sig = Signature(task=t, args=(1,), kwargs={"y": 2})
        assert sig.task is t
        assert sig.args == (1,)
        assert sig.kwargs == {"y": 2}
        assert sig.immutable is False

    def test_clone(self):
        t = Task(func=lambda x: x, name="prim.sig_clone")
        sig = Signature(task=t, args=(1,), kwargs={"y": 2})
        cloned = sig.clone(args=(10,))
        assert cloned.args == (10,)
        assert cloned.kwargs == {"y": 2}
        assert cloned is not sig

    def test_set_options(self):
        t = Task(func=lambda: None, name="prim.sig_set")
        sig = Signature(task=t)
        result = sig.set(queue="high", priority=5)
        assert result is sig
        assert sig.options["queue"] == "high"

    def test_repr(self):
        t = Task(func=lambda: None, name="prim.sig_repr")
        sig = Signature(task=t, args=(1,), kwargs={"x": 2})
        r = repr(sig)
        assert "prim.sig_repr" in r

    def test_apply_sync(self):
        t = Task(func=lambda x: x * 2, name="prim.sig_apply")
        sig = Signature(task=t, args=(5,))
        result = sig.apply()
        assert result.status == TaskStatus.SUCCESS
        assert result.result == 10

    def test_or_creates_chain(self):
        t = Task(func=lambda x: x, name="prim.sig_or")
        sig1 = t.s(1)
        sig2 = t.s(2)
        result = sig1 | sig2
        assert isinstance(result, Chain)


class TestGroup:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_group_creation(self):
        t = Task(func=lambda x: x, name="prim.group_create")
        g = group(t.s(1), t.s(2), t.s(3))
        assert isinstance(g, Group)
        assert len(g) == 3

    def test_group_iter(self):
        t = Task(func=lambda x: x, name="prim.group_iter")
        g = group(t.s(1), t.s(2))
        sigs = list(g)
        assert len(sigs) == 2

    def test_group_apply_sync(self):
        t = Task(func=lambda x: x * 10, name="prim.group_apply")
        g = group(t.s(1), t.s(2), t.s(3))
        result = g.apply()
        assert isinstance(result, GroupResult)
        values = result.get()
        assert values == [10, 20, 30]


class TestChain:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_chain_creation(self):
        t = Task(func=lambda x: x, name="prim.chain_create")
        c = chain(t.s(1), t.s(2))
        assert isinstance(c, Chain)
        assert len(c) == 2

    def test_chain_apply_sync(self):
        add_one = Task(func=lambda x: x + 1, name="prim.chain_add_one")
        double = Task(func=lambda x: x * 2, name="prim.chain_double")
        c = chain(add_one.s(0), double.s())
        result = c.apply()
        assert result.result == 2

    def test_chain_immutable_skips_result_passing(self):
        t1 = Task(func=lambda: 100, name="prim.chain_imm_t1")
        t2 = Task(func=lambda: 42, name="prim.chain_imm_t2")
        sig2 = Signature(task=t2, immutable=True)
        c = Chain(tasks=[t1.s(), sig2])
        result = c.apply()
        assert result.result == 42

    def test_chain_or_extends(self):
        t = Task(func=lambda x: x, name="prim.chain_or")
        c = chain(t.s(1), t.s(2))
        extended = c | t.s(3)
        assert isinstance(extended, Chain)
        assert len(extended) == 3


class TestChord:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_chord_apply_sync(self):
        square = Task(func=lambda x: x**2, name="prim.chord_square")
        sum_all = Task(func=lambda results: sum(results), name="prim.chord_sum")
        header = group(square.s(1), square.s(2), square.s(3))
        c = chord(header, sum_all.s())
        result = c.apply()
        assert result.result == 14


# ==============================================================================
# SyncBackend
# ==============================================================================


class TestSyncBackend:
    def setup_method(self):
        self.backend = SyncBackend()
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_send_task_success(self):
        t = Task(func=lambda x: x + 1, name="sync.success")
        result = self.backend.send_task(t, args=(5,))
        assert result.status == TaskStatus.SUCCESS
        assert result.result == 6

    def test_send_task_failure(self):
        def fail():
            raise RuntimeError("boom")
        t = Task(func=fail, name="sync.fail")
        result = self.backend.send_task(t, args=())
        assert result.status == TaskStatus.FAILURE
        assert "boom" in result.error

    def test_send_task_with_bind(self):
        def bound(self, x):
            return f"{self.name}={x}"
        t = Task(func=bound, name="sync.bound", bind=True)
        result = self.backend.send_task(t, args=(7,))
        assert result.status == TaskStatus.SUCCESS
        assert "sync.bound=7" == result.result

    def test_get_result_stored(self):
        t = Task(func=lambda: "val", name="sync.stored")
        result = self.backend.send_task(t)
        fetched = self.backend.get_result(result.task_id)
        assert fetched.result == "val"

    def test_get_result_missing(self):
        result = self.backend.get_result("nonexistent")
        assert result.status == TaskStatus.PENDING

    def test_revoke_noop(self):
        self.backend.revoke("some-id")

    def test_send_group(self):
        t = Task(func=lambda x: x * 2, name="sync.group")
        sigs = [t.s(1), t.s(2), t.s(3)]
        result = self.backend.send_group(sigs)
        values = [r.result for r in result.results]
        assert values == [2, 4, 6]

    def test_send_chain(self):
        inc = Task(func=lambda x: x + 1, name="sync.chain_inc")
        dbl = Task(func=lambda x: x * 2, name="sync.chain_dbl")
        sigs = [inc.s(0), dbl.s()]
        result = self.backend.send_chain(sigs)
        assert result.result == 2

    def test_send_chain_empty(self):
        result = self.backend.send_chain([])
        assert result.status == TaskStatus.SUCCESS

    def test_send_chain_stops_on_failure(self):
        def fail(x):
            raise ValueError("stop")
        t1 = Task(func=lambda: 1, name="sync.chain_ok")
        t2 = Task(func=fail, name="sync.chain_stop")
        t3 = Task(func=lambda x: x, name="sync.chain_never")
        sigs = [t1.s(), t2.s(), t3.s()]
        result = self.backend.send_chain(sigs)
        assert result.status == TaskStatus.FAILURE

    def test_send_chord(self):
        sq = Task(func=lambda x: x**2, name="sync.chord_sq")
        total = Task(func=lambda results: sum(results), name="sync.chord_total")
        g = Group(tasks=[sq.s(2), sq.s(3)])
        result = self.backend.send_chord(g, total.s())
        assert result.result == 13

    def test_close_clears_results(self):
        t = Task(func=lambda: 1, name="sync.close")
        self.backend.send_task(t)
        assert len(self.backend._results) > 0
        self.backend.close()
        assert len(self.backend._results) == 0


# ==============================================================================
# TaskConfig
# ==============================================================================


class TestTaskConfig:
    def test_default_values(self):
        config = TaskConfig()
        assert config.backend == "sync"
        assert config.default_queue == "default"
        assert config.default_retry == 3
        assert config.default_timeout == 300
        assert config.task_always_eager is False

    def test_get_backend_sync(self):
        from django_matt.tasks.config import get_backend, set_backend
        cfg = TaskConfig(backend="sync")
        set_task_config(cfg)
        set_backend(None)
        backend = get_backend()
        assert isinstance(backend, SyncBackend)

    def test_from_django_settings(self):
        with patch("django.conf.settings") as mock_settings:
            mock_settings.DJANGO_MATT_TASKS = {
                "BACKEND": "celery",
                "DEFAULT_QUEUE": "custom",
                "DEFAULT_RETRY": 5,
            }
            config = TaskConfig.from_django_settings()
            assert config.backend == "celery"
            assert config.default_queue == "custom"
            assert config.default_retry == 5


# ==============================================================================
# GroupResult
# ==============================================================================


class TestGroupResult:
    def test_get_all_results(self):
        results = [
            TaskResult(task_id="1", status=TaskStatus.SUCCESS, result=10),
            TaskResult(task_id="2", status=TaskStatus.SUCCESS, result=20),
        ]
        gr = GroupResult(results=results)
        assert gr.get() == [10, 20]

    def test_is_complete(self):
        results = [
            TaskResult(task_id="1", status=TaskStatus.SUCCESS),
            TaskResult(task_id="2", status=TaskStatus.FAILURE),
        ]
        gr = GroupResult(results=results)
        assert gr.is_complete is True

    def test_is_not_complete(self):
        results = [
            TaskResult(task_id="1", status=TaskStatus.SUCCESS),
            TaskResult(task_id="2", status=TaskStatus.PENDING),
        ]
        gr = GroupResult(results=results)
        assert gr.is_complete is False

    def test_iter_and_len(self):
        results = [
            TaskResult(task_id="1", status=TaskStatus.SUCCESS),
            TaskResult(task_id="2", status=TaskStatus.SUCCESS),
        ]
        gr = GroupResult(results=results)
        assert len(gr) == 2
        assert list(gr) == results


# ==============================================================================
# Retry exception
# ==============================================================================


class TestRetryException:
    def test_retry_with_exc(self):
        err = ValueError("inner")
        retry = Retry(exc=err, countdown=10, max_retries=3)
        assert retry.exc is err
        assert retry.countdown == 10
        assert retry.max_retries == 3
        assert "inner" in str(retry)

    def test_retry_without_exc(self):
        retry = Retry()
        assert "retry requested" in str(retry).lower()


# ==============================================================================
# signature() function
# ==============================================================================


class TestSignatureFunction:
    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_signature_function(self):
        t = Task(func=lambda x: x, name="prim.sig_func")
        sig = signature(t, args=(1, 2), kwargs={"key": "val"}, queue="low")
        assert isinstance(sig, Signature)
        assert sig.args == (1, 2)
        assert sig.kwargs == {"key": "val"}
        assert sig.options["queue"] == "low"


# ==============================================================================
# Task Execution + Status Tests (07-03)
# ==============================================================================


class TestTaskExecution:
    """Tests for task execution with status tracking.

    Verifies:
    - @task decorated function executes and returns TaskResult with SUCCESS
    - TaskResult contains the return value
    - Task status is retrievable after execution
    - datetime.now(UTC) is used (not utcnow)
    """

    def setup_method(self):
        self._original_tasks = task_registry._tasks.copy()

    def teardown_method(self):
        task_registry._tasks = self._original_tasks

    def test_task_decorator_execute_returns_success(self):
        """Test: @task function executes with .apply() and returns SUCCESS."""
        @task
        def add_numbers(x, y):
            return x + y

        result = add_numbers.apply(args=(3, 7))

        assert isinstance(result, TaskResult)
        assert result.status == TaskStatus.SUCCESS
        assert result.result == 10
        assert result.error is None

    def test_task_result_contains_return_value(self):
        """Test: TaskResult.result contains the function's return value."""
        @task
        def make_greeting(name):
            return f"Hello, {name}!"

        result = make_greeting.apply(args=("World",))

        assert result.result == "Hello, World!"
        assert result.is_success is True
        assert result.is_complete is True

    def test_task_status_retrievable_via_sync_backend(self):
        """Test: Task status is retrievable after execution via SyncBackend."""
        backend = SyncBackend()

        @task
        def compute(x):
            return x * x

        compute._backend = backend
        async_result = compute.delay(5)

        assert async_result.status == TaskStatus.SUCCESS
        assert async_result.result == 25

        # Verify retrievable via get_result
        fetched = backend.get_result(async_result.task_id)
        assert fetched.status == TaskStatus.SUCCESS
        assert fetched.result == 25

    def test_task_apply_timestamps_use_utc(self):
        """Test: Task.apply() uses datetime.now(UTC) for timestamps."""
        @task
        def noop():
            return None

        result = noop.apply()

        assert result.started_at is not None
        assert result.completed_at is not None
        # After fix: timestamps should be timezone-aware (UTC)
        assert result.started_at.tzinfo is not None
        assert result.completed_at.tzinfo is not None

    def test_task_failure_status_retrievable(self):
        """Test: Failed task has FAILURE status with error message."""
        @task
        def failing_task():
            raise ValueError("something went wrong")

        result = failing_task.apply(throw=False)

        assert result.status == TaskStatus.FAILURE
        assert result.is_failure is True
        assert "something went wrong" in result.error
