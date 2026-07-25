# file-length-max: 950
"""
Controllers for multi-tenancy endpoints.

Provides API endpoints for managing organizations, teams, memberships, and invitations.
All methods are async to avoid blocking the ASGI event loop.
"""

import uuid

from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse

from asgiref.sync import sync_to_async

from django_matt.core.controller import APIController
from django_matt.core.errors import APIError, NotFoundAPIError
from django_matt.multitenancy.models import (
    Invitation,
    InvitationStatus,
    Membership,
    MembershipRole,
    Organization,
    Team,
    TeamMembership,
)
from django_matt.multitenancy.schemas import (
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationResponse,
    MemberResponse,
    MembershipResponse,
    MembershipUpdate,
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
    SwitchOrganizationRequest,
    TeamCreate,
    TeamListResponse,
    TeamResponse,
    TeamUpdate,
    TenantContext,
)
from django_matt.multitenancy.utils import (
    acreate_organization_with_owner,
    auser_can_manage_team,
    auser_is_org_admin,
)


class ForbiddenError(APIError):
    """Error for forbidden operations."""

    status_code = 403
    code = "forbidden"


class ConflictError(APIError):
    """Error for conflict operations (e.g., duplicate)."""

    status_code = 409
    code = "conflict"


class OrganizationController(APIController):
    """
    Controller for organization management endpoints.

    Endpoints:
        GET /organizations - List user's organizations
        POST /organizations - Create new organization
        GET /organizations/{id} - Get organization details
        PUT /organizations/{id} - Update organization
        DELETE /organizations/{id} - Delete organization
        POST /organizations/{id}/switch - Switch to organization
    """

    prefix = "organizations"
    tags = ["Organizations"]

    async def list(self, request: HttpRequest) -> list[OrganizationListResponse]:
        """List all organizations the user is a member of."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        results = []
        async for membership in Membership.objects.filter(
            user=request.user,
            organization__is_active=True,
        ).select_related("organization"):
            org = membership.organization
            results.append(
                OrganizationListResponse(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    description=org.description,
                    logo_url=org.logo_url,
                    role=membership.role,
                    is_active=org.is_active,
                )
            )

        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)

    async def create(self, request: HttpRequest, data: OrganizationCreate) -> OrganizationResponse:
        """Create a new organization with the current user as owner."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            organization = await acreate_organization_with_owner(
                name=data.name,
                slug=data.slug,
                owner=request.user,
                description=data.description,
                logo_url=data.logo_url,
                settings=data.settings,
            )
        except IntegrityError:
            raise ConflictError(f"Organization with slug '{data.slug}' already exists")

        return JsonResponse(
            OrganizationResponse.model_validate(organization).model_dump(mode="json"),
            status=201,
        )

    async def retrieve(self, request: HttpRequest, id: str) -> OrganizationResponse:
        """Get organization details (only if user is a member)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            org_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        # Org-scoped query: only retrieve if user has membership (avoids timing leak)
        membership = (
            await Membership.objects.filter(
                user=request.user,
                organization_id=org_id,
                organization__is_active=True,
            )
            .select_related("organization")
            .afirst()
        )

        if not membership:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        organization = membership.organization
        return JsonResponse(
            OrganizationResponse.model_validate(organization).model_dump(mode="json")
        )

    async def update(
        self,
        request: HttpRequest,
        id: str,
        data: OrganizationUpdate,
    ) -> OrganizationResponse:
        """Update an organization (admin/owner only)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            org_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        # Org-scoped query with membership check
        membership = (
            await Membership.objects.filter(
                user=request.user,
                organization_id=org_id,
                role__in=[MembershipRole.ADMIN.value, MembershipRole.OWNER.value],
            )
            .select_related("organization")
            .afirst()
        )

        if not membership:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        organization = membership.organization

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(organization, field, value)

        try:
            await organization.asave()
        except IntegrityError:
            raise ConflictError(f"Organization with slug '{data.slug}' already exists")

        return JsonResponse(
            OrganizationResponse.model_validate(organization).model_dump(mode="json")
        )

    async def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Delete an organization (owner only)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            org_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        # Org-scoped query: only owners can delete
        membership = (
            await Membership.objects.filter(
                user=request.user,
                organization_id=org_id,
                role=MembershipRole.OWNER.value,
            )
            .select_related("organization")
            .afirst()
        )

        if not membership:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        await membership.organization.adelete()
        return JsonResponse({"message": "Organization deleted"}, status=200)

    async def switch(
        self,
        request: HttpRequest,
        data: SwitchOrganizationRequest,
    ) -> TenantContext:
        """Switch to a different organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = None

        if data.organization_id:
            organization = await Organization.objects.filter(
                id=data.organization_id,
                is_active=True,
            ).afirst()
        elif data.organization_slug:
            organization = await Organization.objects.filter(
                slug=data.organization_slug,
                is_active=True,
            ).afirst()

        if not organization:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=str(data.organization_id or data.organization_slug),
            )

        # Check if user is a member (org-scoped)
        membership = await Membership.objects.filter(
            organization=organization,
            user=request.user,
        ).afirst()

        if not membership:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        # Store in session
        if hasattr(request, "session"):
            request.session["current_organization_id"] = str(organization.id)

        return JsonResponse(
            TenantContext(
                organization_id=organization.id,
                organization_slug=organization.slug,
                organization_name=organization.name,
                user_role=membership.role,
            ).model_dump(mode="json")
        )


class TeamController(APIController):
    """
    Controller for team management endpoints.

    Endpoints:
        GET /teams - List teams in current organization
        POST /teams - Create new team
        GET /teams/{id} - Get team details
        PUT /teams/{id} - Update team
        DELETE /teams/{id} - Delete team
    """

    prefix = "teams"
    tags = ["Teams"]

    async def list(self, request: HttpRequest) -> list[TeamListResponse]:
        """List all teams in the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)

        results = []
        async for team in Team.objects.filter(organization=organization):
            # Get user's role in team if member
            team_membership = await TeamMembership.objects.filter(
                team=team,
                user=request.user,
            ).afirst()

            member_count = await team.memberships.acount()

            results.append(
                TeamListResponse(
                    id=team.id,
                    name=team.name,
                    slug=team.slug,
                    description=team.description,
                    role=team_membership.role if team_membership else None,
                    is_default=team.is_default,
                    member_count=member_count,
                )
            )

        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)

    async def create(self, request: HttpRequest, data: TeamCreate) -> TeamResponse:
        """Create a new team in the organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        if data.organization_id:
            # Org-scoped: verify user is member before using requested org
            membership = await Membership.objects.filter(
                user=request.user,
                organization_id=data.organization_id,
            ).afirst()
            if not membership:
                return JsonResponse({"detail": "Forbidden"}, status=403)
            organization = await Organization.objects.filter(id=data.organization_id).afirst()

        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)

        # Check if user is admin
        if not await auser_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can create teams")

        try:
            team = await Team.objects.acreate(
                organization=organization,
                name=data.name,
                slug=data.slug,
                description=data.description,
                settings=data.settings,
                is_default=data.is_default,
            )
        except IntegrityError:
            raise ConflictError(f"Team with slug '{data.slug}' already exists in this organization")

        return JsonResponse(
            TeamResponse.model_validate(team).model_dump(mode="json"),
            status=201,
        )

    async def retrieve(self, request: HttpRequest, id: str) -> TeamResponse:
        """Get team details (org-scoped: 403 if outside user's org)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            team_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped lookup: returns 403 for cross-org access (explicit denial)
            team = (
                await Team.objects.filter(
                    organization=organization,
                    id=team_id,
                )
                .select_related("organization")
                .afirst()
            )
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            # No org context: still check membership
            team = await Team.objects.filter(id=team_id).select_related("organization").afirst()
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)
            is_member = await Membership.objects.filter(
                organization=team.organization,
                user=request.user,
            ).aexists()
            if not is_member:
                return JsonResponse({"detail": "Forbidden"}, status=403)

        return JsonResponse(TeamResponse.model_validate(team).model_dump(mode="json"))

    async def update(
        self,
        request: HttpRequest,
        id: str,
        data: TeamUpdate,
    ) -> TeamResponse:
        """Update a team (org-scoped, admin/team-lead only)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            team_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped lookup: 403 for cross-org (explicit denial per user decision)
            team = (
                await Team.objects.filter(
                    organization=organization,
                    id=team_id,
                )
                .select_related("organization")
                .afirst()
            )
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            team = await Team.objects.filter(id=team_id).select_related("organization").afirst()
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)

        # Check if user can manage team
        if not await auser_can_manage_team(request.user, team):
            raise ForbiddenError("You don't have permission to update this team")

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(team, field, value)

        try:
            await team.asave()
        except IntegrityError:
            raise ConflictError(f"Team with slug '{data.slug}' already exists in this organization")

        return JsonResponse(TeamResponse.model_validate(team).model_dump(mode="json"))

    async def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Delete a team (org admin only, org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            team_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped: 403 for cross-org (explicit denial)
            team = (
                await Team.objects.filter(
                    organization=organization,
                    id=team_id,
                )
                .select_related("organization")
                .afirst()
            )
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            team = await Team.objects.filter(id=team_id).select_related("organization").afirst()
            if not team:
                return JsonResponse({"detail": "Forbidden"}, status=403)

        # Check if user is org admin
        if not await auser_is_org_admin(request.user, team.organization):
            raise ForbiddenError("Only organization admins can delete teams")

        await team.adelete()
        return JsonResponse({"message": "Team deleted"}, status=200)


class MembershipController(APIController):
    """
    Controller for membership management endpoints.

    Endpoints:
        GET /members - List members in current organization
        POST /members - Add member to organization
        GET /members/{id} - Get member details
        PUT /members/{id} - Update member role
        DELETE /members/{id} - Remove member from organization
    """

    prefix = "members"
    tags = ["Members"]

    async def list(self, request: HttpRequest) -> list[MemberResponse]:
        """List all members of the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)

        results = []
        async for membership in Membership.objects.filter(
            organization=organization,
        ).select_related("user"):
            user = membership.user
            results.append(
                MemberResponse(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    username=getattr(user, "username", None),
                    first_name=getattr(user, "first_name", None),
                    last_name=getattr(user, "last_name", None),
                    role=membership.role,
                    joined_at=membership.joined_at,
                )
            )

        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)

    async def update(
        self,
        request: HttpRequest,
        id: str,
        data: MembershipUpdate,
    ) -> MembershipResponse:
        """Update a member's role (org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            membership_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped: only see memberships within request.organization
            membership = (
                await Membership.objects.filter(
                    id=membership_id,
                    organization=organization,
                )
                .select_related("organization", "user")
                .afirst()
            )
            if not membership:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            membership = await (
                Membership.objects.filter(id=membership_id)
                .select_related("organization", "user")
                .afirst()
            )
            if not membership:
                raise NotFoundAPIError(
                    message="Membership not found",
                    resource_type="Membership",
                    resource_id=id,
                )

        # Check if user is admin in the membership's org
        if not await auser_is_org_admin(request.user, membership.organization):
            raise ForbiddenError("Only admins can update member roles")

        # Get actor's membership
        actor_membership = await Membership.objects.filter(
            organization=membership.organization,
            user=request.user,
        ).afirst()

        # Check role hierarchy
        if not MembershipRole.can_manage(actor_membership.role, membership.role):
            raise ForbiddenError("Cannot modify a member with higher or equal role")

        if not MembershipRole.can_manage(actor_membership.role, data.role):
            raise ForbiddenError("Cannot assign a role higher than or equal to your own")

        membership.role = data.role
        await membership.asave(update_fields=["role", "updated_at"])

        return JsonResponse(MembershipResponse.model_validate(membership).model_dump(mode="json"))

    async def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Remove a member from the organization (org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            membership_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped: only see memberships within request.organization
            membership = (
                await Membership.objects.filter(
                    id=membership_id,
                    organization=organization,
                )
                .select_related("organization", "user")
                .afirst()
            )
            if not membership:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            membership = await (
                Membership.objects.filter(id=membership_id)
                .select_related("organization", "user")
                .afirst()
            )
            if not membership:
                raise NotFoundAPIError(
                    message="Membership not found",
                    resource_type="Membership",
                    resource_id=id,
                )

        # Check if user is admin
        if not await auser_is_org_admin(request.user, membership.organization):
            raise ForbiddenError("Only admins can remove members")

        # Get actor's membership
        actor_membership = await Membership.objects.filter(
            organization=membership.organization,
            user=request.user,
        ).afirst()

        # Can't remove yourself if you're the only owner
        if membership.user_id == request.user.pk:
            if membership.role == MembershipRole.OWNER.value:
                owner_count = await Membership.objects.filter(
                    organization=membership.organization,
                    role=MembershipRole.OWNER.value,
                ).acount()
                if owner_count <= 1:
                    raise ForbiddenError("Cannot remove the only owner. Transfer ownership first.")
        # Check role hierarchy
        elif not MembershipRole.can_manage(actor_membership.role, membership.role):
            raise ForbiddenError("Cannot remove a member with higher or equal role")

        await membership.adelete()
        return JsonResponse({"message": "Member removed"}, status=200)


class InvitationController(APIController):
    """
    Controller for invitation management endpoints.

    Endpoints:
        GET /invitations - List invitations for current organization
        POST /invitations - Create new invitation
        GET /invitations/{token}/accept - Accept invitation (public)
        DELETE /invitations/{id} - Revoke invitation
        POST /invitations/{id}/resend - Resend invitation
    """

    prefix = "invitations"
    tags = ["Invitations"]

    async def list(self, request: HttpRequest) -> list[InvitationResponse]:
        """List all invitations for the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)

        # Check if user is admin
        if not await auser_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can view invitations")

        results = [
            InvitationResponse.model_validate(inv).model_dump(mode="json")
            async for inv in Invitation.objects.filter(organization=organization)
        ]

        return JsonResponse(results, safe=False)

    async def create(self, request: HttpRequest, data: InvitationCreate) -> InvitationResponse:
        """Create a new invitation (org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        if data.organization_id:
            # Org-scoped: verify user is member before using requested org
            membership = await Membership.objects.filter(
                user=request.user,
                organization_id=data.organization_id,
            ).afirst()
            if not membership:
                return JsonResponse({"detail": "Forbidden"}, status=403)
            organization = await Organization.objects.filter(id=data.organization_id).afirst()

        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)

        # Check if user is admin
        if not await auser_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can send invitations")

        # Check if email is already a member
        from django.contrib.auth import get_user_model

        User = get_user_model()

        existing_user = await User.objects.filter(email=data.email).afirst()
        if existing_user:
            is_member = await Membership.objects.filter(
                organization=organization,
                user=existing_user,
            ).aexists()
            if is_member:
                raise ConflictError("User is already a member of this organization")

        # Check for pending invitation
        existing_invitation = await Invitation.objects.filter(
            organization=organization,
            email=data.email,
            status=InvitationStatus.PENDING.value,
        ).afirst()

        if existing_invitation:
            raise ConflictError("An invitation is already pending for this email")

        # Get team if specified (org-scoped)
        team = None
        if data.team_id:
            team = await Team.objects.filter(
                id=data.team_id,
                organization=organization,
            ).afirst()
            if not team:
                raise NotFoundAPIError(
                    message="Team not found",
                    resource_type="Team",
                    resource_id=str(data.team_id),
                )

        invitation = await Invitation.objects.acreate(
            organization=organization,
            team=team,
            email=data.email,
            role=data.role,
            invited_by=request.user,
        )

        # Send invitation email (sync function — wrap for async context)
        from django_matt.multitenancy.emails import send_invitation_email

        await sync_to_async(send_invitation_email)(invitation)

        return JsonResponse(
            InvitationResponse.model_validate(invitation).model_dump(mode="json"),
            status=201,
        )

    async def accept(self, request: HttpRequest, data: InvitationAcceptRequest) -> JsonResponse:
        """Accept an invitation."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        invitation = await (
            Invitation.objects.filter(
                token=data.token,
            )
            .select_related("organization", "team")
            .afirst()
        )

        if not invitation:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=data.token,
            )

        try:
            membership = await sync_to_async(invitation.accept)(request.user)
        except ValueError as e:
            raise APIError(str(e), status_code=400)

        return JsonResponse(
            {
                "message": "Invitation accepted",
                "organization_id": str(invitation.organization.id),
                "organization_name": invitation.organization.name,
                "role": membership.role,
            }
        )

    async def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Revoke an invitation (org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            invitation_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped: 403 for cross-org (explicit denial)
            invitation = (
                await Invitation.objects.filter(
                    id=invitation_id,
                    organization=organization,
                )
                .select_related("organization")
                .afirst()
            )
            if not invitation:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            invitation = await (
                Invitation.objects.filter(id=invitation_id).select_related("organization").afirst()
            )
            if not invitation:
                raise NotFoundAPIError(
                    message="Invitation not found",
                    resource_type="Invitation",
                    resource_id=id,
                )

        # Check if user is admin
        if not await auser_is_org_admin(request.user, invitation.organization):
            raise ForbiddenError("Only admins can revoke invitations")

        try:
            await sync_to_async(invitation.revoke)()
        except ValueError as e:
            raise APIError(str(e), status_code=400)

        return JsonResponse({"message": "Invitation revoked"})

    async def resend(self, request: HttpRequest, id: str) -> InvitationResponse:
        """Resend an invitation (org-scoped)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization = getattr(request, "organization", None)

        try:
            invitation_id = uuid.UUID(id)
        except ValueError:
            return JsonResponse({"detail": "Forbidden"}, status=403)

        if organization:
            # Org-scoped: 403 for cross-org (explicit denial)
            invitation = (
                await Invitation.objects.filter(
                    id=invitation_id,
                    organization=organization,
                )
                .select_related("organization")
                .afirst()
            )
            if not invitation:
                return JsonResponse({"detail": "Forbidden"}, status=403)
        else:
            invitation = await (
                Invitation.objects.filter(id=invitation_id).select_related("organization").afirst()
            )
            if not invitation:
                raise NotFoundAPIError(
                    message="Invitation not found",
                    resource_type="Invitation",
                    resource_id=id,
                )

        # Check if user is admin
        if not await auser_is_org_admin(request.user, invitation.organization):
            raise ForbiddenError("Only admins can resend invitations")

        await sync_to_async(invitation.resend)()

        # Send invitation email (sync function — wrap for async context)
        from django_matt.multitenancy.emails import send_invitation_email

        await sync_to_async(send_invitation_email)(invitation)

        return JsonResponse(InvitationResponse.model_validate(invitation).model_dump(mode="json"))
