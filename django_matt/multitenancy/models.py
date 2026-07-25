# file-length-max: 650
"""
Multi-tenancy models for B2B organization and team management.

Provides Organization, Team, Membership, and Invitation models
for multi-tenant applications.
"""

import secrets
import uuid
from datetime import timedelta
from enum import Enum

from django.conf import settings
from django.db import models
from django.utils import timezone


class MembershipRole(str, Enum):
    """Roles for organization/team membership."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

    @classmethod
    def choices(cls):
        return [(role.value, role.name.title()) for role in cls]

    @classmethod
    def get_priority(cls, role: str) -> int:
        """Get priority level for role (higher = more privileged)."""
        priorities = {
            cls.OWNER.value: 100,
            cls.ADMIN.value: 75,
            cls.MEMBER.value: 50,
            cls.VIEWER.value: 25,
        }
        return priorities.get(role, 0)

    @classmethod
    def can_manage(cls, actor_role: str, target_role: str) -> bool:
        """Check if actor_role can manage target_role."""
        return cls.get_priority(actor_role) > cls.get_priority(target_role)


class InvitationStatus(str, Enum):
    """Status for invitations."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @classmethod
    def choices(cls):
        return [(status.value, status.name.title()) for status in cls]


class Organization(models.Model):
    """
    Top-level tenant for B2B applications.

    Organizations are the primary isolation boundary for multi-tenant apps.
    Each organization can have multiple teams and members.

    Attributes:
        id: UUID primary key
        name: Display name of the organization
        slug: URL-safe identifier (unique)
        description: Optional description
        logo_url: Optional logo URL
        settings: JSON field for org-specific settings
        is_active: Whether the organization is active
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=255,
        help_text="Display name of the organization",
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-safe identifier for the organization",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the organization",
    )
    logo_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to the organization's logo",
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Organization-specific settings",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the organization is active",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["name"]
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def get_members(self):
        """Get all members of this organization."""
        return self.memberships.select_related("user")

    def get_teams(self):
        """Get all teams in this organization."""
        return self.teams.all()

    def get_owners(self):
        """Get all owners of this organization."""
        return self.memberships.filter(role=MembershipRole.OWNER.value)

    def get_admins(self):
        """Get all admins (and owners) of this organization."""
        return self.memberships.filter(
            role__in=[MembershipRole.OWNER.value, MembershipRole.ADMIN.value]
        )

    def add_member(
        self,
        user,
        role: str = MembershipRole.MEMBER.value,
        invited_by=None,
    ) -> "Membership":
        """Add a user as a member of this organization."""
        membership, created = Membership.objects.get_or_create(
            organization=self,
            user=user,
            defaults={
                "role": role,
                "invited_by": invited_by,
            },
        )
        if not created and membership.role != role:
            membership.role = role
            membership.save(update_fields=["role", "updated_at"])
        return membership

    def remove_member(self, user) -> bool:
        """Remove a user from this organization."""
        deleted, _ = Membership.objects.filter(
            organization=self,
            user=user,
        ).delete()
        return deleted > 0

    def is_member(self, user) -> bool:
        """Check if a user is a member of this organization."""
        return self.memberships.filter(user=user).exists()

    def get_member_role(self, user) -> str | None:
        """Get a user's role in this organization."""
        membership = self.memberships.filter(user=user).first()
        return membership.role if membership else None


class Team(models.Model):
    """
    Team within an organization.

    Teams allow grouping members within an organization for
    more granular access control and collaboration.

    Attributes:
        id: UUID primary key
        organization: Parent organization
        name: Display name of the team
        slug: URL-safe identifier (unique within org)
        description: Optional description
        settings: JSON field for team-specific settings
        is_default: Whether this is the default team for new members
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(
        max_length=255,
        help_text="Display name of the team",
    )
    slug = models.SlugField(
        max_length=100,
        help_text="URL-safe identifier for the team",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the team",
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Team-specific settings",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default team for new members",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["name"]
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        unique_together = [["organization", "slug"]]
        indexes = [
            models.Index(fields=["organization", "slug"]),
            models.Index(fields=["is_default"]),
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

    def get_members(self):
        """Get all members of this team."""
        return self.memberships.select_related("user", "organization_membership")

    def add_member(
        self,
        user,
        role: str = MembershipRole.MEMBER.value,
    ) -> "TeamMembership":
        """Add a user to this team."""
        # Ensure user is a member of the organization
        org_membership = Membership.objects.filter(
            organization=self.organization,
            user=user,
        ).first()

        if not org_membership:
            raise ValueError(f"User {user} is not a member of organization {self.organization}")

        team_membership, created = TeamMembership.objects.get_or_create(
            team=self,
            user=user,
            defaults={
                "role": role,
                "organization_membership": org_membership,
            },
        )
        return team_membership

    def remove_member(self, user) -> bool:
        """Remove a user from this team."""
        deleted, _ = TeamMembership.objects.filter(
            team=self,
            user=user,
        ).delete()
        return deleted > 0

    def is_member(self, user) -> bool:
        """Check if a user is a member of this team."""
        return self.memberships.filter(user=user).exists()


class Membership(models.Model):
    """
    Organization membership linking users to organizations.

    Attributes:
        id: UUID primary key
        organization: The organization
        user: The user
        role: Role in the organization (owner, admin, member, viewer)
        invited_by: User who invited this member (optional)
        joined_at: When the user joined
        updated_at: Last update timestamp
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=50,
        choices=MembershipRole.choices(),
        default=MembershipRole.MEMBER.value,
        help_text="Role in the organization",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_org_invitations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-joined_at"]
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        unique_together = [["organization", "user"]]
        indexes = [
            models.Index(fields=["organization", "user"]),
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.organization} ({self.role})"

    @property
    def is_owner(self) -> bool:
        return self.role == MembershipRole.OWNER.value

    @property
    def is_admin(self) -> bool:
        return self.role in [MembershipRole.OWNER.value, MembershipRole.ADMIN.value]

    @property
    def can_invite(self) -> bool:
        return self.is_admin

    @property
    def can_manage_members(self) -> bool:
        return self.is_admin

    @property
    def can_manage_teams(self) -> bool:
        return self.is_admin

    @property
    def can_delete_organization(self) -> bool:
        return self.is_owner


