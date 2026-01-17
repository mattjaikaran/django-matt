"""
Task decorators.

Provides decorators for defining background tasks.
"""

from functools import wraps
from typing import Callable, Union, TYPE_CHECKING

from .base import Task

if TYPE_CHECKING:
    from .retry import RetryPolicy
    from .scheduling import ScheduleEntry


def task(
    func: Callable = None,
    *,
    name: str = None,
    queue: str = None,
    priority: int = 0,
    timeout: int = None,
    retry: int = 0,
    retry_delay: int = 0,
    retry_policy: "RetryPolicy" = None,
    rate_limit: str = None,
    ignore_result: bool = False,
    bind: bool = False,
    **kwargs,
) -> Union[Task, Callable[[Callable], Task]]:
    """
    Decorator to define a background task.

    Usage:
        @task
        def simple_task(x, y):
            return x + y

        @task(retry=3, retry_delay=60)
        def reliable_task():
            # This will retry up to 3 times
            do_something()

        @task(queue="high-priority", timeout=300)
        def important_task():
            # Runs on high-priority queue with 5min timeout
            do_important_work()

        @task(bind=True)
        def task_with_self(self, x):
            # self is the Task instance
            print(f"Running {self.name}")
            return x * 2

    Args:
        func: The function to wrap (when used without parentheses)
        name: Task name (defaults to function's qualified name)
        queue: Default queue for this task
        priority: Task priority (higher = more important)
        timeout: Execution timeout in seconds
        retry: Number of retries on failure
        retry_delay: Delay between retries in seconds
        retry_policy: Custom retry policy
        rate_limit: Rate limit (e.g., "10/m" for 10 per minute)
        ignore_result: Whether to discard the result
        bind: Whether to pass the task instance as first argument

    Returns:
        Task instance
    """

    def decorator(fn: Callable) -> Task:
        return Task(
            func=fn,
            name=name,
            queue=queue,
            priority=priority,
            timeout=timeout,
            retry=retry,
            retry_delay=retry_delay,
            retry_policy=retry_policy,
            rate_limit=rate_limit,
            ignore_result=ignore_result,
            bind=bind,
            **kwargs,
        )

    if func is not None:
        # Used without parentheses: @task
        return decorator(func)

    # Used with parentheses: @task(...)
    return decorator


# Alias for task - matches Celery's naming
shared_task = task


def periodic_task(
    schedule: "ScheduleEntry",
    *,
    name: str = None,
    queue: str = None,
    **task_kwargs,
) -> Callable[[Callable], Task]:
    """
    Decorator to define a periodic (scheduled) task.

    Usage:
        from django_matt.tasks import periodic_task, crontab, every

        @periodic_task(crontab(hour=0, minute=0))
        def daily_cleanup():
            # Runs daily at midnight
            OldData.objects.filter(created_at__lt=days_ago(30)).delete()

        @periodic_task(every(minutes=5))
        def health_check():
            # Runs every 5 minutes
            check_system_health()

    Args:
        schedule: When to run the task (crontab or interval)
        name: Task name
        queue: Queue to run on
        **task_kwargs: Additional task options

    Returns:
        Task instance with schedule attached
    """

    def decorator(func: Callable) -> Task:
        # Create the task
        task_instance = Task(
            func=func,
            name=name,
            queue=queue,
            **task_kwargs,
        )

        # Attach schedule to the task
        task_instance.schedule = schedule

        # Register with scheduler
        from .scheduling import scheduler

        scheduler.register(task_instance, schedule)

        return task_instance

    return decorator


def schedule(
    schedule_entry: "ScheduleEntry",
) -> Callable[[Task], Task]:
    """
    Decorator to add a schedule to an existing task.

    This allows separating task definition from scheduling.

    Usage:
        @schedule(crontab(hour=0, minute=0))
        @task
        def daily_task():
            ...

        # Or on an existing task
        @schedule(every(hours=1))
        @task
        def hourly_task():
            ...

    Args:
        schedule_entry: When to run the task

    Returns:
        Decorated task with schedule
    """

    def decorator(task_instance: Task) -> Task:
        if not isinstance(task_instance, Task):
            raise TypeError(
                "@schedule must be applied to a @task decorated function. "
                "Make sure @schedule is above @task."
            )

        task_instance.schedule = schedule_entry

        from .scheduling import scheduler

        scheduler.register(task_instance, schedule_entry)

        return task_instance

    return decorator


def on_success(callback: Callable) -> Callable[[Task], Task]:
    """
    Add a callback to run when task succeeds.

    Usage:
        def notify_success(result):
            send_notification(f"Task completed: {result}")

        @on_success(notify_success)
        @task
        def my_task():
            return "done"
    """

    def decorator(task_instance: Task) -> Task:
        original_func = task_instance.func

        @wraps(original_func)
        def wrapper(*args, **kwargs):
            result = original_func(*args, **kwargs)
            callback(result)
            return result

        task_instance.func = wrapper
        return task_instance

    return decorator


def on_failure(callback: Callable) -> Callable[[Task], Task]:
    """
    Add a callback to run when task fails.

    Usage:
        def notify_failure(exc):
            send_alert(f"Task failed: {exc}")

        @on_failure(notify_failure)
        @task
        def my_task():
            do_risky_thing()
    """

    def decorator(task_instance: Task) -> Task:
        original_func = task_instance.func

        @wraps(original_func)
        def wrapper(*args, **kwargs):
            try:
                return original_func(*args, **kwargs)
            except Exception as e:
                callback(e)
                raise

        task_instance.func = wrapper
        return task_instance

    return decorator
