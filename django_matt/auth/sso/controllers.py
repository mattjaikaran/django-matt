# file-length-max: 500
"""
API Controllers for Enterprise SSO authentication.

Provides endpoints for:
- SSO connection management (admin)
- SSO login flow
- SSO callback handling
- SP metadata (for SAML)
"""

from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect

from asgiref.sync import sync_to_async

from django_matt.auth.decorators import jwt_required
from django_matt.auth.jwt import acreate_token_pair
from django_matt.auth.sso.config import get_sso_config
from django_matt.auth.sso.providers import (
    SSOError,
    SSOUserInfo,
    get_provider_for_connection,
)
from django_matt.auth.sso.schemas import (
    SPMetadataResponse,
    SSOCallbackResponse,
    SSOConnectionCreateRequest,
    SSOConnectionResponse,
    SSODomainCheckRequest,
    SSOLoginResponse,
    SSOStatusResponse,
)
from django_matt.core.errors import (
    NotFoundAPIError,
    PermissionAPIError,
    ValidationAPIError,
)

User = get_user_model()


class SSOController:
    """
    Enterprise SSO controller.

    Endpoints:
        POST /sso/check - Check if email domain uses SSO
        GET  /sso/{org_id}/login - Start SSO login flow
        POST /sso/{org_id}/login - Start SSO login flow (API)
        GET  /sso/{org_id}/callback - Handle SSO callback
        POST /sso/{org_id}/callback - Handle SSO callback (SAML POST)
        GET  /sso/{org_id}/metadata - Get SP metadata (SAML)

    Admin endpoints (require authentication + org admin):
        GET  /sso/{org_id}/connection - Get SSO connection config
        POST /sso/{org_id}/connection - Create/update SSO connection
        DELETE /sso/{org_id}/connection - Delete SSO connection

    Usage:
        from django_matt import DjangoMattAPI
        from django_matt.auth.sso import SSOController

        api = DjangoMattAPI()
        api.register_controller(SSOController, prefix="/auth")
    """

    prefix = "sso"
    tags = ["SSO"]

    # =========================================================================
    # Domain Check
    # =========================================================================

    @staticmethod
    async def check_domain(request, data: SSODomainCheckRequest) -> SSOStatusResponse:
        """
        Check if an email domain uses SSO.

        POST /sso/check
        """
        from django_matt.auth.sso.models import SSOConnection

        email = data.email.lower()
        domain = email.split("@")[-1] if "@" in email else ""

        if not domain:
            return SSOStatusResponse(sso_enabled=False)

        # SSOConnection.get_for_domain is a custom classmethod with sync ORM internally —
        # it must be wrapped with sync_to_async.
        connection = await sync_to_async(SSOConnection.get_for_domain)(domain)

        if not connection:
            return SSOStatusResponse(sso_enabled=False)

        config = get_sso_config()
        base = config.callback_url_base.rstrip("/")

        return SSOStatusResponse(
            sso_enabled=True,
            sso_required=connection.is_required,
            organization_id=connection.organization_id,
            provider_type=connection.provider_type,
            login_url=f"{base}/auth/sso/{connection.organization_id}/login",
        )

    # =========================================================================
    # Login Flow
    # =========================================================================

    @staticmethod
    async def login(request, org_id: str) -> SSOLoginResponse:
        """
        Start SSO login flow.

        GET /sso/{org_id}/login - Redirects to IdP
        POST /sso/{org_id}/login - Returns login URL (for SPA)
        """
        from django_matt.auth.sso.models import SSOConnection

        # SSOConnection.get_for_organization is a custom classmethod with sync ORM internally.
        connection = await sync_to_async(SSOConnection.get_for_organization)(org_id)
        if not connection:
            raise NotFoundAPIError(f"SSO not configured for organization: {org_id}")

        provider = get_provider_for_connection(connection)
        if not provider:
            raise ValidationAPIError(f"Unsupported SSO provider: {connection.provider_type}")

        try:
            login_url = provider.get_login_url()
            return SSOLoginResponse(
                login_url=login_url,
                organization_id=org_id,
                provider_type=connection.provider_type,
            )
        except SSOError as e:
            raise ValidationAPIError(str(e))

    @staticmethod
    async def login_redirect(request, org_id: str):
        """
        Start SSO login with direct redirect.

        GET /sso/{org_id}/login (browser request)
        """
        from django_matt.auth.sso.models import SSOConnection

        connection = await sync_to_async(SSOConnection.get_for_organization)(org_id)
        if not connection:
            config = get_sso_config()
            return HttpResponseRedirect(
                f"{config.callback_url_base}/login?error=sso_not_configured"
            )

        provider = get_provider_for_connection(connection)
        if not provider:
            config = get_sso_config()
            return HttpResponseRedirect(
                f"{config.callback_url_base}/login?error=unsupported_provider"
            )

        try:
            login_url = provider.get_login_url()
            return HttpResponseRedirect(login_url)
        except SSOError:
            config = get_sso_config()
            return HttpResponseRedirect(f"{config.callback_url_base}/login?error=sso_error")

    # =========================================================================
    # Callback Handling
    # =========================================================================

    @staticmethod
    async def callback(request, org_id: str) -> SSOCallbackResponse:
        """
        Handle SSO callback from IdP.

        GET /sso/{org_id}/callback - OIDC callback
        POST /sso/{org_id}/callback - SAML callback (form_post)
        """
        from django_matt.auth.sso.models import SSOConnection, SSOUserLink

        connection = await sync_to_async(SSOConnection.get_for_organization)(org_id)
        if not connection:
            raise NotFoundAPIError(f"SSO not configured for organization: {org_id}")

        provider = get_provider_for_connection(connection)
        if not provider:
            raise ValidationAPIError(f"Unsupported SSO provider: {connection.provider_type}")

        try:
            # Process the SSO callback
            user_info = await provider.process_callback(request)
        except SSOError as e:
            raise ValidationAPIError(str(e))

        # Find or create user
        user, created = await _get_or_create_sso_user(connection, user_info)

        # Update or create SSO link
        await SSOUserLink.objects.aupdate_or_create(
            connection=connection,
            idp_user_id=user_info.idp_user_id,
            defaults={
                "user": user,
                "idp_email": user_info.email or "",
                "last_attributes": user_info.raw_attributes or {},
            },
        )

        # Generate JWT tokens
        tokens = await acreate_token_pair(user)

        return SSOCallbackResponse(
            success=True,
            user_id=user.pk,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            organization_id=org_id,
            created=created,
        )

    # =========================================================================
    # SP Metadata (SAML)
    # =========================================================================

    @staticmethod
    async def metadata(request, org_id: str):
        """
        Get Service Provider metadata for SAML configuration.

        GET /sso/{org_id}/metadata
        """
        from django_matt.auth.sso.models import SSOConnection

        connection = await sync_to_async(SSOConnection.get_for_organization)(org_id)
        if not connection:
            raise NotFoundAPIError(f"SSO not configured for organization: {org_id}")

        if connection.provider_type not in ["saml", "onelogin"]:
            # Return basic SP info for non-SAML
            return SPMetadataResponse(
                entity_id=connection.get_sp_entity_id(),
                acs_url=connection.get_callback_url(),
            )

        provider = get_provider_for_connection(connection)
        if not provider:
            raise ValidationAPIError("Could not initialize SSO provider")

        try:
            metadata_xml = provider.get_metadata()
            if metadata_xml:
                # Return as XML
                return HttpResponse(
                    metadata_xml,
                    content_type="application/xml",
                )
        except SSOError:
            pass

        # Fallback to JSON response
        return SPMetadataResponse(
            entity_id=connection.get_sp_entity_id(),
            acs_url=connection.get_callback_url(),
        )

    # =========================================================================
    # Admin: Connection Management
    # =========================================================================

    @staticmethod
    @jwt_required
    async def get_connection(request, org_id: str) -> SSOConnectionResponse:
        """
        Get SSO connection configuration (admin only).

        GET /sso/{org_id}/connection
        """
        from django_matt.auth.sso.models import SSOConnection
        from django_matt.multitenancy import Organization, user_is_org_admin

        # Check if user is admin of this organization
        organization = await Organization.objects.filter(id=org_id).afirst()
        if not organization:
            raise NotFoundAPIError(f"Organization not found: {org_id}")

        # user_is_org_admin is a sync utility function with sync ORM internally.
        is_admin = await sync_to_async(user_is_org_admin)(request.user, organization)
        if not is_admin:
            raise PermissionAPIError("Only organization admins can manage SSO settings")

        connection = await sync_to_async(SSOConnection.get_for_organization)(org_id)
        if not connection:
            raise NotFoundAPIError(f"SSO not configured for organization: {org_id}")

        return SSOConnectionResponse.from_model(connection)

    @staticmethod
    @jwt_required
    async def create_connection(
        request, org_id: str, data: SSOConnectionCreateRequest
    ) -> SSOConnectionResponse:
        """
        Create or update SSO connection (admin only).

        POST /sso/{org_id}/connection
        """
        from django_matt.auth.sso.models import SSOConnection

        config = get_sso_config()

        # Validate provider type
        if not config.is_provider_allowed(data.provider_type):
            raise ValidationAPIError(f"Provider type not allowed: {data.provider_type}")

        # Build connection data
        connection_data = {
            "organization_id": org_id,
            "provider_type": data.provider_type,
            "name": data.name,
            "is_active": data.is_active,
            "is_required": data.is_required,
            "domains": data.domains,
            "default_role": data.default_role,
            "attribute_mapping": data.attribute_mapping,
            "extra_config": data.extra_config,
            "created_by": request.user,
        }

        # Add SAML config
        if data.saml_config:
            connection_data.update(
                {
                    "idp_entity_id": data.saml_config.idp_entity_id,
                    "idp_sso_url": data.saml_config.idp_sso_url,
                    "idp_slo_url": data.saml_config.idp_slo_url or "",
                    "idp_certificate": data.saml_config.idp_certificate,
                }
            )

        # Add OIDC config
        if data.oidc_config:
            connection_data.update(
                {
                    "client_id": data.oidc_config.client_id,
                    "client_secret": data.oidc_config.client_secret,
                    "discovery_url": data.oidc_config.discovery_url or "",
                    "authorization_url": data.oidc_config.authorization_url or "",
                    "token_url": data.oidc_config.token_url or "",
                    "userinfo_url": data.oidc_config.userinfo_url or "",
                }
            )

        connection, _ = await SSOConnection.objects.aupdate_or_create(
            organization_id=org_id,
            defaults=connection_data,
        )

        return SSOConnectionResponse.from_model(connection)

    @staticmethod
    @jwt_required
    async def delete_connection(request, org_id: str) -> dict:
        """
        Delete SSO connection (admin only).

        DELETE /sso/{org_id}/connection
        """
        from django_matt.auth.sso.models import SSOConnection

        try:
            connection = await SSOConnection.objects.aget(organization_id=org_id)
        except SSOConnection.DoesNotExist:
            raise NotFoundAPIError(f"SSO not configured for organization: {org_id}")

        await connection.adelete()

        return {"success": True, "message": "SSO connection deleted"}

    @classmethod
    def get_urls(cls):
        """Get URL patterns for this controller."""
        return [
            ("check", "POST", cls.check_domain, "sso-check-domain"),
            ("<str:org_id>/login", "GET", cls.login_redirect, "sso-login-redirect"),
            ("<str:org_id>/login", "POST", cls.login, "sso-login"),
            ("<str:org_id>/callback", "GET", cls.callback, "sso-callback-get"),
            ("<str:org_id>/callback", "POST", cls.callback, "sso-callback-post"),
            ("<str:org_id>/metadata", "GET", cls.metadata, "sso-metadata"),
            ("<str:org_id>/connection", "GET", cls.get_connection, "sso-get-connection"),
            ("<str:org_id>/connection", "POST", cls.create_connection, "sso-create-connection"),
            ("<str:org_id>/connection", "DELETE", cls.delete_connection, "sso-delete-connection"),
        ]


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_or_create_sso_user(connection, user_info: SSOUserInfo) -> tuple:
    """
    Get existing user or create new one from SSO user info.

    Returns:
        Tuple of (user, created)
    """
    from django_matt.auth.sso.models import SSOUserLink

    config = get_sso_config()

    # SSOUserLink.get_user is a custom classmethod with sync ORM internally.
    existing_user = await sync_to_async(SSOUserLink.get_user)(connection, user_info.idp_user_id)
    if existing_user:
        # Optionally update user info
        if config.auto_update_user and user_info.email:
            await _update_user_from_sso(existing_user, user_info)
        return existing_user, False

    # Check for existing user by email
    if user_info.email:
        try:
            user = await User.objects.aget(email=user_info.email)
            return user, False
        except User.DoesNotExist:
            pass

    # Create new user if allowed
    if not config.auto_create_user:
        from django_matt.core.errors import ValidationAPIError

        raise ValidationAPIError("Account not found. Please contact your administrator.")

    # Generate username
    username = user_info.email or f"sso_{user_info.idp_user_id}"
    base_username = username.split("@")[0] if "@" in username else username
    username = base_username
    counter = 1

    while await User.objects.filter(username=username).aexists():
        username = f"{base_username}{counter}"
        counter += 1

    # Create user
    user_data = {
        "username": username,
        "email": user_info.email or "",
    }

    if hasattr(User, "first_name") and user_info.first_name:
        user_data["first_name"] = user_info.first_name
    if hasattr(User, "last_name") and user_info.last_name:
        user_data["last_name"] = user_info.last_name

    user = await User.objects.acreate_user(**user_data)

    return user, True


async def _update_user_from_sso(user, user_info: SSOUserInfo):
    """Update user fields from SSO user info."""
    updated = False

    if user_info.first_name and hasattr(user, "first_name"):
        if user.first_name != user_info.first_name:
            user.first_name = user_info.first_name
            updated = True

    if user_info.last_name and hasattr(user, "last_name"):
        if user.last_name != user_info.last_name:
            user.last_name = user_info.last_name
            updated = True

    if updated:
        await user.asave()
