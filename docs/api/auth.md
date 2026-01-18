# Authentication API Reference

Complete authentication system with JWT, RBAC, OAuth, Passkeys, and SSO support.

## JWT Authentication

### Configuration

::: django_matt.auth.jwt.JWTConfig
    options:
      show_source: false
      heading_level: 4

### Token Functions

#### create_token_pair

::: django_matt.auth.jwt.create_token_pair
    options:
      show_source: false
      heading_level: 5

#### create_access_token

::: django_matt.auth.jwt.create_access_token
    options:
      show_source: false
      heading_level: 5

#### create_refresh_token

::: django_matt.auth.jwt.create_refresh_token
    options:
      show_source: false
      heading_level: 5

#### verify_access_token

::: django_matt.auth.jwt.verify_access_token
    options:
      show_source: false
      heading_level: 5

#### verify_refresh_token

::: django_matt.auth.jwt.verify_refresh_token
    options:
      show_source: false
      heading_level: 5

#### decode_token

::: django_matt.auth.jwt.decode_token
    options:
      show_source: false
      heading_level: 5

#### refresh_tokens

::: django_matt.auth.jwt.refresh_tokens
    options:
      show_source: false
      heading_level: 5

---

## Decorators

### jwt_required

::: django_matt.auth.decorators.jwt_required
    options:
      show_source: false
      heading_level: 4

### jwt_optional

::: django_matt.auth.decorators.jwt_optional
    options:
      show_source: false
      heading_level: 4

### requires_auth

::: django_matt.auth.decorators.requires_auth
    options:
      show_source: false
      heading_level: 4

### admin_required

::: django_matt.auth.decorators.admin_required
    options:
      show_source: false
      heading_level: 4

### superuser_required

::: django_matt.auth.decorators.superuser_required
    options:
      show_source: false
      heading_level: 4

### with_roles

::: django_matt.auth.decorators.with_roles
    options:
      show_source: false
      heading_level: 4

### with_permission

::: django_matt.auth.decorators.with_permission
    options:
      show_source: false
      heading_level: 4

---

## Middleware

### JWTAuthenticationMiddleware

::: django_matt.auth.middleware.JWTAuthenticationMiddleware
    options:
      show_source: false
      heading_level: 4

### JWTAuthenticationMiddlewareAsync

::: django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync
    options:
      show_source: false
      heading_level: 4

---

## RBAC (Role-Based Access Control)

### Role

::: django_matt.auth.rbac.Role
    options:
      show_source: false
      heading_level: 4

### RBACConfig

::: django_matt.auth.rbac.RBACConfig
    options:
      show_source: false
      heading_level: 4

### RBAC Functions

#### get_user_roles

::: django_matt.auth.rbac.get_user_roles
    options:
      show_source: false
      heading_level: 5

#### get_user_permissions

::: django_matt.auth.rbac.get_user_permissions
    options:
      show_source: false
      heading_level: 5

#### user_has_role

::: django_matt.auth.rbac.user_has_role
    options:
      show_source: false
      heading_level: 5

#### user_has_permission

::: django_matt.auth.rbac.user_has_permission
    options:
      show_source: false
      heading_level: 5

---

## Magic Link Authentication

### MagicLinkConfig

::: django_matt.auth.magic_link.MagicLinkConfig
    options:
      show_source: false
      heading_level: 4

### Functions

#### create_magic_link_token

::: django_matt.auth.magic_link.create_magic_link_token
    options:
      show_source: false
      heading_level: 5

#### verify_magic_link_token

::: django_matt.auth.magic_link.verify_magic_link_token
    options:
      show_source: false
      heading_level: 5

#### send_magic_link

::: django_matt.auth.magic_link.send_magic_link
    options:
      show_source: false
      heading_level: 5

---

## API Keys

### APIKeyConfig

::: django_matt.auth.api_keys.APIKeyConfig
    options:
      show_source: false
      heading_level: 4

### Decorators

#### api_key_required

::: django_matt.auth.api_keys.api_key_required
    options:
      show_source: false
      heading_level: 5

#### api_key_optional

::: django_matt.auth.api_keys.api_key_optional
    options:
      show_source: false
      heading_level: 5

#### requires_scope

::: django_matt.auth.api_keys.requires_scope
    options:
      show_source: false
      heading_level: 5

#### requires_plan

::: django_matt.auth.api_keys.requires_plan
    options:
      show_source: false
      heading_level: 5

---

## OAuth Providers

### OAuthConfig

::: django_matt.auth.oauth.OAuthConfig
    options:
      show_source: false
      heading_level: 4

### Providers

#### GoogleOAuthProvider

::: django_matt.auth.oauth.GoogleOAuthProvider
    options:
      show_source: false
      heading_level: 5

#### GitHubOAuthProvider

::: django_matt.auth.oauth.GitHubOAuthProvider
    options:
      show_source: false
      heading_level: 5

#### AppleOAuthProvider

::: django_matt.auth.oauth.AppleOAuthProvider
    options:
      show_source: false
      heading_level: 5

#### MicrosoftOAuthProvider

::: django_matt.auth.oauth.MicrosoftOAuthProvider
    options:
      show_source: false
      heading_level: 5

---

## Passkeys / WebAuthn

### PasskeyConfig

::: django_matt.auth.passkeys.PasskeyConfig
    options:
      show_source: false
      heading_level: 4

### Functions

#### generate_registration_options

::: django_matt.auth.passkeys.generate_registration_options
    options:
      show_source: false
      heading_level: 5

#### verify_registration_response

::: django_matt.auth.passkeys.verify_registration_response
    options:
      show_source: false
      heading_level: 5

#### generate_authentication_options

::: django_matt.auth.passkeys.generate_authentication_options
    options:
      show_source: false
      heading_level: 5

#### verify_authentication_response

::: django_matt.auth.passkeys.verify_authentication_response
    options:
      show_source: false
      heading_level: 5

---

## Enterprise SSO

### SSOConfig

::: django_matt.auth.sso.SSOConfig
    options:
      show_source: false
      heading_level: 4

### Providers

#### SAMLProvider

::: django_matt.auth.sso.SAMLProvider
    options:
      show_source: false
      heading_level: 5

#### OIDCProvider

::: django_matt.auth.sso.OIDCProvider
    options:
      show_source: false
      heading_level: 5

---

## Controllers

### AuthController

Pre-built authentication controller with login, register, refresh, and logout endpoints.

::: django_matt.auth.controllers.AuthController
    options:
      show_source: false
      heading_level: 4

### OAuthController

::: django_matt.auth.oauth.OAuthController
    options:
      show_source: false
      heading_level: 4

### PasskeyController

::: django_matt.auth.passkeys.PasskeyController
    options:
      show_source: false
      heading_level: 4

### SSOController

::: django_matt.auth.sso.SSOController
    options:
      show_source: false
      heading_level: 4

### APIKeyController

::: django_matt.auth.api_keys.APIKeyController
    options:
      show_source: false
      heading_level: 4

---

## Schemas

### TokenPair

::: django_matt.auth.schemas.TokenPair
    options:
      show_source: false
      heading_level: 4

### LoginRequest

::: django_matt.auth.schemas.LoginRequest
    options:
      show_source: false
      heading_level: 4

### RegisterRequest

::: django_matt.auth.schemas.RegisterRequest
    options:
      show_source: false
      heading_level: 4

### UserResponse

::: django_matt.auth.schemas.UserResponse
    options:
      show_source: false
      heading_level: 4
