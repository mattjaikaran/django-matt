# Enterprise SSO

SAML 2.0 and OpenID Connect (OIDC) for enterprise single sign-on.

## Overview

Enterprise SSO allows organizations to authenticate users through their identity provider (IdP):
- **SAML 2.0** - Okta, Azure AD, OneLogin, PingFederate
- **OIDC** - Google Workspace, Auth0, Keycloak, Azure AD

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "SSO": {
        "ENABLED": True,
        "SP_ENTITY_ID": "https://myapp.com/saml/metadata",
        "SP_ACS_URL": "https://myapp.com/auth/sso/callback",
        "DEFAULT_RELAY_STATE": "/dashboard",
    },
}
```

## SSOController

Use the pre-built controller:

```python
from django_matt.auth.sso import SSOController

api.register_controller(SSOController)

# Provides:
# GET /auth/sso/{connection_id}/login - Redirect to IdP
# POST /auth/sso/{connection_id}/callback - Handle SAML/OIDC response
# GET /auth/sso/metadata/{connection_id} - SP metadata for SAML
```

## SSO Connection Model

Store per-organization SSO configurations:

```python
# Your app's models
class SSOConnection(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    provider_type = models.CharField(max_length=20)  # "saml" or "oidc"
    name = models.CharField(max_length=100)  # "Okta", "Azure AD"
    is_active = models.BooleanField(default=True)

    # SAML settings
    idp_entity_id = models.URLField(blank=True)
    idp_sso_url = models.URLField(blank=True)
    idp_certificate = models.TextField(blank=True)

    # OIDC settings
    client_id = models.CharField(max_length=255, blank=True)
    client_secret = models.CharField(max_length=255, blank=True)
    issuer_url = models.URLField(blank=True)
```

## SAML 2.0

### Configuration

```python
from django_matt.auth.sso import SAMLProvider

saml = SAMLProvider(
    sp_entity_id="https://myapp.com/saml/metadata",
    sp_acs_url="https://myapp.com/auth/sso/callback",
    idp_entity_id="https://idp.okta.com/xxxx",
    idp_sso_url="https://idp.okta.com/app/xxx/sso/saml",
    idp_certificate="-----BEGIN CERTIFICATE-----...",
)
```

### Flow

```python
@api.get("/sso/{connection_id}/login")
async def sso_login(request, connection_id: int):
    connection = await SSOConnection.objects.aget(id=connection_id)
    provider = get_provider_for_connection(connection)

    # Generate SAML request
    redirect_url = provider.get_login_url(
        relay_state=request.GET.get("next", "/dashboard")
    )
    return RedirectResponse(redirect_url)

@api.post("/sso/{connection_id}/callback")
async def sso_callback(request, connection_id: int):
    connection = await SSOConnection.objects.aget(id=connection_id)
    provider = get_provider_for_connection(connection)

    # Verify SAML response
    saml_response = request.POST.get("SAMLResponse")
    user_info = await provider.verify_response(saml_response)

    # Create/update user
    user = await get_or_create_sso_user(user_info, connection)
    return create_token_pair(user)
```

### Metadata

Provide SP metadata to your IdP:

```python
@api.get("/sso/metadata/{connection_id}")
async def sp_metadata(request, connection_id: int):
    connection = await SSOConnection.objects.aget(id=connection_id)
    provider = get_provider_for_connection(connection)

    return Response(
        provider.get_sp_metadata(),
        content_type="application/xml",
    )
```

## OpenID Connect (OIDC)

### Configuration

```python
from django_matt.auth.sso import OIDCProvider

oidc = OIDCProvider(
    client_id="your-client-id",
    client_secret="your-client-secret",
    issuer_url="https://accounts.google.com",
    redirect_uri="https://myapp.com/auth/sso/callback",
)
```

### Flow

```python
@api.get("/sso/{connection_id}/login")
async def sso_login(request, connection_id: int):
    connection = await SSOConnection.objects.aget(id=connection_id)
    provider = get_provider_for_connection(connection)

    # Generate OIDC authorization URL with PKCE
    redirect_url, state, code_verifier = provider.get_authorization_url()

    # Store state and code_verifier in session
    request.session["sso_state"] = state
    request.session["sso_code_verifier"] = code_verifier

    return RedirectResponse(redirect_url)

@api.get("/sso/{connection_id}/callback")
async def sso_callback(request, connection_id: int, code: str, state: str):
    connection = await SSOConnection.objects.aget(id=connection_id)
    provider = get_provider_for_connection(connection)

    # Verify state
    if state != request.session.get("sso_state"):
        raise AuthenticationAPIError("Invalid state")

    # Exchange code for tokens
    code_verifier = request.session.get("sso_code_verifier")
    user_info = await provider.exchange_code(code, code_verifier)

    user = await get_or_create_sso_user(user_info, connection)
    return create_token_pair(user)
```

## User Provisioning

```python
async def get_or_create_sso_user(info: SSOUserInfo, connection: SSOConnection):
    # Check if user exists
    user = await User.objects.filter(email=info.email).afirst()

    if not user:
        # Create new user
        user = await User.objects.acreate(
            email=info.email,
            first_name=info.first_name or "",
            last_name=info.last_name or "",
            is_active=True,
        )

    # Add user to organization
    await Membership.objects.aupdate_or_create(
        user=user,
        organization=connection.organization,
        defaults={"role": "member"},
    )

    return user
```

## Domain Verification

Route users to SSO based on email domain:

```python
@api.post("/auth/check-sso")
async def check_sso(request, data: EmailCheckRequest):
    domain = data.email.split("@")[1]

    connection = await SSOConnection.objects.filter(
        organization__verified_domains__domain=domain,
        is_active=True,
    ).afirst()

    if connection:
        return {
            "sso_required": True,
            "sso_url": f"/auth/sso/{connection.id}/login",
            "provider_name": connection.name,
        }

    return {"sso_required": False}
```

## Error Handling

```python
from django_matt.auth.sso import (
    SSOError,
    SSOConfigError,
    SSOAuthenticationError,
)

@api.post("/sso/{connection_id}/callback")
async def sso_callback(request, connection_id: int):
    try:
        connection = await SSOConnection.objects.aget(id=connection_id)
        provider = get_provider_for_connection(connection)
        user_info = await provider.verify_response(...)
        user = await get_or_create_sso_user(user_info, connection)
        return create_token_pair(user)
    except SSOConfigError as e:
        raise APIError(f"SSO configuration error: {e}", status_code=500)
    except SSOAuthenticationError as e:
        raise AuthenticationAPIError(f"SSO authentication failed: {e}")
```

## Security Considerations

1. **Validate signatures** - Always verify SAML/OIDC signatures
2. **Check audience** - Ensure tokens are intended for your app
3. **Use HTTPS** - SSO requires secure connections
4. **Validate domains** - Only allow verified organization domains
5. **Implement JIT provisioning** - Create users on first login
6. **Handle IdP-initiated logout** - Support single logout (SLO)
