"""
Custom admin filters for task models.
"""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from ..types import TaskState


class StateFilter(admin.SimpleListFilter):
    """Filter by task state."""

    title = "state"
    parameter_name = "state"

    def lookups(self, request: HttpRequest, model_admin) -> list[tuple[str, str]]:
        return [(s.value, s.name.title()) for s in TaskState]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value():
            return queryset.filter(state=self.value())
        return queryset


class QueueFilter(admin.SimpleListFilter):
    """Filter by queue name."""

    title = "queue"
    parameter_name = "queue"

    def lookups(self, request: HttpRequest, model_admin) -> list[tuple[str, str]]:
        from ..models import TaskExecution

        queues = (
            TaskExecution.objects.values_list("queue", flat=True)
            .distinct()
            .order_by("queue")
        )
        return [(q, q) for q in queues]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value():
            return queryset.filter(queue=self.value())
        return queryset


class TaskNameFilter(admin.SimpleListFilter):
    """Filter by task name."""

    title = "task"
    parameter_name = "task_name"

    def lookups(self, request: HttpRequest, model_admin) -> list[tuple[str, str]]:
        from ..models import TaskExecution

        task_names = (
            TaskExecution.objects.values_list("task_name", flat=True)
            .distinct()
            .order_by("task_name")[:50]
        )
        return [(name, self._shorten_name(name)) for name in task_names]

    def _shorten_name(self, name: str) -> str:
        """Shorten task name for display."""
        parts = name.split(".")
        if len(parts) > 2:
            return f"...{'.'.join(parts[-2:])}"
        return name

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value():
            return queryset.filter(task_name=self.value())
        return queryset
