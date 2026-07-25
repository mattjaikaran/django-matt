from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError

from apps.organizations.controllers.utils import get_membership
from apps.todos.models import Todo, TodoList
from apps.todos.schemas import TodoCreateSchema, TodoSchema, TodoUpdateSchema


class TodoController(APIController):
    tags = ["Todos"]

    @staticmethod
    @jwt_required
    async def list_todos(request, org_id: str) -> dict:
        """List todos with filtering and pagination."""
        await get_membership(request.user, org_id)

        qs = Todo.objects.filter(todo_list__organization_id=org_id).select_related("todo_list")

        # Filtering
        params = request.GET
        if status := params.get("status"):
            qs = qs.filter(status=status)
        if priority := params.get("priority"):
            qs = qs.filter(priority=priority)
        if list_id := params.get("list_id"):
            qs = qs.filter(todo_list_id=list_id)
        if assignee_id := params.get("assignee_id"):
            qs = qs.filter(assignee_id=assignee_id)
        if search := params.get("search"):
            qs = qs.filter(title__icontains=search)

        # Ordering
        ordering = params.get("ordering", "-created_at")
        allowed_orderings = {
            "created_at",
            "-created_at",
            "due_date",
            "-due_date",
            "priority",
            "-priority",
            "status",
            "-status",
            "title",
            "-title",
        }
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering)

        # Pagination
        total = await qs.acount()
        limit = min(int(params.get("limit", "20")), 100)
        offset = int(params.get("offset", "0"))
        qs = qs[offset : offset + limit]

        items = []
        async for todo in qs:
            items.append(
                TodoSchema(
                    id=str(todo.id),
                    title=todo.title,
                    description=todo.description,
                    status=todo.status,
                    priority=todo.priority,
                    assignee_id=todo.assignee_id,
                    todo_list_id=str(todo.todo_list_id),
                    due_date=todo.due_date,
                    completed_at=todo.completed_at,
                    created_at=todo.created_at,
                    updated_at=todo.updated_at,
                ).model_dump(mode="json")
            )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    @jwt_required
    async def create_todo(request, org_id: str, body: TodoCreateSchema) -> dict:
        await get_membership(request.user, org_id)

        # Validate list belongs to org
        list_id = body.todo_list_id
        if list_id:
            if not await TodoList.objects.filter(id=list_id, organization_id=org_id).aexists():
                raise APIError(status_code=404, message="Todo list not found in this organization")
        else:
            # Get or create a default list
            default_list, _ = await TodoList.objects.aget_or_create(
                organization_id=org_id,
                name="Default",
                defaults={"created_by": request.user},
            )
            list_id = str(default_list.id)

        todo = await Todo.objects.acreate(
            todo_list_id=list_id,
            title=body.title,
            description=body.description,
            status=body.status,
            priority=body.priority,
            assignee_id=body.assignee_id,
            due_date=body.due_date,
        )
        return TodoSchema(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            status=todo.status,
            priority=todo.priority,
            assignee_id=todo.assignee_id,
            todo_list_id=str(todo.todo_list_id),
            due_date=todo.due_date,
            completed_at=todo.completed_at,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_todo(request, org_id: str, todo_id: str) -> dict:
        await get_membership(request.user, org_id)
        try:
            todo = await Todo.objects.select_related("todo_list").aget(
                id=todo_id, todo_list__organization_id=org_id
            )
        except Todo.DoesNotExist:
            raise APIError(status_code=404, message="Todo not found")

        return TodoSchema(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            status=todo.status,
            priority=todo.priority,
            assignee_id=todo.assignee_id,
            todo_list_id=str(todo.todo_list_id),
            due_date=todo.due_date,
            completed_at=todo.completed_at,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_todo(request, org_id: str, todo_id: str, body: TodoUpdateSchema) -> dict:
        await get_membership(request.user, org_id)

        try:
            todo = await Todo.objects.aget(id=todo_id, todo_list__organization_id=org_id)
        except Todo.DoesNotExist:
            raise APIError(status_code=404, message="Todo not found")

        updates = body.model_dump(exclude_unset=True)

        # Auto-set completed_at when status changes to done
        if updates.get("status") == "done" and todo.status != "done":
            updates["completed_at"] = timezone.now()
        elif updates.get("status") and updates["status"] != "done":
            updates["completed_at"] = None

        for field, value in updates.items():
            setattr(todo, field, value)
        await todo.asave()

        return TodoSchema(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            status=todo.status,
            priority=todo.priority,
            assignee_id=todo.assignee_id,
            todo_list_id=str(todo.todo_list_id),
            due_date=todo.due_date,
            completed_at=todo.completed_at,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_todo(request, org_id: str, todo_id: str) -> dict:
        await get_membership(request.user, org_id)
        try:
            todo = await Todo.objects.aget(id=todo_id, todo_list__organization_id=org_id)
        except Todo.DoesNotExist:
            raise APIError(status_code=404, message="Todo not found")
        await todo.adelete()
        return {"message": "Todo deleted"}
