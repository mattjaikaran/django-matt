# file-length-max: 500
"""
API Controllers for OAuth authentication.

Provides endpoints for:
- Listing available OAuth providers
- Starting OAuth login flow
- Handling OAuth callbacks
- Managing OAuth connections
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.utils import timezone

import orjson

from django_matt.auth.decorators import jwt_required
from django_matt.auth.jwt import acreate_token_pair
from django_matt.auth.oauth.config import get_oauth_config
from django_matt.auth.oauth.providers import (
    OAuthError,
    OAuthUserInfo,
    get_provider_instance,
)
from django_matt.auth.oauth.schemas import (
    OAuthCallbackResponse,
    OAuthConnectionListResponse,
    OAuthConnectionResponse,
    OAuthLoginRequest,
    OAuthLoginResponse,
    OAuthProviderInfo,
    OAuthProvidersResponse,
)
from django_matt.core.errors import (
    NotFoundAPIError,
    ValidationAPIError,
)

User = get_user_model()


PROVIDER_DISPLAY_NAMES = {
    "google": "Google",
    "github": "GitHub",
    "apple": "Apple",
    "microsoft": "Microsoft",
}


class OAuthController:
    """
    Full OAuth controller with all endpoints.

    Endpoints:
        GET  /oauth/providers - List available OAuth providers
        POST /oauth/{provider}/login - Start OAuth flow
        GET  /oauth/{provider}/callback - Handle OAuth callback
        POST /oauth/{provider}/callback - Handle OAuth callback (Apple)
        GET  /oauth/connections - List user's OAuth connections
        DELETE /oauth/connections/{provider} - Disconnect a provider

    Usage:
        from django_matt import DjangoMattAPI
        from django_matt.auth.oauth import OAuthController

        api = DjangoMattAPI()
        api.register_controller(OAuthController, prefix="/auth")
    """

    prefix = "oauth"
    tags = ["OAuth"]

    # =========================================================================
    # Provider Discovery
    # =========================================================================

    @staticmethod
    async def list_providers(request) -> OAuthProvidersResponse:
        """
        List available OAuth providers.

        GET /oauth/providers
        """
        config = get_oauth_config()
        providers = []

        for name in ["google", "github", "apple", "microsoft"]:
            provider_config = config.get_provider_config(name)
            enabled = provider_config is not None

            provider_info = OAuthProviderInfo(
                name=name,
                display_name=PROVIDER_DISPLAY_NAMES.get(name, name.title()),
                enabled=enabled,
                authorization_url=f"/auth/oauth/{name}/login" if enabled else None,
            )
            providers.append(provider_info)

        return OAuthProvidersResponse(providers=providers)

    # =========================================================================
    # Login Flow
    # =========================================================================

    @staticmethod
    async def login(request, provider: str, data: OAuthLoginRequest = None) -> OAuthLoginResponse:
        """
        Start OAuth login flow.

        Generates the authorization URL and state, returns them for the client
        to redirect the user.

        POST /oauth/{provider}/login
        """
        provider_instance = get_provider_instance(provider)
        if not provider_instance:
            raise NotFoundAPIError(f"OAuth provider '{provider}' not found")

        try:
            extra_data = {}
            if data and data.redirect_url:
                extra_data["redirect_url"] = data.redirect_url

            state = provider_instance.generate_state(extra_data)
            auth_url, _ = provider_instance.get_authorization_url(state=state)

            return OAuthLoginResponse(
                authorization_url=auth_url,
                state=state,
                provider=provider,
            )
        except OAuthError as e:
            raise ValidationAPIError(str(e))

    @staticmethod
    async def login_redirect(request, provider: str):
        """
        Start OAuth login with direct redirect.

        GET /oauth/{provider}/login

        This endpoint redirects the user directly to the OAuth provider.
        Useful for server-side flows.
        """
        provider_instance = get_provider_instance(provider)
        if not provider_instance:
            raise NotFoundAPIError(f"OAuth provider '{provider}' not found")

        try:
            auth_url, state = provider_instance.get_authorization_url()
            return HttpResponseRedirect(auth_url)
        except OAuthError as e:
            config = get_oauth_config()
            return HttpResponseRedirect(
                f"{config.failure_redirect}?error={e.error_code or 'oauth_error'}"
            )

    # =========================================================================
    # Callback Handling
    # =========================================================================

    @staticmethod
    async def callback(
        request,
        provider: str,
        code: str = None,
        state: str = None,
        error: str = None,
        error_description: str = None,
    ) -> OAuthCallbackResponse:
        """
        Handle OAuth callback from provider.

        GET /oauth/{provider}/callback
        POST /oauth/{provider}/callback (Apple uses POST with form_post)
        """
        from django_matt.auth.oauth.models import OAuthConnection

        config = get_oauth_config()

        # Handle errors from provider
        if error:
            raise ValidationAPIError(
                error_description or f"OAuth error: {error}",
            )

        if not code:
            raise ValidationAPIError("Authorization code is required")

        if not state:
            raise ValidationAPIError("State parameter is required")

        # Get provider instance
        provider_instance = get_provider_instance(provider)
        if not provider_instance:
            raise NotFoundAPIError(f"OAuth provider '{provider}' not found")

        # Verify state
        state_data = provider_instance.verify_state(state)
        if not state_data:
            raise ValidationAPIError("Invalid or expired state parameter")

        try:
            # Exchange code for token
            # For Apple, check if user data is in POST body
            user_data = None
            if provider == "apple" and hasattr(request, "POST"):
                user_json = request.POST.get("user")
                if user_json:
                    try:
                        user_data = orjson.loads(user_json)
                    except orjson.JSONDecodeError:
                        pass

            if provider == "apple" and user_data:
                token = await provider_instance.exchange_code(code, user_data)
            else:
                token = await provider_instance.exchange_code(code)

            # Get user info
            user_info = await provider_instance.fetch_user_info(token)

        except OAuthError as e:
            raise ValidationAPIError(str(e))

        # Find or create user
        user, created = await _get_or_create_user(user_info, config)

        # Create or update OAuth connection
        connection, _ = await OAuthConnection.objects.aupdate_or_create(
            provider=provider,
            provider_user_id=user_info.provider_user_id,
            defaults={
                "user": user,
                "email": user_info.email,
                "name": user_info.name or "",
                "picture": user_info.picture or "",
                "access_token": token.access_token,
                "refresh_token": token.refresh_token or "",
                "token_expires_at": (
                    timezone.now() + timedelta(seconds=token.expires_in)
                    if token.expires_in
                    else None
                ),
                "raw_data": user_info.raw or {},
            },
        )

        # Generate JWT tokens
        tokens = await acreate_token_pair(user)

        return OAuthCallbackResponse(
            success=True,
            user_id=user.pk,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            created=created,
            provider=provider,
        )

    # =========================================================================
    # Connection Management
    # =========================================================================

    @staticmethod
    @jwt_required
    async def list_connections(request) -> OAuthConnectionListResponse:
        """
        List user's OAuth connections.

        GET /oauth/connections
        """
        from django_matt.auth.oauth.models import OAuthConnection

        connections = [conn async for conn in OAuthConnection.objects.filter(user=request.user)]

        return OAuthConnectionListResponse(
            connections=[
                OAuthConnectionResponse(
                    id=conn.id,
                    provider=conn.provider,
                    provider_user_id=conn.provider_user_id,
                    email=conn.email,
                    connected_at=conn.created_at,
                )
                for conn in connections
            ],
            count=len(connections),
        )

    @staticmethod
    @jwt_required
    async def disconnect(request, provider: str) -> dict:
        """
        Disconnect an OAuth provider.

        DELETE /oauth/connections/{provider}
        """
        from django_matt.auth.oauth.models import OAuthConnection

        try:
            connection = await OAuthConnection.objects.aget(
                user=request.user,
                provider=provider,
            )
        except OAuthConnection.DoesNotExist:
            raise NotFoundAPIError(f"No connection to {provider}")

        # Prevent disconnecting last auth method if user has no password
        other_connections = (
            await OAuthConnection.objects.filter(user=request.user)
            .exclude(provider=provider)
            .acount()
        )

        has_password = request.user.has_usable_password()
        has_passkeys = (
            hasattr(request.user, "passkey_credentials")
            and await request.user.passkey_credentials.aexists()
        )

        if not has_password and not has_passkeys and other_connections == 0:
            raise ValidationAPIError(
                "Cannot disconnect last OAuth provider when no other login method is available"
            )

        await connection.adelete()

        return {"success": True, "message": f"Disconnected from {provider}"}

    @classmethod
    def get_urls(cls):
        """Get URL patterns for this controller."""
        return [
            ("providers", "GET", cls.list_providers, "oauth-providers"),
            ("<str:provider>/login", "GET", cls.login_redirect, "oauth-login-redirect"),
            ("<str:provider>/login", "POST", cls.login, "oauth-login"),
            ("<str:provider>/callback", "GET", cls.callback, "oauth-callback-get"),
            ("<str:provider>/callback", "POST", cls.callback, "oauth-callback-post"),
            ("connections", "GET", cls.list_connections, "oauth-connections"),
            ("connections/<str:provider>", "DELETE", cls.disconnect, "oauth-disconnect"),
        ]


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_or_create_user(user_info: OAuthUserInfo, config) -> tuple:
    """
    Get existing user or create new one from OAuth user info.

    Returns:
        Tuple of (user, created)
    """
    from asgiref.sync import sync_to_async

    from django_matt.auth.oauth.models import OAuthConnection

    # First, check if we have an existing OAuth connection.
    # OAuthConnection.get_or_none is a custom classmethod with sync ORM internally —
    # it must be wrapped with sync_to_async.
    connection = await sync_to_async(OAuthConnection.get_or_none)(
        user_info.provider,
        user_info.provider_user_id,
    )

    if connection:
        return connection.user, False

    # Check if we should link to existing user by email
    if config.link_existing_user and user_info.email:
        try:
            user = await User.objects.aget(email=user_info.email)
            return user, False
        except User.DoesNotExist:
            pass

    # Create new user if allowed
    if not config.auto_create_user:
        raise ValidationAPIError(
            "Account not found. Please register first.",
        )

    # Generate username from email or provider info
    username = user_info.email
    if not username:
        username = f"{user_info.provider}_{user_info.provider_user_id}"

    # Ensure unique username
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

    # Add name fields if model supports them
    if hasattr(User, "first_name") and user_info.first_name:
        user_data["first_name"] = user_info.first_name
    if hasattr(User, "last_name") and user_info.last_name:
        user_data["last_name"] = user_info.last_name

    user = await User.objects.acreate_user(**user_data)

    return user, True
