from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, ValidationAPIError

from apps.organizations.models import Membership, MembershipRole, Organization
from apps.organizations.schemas import (
    OrganizationCreateSchema,
    OrganizationSchema,
    OrganizationUpdateSchema,
    OrganizationWithRoleSchema,
)

from .utils import require_admin, require_owner


class OrganizationController(APIController):
    tags = ["Organizations"]

    @staticmethod
    @jwt_required
    async def list_organizations(request) -> list[dict]:
        memberships = Membership.objects.filter(user=request.user, is_active=True).select_related(
            "organization"
        )
        result = []
        async for m in memberships:
            org_data = OrganizationWithRoleSchema(
                id=str(m.organization.id),
                name=m.organization.name,
                slug=m.organization.slug,
                description=m.organization.description,
                created_at=m.organization.created_at,
                updated_at=m.organization.updated_at,
                role=m.role,
            )
            result.append(org_data.model_dump(mode="json"))
        return result

    @staticmethod
    @jwt_required
    async def create_organization(request, body: OrganizationCreateSchema) -> dict:
        if await Organization.objects.filter(slug=body.slug).aexists():
            raise ValidationAPIError("Organization slug already taken")

        org = await Organization.objects.acreate(
            name=body.name,
            slug=body.slug,
            description=body.description,
        )
        await Membership.objects.acreate(
            user=request.user,
            organization=org,
            role=MembershipRole.OWNER.value,
        )
        return OrganizationSchema.model_validate(org).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def get_organization(request, org_id: str) -> dict:
        try:
            org = await Organization.objects.aget(id=org_id)
        except Organization.DoesNotExist:
            raise APIError(status_code=404, message="Organization not found")
        return OrganizationSchema.model_validate(org).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_organization(request, org_id: str, body: OrganizationUpdateSchema) -> dict:
        await require_admin(request.user, org_id)

        try:
            org = await Organization.objects.aget(id=org_id)
        except Organization.DoesNotExist:
            raise APIError(status_code=404, message="Organization not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        await org.asave()
        return OrganizationSchema.model_validate(org).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_organization(request, org_id: str) -> dict:
        await require_owner(request.user, org_id)
        try:
            org = await Organization.objects.aget(id=org_id)
        except Organization.DoesNotExist:
            raise APIError(status_code=404, message="Organization not found")
        await org.adelete()
        return {"message": "Organization deleted"}
