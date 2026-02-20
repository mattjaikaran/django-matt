"""
Dramatiq backend implementation.

Provides integration with Dramatiq for task processing.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseBackend

if TYPE_CHECKING:
    from ..base import Task, TaskResult


class DramatiqBackend(BaseBackend):
    """
    Dramatiq task queue backend.

    Dramatiq is a fast, reliable task processing library with:
    - Simple API
    - Multiple message brokers (Redis, RabbitMQ)
    - Automatic retries with exponential backoff
    - Rate limiting
    - Result storage

    Usage:
        # In settings.py
        DJANGO_MATT_TASKS = {
            "BACKEND": "dramatiq",
            "DRAMATIQ_BROKER": "redis",
            "DRAMATIQ_REDIS_URL": "redis://localhost:6379/0",
        }

        # Define tasks
        @task
        def my_task(x, y):
            return x + y

        # Execute
        my_task.delay(1, 2)

    Requires:
        uv add "dramatiq[redis]"
    """

    def __init__(self, **config):
        """
        Initialize Dramatiq backend.

        Args:
            **config: Dramatiq configuration options
        """
        self._broker = None
        self._config = config
        self._actors = {}

    @property
    def broker(self):
        """Get or create the Dramatiq broker."""
        if self._broker is None:
            self._broker = self._create_broker()
        return self._broker

    def _create_broker(self):
        """Create and configure the Dramatiq broker."""
        try:
            import dramatiq
            from dramatiq.brokers.rabbitmq import RabbitmqBroker
            from dramatiq.brokers.redis import RedisBroker
        except ImportError:
            raise ImportError(
                "Dramatiq is required for DramatiqBackend. "
                "Install with: uv add \"dramatiq[redis]\""
            )

        broker_type = self._config.get("DRAMATIQ_BROKER", "redis").lower()

        if broker_type == "redis":
            redis_url = self._config.get(
                "DRAMATIQ_REDIS_URL",
                self._config.get("redis_url", "redis://localhost:6379/0"),
            )
            broker = RedisBroker(url=redis_url)
        elif broker_type == "rabbitmq":
            rabbitmq_url = self._config.get(
                "DRAMATIQ_RABBITMQ_URL",
                self._config.get("rabbitmq_url", "amqp://guest:guest@localhost:5672"),
            )
            broker = RabbitmqBroker(url=rabbitmq_url)
        else:
            raise ValueError(f"Unknown broker type: {broker_type}")

        dramatiq.set_broker(broker)

        # Add result backend middleware if configured
        if self._config.get("DRAMATIQ_RESULT_BACKEND"):
            try:
                from dramatiq.results import Results
                from dramatiq.results.backends import RedisBackend

                result_backend = RedisBackend(url=self._config.get("DRAMATIQ_RESULT_BACKEND"))
                broker.add_middleware(Results(backend=result_backend))
            except ImportError:
                pass

        # Register all tasks from registry
        from ..base import task_registry

        for task in task_registry:
            self._register_dramatiq_actor(task)

        return broker

    def _register_dramatiq_actor(self, task: "Task"):
        """Register a django-matt task as a Dramatiq actor."""
        import dramatiq

        # Build actor options
        options = {}
        if task.options.queue:
            options["queue_name"] = task.options.queue
        if task.options.priority:
            options["priority"] = task.options.priority
        if task.options.retry:
            options["max_retries"] = task.options.retry
        if task.options.retry_delay:
            options["min_backoff"] = task.options.retry_delay * 1000

        # Create actor
        @dramatiq.actor(actor_name=task.name, **options)
        def actor(*args, **kwargs):
            if task.bind:
                return task.func(task, *args, **kwargs)
            return task.func(*args, **kwargs)

        self._actors[task.name] = actor
        task._dramatiq_actor = actor

    def send_task(
        self,
        task: "Task",
        args: tuple = (),
        kwargs: dict = None,
        task_id: str = None,
        countdown: int = None,
        eta: datetime = None,
        expires: int = None,
        queue: str = None,
        priority: int = None,
        **options,
    ) -> "TaskResult":
        """Send a task to Dramatiq."""

        # Ensure broker is created
        _ = self.broker

        # Get the Dramatiq actor
        actor = self._actors.get(task.name)
        if actor is None:
            self._register_dramatiq_actor(task)
            actor = task._dramatiq_actor

        # Build send options
        send_options = {}
        if countdown:
            send_options["delay"] = countdown * 1000  # Dramatiq uses milliseconds

        # Send message
        message = actor.send_with_options(
            args=args,
            kwargs=kwargs or {},
            **send_options,
        )

        task_id = task_id or message.message_id

        return DramatiqTaskResult(
            task_id=task_id,
            message=message,
        )

    def get_result(self, task_id: str) -> "TaskResult":
        """Get a task result from Dramatiq."""
        # Dramatiq requires the result backend middleware
        return DramatiqTaskResult(task_id=task_id)

    def revoke(self, task_id: str, terminate: bool = False) -> None:
        """
        Revoke a Dramatiq task.

        Note: Dramatiq doesn't have built-in task revocation.
        This is a no-op.
        """

    def configure(self, **config) -> None:
        """Update configuration."""
        self._config.update(config)
        self._broker = None

    def close(self) -> None:
        """Close Dramatiq connections."""
        if self._broker:
            self._broker.close()


class DramatiqTaskResult:
    """Task result wrapper for Dramatiq."""

    def __init__(self, task_id: str, message=None):
        self.task_id = task_id
        self._message = message
        self._result = None
        self._status = None

    @property
    def status(self):
        from ..base import TaskStatus

        if self._status:
            return self._status

        # Dramatiq doesn't have built-in status tracking without result backend
        if self._result is not None:
            return TaskStatus.SUCCESS

        return TaskStatus.PENDING

    @property
    def result(self):
        return self._result

    @property
    def error(self):
        return None

    @property
    def is_pending(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.PENDING

    @property
    def is_success(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.SUCCESS

    @property
    def is_failure(self):
        from ..base import TaskStatus

        return self.status == TaskStatus.FAILURE

    @property
    def is_complete(self):
        from ..base import TaskStatus

        return self.status in (TaskStatus.SUCCESS, TaskStatus.FAILURE)

    def get(self, timeout: float = None, propagate: bool = True):
        """
        Wait for result.

        Note: Requires Dramatiq result backend to be configured.
        """
        if self._message:
            try:
                self._result = self._message.get_result(block=True, timeout=timeout)
                return self._result
            except Exception:
                if propagate:
                    raise
                return None
        return None
