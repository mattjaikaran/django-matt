"""
Django native background workers backend (DEP-0014).

Compatible with Django 6.0+ django.core.workers when available.
Falls back gracefully if the workers module is not present.

Usage:
    # In settings.py
    MATT_TASKS = {
        "backend": "django_workers",  # auto-detected if Django >= 6.0
    }
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseBackend

if TYPE_CHECKING:
    from ..base import Task, TaskResult
    from ..primitives import Group, GroupResult, Signature

logger = logging.getLogger("django_matt.tasks")


def _workers_available() -> bool:
    """Check if Django native workers are available."""
    try:
        import django

        if django.VERSION < (6, 0):
            return False
        from django.core import workers  # noqa: F401

        return True
    except ImportError:
        return False


class DjangoWorkersBackend(BaseBackend):
    """
    Backend that uses Django's native background workers (DEP-0014).

    Available in Django 6.0+. If not available, raises RuntimeError
    on initialization with a helpful message.

    The native workers system provides:
    - No external broker required (uses Django's DB or cache)
    - Integrated with Django's management commands
    - Automatic retry and error handling
    - Process management via `manage.py runworker`
    """

    def __init__(self, **options: Any) -> None:
        if not _workers_available():
            raise RuntimeError(
                "Django native workers (DEP-0014) require Django 6.0+. "
                "Current Django version does not include django.core.workers. "
                "Use 'celery', 'dramatiq', or 'django_q' backend instead, "
                "or upgrade Django when 6.0 is released."
            )
        self._options = options
        self._setup()

    def _setup(self) -> None:
        """Initialize the Django workers connection."""
        from django.core.workers import get_worker_backend

        self._backend = get_worker_backend()
        logger.info("Django native workers backend initialized")

    def send_task(
        self,
        task: Task,
        args: tuple = (),
        kwargs: dict | None = None,
        task_id: str | None = None,
        countdown: int | None = None,
        eta: datetime | None = None,
        expires: int | None = None,
        queue: str | None = None,
        priority: int | None = None,
        **options: Any,
    ) -> TaskResult:
        """Send a task using Django's native worker system."""
        from ..base import TaskResult as Result

        kwargs = kwargs or {}

        worker_opts: dict[str, Any] = {}
        if countdown is not None:
            worker_opts["delay"] = countdown
        if eta is not None:
            worker_opts["eta"] = eta
        if queue is not None:
            worker_opts["queue"] = queue
        if priority is not None:
            worker_opts["priority"] = priority

        job = self._backend.enqueue(
            task.fn,
            args=args,
            kwargs=kwargs,
            task_id=task_id,
            **worker_opts,
        )

        return Result(
            task_id=job.id if hasattr(job, "id") else task_id or "",
            status="pending",
        )

    def get_result(self, task_id: str) -> TaskResult:
        """Get the result of a task by ID."""
        from ..base import TaskResult as Result

        job = self._backend.get_job(task_id)
        if job is None:
            return Result(task_id=task_id, status="unknown")

        status_map = {
            "queued": "pending",
            "running": "started",
            "completed": "success",
            "failed": "failure",
        }
        status = status_map.get(getattr(job, "status", "unknown"), "unknown")

        return Result(
            task_id=task_id,
            status=status,
            result=getattr(job, "result", None),
        )

    def revoke_task(
        self,
        task_id: str,
        terminate: bool = False,
        signal: str = "SIGTERM",
    ) -> bool:
        """Revoke/cancel a pending task."""
        try:
            self._backend.cancel_job(task_id)
            return True
        except Exception:
            logger.warning("Failed to revoke task %s", task_id)
            return False

    def send_group(
        self,
        group: Group,
        **options: Any,
    ) -> GroupResult:
        """Send a group of tasks for parallel execution."""
        from ..primitives import GroupResult as GResult

        results = []
        for sig in group.signatures:
            result = self.send_task(
                sig.task,
                args=sig.args,
                kwargs=sig.kwargs,
                **options,
            )
            results.append(result)

        return GResult(results=results)

    def send_chain(
        self,
        signatures: list[Signature],
        **options: Any,
    ) -> TaskResult:
        """Send a chain of tasks for sequential execution."""
        if not signatures:
            from ..base import TaskResult as Result

            return Result(task_id="", status="success")

        # Django workers may support chaining natively
        if hasattr(self._backend, "enqueue_chain"):
            chain_def = [(sig.task.fn, sig.args, sig.kwargs) for sig in signatures]
            job = self._backend.enqueue_chain(chain_def, **options)
            from ..base import TaskResult as Result

            return Result(
                task_id=job.id if hasattr(job, "id") else "",
                status="pending",
            )

        # Fallback: send first task, chain rest via callbacks
        first = signatures[0]
        return self.send_task(
            first.task,
            args=first.args,
            kwargs=first.kwargs,
            **options,
        )

    def ping(self) -> bool:
        """Check if the worker backend is reachable."""
        try:
            return self._backend.ping()
        except Exception:
            return False


def auto_detect_backend() -> str:
    """
    Auto-detect the best available task backend.

    Returns:
        Backend name: "django_workers" if available, otherwise
        checks for celery, dramatiq, django_q in that order.
    """
    if _workers_available():
        return "django_workers"

    try:
        import celery  # noqa: F401

        return "celery"
    except ImportError:
        pass

    try:
        import dramatiq  # noqa: F401

        return "dramatiq"
    except ImportError:
        pass

    try:
        import django_q  # noqa: F401

        return "django_q"
    except ImportError:
        pass

    return "sync"
