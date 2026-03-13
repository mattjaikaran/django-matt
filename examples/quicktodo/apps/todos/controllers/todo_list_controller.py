from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError

from apps.organizations.controllers.utils import get_membership
from apps.todos.models import TodoList
from apps.todos.schemas import (
    TodoListCreateSchema,
    TodoListSchema,
    TodoListUpdateSchema,
)


class TodoListController(APIController):
    tags = ["Todo Lists"]

    @staticmethod
    @jwt_required
    async def list_todo_lists(request, org_id: str) -> list[dict]:
        await get_membership(request.user, org_id)

        qs = (
            TodoList.objects.filter(organization_id=org_id)
            .annotate(
                todo_count=Coalesce(Count("todos"), Value(0)),
                completed_count=Coalesce(
                    Count("todos", filter=Q(todos__status="done")), Value(0)
                ),
            )
            .order_by("-created_at")
        )

        result = []
        async for tl in qs:
            data = TodoListSchema(
                id=str(tl.id),
                name=tl.name,
                description=tl.description,
                created_by_id=tl.created_by_id,
                organization_id=str(tl.organization_id),
                created_at=tl.created_at,
                updated_at=tl.updated_at,
                todo_count=tl.todo_count,
                completed_count=tl.completed_count,
            )
            result.append(data.model_dump(mode="json"))
        return result

    @staticmethod
    @jwt_required
    async def create_todo_list(request, org_id: str) -> dict:
        await get_membership(request.user, org_id)
        body = request.json
        data = TodoListCreateSchema(**body)

        tl = await TodoList.objects.acreate(
            organization_id=org_id,
            name=data.name,
            description=data.description,
            created_by=request.user,
        )
        return TodoListSchema(
            id=str(tl.id),
            name=tl.name,
            description=tl.description,
            created_by_id=tl.created_by_id,
            organization_id=str(tl.organization_id),
            created_at=tl.created_at,
            updated_at=tl.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_todo_list(request, org_id: str, list_id: str) -> dict:
        await get_membership(request.user, org_id)
        try:
            tl = await (
                TodoList.objects.filter(organization_id=org_id)
                .annotate(
                    todo_count=Coalesce(Count("todos"), Value(0)),
                    completed_count=Coalesce(
                        Count("todos", filter=Q(todos__status="done")), Value(0)
                    ),
                )
                .aget(id=list_id)
            )
        except TodoList.DoesNotExist:
            raise APIError(status_code=404, message="Todo list not found")

        return TodoListSchema(
            id=str(tl.id),
            name=tl.name,
            description=tl.description,
            created_by_id=tl.created_by_id,
            organization_id=str(tl.organization_id),
            created_at=tl.created_at,
            updated_at=tl.updated_at,
            todo_count=tl.todo_count,
            completed_count=tl.completed_count,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_todo_list(request, org_id: str, list_id: str) -> dict:
        await get_membership(request.user, org_id)
        body = request.json
        data = TodoListUpdateSchema(**body)

        try:
            tl = await TodoList.objects.aget(id=list_id, organization_id=org_id)
        except TodoList.DoesNotExist:
            raise APIError(status_code=404, message="Todo list not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(tl, field, value)
        await tl.asave()

        return TodoListSchema(
            id=str(tl.id),
            name=tl.name,
            description=tl.description,
            created_by_id=tl.created_by_id,
            organization_id=str(tl.organization_id),
            created_at=tl.created_at,
            updated_at=tl.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_todo_list(request, org_id: str, list_id: str) -> dict:
        await get_membership(request.user, org_id)
        try:
            tl = await TodoList.objects.aget(id=list_id, organization_id=org_id)
        except TodoList.DoesNotExist:
            raise APIError(status_code=404, message="Todo list not found")
        await tl.adelete()
        return {"message": "Todo list deleted"}
