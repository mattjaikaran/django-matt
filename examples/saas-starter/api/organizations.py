"""
Organization API controllers.

Includes:
- Organization CRUD
- Member management
- Invitations
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import delete, get, patch, post

from core.models import AuditLog, Invitation, Membership, MembershipRole, Organization
from core.schemas import (
    InvitationAccept,
    InvitationCreate,
    InvitationResponse,
    MembershipDetailResponse,
    MembershipUpdate,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationResponse,
    OrganizationUpdate,
)


class OrganizationController(APIController):
    prefix = "/organizations"
    tags = ["Organizations"]

    # =========================================================================
    # Organization CRUD
    # =========================================================================

    @get("/")
    @jwt_required
    async def list_organizations(self, request) -> list:
        """List all organizations the current user is a member of."""
        memberships = Membership.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related("organization")

        orgs = []
        async for membership in memberships:
            org = membership.organization
            orgs.append(OrganizationResponse.model_validate(org))

        return orgs

    @post("/")
    @jwt_required
    async def create_organization(self, request, data: OrganizationCreate) -> dict:
        """Create a new organization. The creating user becomes the owner."""
        user = request.user

        # Check if slug is unique
        if await Organization.objects.filter(slug=data.slug).aexists():
            return {"error": "Organization slug already exists"}, 400

        # Get plan limits
        plan_limits = settings.BILLING_PRODUCTS.get("free", {}).get("limits", {})

        # Create organization
        org = await Organization.objects.acreate(
            name=data.name,
            slug=data.slug,
            description=data.description,
            website=data.website,
            owner=user,
            plan="free",
            plan_limits=plan_limits,
        )

        # Create owner membership
        await Membership.objects.acreate(
            user=user,
            organization=org,
            role=MembershipRole.OWNER,
        )

        # Create audit log
        await AuditLog.objects.acreate(
            user=user,
            organization=org,
            action="organization.created",
            data={"name": org.name},
        )

        return OrganizationDetailResponse.model_validate(org)

    @get("/<str:org_slug>")
    @jwt_required
    async def get_organization(self, request, org_slug: str) -> dict:
        """Get organization details."""
        try:
            org = await Organization.objects.select_related("owner").aget(slug=org_slug)

            # Check membership
            is_member = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).aexists()

            if not is_member:
                return {"error": "Not a member of this organization"}, 403

            return OrganizationDetailResponse.model_validate(org)

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    @patch("/<str:org_slug>")
    @jwt_required
    async def update_organization(self, request, org_slug: str, data: OrganizationUpdate) -> dict:
        """Update organization details. Requires admin or owner role."""
        try:
            org = await Organization.objects.select_related("owner").aget(slug=org_slug)

            # Check admin permission
            membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            if not membership or not membership.is_admin:
                return {"error": "Admin permission required"}, 403

            # Update fields
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(org, field, value)

            await org.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="organization.updated",
                data=data.model_dump(exclude_unset=True),
            )

            return OrganizationDetailResponse.model_validate(org)

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    @delete("/<str:org_slug>")
    @jwt_required
    async def delete_organization(self, request, org_slug: str) -> dict:
        """Delete organization. Requires owner role."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check owner permission
            if org.owner_id != request.user.id:
                return {"error": "Only the owner can delete the organization"}, 403

            if org.is_personal:
                return {"error": "Personal workspace cannot be deleted"}, 400

            # Soft delete or actual delete based on requirements
            org.is_active = False
            await org.asave()

            return {"message": "Organization deleted"}

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    # =========================================================================
    # Members
    # =========================================================================

    @get("/<str:org_slug>/members")
    @jwt_required
    async def list_members(self, request, org_slug: str) -> list:
        """List all members of an organization."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check membership
            is_member = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).aexists()

            if not is_member:
                return {"error": "Not a member of this organization"}, 403

            memberships = (
                Membership.objects.filter(
                    organization=org,
                    is_active=True,
                )
                .select_related("user", "invited_by")
                .prefetch_related("teams")
            )

            result = []
            async for membership in memberships:
                result.append(MembershipDetailResponse.model_validate(membership))

            return result

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    @patch("/<str:org_slug>/members/<str:member_id>")
    @jwt_required
    async def update_member(
        self, request, org_slug: str, member_id: str, data: MembershipUpdate
    ) -> dict:
        """Update member role or team assignments. Requires admin permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check admin permission
            requester_membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            if not requester_membership or not requester_membership.is_admin:
                return {"error": "Admin permission required"}, 403

            # Get target membership
            membership = await Membership.objects.select_related("user").aget(
                id=member_id,
                organization=org,
            )

            # Cannot change owner's role
            if membership.role == MembershipRole.OWNER and data.role:
                return {"error": "Cannot change owner's role"}, 400

            # Update fields
            if data.role:
                membership.role = data.role

            if data.team_ids is not None:
                # Update team assignments
                await membership.teams.aclear()
                for team_id in data.team_ids:
                    await membership.teams.aadd(team_id)

            await membership.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="membership.updated",
                resource_type="membership",
                resource_id=str(membership.id),
                data=data.model_dump(exclude_unset=True),
            )

            return MembershipDetailResponse.model_validate(membership)

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404
        except Membership.DoesNotExist:
            return {"error": "Member not found"}, 404

    @delete("/<str:org_slug>/members/<str:member_id>")
    @jwt_required
    async def remove_member(self, request, org_slug: str, member_id: str) -> dict:
        """Remove member from organization. Requires admin permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check admin permission (or self-removal)
            requester_membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            membership = await Membership.objects.select_related("user").aget(
                id=member_id,
                organization=org,
            )

            # Self-removal is allowed
            is_self_removal = membership.user_id == request.user.id

            if not is_self_removal and (
                not requester_membership or not requester_membership.is_admin
            ):
                return {"error": "Admin permission required"}, 403

            # Cannot remove owner
            if membership.role == MembershipRole.OWNER:
                return {"error": "Cannot remove organization owner"}, 400

            # Soft delete membership
            membership.is_active = False
            await membership.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="membership.removed",
                resource_type="membership",
                resource_id=str(membership.id),
                data={"user_email": membership.user.email},
            )

            return {"message": "Member removed"}

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404
        except Membership.DoesNotExist:
            return {"error": "Member not found"}, 404

    # =========================================================================
    # Invitations
    # =========================================================================

    @get("/<str:org_slug>/invitations")
    @jwt_required
    async def list_invitations(self, request, org_slug: str) -> list:
        """List pending invitations. Requires admin permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check admin permission
            membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            if not membership or not membership.is_admin:
                return {"error": "Admin permission required"}, 403

            invitations = Invitation.objects.filter(
                organization=org,
                status="pending",
            ).select_related("organization", "invited_by")

            result = []
            async for inv in invitations:
                result.append(InvitationResponse.model_validate(inv))

            return result

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    @post("/<str:org_slug>/invitations")
    @jwt_required
    async def create_invitation(self, request, org_slug: str, data: InvitationCreate) -> dict:
        """Invite a user to the organization. Requires invite permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check invite permission
            membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            if not membership or not membership.has_permission("invite"):
                return {"error": "Invite permission required"}, 403

            # Check if already a member
            if await Membership.objects.filter(
                user__email=data.email.lower(),
                organization=org,
                is_active=True,
            ).aexists():
                return {"error": "User is already a member"}, 400

            # Check if pending invitation exists
            if await Invitation.objects.filter(
                email=data.email.lower(),
                organization=org,
                status="pending",
            ).aexists():
                return {"error": "Invitation already sent"}, 400

            # Check email domain restrictions
            if org.allowed_email_domains:
                email_domain = data.email.split("@")[1]
                if email_domain not in org.allowed_email_domains:
                    return {"error": "Email domain not allowed"}, 400

            # Create invitation
            invitation = await Invitation.objects.acreate(
                organization=org,
                email=data.email.lower(),
                role=data.role,
                token=secrets.token_urlsafe(32),
                invited_by=request.user,
                message=data.message,
                expires_at=timezone.now() + timedelta(days=7),
            )

            # Add teams
            for team_id in data.team_ids:
                await invitation.teams.aadd(team_id)

            # TODO: Send invitation email
            # send_invitation_email.delay(invitation.id)

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="invitation.created",
                resource_type="invitation",
                resource_id=str(invitation.id),
                data={"email": invitation.email, "role": invitation.role},
            )

            return InvitationResponse.model_validate(invitation)

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

    @post("/invitations/accept")
    @jwt_required
    async def accept_invitation(self, request, data: InvitationAccept) -> dict:
        """Accept an invitation to join an organization."""
        try:
            invitation = (
                await Invitation.objects.select_related("organization")
                .prefetch_related("teams")
                .aget(
                    token=data.token,
                    status="pending",
                )
            )

            if not invitation.is_valid:
                return {"error": "Invitation is expired or invalid"}, 400

            # Check if email matches
            if invitation.email != request.user.email:
                return {"error": "Invitation was sent to a different email"}, 400

            # Create membership
            membership = await Membership.objects.acreate(
                user=request.user,
                organization=invitation.organization,
                role=invitation.role,
                invited_by=invitation.invited_by,
                invited_at=invitation.created_at,
                accepted_at=timezone.now(),
            )

            # Add teams
            async for team in invitation.teams.all():
                await membership.teams.aadd(team)

            # Update invitation status
            invitation.status = "accepted"
            invitation.accepted_at = timezone.now()
            await invitation.asave()

            return {
                "message": "Invitation accepted",
                "organization": {
                    "id": str(invitation.organization.id),
                    "name": invitation.organization.name,
                    "slug": invitation.organization.slug,
                },
            }

        except Invitation.DoesNotExist:
            return {"error": "Invalid invitation token"}, 400

    @delete("/<str:org_slug>/invitations/<str:invitation_id>")
    @jwt_required
    async def revoke_invitation(self, request, org_slug: str, invitation_id: str) -> dict:
        """Revoke a pending invitation. Requires admin permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)

            # Check admin permission
            membership = await Membership.objects.filter(
                user=request.user,
                organization=org,
                is_active=True,
            ).afirst()

            if not membership or not membership.is_admin:
                return {"error": "Admin permission required"}, 403

            invitation = await Invitation.objects.aget(
                id=invitation_id,
                organization=org,
                status="pending",
            )

            invitation.status = "revoked"
            await invitation.asave()

            return {"message": "Invitation revoked"}

        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404
        except Invitation.DoesNotExist:
            return {"error": "Invitation not found"}, 404
