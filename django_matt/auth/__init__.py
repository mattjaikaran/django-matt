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
from django_matt.auth.jwt import (
    JWTConfig,
    jwt_config,
    JWTAuthentication,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_access_token,
    verify_refresh_token,
    refresh_tokens,
    get_token_from_request,
    get_user_from_token,
)

# RBAC (from folder)
from django_matt.auth.rbac import (
    Role,
    RBACConfig,
    rbac_config,
    get_user_roles,
    get_user_permissions,
    user_has_permission,
    user_has_role,
    user_has_any_role,
    user_has_all_roles,
    get_user_highest_role,
    requires_role_hierarchy,
    requires_rbac_permission,
)

# Decorators (from folder)
from django_matt.auth.decorators import (
    jwt_required,
    jwt_optional,
    requires_auth,
    admin_required,
    superuser_required,
    with_roles,
    with_permission,
)

# Middleware
from django_matt.auth.middleware import (
    JWTAuthenticationMiddleware,
    JWTAuthenticationMiddlewareAsync,
    JWTStrictAuthenticationMiddleware,
)

# Magic Link Passwordless Auth
from django_matt.auth.magic_link import (
    MagicLinkConfig,
    magic_link_config,
    MagicLinkTokenError,
    MagicLinkExpiredError,
    MagicLinkInvalidError,
    MagicLinkUserNotFoundError,
    MagicLinkVerifyResult,
    create_magic_link_token,
    verify_magic_link_token,
    get_magic_link_payload,
    create_magic_link_url,
    send_magic_link,
    send_magic_link_async,
)

# Controllers
from django_matt.auth.controllers import (
    AuthController,
    MinimalAuthController,
)

# Passkeys/WebAuthn
from django_matt.auth.passkeys import (
    PasskeyConfig,
    passkey_config,
    PasskeyController,
    MinimalPasskeyController,
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    PasskeyError,
    PasskeyRegistrationError,
    PasskeyAuthenticationError,
    PasskeyCredentialNotFoundError,
)

# OAuth (Social Login)
from django_matt.auth.oauth import (
    OAuthConfig,
    OAuthProviderConfig,
    get_oauth_config,
    oauth_config,
    OAuthController,
    OAuthProvider,
    OAuthUserInfo,
    OAuthToken,
    OAuthError,
    OAuthConfigError,
    OAuthAuthenticationError,
    OAuthUserInfoError,
    GoogleOAuthProvider,
    GitHubOAuthProvider,
    AppleOAuthProvider,
    MicrosoftOAuthProvider,
    get_provider,
    get_provider_instance,
)

# SSO (Enterprise)
from django_matt.auth.sso import (
    SSOConfig,
    get_sso_config,
    sso_config,
    SSOController,
    SSOProvider,
    SSOUserInfo as SSOUserInfoType,
    SSOError,
    SSOConfigError,
    SSOAuthenticationError,
    SAMLProvider,
    OIDCProvider,
    get_provider_class,
    get_provider_for_connection,
)

# Schemas
from django_matt.auth.schemas import (
    TokenPayload,
    TokenPair,
    AccessToken,
    LoginRequest,
    LoginWithUsernameRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    ResetPasswordConfirmRequest,
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    AuthResponse,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    OTPRequest,
    OTPVerifyRequest,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
    MessageResponse,
    ErrorResponse,
)

__all__ = [
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
]
