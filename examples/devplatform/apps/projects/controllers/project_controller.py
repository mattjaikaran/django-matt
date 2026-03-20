from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from apps.organizations.controllers.utils import get_membership, require_admin
from apps.projects.models import Project
from apps.projects.schemas import ProjectCreateSchema, ProjectSchema, ProjectUpdateSchema


class ProjectController(APIController):
    prefix = "/organizations/{org_id}/projects"
    tags = ["Projects"]

    @staticmethod
    @jwt_required
    async def list_projects(request, org_id: str) -> dict:
        """List all projects in an organization."""
        await get_membership(request.user, org_id)

        projects = Project.objects.filter(
            organization_id=org_id,
            is_active=True,
        ).order_by("-created_at")

        items = []
        async for project in projects:
            items.append(
                ProjectSchema(
                    id=str(project.id),
                    organization_id=str(project.organization_id),
                    name=project.name,
                    slug=project.slug,
                    description=project.description,
                    environment=project.environment,
                    is_active=project.is_active,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_project(request, org_id: str, body: ProjectCreateSchema) -> dict:
        """Create a new project in an organization. Requires admin role."""
        await require_admin(request.user, org_id)

        if await Project.objects.filter(
            organization_id=org_id, slug=body.slug
        ).aexists():
            raise ValidationAPIError(
                "A project with this slug already exists in this organization"
            )

        project = await Project.objects.acreate(
            organization_id=org_id,
            name=body.name,
            slug=body.slug,
            description=body.description,
            environment=body.environment,
        )

        return ProjectSchema(
            id=str(project.id),
            organization_id=str(project.organization_id),
            name=project.name,
            slug=project.slug,
            description=project.description,
            environment=project.environment,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_project(request, org_id: str, project_id: str) -> dict:
        """Get a specific project."""
        await get_membership(request.user, org_id)

        project = await Project.objects.filter(
            id=project_id,
            organization_id=org_id,
        ).afirst()

        if not project:
            raise NotFoundAPIError("Project not found")

        return ProjectSchema(
            id=str(project.id),
            organization_id=str(project.organization_id),
            name=project.name,
            slug=project.slug,
            description=project.description,
            environment=project.environment,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_project(request, org_id: str, project_id: str, body: ProjectUpdateSchema) -> dict:
        """Update a project. Requires admin role."""
        await require_admin(request.user, org_id)

        project = await Project.objects.filter(
            id=project_id,
            organization_id=org_id,
        ).afirst()

        if not project:
            raise NotFoundAPIError("Project not found")

        updates = body.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(project, field, value)
        await project.asave()

        return ProjectSchema(
            id=str(project.id),
            organization_id=str(project.organization_id),
            name=project.name,
            slug=project.slug,
            description=project.description,
            environment=project.environment,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_project(request, org_id: str, project_id: str) -> dict:
        """Delete a project. Requires admin role."""
        await require_admin(request.user, org_id)

        project = await Project.objects.filter(
            id=project_id,
            organization_id=org_id,
        ).afirst()

        if not project:
            raise NotFoundAPIError("Project not found")

        await project.adelete()
        return {"message": "Project deleted"}
