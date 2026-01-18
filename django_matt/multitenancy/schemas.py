"""
Pydantic schemas for multi-tenancy models.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# ============================================================================
# Organization Schemas
# ============================================================================


class OrganizationBase(BaseModel):
    """Base schema for Organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    logo_url: str | None = None
    settings: dict = Field(default_factory=dict)


class OrganizationCreate(OrganizationBase):
    """Schema for creating an Organization."""


class OrganizationUpdate(BaseModel):
    """Schema for updating an Organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    logo_url: str | None = None
    settings: dict | None = None
    is_active: bool | None = None


class OrganizationResponse(OrganizationBase):
    """Schema for Organization response."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    """Schema for listing organizations with membership info."""

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    role: str  # User's role in this organization
    is_active: bool

    model_config = {"from_attributes": True}


# ============================================================================
# Team Schemas
# ============================================================================


class TeamBase(BaseModel):
    """Base schema for Team."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    settings: dict = Field(default_factory=dict)
    is_default: bool = False


class TeamCreate(TeamBase):
    """Schema for creating a Team."""

    organization_id: uuid.UUID | None = None  # Can be inferred from context


class TeamUpdate(BaseModel):
    """Schema for updating a Team."""

    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    settings: dict | None = None
    is_default: bool | None = None


class TeamResponse(TeamBase):
    """Schema for Team response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    """Schema for listing teams with membership info."""

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    role: str | None = None  # User's role in this team (if member)
    is_default: bool
    member_count: int = 0

    model_config = {"from_attributes": True}


# ============================================================================
# Membership Schemas
# ============================================================================


class MembershipBase(BaseModel):
    """Base schema for Membership."""

    role: str = Field(default="member", pattern=r"^(owner|admin|member|viewer)$")


class MembershipCreate(MembershipBase):
    """Schema for creating a Membership."""

    user_id: uuid.UUID
    organization_id: uuid.UUID | None = None  # Can be inferred from context


class MembershipUpdate(BaseModel):
    """Schema for updating a Membership."""

    role: str = Field(..., pattern=r"^(owner|admin|member|viewer)$")


class MembershipResponse(MembershipBase):
    """Schema for Membership response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    invited_by_id: uuid.UUID | None = None
    joined_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    """Schema for member info (includes user details)."""

    id: uuid.UUID  # Membership ID
    user_id: uuid.UUID
    email: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class TeamMembershipCreate(BaseModel):
    """Schema for adding a user to a team."""

    user_id: uuid.UUID
    role: str = Field(default="member", pattern=r"^(owner|admin|member|viewer)$")


class TeamMembershipResponse(BaseModel):
    """Schema for team membership response."""

    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Invitation Schemas
# ============================================================================


class InvitationCreate(BaseModel):
    """Schema for creating an Invitation."""

    email: EmailStr
    role: str = Field(default="member", pattern=r"^(owner|admin|member|viewer)$")
    team_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None  # Can be inferred from context


class InvitationResponse(BaseModel):
    """Schema for Invitation response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    team_id: uuid.UUID | None = None
    email: str
    role: str
    status: str
    invited_by_id: uuid.UUID | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitationAcceptRequest(BaseModel):
    """Schema for accepting an invitation."""

    token: str


class InvitationResendRequest(BaseModel):
    """Schema for resending an invitation."""

    invitation_id: uuid.UUID


# ============================================================================
# Tenant Context Schemas
# ============================================================================


class TenantContext(BaseModel):
    """Schema for current tenant context."""

    organization_id: uuid.UUID | None = None
    organization_slug: str | None = None
    organization_name: str | None = None
    team_id: uuid.UUID | None = None
    team_slug: str | None = None
    user_role: str | None = None

    @property
    def has_organization(self) -> bool:
        return self.organization_id is not None

    @property
    def has_team(self) -> bool:
        return self.team_id is not None


# ============================================================================
# Switch Organization/Team Schemas
# ============================================================================


class SwitchOrganizationRequest(BaseModel):
    """Schema for switching to a different organization."""

    organization_id: uuid.UUID | None = None
    organization_slug: str | None = None


class SwitchTeamRequest(BaseModel):
    """Schema for switching to a different team."""

    team_id: uuid.UUID | None = None
    team_slug: str | None = None
