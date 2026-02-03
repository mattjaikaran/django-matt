"""
Core models for SaaS Starter.

Includes:
- Custom User model with email authentication
- Organization and Team models (multi-tenancy)
- Membership with roles
- Invitation system
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with email authentication.

    Features:
    - Email-based login (no username)
    - Profile fields (name, avatar)
    - Timezone and locale preferences
    - Account status tracking
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)

    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    # Preferences
    timezone = models.CharField(max_length=50, default="UTC")
    locale = models.CharField(max_length=10, default="en")
    notification_preferences = models.JSONField(default=dict, blank=True)

    # OAuth connections
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    github_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def display_name(self):
        if self.first_name:
            return self.first_name
        return self.email.split("@")[0]

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at"])


class Organization(models.Model):
    """
    Organization model for multi-tenancy.

    Features:
    - Unique slug for URLs
    - Billing integration
    - Feature limits based on plan
    - Settings and branding
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_organizations")

    # Branding
    logo_url = models.URLField(max_length=500, blank=True)
    website = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    # Billing
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    plan = models.CharField(
        max_length=50,
        choices=[
            ("free", "Free"),
            ("pro", "Pro"),
            ("enterprise", "Enterprise"),
        ],
        default="free",
    )
    plan_limits = models.JSONField(default=dict)

    # Settings
    settings = models.JSONField(default=dict)
    allowed_email_domains = models.JSONField(default=list)  # For SSO/invite restrictions

    # Status
    is_active = models.BooleanField(default=True)
    is_personal = models.BooleanField(default=False)  # Personal workspace

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def project_count(self):
        return self.projects.count()

    def check_limit(self, limit_name: str, current_value: int) -> bool:
        """Check if current value is within plan limits."""
        limit = self.plan_limits.get(limit_name, 0)
        if limit == -1:  # Unlimited
            return True
        return current_value < limit


class Team(models.Model):
    """
    Team within an organization.

    Features:
    - Group members for project access
    - Team-specific settings
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, db_index=True)
    description = models.TextField(blank=True)

    # Settings
    settings = models.JSONField(default=dict)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teams"
        unique_together = [["organization", "slug"]]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization.name} / {self.name}"


class MembershipRole(models.TextChoices):
    """Membership roles with hierarchy."""
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class Membership(models.Model):
    """
    Organization membership linking users to organizations with roles.

    Features:
    - Role-based access control
    - Team membership tracking
    - Invitation tracking
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )
    teams = models.ManyToManyField(Team, related_name="members", blank=True)

    # Invitation tracking
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations_sent"
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "memberships"
        unique_together = [["user", "organization"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"

    @property
    def is_owner(self):
        return self.role == MembershipRole.OWNER

    @property
    def is_admin(self):
        return self.role in [MembershipRole.OWNER, MembershipRole.ADMIN]

    def has_permission(self, permission: str) -> bool:
        """Check if membership has a specific permission."""
        permissions = {
            MembershipRole.OWNER: ["read", "write", "delete", "admin", "billing", "invite"],
            MembershipRole.ADMIN: ["read", "write", "delete", "admin", "invite"],
            MembershipRole.MEMBER: ["read", "write"],
            MembershipRole.VIEWER: ["read"],
        }
        return permission in permissions.get(self.role, [])


class Invitation(models.Model):
    """
    Pending invitation to join an organization.

    Features:
    - Email-based invitations
    - Expiration handling
    - Role pre-assignment
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )
    teams = models.ManyToManyField(Team, related_name="pending_invitations", blank=True)

    # Invitation details
    token = models.CharField(max_length=255, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="invitations_created"
    )
    message = models.TextField(blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("declined", "Declined"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        default="pending",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "invitations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation for {self.email} to {self.organization.name}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return self.status == "pending" and not self.is_expired


class MagicLinkToken(models.Model):
    """
    Magic link token for passwordless authentication.

    Features:
    - One-time use tokens
    - Expiration handling
    - IP tracking
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=255, unique=True, db_index=True)

    # Security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Status
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "magic_link_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Magic link for {self.email}"

    @property
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


class AuditLog(models.Model):
    """
    Audit log for tracking user actions.

    Features:
    - Action tracking
    - Resource tracking
    - IP and user agent logging
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, related_name="audit_logs"
    )

    # Action details
    action = models.CharField(max_length=100, db_index=True)  # e.g., "user.login", "project.create"
    resource_type = models.CharField(max_length=100, blank=True)  # e.g., "project", "task"
    resource_id = models.CharField(max_length=255, blank=True)

    # Context
    data = models.JSONField(default=dict)  # Additional action data
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "action", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"