class TeamMembership(models.Model):
    """
    Team membership linking users to teams.

    Attributes:
        id: UUID primary key
        team: The team
        user: The user
        organization_membership: Link to org membership
        role: Role in the team
        joined_at: When the user joined the team
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    organization_membership = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=50,
        choices=MembershipRole.choices(),
        default=MembershipRole.MEMBER.value,
        help_text="Role in the team",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-joined_at"]
        verbose_name = "Team Membership"
        verbose_name_plural = "Team Memberships"
        unique_together = [["team", "user"]]
        indexes = [
            models.Index(fields=["team", "user"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.team} ({self.role})"


def generate_invitation_token() -> str:
    """Generate a secure random invitation token."""
    return secrets.token_urlsafe(32)


def get_invitation_expiry() -> timezone.datetime:
    """Get default invitation expiry (7 days from now)."""
    expiry_days = getattr(settings, "INVITATION_EXPIRY_DAYS", 7)
    return timezone.now() + timedelta(days=expiry_days)


class Invitation(models.Model):
    """
    Invitation to join an organization.

    Attributes:
        id: UUID primary key
        organization: The organization being invited to
        team: Optional team to add the user to
        email: Email address of the invitee
        role: Role to assign when accepted
        token: Unique invitation token
        invited_by: User who sent the invitation
        status: Current status of the invitation
        expires_at: When the invitation expires
        accepted_at: When the invitation was accepted
        created_at: Creation timestamp
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        help_text="Optional team to add the user to upon acceptance",
    )
    email = models.EmailField(
        help_text="Email address of the invitee",
    )
    role = models.CharField(
        max_length=50,
        choices=MembershipRole.choices(),
        default=MembershipRole.MEMBER.value,
        help_text="Role to assign when invitation is accepted",
    )
    token = models.CharField(
        max_length=100,
        unique=True,
        default=generate_invitation_token,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices(),
        default=InvitationStatus.PENDING.value,
    )
    expires_at = models.DateTimeField(
        default=get_invitation_expiry,
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        verbose_name = "Invitation"
        verbose_name_plural = "Invitations"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["email"]),
            models.Index(fields=["organization", "email"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Invitation to {self.organization} for {self.email}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_pending(self) -> bool:
        return self.status == InvitationStatus.PENDING.value and not self.is_expired

    @property
    def can_accept(self) -> bool:
        return self.is_pending

    def accept(self, user) -> Membership:
        """
        Accept this invitation and create a membership.

        Args:
            user: The user accepting the invitation

        Returns:
            The created Membership

        Raises:
            ValueError: If invitation cannot be accepted
        """
        if not self.can_accept:
            if self.is_expired:
                self.status = InvitationStatus.EXPIRED.value
                self.save(update_fields=["status"])
                raise ValueError("Invitation has expired")
            raise ValueError(f"Invitation cannot be accepted (status: {self.status})")

        # Create organization membership
        membership = self.organization.add_member(
            user=user,
            role=self.role,
            invited_by=self.invited_by,
        )

        # Add to team if specified
        if self.team:
            self.team.add_member(user=user, role=self.role)

        # Update invitation status
        self.status = InvitationStatus.ACCEPTED.value
        self.accepted_at = timezone.now()
        self.save(update_fields=["status", "accepted_at"])

        return membership

    def decline(self):
        """Decline this invitation."""
        if self.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot decline invitation (status: {self.status})")

        self.status = InvitationStatus.DECLINED.value
        self.save(update_fields=["status"])

    def revoke(self):
        """Revoke this invitation."""
        if self.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot revoke invitation (status: {self.status})")

        self.status = InvitationStatus.REVOKED.value
        self.save(update_fields=["status"])

    def resend(self):
        """Resend this invitation (reset expiry)."""
        self.expires_at = get_invitation_expiry()
        self.token = generate_invitation_token()
        self.status = InvitationStatus.PENDING.value
        self.save(update_fields=["expires_at", "token", "status"])
