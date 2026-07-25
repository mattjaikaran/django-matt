"""
Django-Q2 compatibility backend.

Allows using Django-Q2 as the task backend while maintaining
the native task API.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..types import TaskMeta, TaskResult, TaskState
from .base import BaseNativeBackend

if TYPE_CHECKING:
    from ..config import NativeTaskConfig
    from ..core import NativeTask


class DjangoQNativeBackend(BaseNativeBackend):
    """
    Django-Q2-based task backend.

    Wraps Django-Q2 to provide the native task API while
    leveraging Django-Q2's Django-native task processing.
    """

    name = "django_q"

    def __init__(self, config: "NativeTaskConfig"):
        super().__init__(config)
        self._results: dict[str, TaskResult] = {}
        self._verify_django_q()

    def _verify_django_q(self) -> None:
        """Verify Django-Q2 is installed and configured."""
        try:
            from django_q.tasks import async_task  # noqa: F401
        except ImportError:
            raise ImportError("Django-Q2 is not installed. Install it with: uv add django-q2")

    def _create_task_wrapper(self, task: "NativeTask"):
        """Create a wrapper function for Django-Q2."""

        def wrapper(*args, **kwargs):
            if task.bind:
                if task.is_async:
                    loop = asyncio.new_event_loop()
                    try:
                        return loop.run_until_complete(task.func(task, *args, **kwargs))
                    finally:
                        loop.close()
                return task.func(task, *args, **kwargs)
            if task.is_async:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(task.func(*args, **kwargs))
                finally:
                    loop.close()
            return task.func(*args, **kwargs)

        wrapper.__name__ = task.name
        wrapper.__module__ = task.func.__module__
        return wrapper

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
        """Enqueue task using Django-Q2."""
        from django_q.tasks import async_task

        wrapper = self._create_task_wrapper(task)

        # Prepare Django-Q options
        q_options = {
            "task_name": task.name,
            "group": meta.queue,
        }

        if task.options.timeout:
            q_options["timeout"] = task.options.timeout

        # Handle scheduling
        if eta:
            from django_q.models import Schedule

            Schedule.objects.create(
                name=meta.task_id,
                func=f"{wrapper.__module__}.{wrapper.__name__}",
                args=str(args),
                kwargs=str(kwargs),
                schedule_type=Schedule.ONCE,
                next_run=eta,
            )
            task_id = meta.task_id
        # Immediate execution (with optional countdown)
        elif countdown:
            from datetime import timedelta

            from django_q.models import Schedule

            Schedule.objects.create(
                name=meta.task_id,
                func=f"{wrapper.__module__}.{wrapper.__name__}",
                args=str(args),
                kwargs=str(kwargs),
                schedule_type=Schedule.ONCE,
                next_run=datetime.now(UTC) + timedelta(seconds=countdown),
            )
            task_id = meta.task_id
        else:
            task_id = async_task(wrapper, *args, **kwargs, **q_options)

        meta.state = TaskState.QUEUED
        meta.queued_at = datetime.now(UTC)
        meta.task_id = str(task_id)

        task_result = TaskResult(task_id=meta.task_id, meta=meta)
        self._results[meta.task_id] = task_result

        return task_result

    def get_result(self, task_id: str) -> TaskResult | None:
        """Get task result from Django-Q2."""
        task_result = self._results.get(task_id)

        if task_result:
            try:
                from django_q.tasks import result

                q_result = result(task_id)
                if q_result is not None:
                    task_result.meta.state = TaskState.COMPLETED
                    task_result.meta.result = q_result
                    task_result.meta.completed_at = datetime.now(UTC)
            except Exception:
                pass

        return task_result

    def revoke(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a Django-Q2 task."""
        try:
            from django_q.models import OrmQ

            OrmQ.objects.filter(id=task_id).delete()

            if task_id in self._results:
                self._results[task_id].meta.state = TaskState.CANCELLED

            return True
        except Exception:
            return False

    def get_queue_length(self, queue: str = "default") -> int:
        """Get Django-Q2 queue length."""
        try:
            from django_q.models import OrmQ

            return OrmQ.objects.filter(lock__isnull=True).count()
        except Exception:
            return 0

    def purge_queue(self, queue: str = "default") -> int:
        """Purge Django-Q2 queue."""
        try:
            from django_q.models import OrmQ

            count = OrmQ.objects.filter(lock__isnull=True).count()
            OrmQ.objects.filter(lock__isnull=True).delete()
            return count
        except Exception:
            return 0

    def health_check(self) -> dict[str, Any]:
        """Check Django-Q2 backend health."""
        try:
            from django_q.brokers import get_broker
            from django_q.conf import Conf

            broker = get_broker()
            info = broker.info()

            return {
                "healthy": True,
                "backend": self.name,
                "broker_type": Conf.ORM if hasattr(Conf, "ORM") else "default",
                "info": info,
            }
        except Exception as e:
            return {"healthy": False, "backend": self.name, "error": str(e)}
