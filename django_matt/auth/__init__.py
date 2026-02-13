"""
Django Matt Authentication - Complete auth system with JWT, RBAC, and decorators.

Provides:
- JWT token generation and validation
- Role-Based Access Control (RBAC) with hierarchy
- Authentication decorators for controllers
- Pydantic schemas for auth requests/responses
- Middleware for automatic JWT authentication

All validation uses Pydantic v2 schemas, not DRF serializers.

Example:
    from django_matt.auth import (
        jwt_required,
        create_token_pair,
        with_roles,
        with_permission,
    )
    from django_matt.auth.schemas import LoginRequest, TokenPair

    class AuthController(APIController):
        prefix = "auth"

        @post("login")
        async def login(self, request, data: LoginRequest) -> TokenPair:
            user = await authenticate(data.email, data.password)
            return create_token_pair(user)

        @get("me")
        @jwt_required
        async def me(self, request) -> UserResponse:
            return UserResponse.from_user(request.user)

        @delete("users/{id}")
        @jwt_required
        @with_roles("admin")
        async def delete_user(self, request, id: str):
            ...
"""

# JWT Authentication
# Blacklist
# API Keys
from django_matt.auth.api_keys import (
    PLAN_RATE_LIMITS,
    APIKey,
    APIKeyAuthenticationMiddleware,
    APIKeyConfig,
    APIKeyController,
    APIKeyRateLimitMiddleware,
    APIKeyUsage,
    APIKeyUsageTrackingMiddleware,
    acreate_api_key,
    api_key_config,
    api_key_optional,
    api_key_required,
    arotate_api_key,
    create_api_key,
    generate_api_key,
    get_api_key_from_request,
    hash_api_key,
    requires_live_key,
    requires_plan,
    requires_scope,
    rotate_api_key,
)
from django_matt.auth.blacklist import (
    BlacklistConfig,
    BlacklistedToken,
    CacheBlacklistBackend,
    DatabaseBlacklistBackend,
    NullBlacklistBackend,
    ablacklist_token,
    ais_token_blacklisted,
    aprune_expired_tokens,
    blacklist_config,
    blacklist_token,
    is_token_blacklisted,
    prune_expired_tokens,
    reset_backend,
)

# Controllers
from django_matt.auth.controllers import (
    AuthController,
    MinimalAuthController,
)

# Decorators (from folder)
from django_matt.auth.decorators import (
    admin_required,
    jwt_optional,
    jwt_required,
    requires_auth,
    superuser_required,
    with_permission,
    with_roles,
)
from django_matt.auth.jwt import (
    JWTAuthentication,
    JWTConfig,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    get_token_from_request,
    get_user_from_token,
    jwt_config,
    refresh_tokens,
    verify_access_token,
    verify_refresh_token,
)

# Magic Link Passwordless Auth
from django_matt.auth.magic_link import (
    MagicLinkConfig,
    MagicLinkExpiredError,
    MagicLinkInvalidError,
    MagicLinkTokenError,
    MagicLinkUserNotFoundError,
    MagicLinkVerifyResult,
    create_magic_link_token,
    create_magic_link_url,
    get_magic_link_payload,
    magic_link_config,
    send_magic_link,
    send_magic_link_async,
    verify_magic_link_token,
)

# Middleware
from django_matt.auth.middleware import (
    JWTAuthenticationMiddleware,
    JWTAuthenticationMiddlewareAsync,
    JWTStrictAuthenticationMiddleware,
)

# OAuth (Social Login)
from django_matt.auth.oauth import (
    AppleOAuthProvider,
    GitHubOAuthProvider,
    GoogleOAuthProvider,
    MicrosoftOAuthProvider,
    OAuthAuthenticationError,
    OAuthConfig,
    OAuthConfigError,
    OAuthController,
    OAuthError,
    OAuthProvider,
    OAuthProviderConfig,
    OAuthToken,
    OAuthUserInfo,
    OAuthUserInfoError,
    get_oauth_config,
    get_provider,
    get_provider_instance,
    oauth_config,
)

# Passkeys/WebAuthn
from django_matt.auth.passkeys import (
    MinimalPasskeyController,
    PasskeyAuthenticationError,
    PasskeyConfig,
    PasskeyController,
    PasskeyCredentialNotFoundError,
    PasskeyError,
    PasskeyRegistrationError,
    generate_authentication_options,
    generate_registration_options,
    passkey_config,
    verify_authentication_response,
    verify_registration_response,
)

# Password Reset
from django_matt.auth.password_reset import (
    PasswordResetConfig,
    PasswordResetResult,
    averify_password_reset_token,
    create_password_reset_token,
    get_reset_url,
    password_reset_config,
    verify_password_reset_token,
)

# RBAC (from folder)
from django_matt.auth.rbac import (
    RBACConfig,
    Role,
    get_user_highest_role,
    get_user_permissions,
    get_user_roles,
    rbac_config,
    requires_rbac_permission,
    requires_role_hierarchy,
    user_has_all_roles,
    user_has_any_role,
    user_has_permission,
    user_has_role,
)

# Schemas
from django_matt.auth.schemas import (
    AccessToken,
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    AuthResponse,
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    LoginWithUsernameRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MessageResponse,
    OTPRequest,
    OTPVerifyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordConfirmRequest,
    ResetPasswordRequest,
    TokenPair,
    TokenPayload,
    UserBase,
    UserCreate,
    UserResponse,
    UserUpdate,
)

