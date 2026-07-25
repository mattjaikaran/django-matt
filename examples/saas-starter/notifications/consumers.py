"""
WebSocket consumers for real-time features.

Includes:
- Notification consumer (user-specific)
- Project consumer (project room)
- Task consumer (task room for comments)
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.models import Membership
from projects.models import Project, ProjectMember, Task


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for user notifications.

    Each user connects to their own channel to receive real-time notifications.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user_id = str(user.id)
        self.room_group_name = f"user_{self.user_id}"

        # Join user group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Send connection confirmation
        await self.send_json(
            {
                "type": "connected",
                "user_id": self.user_id,
            }
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content):
        """Handle incoming messages."""
        message_type = content.get("type")

        if message_type == "mark_read":
            # Handle mark as read
            notification_id = content.get("notification_id")
            if notification_id:
                await self.mark_notification_read(notification_id)

    async def notification(self, event):
        """Send notification to WebSocket."""
        await self.send_json(
            {
                "type": "notification",
                "notification": event["notification"],
            }
        )

    async def presence(self, event):
        """Send presence update to WebSocket."""
        await self.send_json(
            {
                "type": "presence",
                "user_id": event["user_id"],
                "status": event["status"],
            }
        )

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read."""
        from notifications.models import Notification

        try:
            notification = Notification.objects.get(
                id=notification_id,
                user_id=self.user_id,
            )
            notification.mark_as_read()
        except Notification.DoesNotExist:
            pass


class ProjectConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for project room.

    Users in this room receive real-time task updates.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope.get("user")
        project_id = self.scope["url_route"]["kwargs"]["project_id"]

        if not user or not user.is_authenticated:
            await self.close()
            return

        # Verify project access
        has_access = await self.check_project_access(user.id, project_id)
        if not has_access:
            await self.close()
            return

        self.user_id = str(user.id)
        self.project_id = project_id
        self.room_group_name = f"project_{project_id}"

        # Join project group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Notify others of presence
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "user_id": self.user_id,
            },
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "room_group_name"):
            # Notify others
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_left",
                    "user_id": self.user_id,
                },
            )

            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content):
        """Handle incoming messages (e.g., cursor position for collaboration)."""
        message_type = content.get("type")

        if message_type == "cursor_move":
            # Broadcast cursor position to others
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "cursor_update",
                    "user_id": self.user_id,
                    "position": content.get("position"),
                },
            )

    async def task_update(self, event):
        """Send task update to WebSocket."""
        await self.send_json(
            {
                "type": "task_update",
                "action": event["action"],
                "task_id": event["task_id"],
                "data": event.get("data", {}),
            }
        )

    async def user_joined(self, event):
        """Notify user joined."""
        await self.send_json(
            {
                "type": "user_joined",
                "user_id": event["user_id"],
            }
        )

    async def user_left(self, event):
        """Notify user left."""
        await self.send_json(
            {
                "type": "user_left",
                "user_id": event["user_id"],
            }
        )

    async def cursor_update(self, event):
        """Send cursor update (for collaboration)."""
        # Don't send to self
        if event["user_id"] != self.user_id:
            await self.send_json(
                {
                    "type": "cursor_update",
                    "user_id": event["user_id"],
                    "position": event["position"],
                }
            )

    @database_sync_to_async
    def check_project_access(self, user_id, project_id):
        """Check if user has access to project."""
        try:
            project = Project.objects.get(id=project_id)

            # Check org membership
            is_org_member = Membership.objects.filter(
                user_id=user_id,
                organization=project.organization,
                is_active=True,
            ).exists()

            if not is_org_member:
                return False

            # Check if admin or public project or project member
            membership = Membership.objects.get(
                user_id=user_id,
                organization=project.organization,
            )

            if membership.is_admin:
                return True

            if project.is_public:
                return True

            return ProjectMember.objects.filter(
                project=project,
                user_id=user_id,
            ).exists()

        except (Project.DoesNotExist, Membership.DoesNotExist):
            return False


class TaskConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for task room.

    Users viewing a task receive real-time comment updates and typing indicators.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope.get("user")
        task_id = self.scope["url_route"]["kwargs"]["task_id"]

        if not user or not user.is_authenticated:
            await self.close()
            return

        # Verify task access
        has_access = await self.check_task_access(user.id, task_id)
        if not has_access:
            await self.close()
            return

        self.user_id = str(user.id)
        self.task_id = task_id
        self.room_group_name = f"task_{task_id}"

        # Join task group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "room_group_name"):
            # Clear typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_indicator",
                    "user_id": self.user_id,
                    "is_typing": False,
                },
            )

            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content):
        """Handle incoming messages."""
        message_type = content.get("type")

        if message_type == "typing":
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_indicator",
                    "user_id": self.user_id,
                    "is_typing": content.get("is_typing", False),
                },
            )

    async def comment_added(self, event):
        """Send new comment notification."""
        await self.send_json(
            {
                "type": "comment_added",
                "comment_id": event["comment_id"],
                "author_id": event["author_id"],
            }
        )

    async def comment_updated(self, event):
        """Send comment update notification."""
        await self.send_json(
            {
                "type": "comment_updated",
                "comment_id": event["comment_id"],
            }
        )

    async def comment_deleted(self, event):
        """Send comment deletion notification."""
        await self.send_json(
            {
                "type": "comment_deleted",
                "comment_id": event["comment_id"],
            }
        )

    async def typing_indicator(self, event):
        """Send typing indicator."""
        # Don't send to self
        if event["user_id"] != self.user_id:
            await self.send_json(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )

    @database_sync_to_async
    def check_task_access(self, user_id, task_id):
        """Check if user has access to task."""
        try:
            task = Task.objects.select_related("project", "project__organization").get(id=task_id)
            project = task.project

            # Check org membership
            is_org_member = Membership.objects.filter(
                user_id=user_id,
                organization=project.organization,
                is_active=True,
            ).exists()

            if not is_org_member:
                return False

            membership = Membership.objects.get(
                user_id=user_id,
                organization=project.organization,
            )

            if membership.is_admin:
                return True

            if project.is_public:
                return True

            return ProjectMember.objects.filter(
                project=project,
                user_id=user_id,
            ).exists()

        except (Task.DoesNotExist, Membership.DoesNotExist):
            return False
