"""
Project API controllers.

Includes:
- Project CRUD
- Project member management
- Kanban board view
"""

from uuid import UUID

from django.db import models
from django_matt.auth import jwt_required
from django_matt.core import APIController, api_controller
from django_matt.permissions import IsAuthenticated

from core.models import AuditLog, Membership, Organization, User
from projects.models import Project, ProjectMember, TaskStatus
from projects.schemas import (
    KanbanBoardResponse,
    KanbanColumn,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMemberUpdate,
    ProjectMiniResponse,
    ProjectResponse,
    ProjectUpdate,
    TaskMiniResponse,
)


@api_controller("/organizations/{org_slug}/projects", tags=["Projects"])
class ProjectController(APIController):
    """Project management endpoints."""

    async def get_org_and_check_access(self, request, org_slug: str):
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

        return org, membership, None

    async def check_project_access(self, request, org, project, require_edit: bool = False):
        """Check if user has access to project."""
        # Check org membership
        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership:
            return False

        # Org admins have full access
        if membership.is_admin:
            return True

        # Check project-specific access
        if project.is_public:
            if not require_edit:
                return True
            # For edits, check project membership
            project_member = await ProjectMember.objects.filter(
                project=project,
                user=request.user,
            ).afirst()
            return project_member and project_member.role in ["owner", "editor"]

        # Private project - check membership
        project_member = await ProjectMember.objects.filter(
            project=project,
            user=request.user,
        ).afirst()

        if not project_member:
            return False

        if require_edit:
            return project_member.role in ["owner", "editor"]

        return True

    # =========================================================================
    # Project CRUD
    # =========================================================================

    @APIController.get("/", response=list[ProjectResponse], permissions=[IsAuthenticated])
    @jwt_required
    async def list_projects(
        self,
        request,
        org_slug: str,
        status: str | None = None,
        team_id: UUID | None = None,
        search: str | None = None,
    ):
        """
        List projects in the organization.

        Returns projects the user has access to (public or member of).
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        # Base queryset
        queryset = Project.objects.filter(organization=org)

        # Apply filters
        if status:
            queryset = queryset.filter(status=status)

        if team_id:
            queryset = queryset.filter(teams__id=team_id)

        if search:
            queryset = queryset.filter(name__icontains=search)

        # Filter by access
        if not membership.is_admin:
            # Get projects user is a member of
            member_project_ids = [
                pm.project_id async for pm in ProjectMember.objects.filter(user=request.user)
            ]
            # Include public projects and member projects
            queryset = queryset.filter(
                models.Q(is_public=True) | models.Q(id__in=member_project_ids)
            )

        result = []
        async for project in queryset.order_by("-created_at"):
            result.append(ProjectResponse.model_validate(project))

        return result

    @APIController.post("/", response=ProjectDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def create_project(self, request, org_slug: str, data: ProjectCreate):
        """
        Create a new project.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        # Check project limit
        if not org.check_limit("projects", await Project.objects.filter(organization=org).acount()):
            return {"error": "Project limit reached for your plan"}, 403

        # Check slug uniqueness
        if await Project.objects.filter(organization=org, slug=data.slug).aexists():
            return {"error": "Project slug already exists"}, 400

        # Create project
        project = await Project.objects.acreate(
            organization=org,
            name=data.name,
            slug=data.slug,
            description=data.description,
            owner=request.user,
            color=data.color,
            icon=data.icon,
            start_date=data.start_date,
            due_date=data.due_date,
        )

        # Add teams
        for team_id in data.team_ids:
            await project.teams.aadd(team_id)

        # Add creator as project owner
        await ProjectMember.objects.acreate(
            project=project,
            user=request.user,
            role="owner",
        )

        # Create audit log
        await AuditLog.objects.acreate(
            user=request.user,
            organization=org,
            action="project.created",
            resource_type="project",
            resource_id=str(project.id),
            data={"name": project.name},
        )

        return ProjectDetailResponse.model_validate(project)

    @APIController.get("/{project_slug}", response=ProjectDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_project(self, request, org_slug: str, project_slug: str):
        """
        Get project details.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.select_related("owner").prefetch_related("teams").aget(
                organization=org,
                slug=project_slug,
            )

            if not await self.check_project_access(request, org, project):
                return {"error": "Access denied"}, 403

            return ProjectDetailResponse.model_validate(project)

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404

    @APIController.patch("/{project_slug}", response=ProjectDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_project(self, request, org_slug: str, project_slug: str, data: ProjectUpdate):
        """
        Update project details.

        Requires edit permission on the project.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.select_related("owner").aget(
                organization=org,
                slug=project_slug,
            )

            if not await self.check_project_access(request, org, project, require_edit=True):
                return {"error": "Edit permission required"}, 403

            # Update fields
            update_data = data.model_dump(exclude_unset=True)
            team_ids = update_data.pop("team_ids", None)

            for field, value in update_data.items():
                setattr(project, field, value)

            await project.asave()

            # Update teams if provided
            if team_ids is not None:
                await project.teams.aclear()
                for team_id in team_ids:
                    await project.teams.aadd(team_id)

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="project.updated",
                resource_type="project",
                resource_id=str(project.id),
                data=data.model_dump(exclude_unset=True),
            )

            return ProjectDetailResponse.model_validate(project)

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404

    @APIController.delete("/{project_slug}", permissions=[IsAuthenticated])
    @jwt_required
    async def delete_project(self, request, org_slug: str, project_slug: str):
        """
        Delete (archive) project.

        Requires owner permission on the project.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(
                organization=org,
                slug=project_slug,
            )

            # Check owner permission
            is_project_owner = await ProjectMember.objects.filter(
                project=project,
                user=request.user,
                role="owner",
            ).aexists()

            if not is_project_owner and not membership.is_admin:
                return {"error": "Owner permission required"}, 403

            # Archive project
            project.status = "archived"
            await project.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="project.deleted",
                resource_type="project",
                resource_id=str(project.id),
                data={"name": project.name},
            )

            return {"message": "Project archived"}

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404

    # =========================================================================
    # Project Members
    # =========================================================================

    @APIController.get("/{project_slug}/members", response=list[ProjectMemberResponse], permissions=[IsAuthenticated])
    @jwt_required
    async def list_project_members(self, request, org_slug: str, project_slug: str):
        """
        List project members.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)

            if not await self.check_project_access(request, org, project):
                return {"error": "Access denied"}, 403

            members = ProjectMember.objects.filter(project=project).select_related("user")

            result = []
            async for member in members:
                result.append(ProjectMemberResponse.model_validate(member))

            return result

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404

    @APIController.post("/{project_slug}/members", response=ProjectMemberResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def add_project_member(self, request, org_slug: str, project_slug: str, data: ProjectMemberCreate):
        """
        Add member to project.

        Requires edit permission on the project.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)

            if not await self.check_project_access(request, org, project, require_edit=True):
                return {"error": "Edit permission required"}, 403

            # Check if user is org member
            target_user = await User.objects.aget(id=data.user_id)
            is_org_member = await Membership.objects.filter(
                user=target_user,
                organization=org,
                is_active=True,
            ).aexists()

            if not is_org_member:
                return {"error": "User is not a member of the organization"}, 400

            # Check if already a project member
            if await ProjectMember.objects.filter(project=project, user=target_user).aexists():
                return {"error": "User is already a project member"}, 400

            project_member = await ProjectMember.objects.acreate(
                project=project,
                user=target_user,
                role=data.role,
            )

            return ProjectMemberResponse.model_validate(project_member)

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404
        except User.DoesNotExist:
            return {"error": "User not found"}, 404

    @APIController.patch("/{project_slug}/members/{member_id}", response=ProjectMemberResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_project_member(self, request, org_slug: str, project_slug: str, member_id: UUID, data: ProjectMemberUpdate):
        """
        Update project member role.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)

            if not await self.check_project_access(request, org, project, require_edit=True):
                return {"error": "Edit permission required"}, 403

            project_member = await ProjectMember.objects.select_related("user").aget(
                id=member_id,
                project=project,
            )

            project_member.role = data.role
            await project_member.asave()

            return ProjectMemberResponse.model_validate(project_member)

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404
        except ProjectMember.DoesNotExist:
            return {"error": "Project member not found"}, 404

    @APIController.delete("/{project_slug}/members/{member_id}", permissions=[IsAuthenticated])
    @jwt_required
    async def remove_project_member(self, request, org_slug: str, project_slug: str, member_id: UUID):
        """
        Remove member from project.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)

            if not await self.check_project_access(request, org, project, require_edit=True):
                return {"error": "Edit permission required"}, 403

            project_member = await ProjectMember.objects.aget(
                id=member_id,
                project=project,
            )

            await project_member.adelete()

            return {"message": "Member removed from project"}

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404
        except ProjectMember.DoesNotExist:
            return {"error": "Project member not found"}, 404

    # =========================================================================
    # Kanban Board
    # =========================================================================

    @APIController.get("/{project_slug}/board", response=KanbanBoardResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_kanban_board(self, request, org_slug: str, project_slug: str):
        """
        Get Kanban board view with tasks grouped by status.
        """
        org, membership, error = await self.get_org_and_check_access(request, org_slug)
        if error:
            return error

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)

            if not await self.check_project_access(request, org, project):
                return {"error": "Access denied"}, 403

            # Define column order
            columns = []
            for status in TaskStatus.values:
                tasks = project.tasks.filter(
                    status=status,
                    parent__isnull=True,  # Top-level tasks only
                ).select_related("assignee").order_by("position")

                task_list = []
                async for task in tasks:
                    task_list.append(TaskMiniResponse.model_validate(task))

                columns.append(KanbanColumn(
                    status=status,
                    title=TaskStatus(status).label,
                    tasks=task_list,
                    task_count=len(task_list),
                ))

            return KanbanBoardResponse(
                project=ProjectMiniResponse.model_validate(project),
                columns=columns,
            )

        except Project.DoesNotExist:
            return {"error": "Project not found"}, 404
