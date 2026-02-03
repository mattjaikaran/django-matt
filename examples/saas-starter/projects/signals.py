"""
Signal handlers for projects app.

Handles:
- Task status changes
- Comment mentions
- Activity logging
"""

import re
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.models import User
from notifications.models import Notification, NotificationType
from .models import Task, TaskStatus, Comment, TaskActivity


# Track pre-save state for change detection
_task_pre_save_state = {}


@receiver(pre_save, sender=Task)
def track_task_changes(sender, instance, **kwargs):
    """
    Track task state before save for change detection.
    """
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            _task_pre_save_state[instance.pk] = {
                "status": old.status,
                "assignee_id": str(old.assignee_id) if old.assignee_id else None,
                "priority": old.priority,
                "due_date": old.due_date,
            }
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def handle_task_changes(sender, instance, created, **kwargs):
    """
    Handle task changes - create activity logs and notifications.
    """
    if created:
        # Log creation activity
        TaskActivity.objects.create(
            task=instance,
            user=instance.reporter,
            action="created",
        )

        # Notify assignee if assigned on creation
        if instance.assignee and instance.assignee != instance.reporter:
            Notification.objects.create(
                user=instance.assignee,
                organization=instance.organization,
                type=NotificationType.TASK_ASSIGNED,
                title="New task assigned to you",
                message=f'You have been assigned to "{instance.title}"',
                actor=instance.reporter,
                resource_type="task",
                resource_id=str(instance.id),
                action_url=f"/projects/{instance.project.slug}/tasks/{instance.id}",
            )
        return

    # Check for changes
    old_state = _task_pre_save_state.pop(instance.pk, {})

    # Status change
    if old_state.get("status") != instance.status:
        TaskActivity.objects.create(
            task=instance,
            user=None,  # Will be set by the view
            action="status_changed",
            field="status",
            old_value=old_state.get("status"),
            new_value=instance.status,
        )

        # Notify reporter when task is completed
        if instance.status == TaskStatus.DONE and instance.reporter:
            if instance.assignee and instance.assignee != instance.reporter:
                Notification.objects.create(
                    user=instance.reporter,
                    organization=instance.organization,
                    type=NotificationType.TASK_COMPLETED,
                    title="Task completed",
                    message=f'"{instance.title}" has been marked as complete',
                    actor=instance.assignee,
                    resource_type="task",
                    resource_id=str(instance.id),
                    action_url=f"/projects/{instance.project.slug}/tasks/{instance.id}",
                )

    # Assignee change
    old_assignee = old_state.get("assignee_id")
    new_assignee = str(instance.assignee_id) if instance.assignee_id else None

    if old_assignee != new_assignee:
        TaskActivity.objects.create(
            task=instance,
            user=None,
            action="assigned",
            field="assignee",
            old_value=old_assignee,
            new_value=new_assignee,
        )

        # Notify new assignee
        if instance.assignee:
            Notification.objects.create(
                user=instance.assignee,
                organization=instance.organization,
                type=NotificationType.TASK_ASSIGNED,
                title="Task assigned to you",
                message=f'You have been assigned to "{instance.title}"',
                resource_type="task",
                resource_id=str(instance.id),
                action_url=f"/projects/{instance.project.slug}/tasks/{instance.id}",
            )


@receiver(post_save, sender=Comment)
def handle_new_comment(sender, instance, created, **kwargs):
    """
    Handle new comments - extract mentions and create notifications.
    """
    if not created:
        return

    # Log activity
    TaskActivity.objects.create(
        task=instance.task,
        user=instance.author,
        action="commented",
        metadata={"comment_id": str(instance.id)},
    )

    # Extract mentions from content (format: @username or @[User Name])
    mention_pattern = r"@(\w+)|@\[([^\]]+)\]"
    mentions = re.findall(mention_pattern, instance.content)

    mentioned_users = set()
    for username, display_name in mentions:
        name = username or display_name
        # Try to find user by username part of email or full name
        users = User.objects.filter(
            memberships__organization=instance.organization,
            memberships__is_active=True,
        ).filter(
            models.Q(email__istartswith=name) |
            models.Q(first_name__iexact=name) |
            models.Q(last_name__iexact=name)
        )[:5]  # Limit matches

        for user in users:
            if user != instance.author:
                mentioned_users.add(user)
                instance.mentions.add(user)

    # Notify mentioned users
    for user in mentioned_users:
        Notification.objects.create(
            user=user,
            organization=instance.organization,
            type=NotificationType.TASK_MENTIONED,
            title="You were mentioned in a comment",
            message=f'{instance.author.display_name} mentioned you in "{instance.task.title}"',
            actor=instance.author,
            resource_type="comment",
            resource_id=str(instance.id),
            action_url=f"/projects/{instance.task.project.slug}/tasks/{instance.task.id}#comment-{instance.id}",
        )

    # Notify task assignee about new comment (if not the author)
    if instance.task.assignee and instance.task.assignee != instance.author:
        if instance.task.assignee not in mentioned_users:
            Notification.objects.create(
                user=instance.task.assignee,
                organization=instance.organization,
                type=NotificationType.TASK_COMMENTED,
                title="New comment on your task",
                message=f'{instance.author.display_name} commented on "{instance.task.title}"',
                actor=instance.author,
                resource_type="comment",
                resource_id=str(instance.id),
                action_url=f"/projects/{instance.task.project.slug}/tasks/{instance.task.id}#comment-{instance.id}",
            )


# Import models needed for signals
from django.db import models
