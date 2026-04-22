"""
Dramatiq compatibility backend.

Allows using Dramatiq as the task backend while maintaining
the native task API.
"""

import asyncio
import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..types import TaskMeta, TaskResult, TaskState
from .base import BaseNativeBackend

if TYPE_CHECKING:
    from ..config import NativeTaskConfig
    from ..core import NativeTask


class DramatiqNativeBackend(BaseNativeBackend):
    """
    Dramatiq-based task backend.

    Wraps Dramatiq to provide the native task API while
    leveraging Dramatiq's simple, reliable task processing.
    """

    name = "dramatiq"

    def __init__(self, config: "NativeTaskConfig"):
        super().__init__(config)
        self._broker = None
        self._results: dict[str, TaskResult] = {}
        self._actors: dict[str, Any] = {}
        self._initialize_dramatiq()

    def _initialize_dramatiq(self) -> None:
        """Initialize Dramatiq broker."""
        try:
            import dramatiq
            from dramatiq.brokers.redis import RedisBroker

            broker_url = self.config.url or self.config.redis_url

            self._broker = RedisBroker(url=broker_url)
            dramatiq.set_broker(self._broker)

            # Set up result backend if configured
            if self.config.store_results:
                try:
                    from dramatiq.results import Results
                    from dramatiq.results.backends import RedisBackend

                    result_backend = RedisBackend(url=broker_url)
                    self._broker.add_middleware(Results(backend=result_backend))
                except ImportError:
                    pass

        except ImportError:
            raise ImportError(
                "Dramatiq is not installed. Install it with: uv add dramatiq[redis]"
            )

    def enqueue(
        self,
        task: "NativeTask",
        args: tuple,
        kwargs: dict,
        meta: TaskMeta,
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
    ) -> TaskResult:
        """Enqueue task using Dramatiq."""
        if self._broker is None:
            raise RuntimeError("Dramatiq broker not initialized")

        import dramatiq

        # Get or create actor for this task
        if task.name not in self._actors:

            @dramatiq.actor(
                queue_name=meta.queue,
                max_retries=task.options.max_retries,
                time_limit=task.options.timeout * 1000 if task.options.timeout else None,
            )
            def dramatiq_actor(*task_args, **task_kwargs):
                if task.bind:
                    if task.is_async:
                        loop = asyncio.new_event_loop()
                        try:
                            return loop.run_until_complete(task.func(task, *task_args, **task_kwargs))
                        finally:
                            loop.close()
                    return task.func(task, *task_args, **task_kwargs)
                else:
                    if task.is_async:
                        loop = asyncio.new_event_loop()
                        try:
                            return loop.run_until_complete(task.func(*task_args, **task_kwargs))
                        finally:
                            loop.close()
                    return task.func(*task_args, **task_kwargs)

            dramatiq_actor.actor_name = task.name
            self._actors[task.name] = dramatiq_actor

        actor = self._actors[task.name]

        # Calculate delay
        delay_ms = None
        if countdown:
            delay_ms = countdown * 1000
        elif eta:
            delay_seconds = (eta - datetime.now(UTC)).total_seconds()
            if delay_seconds > 0:
                delay_ms = int(delay_seconds * 1000)

        # Send message
        options = {}
        if delay_ms:
            options["delay"] = delay_ms

        message = actor.send_with_options(args=args, kwargs=kwargs, **options)

        meta.state = TaskState.QUEUED
        meta.queued_at = datetime.now(UTC)

        task_result = TaskResult(task_id=meta.task_id, meta=meta)
        task_result._dramatiq_message = message
        self._results[meta.task_id] = task_result

        return task_result

    def get_result(self, task_id: str) -> TaskResult | None:
        """Get task result from Dramatiq."""
        return self._results.get(task_id)

    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """Dramatiq doesn't support task revocation directly."""
        return False

    def get_queue_length(self, queue: str = "default") -> int:
        """Get Dramatiq queue length."""
        if self._broker is None:
            return 0

        try:
            # Dramatiq doesn't have a built-in way to check queue length
            # This would require accessing Redis directly
            return 0
        except Exception:
            return 0

    def purge_queue(self, queue: str = "default") -> int:
        """Purge Dramatiq queue."""
        if self._broker is None:
            return 0

        try:
            self._broker.flush(queue)
            return 0  # Dramatiq doesn't return count
        except Exception:
            return 0

    def health_check(self) -> dict[str, Any]:
        """Check Dramatiq backend health."""
        if self._broker is None:
            return {"healthy": False, "backend": self.name, "error": "Not initialized"}

        try:
            # Try to connect to Redis
            import redis

            broker_url = self.config.url or self.config.redis_url
            client = redis.from_url(broker_url)
            client.ping()

            return {
                "healthy": True,
                "backend": self.name,
                "broker": "redis",
                "url": broker_url,
            }
        except Exception as e:
            return {"healthy": False, "backend": self.name, "error": str(e)}
