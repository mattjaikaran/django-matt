"""
Team API controllers.

Includes:
- Team CRUD within organizations
- Team member management
"""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import delete, get, patch, post

from core.models import AuditLog, Membership, Organization, Team
from core.schemas import TeamCreate, TeamDetailResponse, TeamUpdate, UserMiniResponse


class TeamController(APIController):
    prefix = "/organizations/<str:org_slug>/teams"
    tags = ["Teams"]

    async def get_org_and_check_access(self, request, org_slug: str, require_admin: bool = False):
        """Helper to get organization and check user access."""
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return None, None, ({"error": "Organization not found"}, 404)

        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership:
            return None, None, ({"error": "Not a member of this organization"}, 403)

        if require_admin and not membership.is_admin:
            return None, None, ({"error": "Admin permission required"}, 403)

        return org, membership, None

    # =========================================================================
    # Team CRUD
    # =========================================================================

    @get("/")
    @jwt_required
    async def list_teams(self, request, org_slug: str) -> list:
        """List all teams in the organization."""
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        teams = Team.objects.filter(organization=org, is_active=True)

        result = []
        async for team in teams:
            team_data = TeamDetailResponse.model_validate(team)
            # Add member count
            team_data.member_count = await team.members.acount()
            result.append(team_data)

        return result

    @post("/")
    @jwt_required
    async def create_team(self, request, org_slug: str, data: TeamCreate) -> dict:
        """Create a new team. Requires admin permission."""
        org, membership, error = await self.get_org_and_check_access(
            request, org_slug, require_admin=True
        )
        if error:
            return error

        # Check team limit
        team_count = await Team.objects.filter(organization=org, is_active=True).acount()
        max_teams = org.plan_limits.get("max_teams", 10)
        if max_teams != -1 and team_count >= max_teams:
            return {"error": f"Team limit reached ({max_teams})"}, 400

        # Check if slug is unique within org
        if await Team.objects.filter(organization=org, slug=data.slug).aexists():
            return {"error": "Team slug already exists in this organization"}, 400

        team = await Team.objects.acreate(
            organization=org,
            name=data.name,
            slug=data.slug,
            description=data.description,
        )

        # Create audit log
        await AuditLog.objects.acreate(
            user=request.user,
            organization=org,
            action="team.created",
            resource_type="team",
            resource_id=str(team.id),
            data={"name": team.name},
        )

        return TeamDetailResponse.model_validate(team)

    @get("/<str:team_slug>")
    @jwt_required
    async def get_team(self, request, org_slug: str, team_slug: str) -> dict:
        """Get team details."""
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)
            team_data = TeamDetailResponse.model_validate(team)
            team_data.member_count = await team.members.acount()
            return team_data
        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404

    @patch("/<str:team_slug>")
    @jwt_required
    async def update_team(self, request, org_slug: str, team_slug: str, data: TeamUpdate) -> dict:
        """Update team details. Requires admin permission."""
        org, membership, error = await self.get_org_and_check_access(
            request, org_slug, require_admin=True
        )
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)

            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(team, field, value)

            await team.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="team.updated",
                resource_type="team",
                resource_id=str(team.id),
                data=data.model_dump(exclude_unset=True),
            )

            return TeamDetailResponse.model_validate(team)

        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404

    @delete("/<str:team_slug>")
    @jwt_required
    async def delete_team(self, request, org_slug: str, team_slug: str) -> dict:
        """Delete team. Requires admin permission."""
        org, membership, error = await self.get_org_and_check_access(
            request, org_slug, require_admin=True
        )
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)

            # Soft delete
            team.is_active = False
            await team.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="team.deleted",
                resource_type="team",
                resource_id=str(team.id),
                data={"name": team.name},
            )

            return {"message": "Team deleted"}

        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404

    # =========================================================================
    # Team Members
    # =========================================================================

    @get("/<str:team_slug>/members")
    @jwt_required
    async def list_team_members(self, request, org_slug: str, team_slug: str) -> list:
        """List members of a team."""
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)

            members = []
            async for member in team.members.select_related("user").all():
                members.append(UserMiniResponse.model_validate(member.user))

            return members

        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404

    @post("/<str:team_slug>/members/<str:member_id>")
    @jwt_required
    async def add_team_member(self, request, org_slug: str, team_slug: str, member_id: str) -> dict:
        """Add member to team. Requires admin permission."""
        org, req_membership, error = await self.get_org_and_check_access(
            request, org_slug, require_admin=True
        )
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)
            target_membership = await Membership.objects.select_related("user").aget(
                id=member_id,
                organization=org,
                is_active=True,
            )

            await target_membership.teams.aadd(team)

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="team.member_added",
                resource_type="team",
                resource_id=str(team.id),
                data={"user_email": target_membership.user.email},
            )

            return {"message": "Member added to team"}

        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404
        except Membership.DoesNotExist:
            return {"error": "Member not found"}, 404

    @delete("/<str:team_slug>/members/<str:member_id>")
    @jwt_required
    async def remove_team_member(
        self, request, org_slug: str, team_slug: str, member_id: str
    ) -> dict:
        """Remove member from team. Requires admin permission."""
        org, req_membership, error = await self.get_org_and_check_access(
            request, org_slug, require_admin=True
        )
        if error:
            return error

        try:
            team = await Team.objects.aget(organization=org, slug=team_slug)
            target_membership = await Membership.objects.select_related("user").aget(
                id=member_id,
                organization=org,
            )

            await target_membership.teams.aremove(team)

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="team.member_removed",
                resource_type="team",
                resource_id=str(team.id),
                data={"user_email": target_membership.user.email},
            )

            return {"message": "Member removed from team"}

        except Team.DoesNotExist:
            return {"error": "Team not found"}, 404
        except Membership.DoesNotExist:
            return {"error": "Member not found"}, 404
