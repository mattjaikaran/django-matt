"""DEPRECATED: Use `django_matt.tasks` instead. The tasks_native system will be removed in v1.0.

The `django_matt.tasks` module provides the same API with broader backend support
(Celery, Dramatiq, Django-Q2, Django 6.0 native) and is the canonical task system.
"""

from .backends import BaseNativeBackend, SyncNativeBackend
from .config import (
    NativeTaskConfig,
    get_backend,
    get_config,
    reset,
    set_backend,
    set_config,
)
from .core import NativeTask, task
from .registry import TaskRegistry, task_registry
from .retry import (
    CompositePolicy,
    ExponentialBackoff,
    FixedDelay,
    LinearBackoff,
    NoRetry,
    RetryOnException,
    RetryPolicy,
    RetryState,
    TaskFailureHandler,
    failure_handler,
    retry,
)
from .scheduling import (
    CrontabSchedule,
    IntervalSchedule,
    ScheduledTaskEntry,
    ScheduleRegistry,
    crontab,
    every,
    periodic_task,
    schedule_registry,
)
from .types import (
    TaskExecutionError,
    TaskMeta,
    TaskOptions,
    TaskResult,
    TaskState,
    TaskValidationError,
)

__all__ = [
    # Core
    "task",
    "NativeTask",
    # Scheduling
    "periodic_task",
    "crontab",
    "every",
    "CrontabSchedule",
    "IntervalSchedule",
    "ScheduledTaskEntry",
    "ScheduleRegistry",
    "schedule_registry",
    # Types
    "TaskState",
    "TaskMeta",
    "TaskResult",
    "TaskOptions",
    "TaskExecutionError",
    "TaskValidationError",
    # Registry
    "TaskRegistry",
    "task_registry",
    # Config
    "NativeTaskConfig",
    "get_config",
    "set_config",
    "get_backend",
    "set_backend",
    "reset",
    # Retry
    "retry",
    "RetryPolicy",
    "ExponentialBackoff",
    "LinearBackoff",
    "FixedDelay",
    "NoRetry",
    "RetryOnException",
    "CompositePolicy",
    "RetryState",
    "TaskFailureHandler",
    "failure_handler",
    # Backends
    "BaseNativeBackend",
    "SyncNativeBackend",
]

default_app_config = "django_matt.tasks_native.apps.TasksNativeConfig"
