from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from apps.projects.models import Project
from apps.projects.schemas import ProjectCreateSchema, ProjectSchema, ProjectUpdateSchema


def _serialize(project: Project) -> dict:
    return ProjectSchema(
        id=str(project.id),
        title=project.title,
        slug=project.slug,
        description=project.description,
        long_description=project.long_description,
        tech_stack=project.tech_stack,
        image_url=project.image_url,
        live_url=project.live_url,
        github_url=project.github_url,
        featured=project.featured,
        order=project.order,
        is_published=project.is_published,
        created_at=project.created_at,
        updated_at=project.updated_at,
    ).model_dump(mode="json")


class ProjectController(APIController):
    tags = ["Projects"]

    @staticmethod
    async def list_projects(request) -> dict:
        params = request.GET
        qs = Project.objects.filter(is_published=True)

        if featured := params.get("featured"):
            qs = qs.filter(featured=featured.lower() in ("true", "1", "yes"))

        items = []
        async for project in qs:
            items.append(_serialize(project))

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_project(request, body: ProjectCreateSchema) -> dict:
        if await Project.objects.filter(slug=body.slug).aexists():
            raise ValidationAPIError("A project with this slug already exists")

        project = await Project.objects.acreate(
            title=body.title,
            slug=body.slug,
            description=body.description,
            long_description=body.long_description,
            tech_stack=body.tech_stack,
            image_url=body.image_url,
            live_url=body.live_url,
            github_url=body.github_url,
            featured=body.featured,
            order=body.order,
            is_published=body.is_published,
        )
        return _serialize(project)

    @staticmethod
    async def get_project(request, slug: str) -> dict:
        project = await Project.objects.filter(slug=slug).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")
        return _serialize(project)

    @staticmethod
    @jwt_required
    async def update_project(request, slug: str, body: ProjectUpdateSchema) -> dict:
        project = await Project.objects.filter(slug=slug).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")

        updates = body.model_dump(exclude_unset=True)

        if "slug" in updates and updates["slug"] != project.slug:
            if await Project.objects.filter(slug=updates["slug"]).exclude(id=project.id).aexists():
                raise ValidationAPIError("A project with this slug already exists")

        for field, value in updates.items():
            setattr(project, field, value)
        await project.asave()
        return _serialize(project)

    @staticmethod
    @jwt_required
    async def delete_project(request, slug: str) -> dict:
        project = await Project.objects.filter(slug=slug).afirst()
        if not project:
            raise NotFoundAPIError("Project not found")
        await project.adelete()
        return {"message": "Project deleted"}
