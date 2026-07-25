from django_matt import DjangoMattAPI

from apps.projects.schemas import ProjectSchema

from .project_controller import ProjectController


def register_project_routes(api: DjangoMattAPI) -> None:
    api.get("projects", tags=["Projects"])(ProjectController.list_projects)

    api.post("projects", response_model=ProjectSchema, status_code=201, tags=["Projects"])(
        ProjectController.create_project
    )

    api.get("projects/<str:slug>", response_model=ProjectSchema, tags=["Projects"])(
        ProjectController.get_project
    )

    api.patch("projects/<str:slug>", response_model=ProjectSchema, tags=["Projects"])(
        ProjectController.update_project
    )

    api.delete("projects/<str:slug>", tags=["Projects"])(ProjectController.delete_project)
