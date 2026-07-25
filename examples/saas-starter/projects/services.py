"""
Service layer for the SaaS Starter projects app.

Encapsulates business logic for Project, Task, and Comment models,
keeping controllers as thin HTTP adapters.
"""

from __future__ import annotations

from django.utils import timezone
from django_matt.services import CRUDService, ValidationError

from core.models import Organization, User

from .models import Comment, Project, Task, TaskStatus

# =============================================================================
# Project Service
# =============================================================================


class ProjectService(CRUDService["Project"]):
    """Service for project CRUD and org/user scoping."""

    model = Project

    def get_queryset(self):
        return (
            super().get_queryset().select_related("organization", "owner").prefetch_related("teams")
        )

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_org(self, org: Organization) -> list[Project]:
        """Return all projects belonging to ``org``, newest first."""
        return [p async for p in self.get_queryset().filter(organization=org)]

    async def for_user(self, user: User) -> list[Project]:
        """
        Return all projects visible to ``user``.

        Includes projects the user owns, is explicitly a member of, or that
        are marked public within the user's organizations.
        """
        return [
            p
            async for p in self.get_queryset()
            .filter(
                organization__memberships__user=user,
                organization__memberships__is_active=True,
            )
            .distinct()
        ]


# =============================================================================
# Task Service
# =============================================================================


class TaskService(CRUDService["Task"]):
    """Service for task CRUD, assignment, and status management."""

    model = Task

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("project", "project__organization", "assignee", "reporter")
        )

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_project(self, project_id) -> list[Task]:
        """Return all tasks for a given project ordered by position."""
        return [
            t
            async for t in self.get_queryset()
            .filter(project_id=project_id)
            .order_by("status", "position", "-created_at")
        ]

    async def assign(self, pk, user: User | None) -> Task:
        """
        Assign (or un-assign) a task to ``user``.

        Pass ``user=None`` to clear the assignee.
        """
        task = await self.get(pk)
        task.assignee = user
        await task.asave(update_fields=["assignee", "updated_at"])
        self._log.info(
            "task pk=%s assigned to user %s",
            pk,
            user.pk if user else "nobody",
        )
        return task

    async def change_status(self, pk, status: str) -> Task:
        """
        Transition a task to ``status``.

        Stamps completed_at when moving to DONE and clears it on any
        other transition. Raises ValidationError for unknown status values.
        """
        if status not in TaskStatus.values:
            raise ValidationError(
                f"Invalid status '{status}'. Choose from: {', '.join(TaskStatus.values)}",
                field="status",
            )

        task = await self.get(pk)
        task.status = status

        if status == TaskStatus.DONE:
            task.completed_at = timezone.now()
        else:
            task.completed_at = None

        await task.asave(update_fields=["status", "completed_at", "updated_at"])
        self._log.info("task pk=%s status -> %s", pk, status)
        return task

    async def overdue(self) -> list[Task]:
        """
        Return all tasks that are past their due date and not yet done or
        cancelled.
        """
        today = timezone.now().date()
        return [
            t
            async for t in self.get_queryset()
            .filter(due_date__lt=today)
            .exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELLED])
            .order_by("due_date")
        ]


# =============================================================================
# Comment Service
# =============================================================================


class CommentService(CRUDService["Comment"]):
    """Service for task comment CRUD."""

    model = Comment

    def get_queryset(self):
        return super().get_queryset().select_related("task", "author", "parent")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_task(self, task_id) -> list[Comment]:
        """Return all top-level comments for a task in chronological order."""
        return [
            c
            async for c in self.get_queryset()
            .filter(task_id=task_id, parent__isnull=True)
            .order_by("created_at")
        ]
