"""
Native Task Engine for django-matt.

Best-in-class background task DX with Django 6.0 native tasks support,
type-safe Pydantic validation, and zero-config development mode.

Quick Start (Zero Config):
    from django_matt.tasks_native import task

    @task
    async def send_email(user_id: int, template: str) -> bool:
        user = await User.objects.aget(id=user_id)
        return await deliver_email(user, template)

    # Enqueue the task
    send_email.delay(user_id=1, template="welcome")

With Pydantic Validation:
    from pydantic import BaseModel
    from django_matt.tasks_native import task

    class EmailPayload(BaseModel):
        user_id: int
        template: str

    @task
    async def send_email(payload: EmailPayload) -> bool:
        user = await User.objects.aget(id=payload.user_id)
        return await deliver_email(user, payload.template)

    # Validates payload at enqueue time
    send_email.delay(EmailPayload(user_id=1, template="welcome"))

    # Dict is auto-converted and validated
    send_email.delay({"user_id": 1, "template": "welcome"})

Periodic Tasks:
    from django_matt.tasks_native import periodic_task, crontab, every

    @periodic_task(crontab(hour=9, minute=0))
    async def daily_report():
        # Runs daily at 9 AM
        await generate_report()

    @periodic_task(every(minutes=5))
    async def health_check():
        # Runs every 5 minutes
        await check_system_health()

Production Setup (One Line):
    # settings.py
    MATT_TASKS = {
        "backend": "redis",
        "url": "redis://localhost:6379/0",
    }

Backend Auto-Detection:
    - Django 6.0+: Uses native tasks (django.tasks)
    - Django 5.x: Falls back to Celery, Dramatiq, or Django-Q2
    - Development: Sync execution (no dependencies)
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
