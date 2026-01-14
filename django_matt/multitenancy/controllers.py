"""
Controllers for multi-tenancy endpoints.

Provides API endpoints for managing organizations, teams, memberships, and invitations.
"""

import uuid
from typing import List, Optional

from django.http import HttpRequest, JsonResponse
from django.db import IntegrityError

from django_matt.core.controller import APIController
from django_matt.core.errors import APIError, NotFoundAPIError
from django_matt.multitenancy.models import (
    Organization,
    Team,
    Membership,
    TeamMembership,
    Invitation,
    MembershipRole,
    InvitationStatus,
)
from django_matt.multitenancy.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse,
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamListResponse,
    MembershipCreate,
    MembershipUpdate,
    MembershipResponse,
    MemberResponse,
    TeamMembershipCreate,
    TeamMembershipResponse,
    InvitationCreate,
    InvitationResponse,
    InvitationAcceptRequest,
    TenantContext,
    SwitchOrganizationRequest,
)
from django_matt.multitenancy.middleware import get_current_tenant
from django_matt.multitenancy.utils import (
    user_is_org_admin,
    user_is_org_owner,
    user_can_manage_team,
    create_organization_with_owner,
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
    
    def list(self, request: HttpRequest) -> List[OrganizationListResponse]:
        """List all organizations the user is a member of."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        memberships = Membership.objects.filter(
            user=request.user,
            organization__is_active=True,
        ).select_related("organization")
        
        results = []
        for membership in memberships:
            org = membership.organization
            results.append(OrganizationListResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                description=org.description,
                logo_url=org.logo_url,
                role=membership.role,
                is_active=org.is_active,
            ))
        
        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)
    
    def create(self, request: HttpRequest, data: OrganizationCreate) -> OrganizationResponse:
        """Create a new organization with the current user as owner."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            organization = create_organization_with_owner(
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
    
    def retrieve(self, request: HttpRequest, id: str) -> OrganizationResponse:
        """Get organization details."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            org_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        organization = Organization.objects.filter(id=org_id, is_active=True).first()
        if not organization:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        # Check if user is a member
        if not organization.is_member(request.user):
            raise ForbiddenError("You are not a member of this organization")
        
        return JsonResponse(
            OrganizationResponse.model_validate(organization).model_dump(mode="json")
        )
    
    def update(
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
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        organization = Organization.objects.filter(id=org_id).first()
        if not organization:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        # Check if user is admin
        if not user_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can update organizations")
        
        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(organization, field, value)
        
        try:
            organization.save()
        except IntegrityError:
            raise ConflictError(f"Organization with slug '{data.slug}' already exists")
        
        return JsonResponse(
            OrganizationResponse.model_validate(organization).model_dump(mode="json")
        )
    
    def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Delete an organization (owner only)."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            org_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        organization = Organization.objects.filter(id=org_id).first()
        if not organization:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=id,
            )
        
        # Check if user is owner
        if not user_is_org_owner(request.user, organization):
            raise ForbiddenError("Only owners can delete organizations")
        
        organization.delete()
        return JsonResponse({"message": "Organization deleted"}, status=200)
    
    def switch(
        self,
        request: HttpRequest,
        data: SwitchOrganizationRequest,
    ) -> TenantContext:
        """Switch to a different organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = None
        
        if data.organization_id:
            organization = Organization.objects.filter(
                id=data.organization_id,
                is_active=True,
            ).first()
        elif data.organization_slug:
            organization = Organization.objects.filter(
                slug=data.organization_slug,
                is_active=True,
            ).first()
        
        if not organization:
            raise NotFoundAPIError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=str(data.organization_id or data.organization_slug),
            )
        
        # Check if user is a member
        membership = Membership.objects.filter(
            organization=organization,
            user=request.user,
        ).first()
        
        if not membership:
            raise ForbiddenError("You are not a member of this organization")
        
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
    
    def list(self, request: HttpRequest) -> List[TeamListResponse]:
        """List all teams in the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = get_current_tenant()
        if not organization:
            organization = getattr(request, "organization", None)
        
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)
        
        teams = Team.objects.filter(organization=organization)
        
        results = []
        for team in teams:
            # Get user's role in team if member
            team_membership = TeamMembership.objects.filter(
                team=team,
                user=request.user,
            ).first()
            
            member_count = team.memberships.count()
            
            results.append(TeamListResponse(
                id=team.id,
                name=team.name,
                slug=team.slug,
                description=team.description,
                role=team_membership.role if team_membership else None,
                is_default=team.is_default,
                member_count=member_count,
            ))
        
        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)
    
    def create(self, request: HttpRequest, data: TeamCreate) -> TeamResponse:
        """Create a new team in the organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = get_current_tenant()
        if not organization:
            organization = getattr(request, "organization", None)
        
        if data.organization_id:
            organization = Organization.objects.filter(id=data.organization_id).first()
        
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)
        
        # Check if user is admin
        if not user_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can create teams")
        
        try:
            team = Team.objects.create(
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
    
    def retrieve(self, request: HttpRequest, id: str) -> TeamResponse:
        """Get team details."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            team_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        team = Team.objects.filter(id=team_id).select_related("organization").first()
        if not team:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        # Check if user is a member of the organization
        if not team.organization.is_member(request.user):
            raise ForbiddenError("You are not a member of this organization")
        
        return JsonResponse(
            TeamResponse.model_validate(team).model_dump(mode="json")
        )
    
    def update(
        self,
        request: HttpRequest,
        id: str,
        data: TeamUpdate,
    ) -> TeamResponse:
        """Update a team."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            team_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        team = Team.objects.filter(id=team_id).select_related("organization").first()
        if not team:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        # Check if user can manage team
        if not user_can_manage_team(request.user, team):
            raise ForbiddenError("You don't have permission to update this team")
        
        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(team, field, value)
        
        try:
            team.save()
        except IntegrityError:
            raise ConflictError(f"Team with slug '{data.slug}' already exists in this organization")
        
        return JsonResponse(
            TeamResponse.model_validate(team).model_dump(mode="json")
        )
    
    def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Delete a team."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            team_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        team = Team.objects.filter(id=team_id).select_related("organization").first()
        if not team:
            raise NotFoundAPIError(
                message="Team not found",
                resource_type="Team",
                resource_id=id,
            )
        
        # Check if user is org admin
        if not user_is_org_admin(request.user, team.organization):
            raise ForbiddenError("Only organization admins can delete teams")
        
        team.delete()
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
    
    def list(self, request: HttpRequest) -> List[MemberResponse]:
        """List all members of the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = get_current_tenant()
        if not organization:
            organization = getattr(request, "organization", None)
        
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)
        
        memberships = Membership.objects.filter(
            organization=organization,
        ).select_related("user")
        
        results = []
        for membership in memberships:
            user = membership.user
            results.append(MemberResponse(
                id=membership.id,
                user_id=user.id,
                email=user.email,
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                role=membership.role,
                joined_at=membership.joined_at,
            ))
        
        return JsonResponse([r.model_dump(mode="json") for r in results], safe=False)
    
    def update(
        self,
        request: HttpRequest,
        id: str,
        data: MembershipUpdate,
    ) -> MembershipResponse:
        """Update a member's role."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            membership_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Membership not found",
                resource_type="Membership",
                resource_id=id,
            )
        
        membership = Membership.objects.filter(id=membership_id).select_related("organization").first()
        if not membership:
            raise NotFoundAPIError(
                message="Membership not found",
                resource_type="Membership",
                resource_id=id,
            )
        
        # Check if user is admin
        if not user_is_org_admin(request.user, membership.organization):
            raise ForbiddenError("Only admins can update member roles")
        
        # Get actor's membership
        actor_membership = Membership.objects.filter(
            organization=membership.organization,
            user=request.user,
        ).first()
        
        # Check role hierarchy
        if not MembershipRole.can_manage(actor_membership.role, membership.role):
            raise ForbiddenError("Cannot modify a member with higher or equal role")
        
        if not MembershipRole.can_manage(actor_membership.role, data.role):
            raise ForbiddenError("Cannot assign a role higher than or equal to your own")
        
        membership.role = data.role
        membership.save(update_fields=["role", "updated_at"])
        
        return JsonResponse(
            MembershipResponse.model_validate(membership).model_dump(mode="json")
        )
    
    def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Remove a member from the organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            membership_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Membership not found",
                resource_type="Membership",
                resource_id=id,
            )
        
        membership = Membership.objects.filter(id=membership_id).select_related("organization").first()
        if not membership:
            raise NotFoundAPIError(
                message="Membership not found",
                resource_type="Membership",
                resource_id=id,
            )
        
        # Check if user is admin
        if not user_is_org_admin(request.user, membership.organization):
            raise ForbiddenError("Only admins can remove members")
        
        # Get actor's membership
        actor_membership = Membership.objects.filter(
            organization=membership.organization,
            user=request.user,
        ).first()
        
        # Can't remove yourself if you're the only owner
        if membership.user == request.user:
            if membership.role == MembershipRole.OWNER.value:
                owner_count = Membership.objects.filter(
                    organization=membership.organization,
                    role=MembershipRole.OWNER.value,
                ).count()
                if owner_count <= 1:
                    raise ForbiddenError("Cannot remove the only owner. Transfer ownership first.")
        else:
            # Check role hierarchy
            if not MembershipRole.can_manage(actor_membership.role, membership.role):
                raise ForbiddenError("Cannot remove a member with higher or equal role")
        
        membership.delete()
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
    
    def list(self, request: HttpRequest) -> List[InvitationResponse]:
        """List all invitations for the current organization."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = get_current_tenant()
        if not organization:
            organization = getattr(request, "organization", None)
        
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)
        
        # Check if user is admin
        if not user_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can view invitations")
        
        invitations = Invitation.objects.filter(organization=organization)
        
        results = [
            InvitationResponse.model_validate(inv).model_dump(mode="json")
            for inv in invitations
        ]
        
        return JsonResponse(results, safe=False)
    
    def create(self, request: HttpRequest, data: InvitationCreate) -> InvitationResponse:
        """Create a new invitation."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        organization = get_current_tenant()
        if not organization:
            organization = getattr(request, "organization", None)
        
        if data.organization_id:
            organization = Organization.objects.filter(id=data.organization_id).first()
        
        if not organization:
            return JsonResponse({"error": "Organization context required"}, status=400)
        
        # Check if user is admin
        if not user_is_org_admin(request.user, organization):
            raise ForbiddenError("Only admins can send invitations")
        
        # Check if email is already a member
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        existing_user = User.objects.filter(email=data.email).first()
        if existing_user and organization.is_member(existing_user):
            raise ConflictError("User is already a member of this organization")
        
        # Check for pending invitation
        existing_invitation = Invitation.objects.filter(
            organization=organization,
            email=data.email,
            status=InvitationStatus.PENDING.value,
        ).first()
        
        if existing_invitation:
            raise ConflictError("An invitation is already pending for this email")
        
        # Get team if specified
        team = None
        if data.team_id:
            team = Team.objects.filter(id=data.team_id, organization=organization).first()
            if not team:
                raise NotFoundAPIError(
                    message="Team not found",
                    resource_type="Team",
                    resource_id=str(data.team_id),
                )
        
        invitation = Invitation.objects.create(
            organization=organization,
            team=team,
            email=data.email,
            role=data.role,
            invited_by=request.user,
        )
        
        # TODO: Send invitation email
        
        return JsonResponse(
            InvitationResponse.model_validate(invitation).model_dump(mode="json"),
            status=201,
        )
    
    def accept(self, request: HttpRequest, data: InvitationAcceptRequest) -> JsonResponse:
        """Accept an invitation."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        invitation = Invitation.objects.filter(
            token=data.token,
        ).select_related("organization", "team").first()
        
        if not invitation:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=data.token,
            )
        
        try:
            membership = invitation.accept(request.user)
        except ValueError as e:
            raise APIError(str(e), status_code=400)
        
        return JsonResponse({
            "message": "Invitation accepted",
            "organization_id": str(invitation.organization.id),
            "organization_name": invitation.organization.name,
            "role": membership.role,
        })
    
    def delete(self, request: HttpRequest, id: str) -> JsonResponse:
        """Revoke an invitation."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            invitation_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=id,
            )
        
        invitation = Invitation.objects.filter(id=invitation_id).select_related("organization").first()
        if not invitation:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=id,
            )
        
        # Check if user is admin
        if not user_is_org_admin(request.user, invitation.organization):
            raise ForbiddenError("Only admins can revoke invitations")
        
        try:
            invitation.revoke()
        except ValueError as e:
            raise APIError(str(e), status_code=400)
        
        return JsonResponse({"message": "Invitation revoked"})
    
    def resend(self, request: HttpRequest, id: str) -> InvitationResponse:
        """Resend an invitation."""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        try:
            invitation_id = uuid.UUID(id)
        except ValueError:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=id,
            )
        
        invitation = Invitation.objects.filter(id=invitation_id).select_related("organization").first()
        if not invitation:
            raise NotFoundAPIError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=id,
            )
        
        # Check if user is admin
        if not user_is_org_admin(request.user, invitation.organization):
            raise ForbiddenError("Only admins can resend invitations")
        
        invitation.resend()
        
        # TODO: Send invitation email
        
        return JsonResponse(
            InvitationResponse.model_validate(invitation).model_dump(mode="json")
        )