# SSO (Enterprise)
from django_matt.auth.sso import (
    OIDCProvider,
    SAMLProvider,
    SSOAuthenticationError,
    SSOConfig,
    SSOConfigError,
    SSOController,
    SSOError,
    SSOProvider,
    get_provider_class,
    get_provider_for_connection,
    get_sso_config,
    sso_config,
)
from django_matt.auth.sso import (
    SSOUserInfo as SSOUserInfoType,
)

__all__ = [
    # Blacklist
    "BlacklistConfig",
    "blacklist_config",
    "blacklist_token",
    "ablacklist_token",
    "is_token_blacklisted",
    "ais_token_blacklisted",
    "prune_expired_tokens",
    "aprune_expired_tokens",
    "reset_backend",
    "NullBlacklistBackend",
    "CacheBlacklistBackend",
    "DatabaseBlacklistBackend",
    "BlacklistedToken",
    # JWT
    "JWTConfig",
    "jwt_config",
    "JWTAuthentication",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
    "refresh_tokens",
    "get_token_from_request",
    "get_user_from_token",
    # RBAC
    "Role",
    "RBACConfig",
    "rbac_config",
    "get_user_roles",
    "get_user_permissions",
    "user_has_permission",
    "user_has_role",
    "user_has_any_role",
    "user_has_all_roles",
    "get_user_highest_role",
    "requires_role_hierarchy",
    "requires_rbac_permission",
    # Decorators
    "jwt_required",
    "jwt_optional",
    "requires_auth",
    "admin_required",
    "superuser_required",
    "with_roles",
    "with_permission",
    # Middleware
    "JWTAuthenticationMiddleware",
    "JWTAuthenticationMiddlewareAsync",
    "JWTStrictAuthenticationMiddleware",
    # Magic Link
    "MagicLinkConfig",
    "magic_link_config",
    "MagicLinkTokenError",
    "MagicLinkExpiredError",
    "MagicLinkInvalidError",
    "MagicLinkUserNotFoundError",
    "MagicLinkVerifyResult",
    "create_magic_link_token",
    "verify_magic_link_token",
    "get_magic_link_payload",
    "create_magic_link_url",
    "send_magic_link",
    "send_magic_link_async",
    # Password Reset
    "PasswordResetConfig",
    "password_reset_config",
    "PasswordResetResult",
    "create_password_reset_token",
    "verify_password_reset_token",
    "averify_password_reset_token",
    "get_reset_url",
    # Passkeys/WebAuthn
    "PasskeyConfig",
    "passkey_config",
    "PasskeyController",
    "MinimalPasskeyController",
    "generate_registration_options",
    "verify_registration_response",
    "generate_authentication_options",
    "verify_authentication_response",
    "PasskeyError",
    "PasskeyRegistrationError",
    "PasskeyAuthenticationError",
    "PasskeyCredentialNotFoundError",
    # Controllers
    "AuthController",
    "MinimalAuthController",
    # OAuth
    "OAuthConfig",
    "OAuthProviderConfig",
    "get_oauth_config",
    "oauth_config",
    "OAuthController",
    "OAuthProvider",
    "OAuthUserInfo",
    "OAuthToken",
    "OAuthError",
    "OAuthConfigError",
    "OAuthAuthenticationError",
    "OAuthUserInfoError",
    "GoogleOAuthProvider",
    "GitHubOAuthProvider",
    "AppleOAuthProvider",
    "MicrosoftOAuthProvider",
    "get_provider",
    "get_provider_instance",
    # SSO (Enterprise)
    "SSOConfig",
    "get_sso_config",
    "sso_config",
    "SSOController",
    "SSOProvider",
    "SSOUserInfoType",
    "SSOError",
    "SSOConfigError",
    "SSOAuthenticationError",
    "SAMLProvider",
    "OIDCProvider",
    "get_provider_class",
    "get_provider_for_connection",
    # Schemas
    "TokenPayload",
    "TokenPair",
    "AccessToken",
    "LoginRequest",
    "LoginWithUsernameRequest",
    "RegisterRequest",
    "RefreshTokenRequest",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "ResetPasswordConfirmRequest",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "AuthResponse",
    "MagicLinkRequest",
    "MagicLinkVerifyRequest",
    "OTPRequest",
    "OTPVerifyRequest",
    "APIKeyCreate",
    "APIKeyResponse",
    "APIKeyCreatedResponse",
    "MessageResponse",
    "ErrorResponse",
    # API Keys (new module)
    "APIKeyConfig",
    "api_key_config",
    "APIKey",
    "APIKeyUsage",
    "PLAN_RATE_LIMITS",
    "generate_api_key",
    "hash_api_key",
    "get_api_key_from_request",
    "create_api_key",
    "acreate_api_key",
    "rotate_api_key",
    "arotate_api_key",
    "api_key_required",
    "api_key_optional",
    "requires_scope",
    "requires_live_key",
    "requires_plan",
    "APIKeyAuthenticationMiddleware",
    "APIKeyRateLimitMiddleware",
    "APIKeyUsageTrackingMiddleware",
    "APIKeyController",
]
