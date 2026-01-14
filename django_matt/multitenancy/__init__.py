"""
Django Matt Multi-Tenancy - B2B organization and team management.

Provides:
- Organization model for top-level tenant isolation
- Team model for grouping users within organizations
- Membership model with role-based access
- Invitation model for user onboarding
- Tenant context middleware for request-scoped tenant resolution

Example:
    from django_matt.multitenancy import (
        Organization,
        Team,
        Membership,
        Invitation,
        TenantMiddleware,
        get_current_tenant,
    )
    
    # In middleware
    MIDDLEWARE = [
        ...
        'django_matt.multitenancy.TenantMiddleware',
    ]
    
    # In views/controllers
    from django_matt.multitenancy import get_current_tenant
    
    @get("dashboard")
    def dashboard(self, request):
        org = get_current_tenant(request)
        return {"organization": org.name}
"""

# Models
from django_matt.multitenancy.models import (
    Organization,
    Team,
    Membership,
    Invitation,
    MembershipRole,
    InvitationStatus,
)

# Schemas
from django_matt.multitenancy.schemas import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    TeamBase,
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    MembershipBase,
    MembershipCreate,
    MembershipUpdate,
    MembershipResponse,
    InvitationCreate,
    InvitationResponse,
    TenantContext,
)

# Middleware
from django_matt.multitenancy.middleware import (
    TenantMiddleware,
    TenantMiddlewareAsync,
    get_current_tenant,
    get_current_organization,
    set_current_tenant,
)

# Controllers
from django_matt.multitenancy.controllers import (
    OrganizationController,
    TeamController,
    MembershipController,
    InvitationController,
)

# Utilities
from django_matt.multitenancy.utils import (
    get_user_organizations,
    get_user_teams,
    get_organization_members,
    get_team_members,
    user_is_org_admin,
    user_is_org_owner,
    user_can_manage_team,
    create_organization_with_owner,
    create_team_with_members,
    transfer_ownership,
)

# Decorators
from django_matt.multitenancy.decorators import (
    requires_organization,
    requires_org_membership,
    requires_org_role,
    requires_org_admin,
    requires_org_owner,
    requires_min_org_role,
    requires_team_membership,
)

__all__ = [
    # Models
    "Organization",
    "Team",
    "Membership",
    "Invitation",
    "MembershipRole",
    "InvitationStatus",
    # Schemas
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "TeamBase",
    "TeamCreate",
    "TeamUpdate",
    "TeamResponse",
    "MembershipBase",
    "MembershipCreate",
    "MembershipUpdate",
    "MembershipResponse",
    "InvitationCreate",
    "InvitationResponse",
    "TenantContext",
    # Middleware
    "TenantMiddleware",
    "TenantMiddlewareAsync",
    "get_current_tenant",
    "get_current_organization",
    "set_current_tenant",
    # Controllers
    "OrganizationController",
    "TeamController",
    "MembershipController",
    "InvitationController",
    # Utilities
    "get_user_organizations",
    "get_user_teams",
    "get_organization_members",
    "get_team_members",
    "user_is_org_admin",
    "user_is_org_owner",
    "user_can_manage_team",
    "create_organization_with_owner",
    "create_team_with_members",
    "transfer_ownership",
    # Decorators
    "requires_organization",
    "requires_org_membership",
    "requires_org_role",
    "requires_org_admin",
    "requires_org_owner",
    "requires_min_org_role",
    "requires_team_membership",
]
