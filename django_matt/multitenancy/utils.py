# file-length-max: 500
"""
Utility functions for multi-tenancy operations.

Provides both sync (for management commands and non-async contexts) and async
(for ASGI controllers and async views) variants of key utility functions.
"""

from typing import TYPE_CHECKING, Optional

from django.db.models import QuerySet

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from django_matt.multitenancy.models import (
        Membership,
        Organization,
        Team,
        TeamMembership,
    )


def get_user_organizations(user: "AbstractUser") -> QuerySet["Organization"]:
    """
    Get all organizations a user is a member of.

    Args:
        user: The user to get organizations for

    Returns:
        QuerySet of Organizations
    """
    from django_matt.multitenancy.models import Organization

    return Organization.objects.filter(
        memberships__user=user,
        is_active=True,
    ).distinct()


def get_user_teams(
    user: "AbstractUser",
    organization: Optional["Organization"] = None,
) -> QuerySet["Team"]:
    """
    Get all teams a user is a member of.

    Args:
        user: The user to get teams for
        organization: Optional organization to filter by

    Returns:
        QuerySet of Teams
    """
    from django_matt.multitenancy.models import Team

    queryset = Team.objects.filter(
        memberships__user=user,
    )

    if organization:
        queryset = queryset.filter(organization=organization)

    return queryset.distinct()


def get_organization_members(
    organization: "Organization",
    role: str | None = None,
) -> QuerySet["Membership"]:
    """
    Get all members of an organization.

    Args:
        organization: The organization
        role: Optional role to filter by

    Returns:
        QuerySet of Memberships with related user
    """
    queryset = organization.memberships.select_related("user")

    if role:
        queryset = queryset.filter(role=role)

    return queryset


def get_team_members(
    team: "Team",
    role: str | None = None,
) -> QuerySet["TeamMembership"]:
    """
    Get all members of a team.

    Args:
        team: The team
        role: Optional role to filter by

    Returns:
        QuerySet of TeamMemberships with related user
    """
    queryset = team.memberships.select_related("user", "organization_membership")

    if role:
        queryset = queryset.filter(role=role)

    return queryset


def user_is_org_admin(user: "AbstractUser", organization: "Organization") -> bool:
    """
    Check if a user is an admin (or owner) of an organization.

    Sync version — safe for management commands and non-async contexts.

    Args:
        user: The user to check
        organization: The organization

    Returns:
        True if user is admin or owner
    """
    from django_matt.multitenancy.models import MembershipRole

    return organization.memberships.filter(
        user=user,
        role__in=[MembershipRole.OWNER.value, MembershipRole.ADMIN.value],
    ).exists()


async def auser_is_org_admin(user: "AbstractUser", organization: "Organization") -> bool:
    """
    Async check if a user is an admin (or owner) of an organization.

    Async version — use this in async controllers and views.

    Args:
        user: The user to check
        organization: The organization

    Returns:
        True if user is admin or owner
    """
    from django_matt.multitenancy.models import MembershipRole

    return await organization.memberships.filter(
        user=user,
        role__in=[MembershipRole.OWNER.value, MembershipRole.ADMIN.value],
    ).aexists()


def user_is_org_owner(user: "AbstractUser", organization: "Organization") -> bool:
    """
    Check if a user is the owner of an organization.

    Sync version — safe for management commands and non-async contexts.

    Args:
        user: The user to check
        organization: The organization

    Returns:
        True if user is owner
    """
    from django_matt.multitenancy.models import MembershipRole

    return organization.memberships.filter(
        user=user,
        role=MembershipRole.OWNER.value,
    ).exists()


async def auser_is_org_owner(user: "AbstractUser", organization: "Organization") -> bool:
    """
    Async check if a user is the owner of an organization.

    Async version — use this in async controllers and views.

    Args:
        user: The user to check
        organization: The organization

    Returns:
        True if user is owner
    """
    from django_matt.multitenancy.models import MembershipRole

    return await organization.memberships.filter(
        user=user,
        role=MembershipRole.OWNER.value,
    ).aexists()


def user_can_manage_team(
    user: "AbstractUser",
    team: "Team",
) -> bool:
    """
    Check if a user can manage a team.

    A user can manage a team if they are:
    - An owner or admin of the organization
    - An owner or admin of the team

    Sync version — safe for management commands and non-async contexts.

    Args:
        user: The user to check
        team: The team

    Returns:
        True if user can manage the team
    """
    from django_matt.multitenancy.models import MembershipRole

    # Check organization-level access
    if user_is_org_admin(user, team.organization):
        return True

    # Check team-level access
    return team.memberships.filter(
        user=user,
        role__in=[MembershipRole.OWNER.value, MembershipRole.ADMIN.value],
    ).exists()


