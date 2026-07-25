"""
Project management models for SaaS Starter.

Includes:
- Project model with organization association
- Task model with assignments and status
- Comment model with mentions
- Activity tracking
"""

import uuid

from django.db import models
from django.utils import timezone

from core.models import Organization, Team, User


class ProjectStatus(models.TextChoices):
    """Project status choices."""

    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On Hold"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class Project(models.Model):
    """
    Project model for organizing tasks.

    Features:
    - Organization scoping
    - Team assignment
    - Status tracking
    - Metadata and settings
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, db_index=True)
    description = models.TextField(blank=True)

    # Association
    teams = models.ManyToManyField(Team, related_name="projects", blank=True)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="owned_projects"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.ACTIVE,
    )

    # Settings
    settings = models.JSONField(default=dict)
    color = models.CharField(max_length=7, default="#3B82F6")  # Hex color
    icon = models.CharField(max_length=50, default="folder")

    # Visibility
    is_public = models.BooleanField(default=False)  # Within organization

    # Dates
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        unique_together = [["organization", "slug"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name} / {self.name}"

    @property
    def task_count(self):
        return self.tasks.count()

    @property
    def completed_task_count(self):
        return self.tasks.filter(status=TaskStatus.DONE).count()

    @property
    def progress_percentage(self):
        total = self.task_count
        if total == 0:
            return 0
        return int((self.completed_task_count / total) * 100)


class TaskStatus(models.TextChoices):
    """Task status choices (Kanban-style)."""

    BACKLOG = "backlog", "Backlog"
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    IN_REVIEW = "in_review", "In Review"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


class TaskPriority(models.TextChoices):
    """Task priority levels."""

    URGENT = "urgent", "Urgent"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class Task(models.Model):
    """
    Task model for project work items.

    Features:
    - Project and organization scoping
    - Assignment to users
    - Status and priority tracking
    - Due dates and time estimation
    - Labels and custom fields
    - Subtask support
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subtasks"
    )

    # Content
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    # Assignment
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks"
    )
    reporter = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="reported_tasks"
    )

    # Status and Priority
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM,
    )

    # Ordering
    position = models.IntegerField(default=0)  # For drag-and-drop ordering

    # Time tracking
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # Dates
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Labels
    labels = models.JSONField(default=list)  # ["bug", "feature", "urgent"]

    # Custom fields (flexible schema)
    custom_fields = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tasks"
        ordering = ["position", "-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assignee", "status"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return self.title

    @property
    def organization(self):
        return self.project.organization

    @property
    def is_overdue(self):
        if self.due_date and self.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
            return self.due_date < timezone.now().date()
        return False

    @property
    def subtask_count(self):
        return self.subtasks.count()

    @property
    def comment_count(self):
        return self.comments.count()

    def mark_complete(self):
        """Mark task as complete."""
        self.status = TaskStatus.DONE
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class Comment(models.Model):
    """
    Comment model for task discussions.

    Features:
    - Rich text content
    - User mentions tracking
    - Reactions support
    - Edit history
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    # Content
    content = models.TextField()
    content_html = models.TextField(blank=True)  # Rendered HTML

    # Mentions (extracted from content)
    mentions = models.ManyToManyField(User, related_name="mentioned_in_comments", blank=True)

    # Reactions
    reactions = models.JSONField(default=dict)  # {"thumbs_up": ["user_id1", "user_id2"]}

    # Attachments
    attachments = models.JSONField(default=list)  # [{"name": "file.pdf", "url": "..."}]

    # Edit tracking
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comments"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"

    @property
    def organization(self):
        return self.task.project.organization

    def add_reaction(self, user_id: str, reaction: str):
        """Add a reaction from a user."""
        if reaction not in self.reactions:
            self.reactions[reaction] = []
        if user_id not in self.reactions[reaction]:
            self.reactions[reaction].append(user_id)
            self.save(update_fields=["reactions", "updated_at"])

    def remove_reaction(self, user_id: str, reaction: str):
        """Remove a reaction from a user."""
        if reaction in self.reactions and user_id in self.reactions[reaction]:
            self.reactions[reaction].remove(user_id)
            if not self.reactions[reaction]:
                del self.reactions[reaction]
            self.save(update_fields=["reactions", "updated_at"])


class TaskActivity(models.Model):
    """
    Activity log for task changes.

    Features:
    - Change tracking
    - Before/after values
    - User attribution
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activities")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # Action type
    action = models.CharField(max_length=50)  # "status_changed", "assigned", "commented", etc.
    field = models.CharField(max_length=50, blank=True)  # Field that was changed

    # Change details
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "task_activities"
        ordering = ["-created_at"]
        verbose_name_plural = "Task activities"

    def __str__(self):
        return f"{self.action} on {self.task} by {self.user}"


class Label(models.Model):
    """
    Label/tag for organizing tasks.

    Features:
    - Organization-scoped
    - Color coding
    - Optional project scoping
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="labels")
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True, related_name="labels"
    )

    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#6B7280")  # Hex color
    description = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "labels"
        ordering = ["name"]
        unique_together = [["organization", "name"]]

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    """
    Project-specific member with role.

    Features:
    - Project-level permissions
    - Different from org membership
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships")

    role = models.CharField(
        max_length=20,
        choices=[
            ("owner", "Owner"),
            ("editor", "Editor"),
            ("viewer", "Viewer"),
        ],
        default="editor",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_members"
        unique_together = [["project", "user"]]

    def __str__(self):
        return f"{self.user.email} - {self.project.name} ({self.role})"
