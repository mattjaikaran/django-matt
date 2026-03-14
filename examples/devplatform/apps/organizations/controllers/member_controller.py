import orjson
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError

from apps.organizations.models import Membership
from apps.organizations.schemas import MembershipSchema, MembershipUpdateSchema

from .utils import get_membership, require_admin


class MemberController(APIController):
    tags = ["Members"]

    @staticmethod
    @jwt_required
    async def list_members(request, org_id: str) -> list[dict]:
        await get_membership(request.user, org_id)
        memberships = Membership.objects.filter(
            organization_id=org_id, is_active=True
        ).select_related("user")
        result = []
        async for m in memberships:
            result.append(
                MembershipSchema(
                    id=str(m.id),
                    role=m.role,
                    is_active=m.is_active,
                    created_at=m.created_at,
                    user=m.user,
                ).model_dump(mode="json")
            )
        return result

    @staticmethod
    @jwt_required
    async def update_member(request, org_id: str, member_id: str) -> dict:
        await require_admin(request.user, org_id)
        body = orjson.loads(request.body)
        data = MembershipUpdateSchema(**body)

        try:
            membership = await Membership.objects.select_related("user").aget(
                id=member_id, organization_id=org_id
            )
        except Membership.DoesNotExist:
            raise APIError(status_code=404, message="Member not found")

        if membership.is_owner:
            raise APIError(status_code=400, message="Cannot modify owner membership")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(membership, field, value)
        await membership.asave()

        return MembershipSchema(
            id=str(membership.id),
            role=membership.role,
            is_active=membership.is_active,
            created_at=membership.created_at,
            user=membership.user,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def remove_member(request, org_id: str, member_id: str) -> dict:
        await require_admin(request.user, org_id)
        try:
            membership = await Membership.objects.aget(
                id=member_id, organization_id=org_id
            )
        except Membership.DoesNotExist:
            raise APIError(status_code=404, message="Member not found")

        if membership.is_owner:
            raise APIError(status_code=400, message="Cannot remove the owner")

        await membership.adelete()
        return {"message": "Member removed"}
