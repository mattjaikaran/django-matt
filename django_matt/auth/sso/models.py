"""
Django models for Enterprise SSO connections.
"""

from django.conf import settings
from django.db import models


class SSOConnection(models.Model):
    """
    Stores an organization's SSO configuration.

    Each organization can have one active SSO connection to their
    identity provider (Okta, Azure AD, Google Workspace, etc.)
    """

    # Link to organization (uses multitenancy if available)
    organization_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Organization ID or slug",
    )

    # Provider type
    provider_type = models.CharField(
        max_length=50,
        choices=[
            ("saml", "SAML 2.0"),
            ("oidc", "OpenID Connect"),
            ("okta", "Okta"),
            ("azure_ad", "Azure AD / Microsoft Entra"),
            ("google_workspace", "Google Workspace"),
            ("onelogin", "OneLogin"),
            ("auth0", "Auth0"),
        ],
        help_text="Type of SSO provider",
    )

    # Display name
    name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Display name for this SSO connection",
    )

    # Whether SSO is active for this organization
    is_active = models.BooleanField(
        default=True,
        help_text="Whether SSO is currently active",
    )

    # Whether SSO is required (disable password login)
    is_required = models.BooleanField(
        default=False,
        help_text="If true, users must use SSO (no password login)",
    )

    # Domain(s) that should use this SSO
    domains = models.JSONField(
        default=list,
        blank=True,
        help_text="Email domains that should use this SSO (e.g., ['acme.com'])",
    )

    # ==========================================================================
    # SAML Configuration
    # ==========================================================================

    # IdP Entity ID (issuer)
    idp_entity_id = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Identity Provider Entity ID (SAML Issuer)",
    )

    # IdP SSO URL (where to send auth requests)
    idp_sso_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="Identity Provider SSO URL",
    )

    # IdP SLO URL (optional, for logout)
    idp_slo_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="Identity Provider Single Logout URL (optional)",
    )

    # IdP Certificate (for signature verification)
    idp_certificate = models.TextField(
        blank=True,
        default="",
        help_text="Identity Provider X.509 certificate (PEM format)",
    )

    # ==========================================================================
    # OIDC Configuration
    # ==========================================================================

    # OIDC Client ID
    client_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="OIDC Client ID",
    )

    # OIDC Client Secret (encrypted in production!)
    client_secret = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="OIDC Client Secret",
    )

    # OIDC Discovery URL (well-known endpoint)
    discovery_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="OIDC Discovery URL (.well-known/openid-configuration)",
    )

    # OIDC Authorization URL (if not using discovery)
    authorization_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="OIDC Authorization URL (if not using discovery)",
    )

    # OIDC Token URL (if not using discovery)
    token_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="OIDC Token URL (if not using discovery)",
    )

    # OIDC UserInfo URL (if not using discovery)
    userinfo_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="OIDC UserInfo URL (if not using discovery)",
    )

    # ==========================================================================
    # Attribute Mapping
    # ==========================================================================

    # Map IdP attributes to user fields
    attribute_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Map IdP attributes to user fields (e.g., {'email': 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress'})",
    )

    # Default role for new SSO users
    default_role = models.CharField(
        max_length=50,
        blank=True,
        default="member",
        help_text="Default role for new users created via SSO",
    )

    # ==========================================================================
    # Metadata
    # ==========================================================================

    # Extra configuration (provider-specific)
    extra_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific configuration",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Who set this up
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sso_connections",
    )

    class Meta:
        db_table = "django_matt_sso_connections"
        verbose_name = "SSO Connection"
        verbose_name_plural = "SSO Connections"

    def __str__(self):
        return f"{self.organization_id} - {self.provider_type}"

    @classmethod
    def get_for_organization(cls, org_id: str):
        """Get SSO connection for an organization."""
        try:
            return cls.objects.get(organization_id=org_id, is_active=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_for_domain(cls, domain: str):
        """Get SSO connection for an email domain."""
        # This is a simple implementation - in production you might want
        # a separate Domain model for better querying
        connections = cls.objects.filter(is_active=True)
        for conn in connections:
            if domain.lower() in [d.lower() for d in conn.domains]:
                return conn
        return None

    def get_callback_url(self) -> str:
        """Get the callback URL for this SSO connection."""
        from django_matt.auth.sso.config import get_sso_config

        config = get_sso_config()
        base = config.callback_url_base.rstrip("/")
        return f"{base}/auth/sso/{self.organization_id}/callback"

    def get_sp_entity_id(self) -> str:
        """Get the Service Provider Entity ID (for SAML)."""
        from django_matt.auth.sso.config import get_sso_config

        config = get_sso_config()
        base = config.callback_url_base.rstrip("/")
        return f"{base}/auth/sso/{self.organization_id}/metadata"


class SSOUserLink(models.Model):
    """
    Links a user to their SSO identity.

    Stores the mapping between local user and IdP user ID.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sso_links",
    )

    connection = models.ForeignKey(
        SSOConnection,
        on_delete=models.CASCADE,
        related_name="user_links",
    )

    # User ID from the IdP (NameID for SAML, sub for OIDC)
    idp_user_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="User ID from Identity Provider",
    )

    # Email from IdP (may differ from user.email)
    idp_email = models.EmailField(
        blank=True,
        default="",
        help_text="Email from Identity Provider",
    )

    # Raw attributes from last login
    last_attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Attributes from last SSO login",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "django_matt_sso_user_links"
        verbose_name = "SSO User Link"
        verbose_name_plural = "SSO User Links"
        unique_together = [("connection", "idp_user_id")]
        indexes = [
            models.Index(fields=["connection", "idp_user_id"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.connection}"

    @classmethod
    def get_user(cls, connection: SSOConnection, idp_user_id: str):
        """Get user by SSO connection and IdP user ID."""
        try:
            link = cls.objects.select_related("user").get(
                connection=connection,
                idp_user_id=idp_user_id,
            )
            return link.user
        except cls.DoesNotExist:
            return None
