from django_matt.core.errors import APIError

from apps.organizations.models import Membership


async def get_membership(user, org_id: str, require_active: bool = True) -> Membership:
    """Get user's membership in an organization."""
    try:
        membership = await Membership.objects.select_related("organization").aget(
            user=user, organization_id=org_id
        )
    except Membership.DoesNotExist:
        raise APIError(status_code=403, message="Not a member of this organization")

    if require_active and not membership.is_active:
        raise APIError(status_code=403, message="Membership is inactive")

    return membership


async def require_admin(user, org_id: str) -> Membership:
    """Require admin or owner role in the organization."""
    membership = await get_membership(user, org_id)
    if not membership.is_admin:
        raise APIError(status_code=403, message="Admin access required")
    return membership


async def require_owner(user, org_id: str) -> Membership:
    """Require owner role in the organization."""
    membership = await get_membership(user, org_id)
    if not membership.is_owner:
        raise APIError(status_code=403, message="Owner access required")
    return membership
