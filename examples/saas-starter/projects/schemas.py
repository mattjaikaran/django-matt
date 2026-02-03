"""
Pydantic schemas for projects app.

Includes:
- Project schemas
- Task schemas
- Comment schemas
- Label schemas
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from core.schemas import UserMiniResponse, OrganizationMiniResponse, TeamResponse


# =============================================================================
# Label Schemas
# =============================================================================

class LabelBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6B7280", pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelCreate(LabelBase):
    description: str = ""
    project_id: Optional[UUID] = None  # If None, org-level label


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None


class LabelResponse(LabelBase):
    id: UUID
    description: str = ""
    organization_id: UUID
    project_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Project Schemas
# =============================================================================

class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class ProjectCreate(ProjectBase):
    description: str = ""
    color: str = "#3B82F6"
    icon: str = "folder"
    team_ids: list[UUID] = []
    start_date: Optional[date] = None
    due_date: Optional[date] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    status: Optional[str] = None
    is_public: Optional[bool] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    settings: Optional[dict] = None
    team_ids: Optional[list[UUID]] = None


class ProjectResponse(ProjectBase):
    id: UUID
    organization_id: UUID
    description: str = ""
    status: str
    color: str
    icon: str
    is_public: bool
    task_count: int = 0
    completed_task_count: int = 0
    progress_percentage: int = 0
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Project with owner, teams, and members."""
    owner: Optional[UserMiniResponse] = None
    teams: list[TeamResponse] = []
    settings: dict = {}


class ProjectMiniResponse(BaseModel):
    """Minimal project info for references."""
    id: UUID
    name: str
    slug: str
    color: str
    icon: str

    class Config:
        from_attributes = True


# =============================================================================
# Project Member Schemas
# =============================================================================

class ProjectMemberCreate(BaseModel):
    user_id: UUID
    role: str = "editor"


class ProjectMemberUpdate(BaseModel):
    role: str


class ProjectMemberResponse(BaseModel):
    id: UUID
    project_id: UUID
    user: UserMiniResponse
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Task Schemas
# =============================================================================

class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class TaskCreate(TaskBase):
    description: str = ""
    assignee_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    status: str = "todo"
    priority: str = "medium"
    labels: list[str] = []
    estimated_hours: Optional[Decimal] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    custom_fields: dict = {}


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[UUID] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    position: Optional[int] = None
    labels: Optional[list[str]] = None
    estimated_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    custom_fields: Optional[dict] = None


class TaskBulkUpdate(BaseModel):
    """Update multiple tasks at once."""
    task_ids: list[UUID]
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[UUID] = None
    labels_add: list[str] = []
    labels_remove: list[str] = []


class TaskMove(BaseModel):
    """Move task to different status/position."""
    status: str
    position: int


class TaskResponse(TaskBase):
    id: UUID
    project_id: UUID
    parent_id: Optional[UUID] = None
    description: str = ""
    assignee: Optional[UserMiniResponse] = None
    reporter: Optional[UserMiniResponse] = None
    status: str
    priority: str
    position: int
    labels: list[str] = []
    estimated_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    is_overdue: bool = False
    subtask_count: int = 0
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    """Task with full details including custom fields."""
    project: ProjectMiniResponse
    custom_fields: dict = {}
    subtasks: list["TaskMiniResponse"] = []


class TaskMiniResponse(BaseModel):
    """Minimal task info for lists and references."""
    id: UUID
    title: str
    status: str
    priority: str
    assignee: Optional[UserMiniResponse] = None
    due_date: Optional[date] = None
    is_overdue: bool = False

    class Config:
        from_attributes = True


# =============================================================================
# Comment Schemas
# =============================================================================

class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    parent_id: Optional[UUID] = None
    attachments: list[dict] = []


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1)


class CommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    author: Optional[UserMiniResponse] = None
    parent_id: Optional[UUID] = None
    content: str
    content_html: str = ""
    reactions: dict = {}
    attachments: list[dict] = []
    is_edited: bool
    edited_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommentDetailResponse(CommentResponse):
    """Comment with mentions and replies."""
    mentions: list[UserMiniResponse] = []
    replies: list["CommentResponse"] = []


class ReactionRequest(BaseModel):
    reaction: str = Field(min_length=1, max_length=50)  # e.g., "thumbs_up", "heart"


# =============================================================================
# Activity Schemas
# =============================================================================

class TaskActivityResponse(BaseModel):
    id: UUID
    task_id: UUID
    user: Optional[UserMiniResponse] = None
    action: str
    field: str = ""
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    metadata: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Filter and List Schemas
# =============================================================================

class TaskFilter(BaseModel):
    """Task list filters."""
    project_id: Optional[UUID] = None
    status: Optional[list[str]] = None
    priority: Optional[list[str]] = None
    assignee_id: Optional[UUID] = None
    reporter_id: Optional[UUID] = None
    labels: Optional[list[str]] = None
    is_overdue: Optional[bool] = None
    has_due_date: Optional[bool] = None
    due_before: Optional[date] = None
    due_after: Optional[date] = None
    search: Optional[str] = None
    parent_id: Optional[UUID] = None  # None = top-level tasks only


class TaskListResponse(BaseModel):
    """Paginated task list."""
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class ProjectFilter(BaseModel):
    """Project list filters."""
    status: Optional[list[str]] = None
    team_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    search: Optional[str] = None


class ProjectListResponse(BaseModel):
    """Paginated project list."""
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


# =============================================================================
# Board/Kanban Schemas
# =============================================================================

class KanbanColumn(BaseModel):
    """Column in Kanban board."""
    status: str
    title: str
    tasks: list[TaskMiniResponse]
    task_count: int


class KanbanBoardResponse(BaseModel):
    """Full Kanban board."""
    project: ProjectMiniResponse
    columns: list[KanbanColumn]
