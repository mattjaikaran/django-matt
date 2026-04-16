"""
Multi-tenant API controllers.

Demonstrates:
- Tenant-scoped CRUD with interceptors
- Feature flag gating by plan
- Event bus for domain events
- Interceptor chains on controllers
"""

from uuid import UUID

from django.db.models import Count
from django.http import HttpRequest

from django_matt.core.controller import APIController
from django_matt.events.bus import EventBus
from django_matt.interceptors.decorators import intercept, intercept_controller

from api.interceptors import FeatureGateInterceptor, TenantInterceptor
from tenants.models import Membership, Organization, Project
from tenants.schemas import (
    CreateOrganizationInput,
    CreateProjectInput,
    MembershipSchema,
    OrganizationSchema,
    ProjectSchema,
)


event_bus = EventBus()


class OrganizationController(APIController):
    """Organization (tenant) management."""

    prefix = "/organizations"
    tags = ["Organizations"]

    async def list(self, request: HttpRequest) -> dict:
        """GET / — list all organizations."""
        orgs = [
            org
            async for org in Organization.objects.annotate(
                member_count=Count("memberships")
            ).all()
        ]
        return {
            "items": [OrganizationSchema.from_orm_fast(org).model_dump() for org in orgs],
            "total": len(orgs),
        }

    async def create(self, request: HttpRequest, body: CreateOrganizationInput) -> dict:
        """POST / — create a new organization."""
        org = await Organization.objects.acreate(**body.model_dump(exclude_unset=True))

        await event_bus.emit(
            "tenant.created",
            org_id=str(org.id),
            name=org.name,
            plan=org.plan,
        )

        return OrganizationSchema.from_orm_fast(org).model_dump()

    async def read(self, request: HttpRequest, org_id: UUID) -> dict:
        """GET /{org_id} — get organization details."""
        org = await Organization.objects.aget(id=org_id)
        schema = OrganizationSchema.from_orm_fast(org)
        schema.member_count = await org.memberships.acount()
        return schema.model_dump()


@intercept_controller(TenantInterceptor())
class ProjectController(APIController):
    """Tenant-scoped project management.

    All endpoints require X-Tenant-Slug header (enforced by TenantInterceptor).
    """

    prefix = "/projects"
    tags = ["Projects"]

    async def list(self, request: HttpRequest) -> dict:
        """GET / — list projects for the current tenant."""
        projects = [
            proj
            async for proj in Project.objects.filter(
                organization=request.tenant, is_archived=False
            )
        ]
        return {
            "items": [ProjectSchema.from_orm_fast(p).model_dump() for p in projects],
            "total": len(projects),
        }

    async def create(self, request: HttpRequest, body: CreateProjectInput) -> dict:
        """POST / — create a project in the current tenant."""
        project = await Project.objects.acreate(
            organization=request.tenant,
            **body.model_dump(exclude_unset=True),
        )

        await event_bus.emit(
            "project.created",
            org_id=str(request.tenant.id),
            project_id=str(project.id),
            name=project.name,
        )

        return ProjectSchema.from_orm_fast(project).model_dump()

    async def read(self, request: HttpRequest, project_id: UUID) -> dict:
        """GET /{project_id} — get project details."""
        project = await Project.objects.aget(
            id=project_id, organization=request.tenant
        )
        return ProjectSchema.from_orm_fast(project).model_dump()

    @intercept(FeatureGateInterceptor(required_plans=["pro", "enterprise"]))
    async def archive(self, request: HttpRequest, project_id: UUID) -> dict:
        """POST /{project_id}/archive — archive a project (Pro+ only)."""
        project = await Project.objects.aget(
            id=project_id, organization=request.tenant
        )
        project.is_archived = True
        await project.asave(update_fields=["is_archived", "updated_at"])
        return ProjectSchema.from_orm_fast(project).model_dump()
