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
# Controllers
from django_matt.multitenancy.controllers import (
    InvitationController,
    MembershipController,
    OrganizationController,
    TeamController,
)

# Decorators
from django_matt.multitenancy.decorators import (
    requires_min_org_role,
    requires_org_admin,
    requires_org_membership,
    requires_org_owner,
    requires_org_role,
    requires_organization,
    requires_team_membership,
)

# Middleware
from django_matt.multitenancy.middleware import (
    TenantMiddleware,
    TenantMiddlewareAsync,
    get_current_organization,
    get_current_tenant,
    set_current_tenant,
)
from django_matt.multitenancy.models import (
    Invitation,
    InvitationStatus,
    Membership,
    MembershipRole,
    Organization,
    Team,
)

# Schemas
from django_matt.multitenancy.schemas import (
    InvitationCreate,
    InvitationResponse,
    MembershipBase,
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
    OrganizationBase,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    TeamBase,
    TeamCreate,
    TeamResponse,
    TeamUpdate,
    TenantContext,
)

# Utilities
from django_matt.multitenancy.utils import (
    create_organization_with_owner,
    create_team_with_members,
    get_organization_members,
    get_team_members,
    get_user_organizations,
    get_user_teams,
    transfer_ownership,
    user_can_manage_team,
    user_is_org_admin,
    user_is_org_owner,
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
