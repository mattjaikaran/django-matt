from django_matt import DjangoMattAPI

from apps.todos.schemas import TodoListSchema, TodoSchema

from .todo_controller import TodoController
from .todo_list_controller import TodoListController


def register_todo_routes(api: DjangoMattAPI) -> None:
    # Todo Lists
    api.get(
        "organizations/<str:org_id>/lists",
        response_model=list[TodoListSchema],
        tags=["Todo Lists"],
    )(TodoListController.list_todo_lists)

    api.post(
        "organizations/<str:org_id>/lists",
        response_model=TodoListSchema,
        status_code=201,
        tags=["Todo Lists"],
    )(TodoListController.create_todo_list)

    api.get(
        "organizations/<str:org_id>/lists/<str:list_id>",
        response_model=TodoListSchema,
        tags=["Todo Lists"],
    )(TodoListController.get_todo_list)

    api.patch(
        "organizations/<str:org_id>/lists/<str:list_id>",
        response_model=TodoListSchema,
        tags=["Todo Lists"],
    )(TodoListController.update_todo_list)

    api.delete(
        "organizations/<str:org_id>/lists/<str:list_id>",
        tags=["Todo Lists"],
    )(TodoListController.delete_todo_list)

    # Todos
    api.get(
        "organizations/<str:org_id>/todos",
        tags=["Todos"],
    )(TodoController.list_todos)

    api.post(
        "organizations/<str:org_id>/todos",
        response_model=TodoSchema,
        status_code=201,
        tags=["Todos"],
    )(TodoController.create_todo)

    api.get(
        "organizations/<str:org_id>/todos/<str:todo_id>",
        response_model=TodoSchema,
        tags=["Todos"],
    )(TodoController.get_todo)

    api.patch(
        "organizations/<str:org_id>/todos/<str:todo_id>",
        response_model=TodoSchema,
        tags=["Todos"],
    )(TodoController.update_todo)

    api.delete(
        "organizations/<str:org_id>/todos/<str:todo_id>",
        tags=["Todos"],
    )(TodoController.delete_todo)
