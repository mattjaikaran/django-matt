"""Project controller — public read, admin write."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError
from django_matt.core.router import delete, get, patch, post

from {{ project_name }}_app.projects.models import Project
from {{ project_name }}_app.projects.schemas import (
    ProjectCreateSchema,
    ProjectDetailSchema,
    ProjectSchema,
    ProjectUpdateSchema,
)


class ProjectController(APIController):
    prefix = "/projects"
    tags = ["Projects"]

    @get("/")
    async def list_projects(self, featured: bool | None = None) -> list[ProjectSchema]:
        qs = Project.objects.filter(is_published=True).order_by("order", "-created_at")
        if featured is not None:
            qs = qs.filter(featured=featured)
        return [ProjectSchema.model_validate(p) async for p in qs]

    @get("/{slug}")
    async def get_project(self, slug: str) -> ProjectDetailSchema:
        project = await Project.objects.filter(slug=slug, is_published=True).afirst()
        if project is None:
            raise NotFoundAPIError(f"Project '{slug}' not found.")
        return ProjectDetailSchema.model_validate(project)

    @post("/")
    @jwt_required
    async def create_project(self, request, body: ProjectCreateSchema) -> ProjectDetailSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create projects.")
        project = await Project.objects.acreate(**body.model_dump())
        return ProjectDetailSchema.model_validate(project)

    @patch("/{slug}")
    @jwt_required
    async def update_project(
        self, request, slug: str, body: ProjectUpdateSchema
    ) -> ProjectDetailSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can update projects.")
        project = await Project.objects.filter(slug=slug).afirst()
        if project is None:
            raise NotFoundAPIError(f"Project '{slug}' not found.")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        await project.asave()
        return ProjectDetailSchema.model_validate(project)

    @delete("/{slug}")
    @jwt_required
    async def delete_project(self, request, slug: str) -> dict:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can delete projects.")
        project = await Project.objects.filter(slug=slug).afirst()
        if project is None:
            raise NotFoundAPIError(f"Project '{slug}' not found.")
        await project.adelete()
        return {"deleted": True}
