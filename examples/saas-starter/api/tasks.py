"""
Task API controllers.

Includes:
- Task CRUD
- Bulk operations
- Task movement (Kanban)
- Real-time updates via WebSocket
"""

from uuid import UUID

from django.db import models
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController, api_controller
from django_matt.permissions import IsAuthenticated

from core.models import AuditLog, Membership, Organization, User
from projects.models import Project, ProjectMember, Task, TaskActivity, TaskStatus
from projects.schemas import (
    TaskActivityResponse,
    TaskBulkUpdate,
    TaskCreate,
    TaskDetailResponse,
    TaskListResponse,
    TaskMiniResponse,
    TaskMove,
    TaskResponse,
    TaskUpdate,
)


@api_controller("/organizations/{org_slug}/projects/{project_slug}/tasks", tags=["Tasks"])
class TaskController(APIController):
    """Task management endpoints."""

    async def get_project_and_check_access(self, request, org_slug: str, project_slug: str, require_edit: bool = False):
        """Helper to get project and check user access."""
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return None, None, None, ({"error": "Organization not found"}, 404)

        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership:
            return None, None, None, ({"error": "Not a member of this organization"}, 403)

        try:
            project = await Project.objects.aget(organization=org, slug=project_slug)
        except Project.DoesNotExist:
            return None, None, None, ({"error": "Project not found"}, 404)

        # Check project access
        if not membership.is_admin:
            if project.is_public:
                if require_edit:
                    pm = await ProjectMember.objects.filter(
                        project=project, user=request.user, role__in=["owner", "editor"]
                    ).afirst()
                    if not pm:
                        return None, None, None, ({"error": "Edit permission required"}, 403)
            else:
                pm = await ProjectMember.objects.filter(project=project, user=request.user).afirst()
                if not pm:
                    return None, None, None, ({"error": "Access denied"}, 403)
                if require_edit and pm.role not in ["owner", "editor"]:
                    return None, None, None, ({"error": "Edit permission required"}, 403)

        return org, project, membership, None

    async def broadcast_task_update(self, org_id: str, project_id: str, action: str, task_id: str, data: dict = None):
        """Broadcast task update via WebSocket."""
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            await channel_layer.group_send(
                f"project_{project_id}",
                {
                    "type": "task_update",
                    "action": action,
                    "task_id": str(task_id),
                    "data": data or {},
                }
            )

    # =========================================================================
    # Task CRUD
    # =========================================================================

    @APIController.get("/", response=TaskListResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def list_tasks(
        self,
        request,
        org_slug: str,
        project_slug: str,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        """
        List tasks in a project with filtering and pagination.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug
        )
        if error:
            return error

        # Build queryset
        queryset = Task.objects.filter(
            project=project,
            parent__isnull=True,  # Top-level tasks only
        ).select_related("assignee", "reporter")

        # Apply filters
        if status:
            statuses = status.split(",")
            queryset = queryset.filter(status__in=statuses)

        if priority:
            priorities = priority.split(",")
            queryset = queryset.filter(priority__in=priorities)

        if assignee_id:
            queryset = queryset.filter(assignee_id=assignee_id)

        if search:
            queryset = queryset.filter(
                models.Q(title__icontains=search) |
                models.Q(description__icontains=search)
            )

        # Get total count
        total = await queryset.acount()

        # Apply pagination
        offset = (page - 1) * page_size
        queryset = queryset.order_by("position", "-created_at")[offset:offset + page_size]

        items = []
        async for task in queryset:
            items.append(TaskResponse.model_validate(task))

        return TaskListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=offset + page_size < total,
            has_prev=page > 1,
        )

    @APIController.post("/", response=TaskDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def create_task(self, request, org_slug: str, project_slug: str, data: TaskCreate):
        """
        Create a new task.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug, require_edit=True
        )
        if error:
            return error

        # Get max position
        max_pos = await Task.objects.filter(
            project=project,
            status=data.status,
            parent__isnull=True,
        ).aaggregate(max_pos=models.Max("position"))
        position = (max_pos.get("max_pos") or 0) + 1

        # Validate assignee
        assignee = None
        if data.assignee_id:
            try:
                assignee = await User.objects.aget(id=data.assignee_id)
                # Verify assignee is org member
                if not await Membership.objects.filter(
                    user=assignee, organization=org, is_active=True
                ).aexists():
                    return {"error": "Assignee is not an organization member"}, 400
            except User.DoesNotExist:
                return {"error": "Assignee not found"}, 404

        # Validate parent
        parent = None
        if data.parent_id:
            try:
                parent = await Task.objects.aget(id=data.parent_id, project=project)
            except Task.DoesNotExist:
                return {"error": "Parent task not found"}, 404

        task = await Task.objects.acreate(
            project=project,
            parent=parent,
            title=data.title,
            description=data.description,
            assignee=assignee,
            reporter=request.user,
            status=data.status,
            priority=data.priority,
            position=position,
            labels=data.labels,
            estimated_hours=data.estimated_hours,
            start_date=data.start_date,
            due_date=data.due_date,
            custom_fields=data.custom_fields,
        )

        # Broadcast update
        await self.broadcast_task_update(
            str(org.id), str(project.id), "created", str(task.id),
            {"status": task.status}
        )

        return TaskDetailResponse.model_validate(task)

    @APIController.get("/{task_id}", response=TaskDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_task(self, request, org_slug: str, project_slug: str, task_id: UUID):
        """
        Get task details including subtasks.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug
        )
        if error:
            return error

        try:
            task = await Task.objects.select_related(
                "assignee", "reporter", "project"
            ).prefetch_related("subtasks").aget(
                id=task_id,
                project=project,
            )

            response = TaskDetailResponse.model_validate(task)

            # Add subtasks
            subtasks = []
            async for subtask in task.subtasks.select_related("assignee"):
                subtasks.append(TaskMiniResponse.model_validate(subtask))
            response.subtasks = subtasks

            return response

        except Task.DoesNotExist:
            return {"error": "Task not found"}, 404

    @APIController.patch("/{task_id}", response=TaskDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_task(self, request, org_slug: str, project_slug: str, task_id: UUID, data: TaskUpdate):
        """
        Update task details.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug, require_edit=True
        )
        if error:
            return error

        try:
            task = await Task.objects.select_related("assignee", "reporter").aget(
                id=task_id,
                project=project,
            )

            update_data = data.model_dump(exclude_unset=True)

            # Handle assignee update
            if "assignee_id" in update_data:
                assignee_id = update_data.pop("assignee_id")
                if assignee_id:
                    try:
                        task.assignee = await User.objects.aget(id=assignee_id)
                    except User.DoesNotExist:
                        return {"error": "Assignee not found"}, 404
                else:
                    task.assignee = None

            # Update fields
            for field, value in update_data.items():
                setattr(task, field, value)

            # Check if status changed to done
            if data.status == TaskStatus.DONE and task.completed_at is None:
                task.completed_at = timezone.now()

            await task.asave()

            # Create activity
            await TaskActivity.objects.acreate(
                task=task,
                user=request.user,
                action="updated",
                metadata={"fields": list(update_data.keys())},
            )

            # Broadcast update
            await self.broadcast_task_update(
                str(org.id), str(project.id), "updated", str(task.id),
                {"status": task.status, "fields": list(update_data.keys())}
            )

            return TaskDetailResponse.model_validate(task)

        except Task.DoesNotExist:
            return {"error": "Task not found"}, 404

    @APIController.delete("/{task_id}", permissions=[IsAuthenticated])
    @jwt_required
    async def delete_task(self, request, org_slug: str, project_slug: str, task_id: UUID):
        """
        Delete task and its subtasks.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug, require_edit=True
        )
        if error:
            return error

        try:
            task = await Task.objects.aget(id=task_id, project=project)

            # Delete task (cascades to subtasks)
            await task.adelete()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="task.deleted",
                resource_type="task",
                resource_id=str(task_id),
            )

            # Broadcast update
            await self.broadcast_task_update(
                str(org.id), str(project.id), "deleted", str(task_id)
            )

            return {"message": "Task deleted"}

        except Task.DoesNotExist:
            return {"error": "Task not found"}, 404

    # =========================================================================
    # Task Movement (Kanban)
    # =========================================================================

    @APIController.post("/{task_id}/move", response=TaskResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def move_task(self, request, org_slug: str, project_slug: str, task_id: UUID, data: TaskMove):
        """
        Move task to different status/position (for Kanban drag-and-drop).
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug, require_edit=True
        )
        if error:
            return error

        try:
            task = await Task.objects.aget(id=task_id, project=project)

            old_status = task.status
            new_status = data.status
            new_position = data.position

            # Update positions of other tasks
            if old_status == new_status:
                # Moving within same column
                if task.position < new_position:
                    # Moving down
                    await Task.objects.filter(
                        project=project,
                        status=new_status,
                        position__gt=task.position,
                        position__lte=new_position,
                    ).aupdate(position=models.F("position") - 1)
                else:
                    # Moving up
                    await Task.objects.filter(
                        project=project,
                        status=new_status,
                        position__lt=task.position,
                        position__gte=new_position,
                    ).aupdate(position=models.F("position") + 1)
            else:
                # Moving to different column
                # Shift tasks in old column
                await Task.objects.filter(
                    project=project,
                    status=old_status,
                    position__gt=task.position,
                ).aupdate(position=models.F("position") - 1)

                # Shift tasks in new column
                await Task.objects.filter(
                    project=project,
                    status=new_status,
                    position__gte=new_position,
                ).aupdate(position=models.F("position") + 1)

            # Update task
            task.status = new_status
            task.position = new_position

            # Mark as completed if moved to done
            if new_status == TaskStatus.DONE and old_status != TaskStatus.DONE:
                task.completed_at = timezone.now()

            await task.asave()

            # Create activity
            if old_status != new_status:
                await TaskActivity.objects.acreate(
                    task=task,
                    user=request.user,
                    action="status_changed",
                    field="status",
                    old_value=old_status,
                    new_value=new_status,
                )

            # Broadcast update
            await self.broadcast_task_update(
                str(org.id), str(project.id), "moved", str(task.id),
                {"old_status": old_status, "new_status": new_status, "position": new_position}
            )

            return TaskResponse.model_validate(task)

        except Task.DoesNotExist:
            return {"error": "Task not found"}, 404

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    @APIController.post("/bulk", response=dict, permissions=[IsAuthenticated])
    @jwt_required
    async def bulk_update_tasks(self, request, org_slug: str, project_slug: str, data: TaskBulkUpdate):
        """
        Bulk update multiple tasks.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug, require_edit=True
        )
        if error:
            return error

        tasks = Task.objects.filter(id__in=data.task_ids, project=project)

        update_data = {}
        if data.status:
            update_data["status"] = data.status
        if data.priority:
            update_data["priority"] = data.priority
        if data.assignee_id:
            update_data["assignee_id"] = data.assignee_id

        updated = 0
        if update_data:
            updated = await tasks.aupdate(**update_data)

        # Handle label changes
        if data.labels_add or data.labels_remove:
            async for task in tasks:
                if data.labels_add:
                    task.labels = list(set(task.labels + data.labels_add))
                if data.labels_remove:
                    task.labels = [label for label in task.labels if label not in data.labels_remove]
                await task.asave(update_fields=["labels"])

        # Broadcast updates
        for task_id in data.task_ids:
            await self.broadcast_task_update(
                str(org.id), str(project.id), "updated", str(task_id),
                {"bulk_update": True}
            )

        return {"updated": updated, "task_ids": [str(t) for t in data.task_ids]}

    # =========================================================================
    # Task Activity
    # =========================================================================

    @APIController.get("/{task_id}/activity", response=list[TaskActivityResponse], permissions=[IsAuthenticated])
    @jwt_required
    async def get_task_activity(self, request, org_slug: str, project_slug: str, task_id: UUID):
        """
        Get activity log for a task.
        """
        org, project, membership, error = await self.get_project_and_check_access(
            request, org_slug, project_slug
        )
        if error:
            return error

        try:
            task = await Task.objects.aget(id=task_id, project=project)

            activities = TaskActivity.objects.filter(
                task=task
            ).select_related("user").order_by("-created_at")[:50]

            result = []
            async for activity in activities:
                result.append(TaskActivityResponse.model_validate(activity))

            return result

        except Task.DoesNotExist:
            return {"error": "Task not found"}, 404
