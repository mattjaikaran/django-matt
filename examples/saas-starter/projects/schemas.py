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
from uuid import UUID

from pydantic import BaseModel, Field

from core.schemas import TeamResponse, UserMiniResponse

# =============================================================================
# Label Schemas
# =============================================================================

class LabelBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6B7280", pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelCreate(LabelBase):
    description: str = ""
    project_id: UUID | None = None  # If None, org-level label


class LabelUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    description: str | None = None


class LabelResponse(LabelBase):
    id: UUID
    description: str = ""
    organization_id: UUID
    project_id: UUID | None = None
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
    start_date: date | None = None
    due_date: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    status: str | None = None
    is_public: bool | None = None
    start_date: date | None = None
    due_date: date | None = None
    settings: dict | None = None
    team_ids: list[UUID] | None = None


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
    start_date: date | None = None
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Project with owner, teams, and members."""
    owner: UserMiniResponse | None = None
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
    assignee_id: UUID | None = None
    parent_id: UUID | None = None
    status: str = "todo"
    priority: str = "medium"
    labels: list[str] = []
    estimated_hours: Decimal | None = None
    start_date: date | None = None
    due_date: date | None = None
    custom_fields: dict = {}


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    position: int | None = None
    labels: list[str] | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    start_date: date | None = None
    due_date: date | None = None
    custom_fields: dict | None = None


class TaskBulkUpdate(BaseModel):
    """Update multiple tasks at once."""
    task_ids: list[UUID]
    status: str | None = None
    priority: str | None = None
    assignee_id: UUID | None = None
    labels_add: list[str] = []
    labels_remove: list[str] = []


class TaskMove(BaseModel):
    """Move task to different status/position."""
    status: str
    position: int


class TaskResponse(TaskBase):
    id: UUID
    project_id: UUID
    parent_id: UUID | None = None
    description: str = ""
    assignee: UserMiniResponse | None = None
    reporter: UserMiniResponse | None = None
    status: str
    priority: str
    position: int
    labels: list[str] = []
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    start_date: date | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
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
    assignee: UserMiniResponse | None = None
    due_date: date | None = None
    is_overdue: bool = False

    class Config:
        from_attributes = True


# =============================================================================
# Comment Schemas
# =============================================================================

class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    parent_id: UUID | None = None
    attachments: list[dict] = []


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1)


class CommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    author: UserMiniResponse | None = None
    parent_id: UUID | None = None
    content: str
    content_html: str = ""
    reactions: dict = {}
    attachments: list[dict] = []
    is_edited: bool
    edited_at: datetime | None = None
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
    user: UserMiniResponse | None = None
    action: str
    field: str = ""
    old_value: dict | None = None
    new_value: dict | None = None
    metadata: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Filter and List Schemas
# =============================================================================

class TaskFilter(BaseModel):
    """Task list filters."""
    project_id: UUID | None = None
    status: list[str] | None = None
    priority: list[str] | None = None
    assignee_id: UUID | None = None
    reporter_id: UUID | None = None
    labels: list[str] | None = None
    is_overdue: bool | None = None
    has_due_date: bool | None = None
    due_before: date | None = None
    due_after: date | None = None
    search: str | None = None
    parent_id: UUID | None = None  # None = top-level tasks only


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
    status: list[str] | None = None
    team_id: UUID | None = None
    owner_id: UUID | None = None
    search: str | None = None


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