async def auser_can_manage_team(
    user: "AbstractUser",
    team: "Team",
) -> bool:
    """
    Async check if a user can manage a team.

    A user can manage a team if they are:
    - An owner or admin of the organization
    - An owner or admin of the team

    Async version — use this in async controllers and views.

    Args:
        user: The user to check
        team: The team

    Returns:
        True if user can manage the team
    """
    from django_matt.multitenancy.models import MembershipRole

    # Check organization-level access first
    if await auser_is_org_admin(user, team.organization):
        return True

    # Check team-level access
    return await team.memberships.filter(
        user=user,
        role__in=[MembershipRole.OWNER.value, MembershipRole.ADMIN.value],
    ).aexists()


def user_has_org_permission(
    user: "AbstractUser",
    organization: "Organization",
    required_role: str,
) -> bool:
    """
    Check if a user has at least the required role in an organization.

    Args:
        user: The user to check
        organization: The organization
        required_role: The minimum required role

    Returns:
        True if user has the required role or higher
    """
    from django_matt.multitenancy.models import MembershipRole

    membership = organization.memberships.filter(user=user).first()
    if not membership:
        return False

    required_priority = MembershipRole.get_priority(required_role)
    user_priority = MembershipRole.get_priority(membership.role)

    return user_priority >= required_priority


def create_organization_with_owner(
    name: str,
    slug: str,
    owner: "AbstractUser",
    **kwargs,
) -> "Organization":
    """
    Create a new organization with the specified user as owner.

    Sync version — safe for management commands, fixtures, and non-async contexts.

    Args:
        name: Organization name
        slug: Organization slug
        owner: User to set as owner
        **kwargs: Additional fields for Organization

    Returns:
        The created Organization
    """
    from django_matt.multitenancy.models import MembershipRole, Organization

    organization = Organization.objects.create(
        name=name,
        slug=slug,
        **kwargs,
    )

    organization.add_member(user=owner, role=MembershipRole.OWNER.value)

    return organization


async def acreate_organization_with_owner(
    name: str,
    slug: str,
    owner: "AbstractUser",
    **kwargs,
) -> "Organization":
    """
    Async create a new organization with the specified user as owner.

    Async version — use this in async controllers and views.

    Args:
        name: Organization name
        slug: Organization slug
        owner: User to set as owner
        **kwargs: Additional fields for Organization

    Returns:
        The created Organization
    """
    from django_matt.multitenancy.models import Membership, MembershipRole, Organization

    organization = await Organization.objects.acreate(
        name=name,
        slug=slug,
        **kwargs,
    )

    await Membership.objects.acreate(
        organization=organization,
        user=owner,
        role=MembershipRole.OWNER.value,
    )

    return organization


def create_team_with_members(
    organization: "Organization",
    name: str,
    slug: str,
    members: list["AbstractUser"] | None = None,
    **kwargs,
) -> "Team":
    """
    Create a new team with optional initial members.

    Args:
        organization: Parent organization
        name: Team name
        slug: Team slug
        members: Optional list of users to add as members
        **kwargs: Additional fields for Team

    Returns:
        The created Team
    """
    from django_matt.multitenancy.models import Team

    team = Team.objects.create(
        organization=organization,
        name=name,
        slug=slug,
        **kwargs,
    )

    if members:
        for user in members:
            try:
                team.add_member(user)
            except ValueError:
                # User is not a member of the organization, skip
                pass

    return team


def transfer_ownership(
    organization: "Organization",
    current_owner: "AbstractUser",
    new_owner: "AbstractUser",
) -> bool:
    """
    Transfer ownership of an organization to another user.

    The new owner must already be a member of the organization.
    The current owner will be demoted to admin.

    Args:
        organization: The organization
        current_owner: Current owner
        new_owner: User to transfer ownership to

    Returns:
        True if transfer was successful

    Raises:
        ValueError: If new_owner is not a member or current_owner is not the owner
    """
    from django_matt.multitenancy.models import Membership, MembershipRole

    # Verify current owner
    current_membership = Membership.objects.filter(
        organization=organization,
        user=current_owner,
        role=MembershipRole.OWNER.value,
    ).first()

    if not current_membership:
        raise ValueError("Current user is not the owner of this organization")

    # Verify new owner is a member
    new_membership = Membership.objects.filter(
        organization=organization,
        user=new_owner,
    ).first()

    if not new_membership:
        raise ValueError("New owner must be a member of the organization")

    # Transfer ownership
    current_membership.role = MembershipRole.ADMIN.value
    current_membership.save(update_fields=["role", "updated_at"])

    new_membership.role = MembershipRole.OWNER.value
    new_membership.save(update_fields=["role", "updated_at"])

    return True
