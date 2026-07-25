from django_matt import DjangoMattAPI

from apps.projects.schemas import ProjectSchema

from .project_controller import ProjectController


def register_project_routes(api: DjangoMattAPI) -> None:
    api.get(
        "organizations/<str:org_id>/projects",
        tags=["Projects"],
    )(ProjectController.list_projects)

    api.post(
        "organizations/<str:org_id>/projects",
        response_model=ProjectSchema,
        status_code=201,
        tags=["Projects"],
    )(ProjectController.create_project)

    api.get(
        "organizations/<str:org_id>/projects/<str:project_id>",
        response_model=ProjectSchema,
        tags=["Projects"],
    )(ProjectController.get_project)

    api.patch(
        "organizations/<str:org_id>/projects/<str:project_id>",
        response_model=ProjectSchema,
        tags=["Projects"],
    )(ProjectController.update_project)

    api.delete(
        "organizations/<str:org_id>/projects/<str:project_id>",
        tags=["Projects"],
    )(ProjectController.delete_project)
