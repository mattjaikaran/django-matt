"""
Pydantic schemas for multi-tenancy models.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# Organization Schemas
# ============================================================================

class OrganizationBase(BaseModel):
    """Base schema for Organization."""
    
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    logo_url: Optional[str] = None
    settings: dict = Field(default_factory=dict)


class OrganizationCreate(OrganizationBase):
    """Schema for creating an Organization."""
    
    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an Organization."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


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
    description: Optional[str] = None
    logo_url: Optional[str] = None
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
    description: Optional[str] = None
    settings: dict = Field(default_factory=dict)
    is_default: bool = False


class TeamCreate(TeamBase):
    """Schema for creating a Team."""
    
    organization_id: Optional[uuid.UUID] = None  # Can be inferred from context


class TeamUpdate(BaseModel):
    """Schema for updating a Team."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    settings: Optional[dict] = None
    is_default: Optional[bool] = None


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
    description: Optional[str] = None
    role: Optional[str] = None  # User's role in this team (if member)
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
    organization_id: Optional[uuid.UUID] = None  # Can be inferred from context


class MembershipUpdate(BaseModel):
    """Schema for updating a Membership."""
    
    role: str = Field(..., pattern=r"^(owner|admin|member|viewer)$")


class MembershipResponse(MembershipBase):
    """Schema for Membership response."""
    
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    invited_by_id: Optional[uuid.UUID] = None
    joined_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    """Schema for member info (includes user details)."""
    
    id: uuid.UUID  # Membership ID
    user_id: uuid.UUID
    email: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
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
    team_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None  # Can be inferred from context


class InvitationResponse(BaseModel):
    """Schema for Invitation response."""
    
    id: uuid.UUID
    organization_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    email: str
    role: str
    status: str
    invited_by_id: Optional[uuid.UUID] = None
    expires_at: datetime
    accepted_at: Optional[datetime] = None
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
    
    organization_id: Optional[uuid.UUID] = None
    organization_slug: Optional[str] = None
    organization_name: Optional[str] = None
    team_id: Optional[uuid.UUID] = None
    team_slug: Optional[str] = None
    user_role: Optional[str] = None
    
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
    
    organization_id: Optional[uuid.UUID] = None
    organization_slug: Optional[str] = None


class SwitchTeamRequest(BaseModel):
    """Schema for switching to a different team."""
    
    team_id: Optional[uuid.UUID] = None
    team_slug: Optional[str] = None
