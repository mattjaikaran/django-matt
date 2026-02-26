"""
Service layer for the todo app.

Keeps controllers thin by centralising all business logic here.
"""

from __future__ import annotations

from django_matt.services import CRUDService

from .models import Todo


class TodoService(CRUDService["Todo"]):
    """CRUD service for Todo items with domain-level helpers."""

    model = Todo

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def list_pending(self) -> list[Todo]:
        """Return all incomplete todo items ordered by creation date."""
        return [t async for t in self.get_queryset().filter(completed=False)]

    async def list_completed(self) -> list[Todo]:
        """Return all completed todo items ordered by creation date."""
        return [t async for t in self.get_queryset().filter(completed=True)]

    async def complete(self, pk) -> Todo:
        """Mark a todo item as completed."""
        return await self.update_fields(pk, completed=True)

    async def uncomplete(self, pk) -> Todo:
        """Revert a todo item to incomplete."""
        return await self.update_fields(pk, completed=False)
