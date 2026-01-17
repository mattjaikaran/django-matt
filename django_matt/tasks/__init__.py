"""
Background task system for django-matt.

Provides a unified interface for background task processing with
multiple backend support:
- Celery (production-grade, distributed)
- Dramatiq (simple, reliable)
- Django-Q2 (Django-native, multiprocessing)

Quick Start:
    # 1. Configure backend in settings
    DJANGO_MATT_TASKS = {
        "BACKEND": "celery",  # or "dramatiq", "django_q"
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
    }

    # 2. Define tasks
    from django_matt.tasks import task, shared_task

    @task
    def send_email(to: str, subject: str, body: str):
        # This runs in the background
        send_mail(to, subject, body)

    @task(retry=3, retry_delay=60)
    def process_payment(order_id: int):
        # Retries up to 3 times with 60s delay
        order = Order.objects.get(id=order_id)
        charge_card(order)

    # 3. Call tasks
    send_email.delay("user@example.com", "Hello", "World")

    # Or with options
    send_email.apply_async(
        args=["user@example.com", "Hello", "World"],
        countdown=60,  # Delay execution by 60 seconds
    )

    # 4. Schedule periodic tasks
    from django_matt.tasks import schedule, crontab

    @schedule(crontab(hour=0, minute=0))  # Run daily at midnight
    @task
    def cleanup_old_data():
        OldData.objects.filter(created_at__lt=days_ago(30)).delete()

Advanced Usage:
    # Task with custom queue
    @task(queue="high-priority")
    def urgent_task():
        ...

    # Task with timeout
    @task(timeout=300)  # 5 minute timeout
    def long_running_task():
        ...

    # Task groups and chains
    from django_matt.tasks import group, chain

    # Run tasks in parallel
    result = group(
        process_item.s(1),
        process_item.s(2),
        process_item.s(3),
    ).apply_async()

    # Run tasks in sequence
    result = chain(
        fetch_data.s(),
        process_data.s(),
        save_results.s(),
    ).apply_async()
"""

from .base import (
    Task,
    TaskResult,
    TaskStatus,
    TaskRegistry,
    task_registry,
)

from .decorators import (
    task,
    shared_task,
    periodic_task,
    schedule,
)

from .config import (
    TaskConfig,
    get_task_config,
    get_backend,
)

from .retry import (
    RetryPolicy,
    ExponentialBackoff,
    LinearBackoff,
    FixedDelay,
)

from .scheduling import (
    crontab,
    every,
    ScheduleEntry,
)

from .primitives import (
    group,
    chain,
    chord,
    signature,
)

from .backends import (
    BaseBackend,
    CeleryBackend,
    DramatiqBackend,
    DjangoQBackend,
    SyncBackend,
)

__all__ = [
    # Base
    "Task",
    "TaskResult",
    "TaskStatus",
    "TaskRegistry",
    "task_registry",
    # Decorators
    "task",
    "shared_task",
    "periodic_task",
    "schedule",
    # Config
    "TaskConfig",
    "get_task_config",
    "get_backend",
    # Retry
    "RetryPolicy",
    "ExponentialBackoff",
    "LinearBackoff",
    "FixedDelay",
    # Scheduling
    "crontab",
    "every",
    "ScheduleEntry",
    # Primitives
    "group",
    "chain",
    "chord",
    "signature",
    # Backends
    "BaseBackend",
    "CeleryBackend",
    "DramatiqBackend",
    "DjangoQBackend",
    "SyncBackend",
]
