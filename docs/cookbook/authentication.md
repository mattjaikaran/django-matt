# Authentication Recipes

This cookbook covers common authentication patterns and recipes.

## Multi-Factor Authentication (MFA)

### TOTP-based MFA

```python
import pyotp
from django_matt import DjangoMattAPI
from django_matt.auth import jwt_required, create_token_pair
from pydantic import BaseModel

api = DjangoMattAPI()


class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str


class MFAVerifyRequest(BaseModel):
    code: str


@api.post("/auth/mfa/setup", response=MFASetupResponse)
@jwt_required
async def setup_mfa(request):
    """Generate MFA secret and QR code for setup."""
    user = request.user

    # Generate secret
    secret = pyotp.random_base32()

    # Store secret (encrypted) in user profile
    user.mfa_secret = encrypt(secret)
    user.mfa_enabled = False  # Not enabled until verified
    await user.asave()

    # Generate QR code URL
    totp = pyotp.TOTP(secret)
    qr_url = totp.provisioning_uri(
        name=user.email,
        issuer_name="MyApp"
    )

    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_url,
    )


@api.post("/auth/mfa/verify")
@jwt_required
async def verify_mfa(request, data: MFAVerifyRequest):
    """Verify MFA code and enable MFA for user."""
    user = request.user

    secret = decrypt(user.mfa_secret)
    totp = pyotp.TOTP(secret)

    if not totp.verify(data.code):
        raise UnauthorizedError("Invalid MFA code")

    user.mfa_enabled = True
    await user.asave()

    return {"mfa_enabled": True}


@api.post("/auth/login-mfa")
async def login_with_mfa(request, data: LoginWithMFARequest):
    """Login with MFA verification."""
    user = await authenticate(data.email, data.password)
    if not user:
        raise UnauthorizedError("Invalid credentials")

    if user.mfa_enabled:
        if not data.mfa_code:
            return {"requires_mfa": True}

        secret = decrypt(user.mfa_secret)
        totp = pyotp.TOTP(secret)

        if not totp.verify(data.mfa_code):
            raise UnauthorizedError("Invalid MFA code")

    return create_token_pair(user)
```

### Backup Codes

```python
import secrets

def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate backup codes for MFA recovery."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


@api.post("/auth/mfa/backup-codes")
@jwt_required
async def get_backup_codes(request):
    """Generate new backup codes."""
    user = request.user

    codes = generate_backup_codes()

    # Store hashed codes
    user.backup_codes = [hash_code(c) for c in codes]
    await user.asave()

    # Return plain codes (only time user sees them)
    return {"backup_codes": codes}


@api.post("/auth/login-backup")
async def login_with_backup_code(request, data: BackupCodeLoginRequest):
    """Login using a backup code."""
    user = await authenticate(data.email, data.password)
    if not user:
        raise UnauthorizedError("Invalid credentials")

    # Check backup code
    code_hash = hash_code(data.backup_code)
    if code_hash not in user.backup_codes:
        raise UnauthorizedError("Invalid backup code")

    # Remove used code
    user.backup_codes.remove(code_hash)
    await user.asave()

    return create_token_pair(user)
```

## Social Login Integration

### Complete OAuth Flow

```python
from django_matt import DjangoMattAPI
from django_matt.auth.oauth import GoogleOAuthProvider, GitHubOAuthProvider

api = DjangoMattAPI()

# Configure providers
providers = {
    "google": GoogleOAuthProvider(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=f"{settings.SITE_URL}/auth/google/callback",
    ),
    "github": GitHubOAuthProvider(
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        redirect_uri=f"{settings.SITE_URL}/auth/github/callback",
    ),
}


@api.get("/auth/{provider}/authorize")
async def oauth_authorize(request, provider: str):
    """Redirect to OAuth provider."""
    if provider not in providers:
        raise NotFoundError(f"Unknown provider: {provider}")

    auth_url = await providers[provider].get_authorization_url(
        state=generate_state_token(),
    )

    return RedirectResponse(auth_url)


@api.get("/auth/{provider}/callback")
async def oauth_callback(request, provider: str, code: str, state: str):
    """Handle OAuth callback."""
    if provider not in providers:
        raise NotFoundError(f"Unknown provider: {provider}")

    # Verify state token
    if not verify_state_token(state):
        raise UnauthorizedError("Invalid state token")

    # Exchange code for tokens
    token_data = await providers[provider].exchange_code(code)

    # Get user info
    user_info = await providers[provider].get_user_info(
        token_data["access_token"]
    )

    # Find or create user
    user, created = await get_or_create_oauth_user(
        provider=provider,
        provider_id=user_info["id"],
        email=user_info["email"],
        name=user_info.get("name"),
    )

    # Create session/tokens
    tokens = create_token_pair(user)

    # Redirect to frontend with tokens
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback?token={tokens.access_token}"
    )


async def get_or_create_oauth_user(
    provider: str,
    provider_id: str,
    email: str,
    name: str | None = None,
):
    """Get existing user or create new one from OAuth data."""
    # Check for existing OAuth connection
    connection = await OAuthConnection.objects.filter(
        provider=provider,
        provider_user_id=provider_id,
    ).select_related("user").afirst()

    if connection:
        return connection.user, False

    # Check for existing user with email
    user = await User.objects.filter(email=email).afirst()

    if not user:
        # Create new user
        user = await User.objects.acreate(
            email=email,
            username=email.split("@")[0],
            first_name=name.split()[0] if name else "",
            last_name=" ".join(name.split()[1:]) if name else "",
        )

    # Create OAuth connection
    await OAuthConnection.objects.acreate(
        user=user,
        provider=provider,
        provider_user_id=provider_id,
    )

    return user, True
```

## Session with Remember Me

```python
from django_matt.auth.session import create_session, SESSION_COOKIE_NAME

@api.post("/auth/login")
async def login(request, data: LoginRequest):
    """Login with optional remember me."""
    user = await authenticate(data.email, data.password)
    if not user:
        raise UnauthorizedError("Invalid credentials")

    # Set session duration based on remember me
    max_age = 86400 * 30 if data.remember_me else None  # 30 days or session

    session = await create_session(user, max_age=max_age)

    response = JsonResponse({"user": UserSchema.from_orm(user).dict()})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.token,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="Lax",
    )

    return response
```

## Rate Limiting Auth Endpoints

```python
from django_matt.throttling import throttle

@api.post("/auth/login")
@throttle(rate="5/minute")  # 5 attempts per minute (auto-selects AnonRateThrottle or UserRateThrottle)
async def login(request, data: LoginRequest):
    """Rate-limited login endpoint."""
    user = await authenticate(data.email, data.password)
    if not user:
        # Log failed attempt for security monitoring
        await log_failed_login(
            email=data.email,
            ip=get_client_ip(request),
        )
        raise UnauthorizedError("Invalid credentials")

    return create_token_pair(user)


# Account lockout after too many failures
async def authenticate_with_lockout(email: str, password: str):
    """Authenticate with account lockout protection."""
    user = await User.objects.filter(email=email).afirst()
    if not user:
        return None

    # Check if locked out
    if user.lockout_until and user.lockout_until > timezone.now():
        raise UnauthorizedError(
            f"Account locked. Try again after {user.lockout_until}"
        )

    # Verify password
    if not user.check_password(password):
        user.failed_login_attempts += 1

        # Lock after 5 failures
        if user.failed_login_attempts >= 5:
            user.lockout_until = timezone.now() + timedelta(minutes=15)

        await user.asave()
        return None

    # Reset on successful login
    user.failed_login_attempts = 0
    user.lockout_until = None
    await user.asave()

    return user
```

## Token Refresh

```python
from django_matt.auth import async_refresh_tokens

@api.post("/auth/refresh")
async def refresh(request, data: RefreshRequest):
    """Refresh access token using the built-in refresh flow."""
    try:
        new_tokens = await async_refresh_tokens(data.refresh_token)
        return new_tokens.model_dump()
    except Exception:
        raise UnauthorizedError("Invalid refresh token")
```

!!! note "Token Blacklisting"
    django-matt does not currently include a `RefreshToken` database model or
    token blacklisting. The built-in `async_refresh_tokens()` verifies the refresh
    token's signature and expiration, then issues a new token pair. For revocation,
    you would need to implement your own blacklist table keyed on the `jti` claim.

## API Key Authentication

```python
from django_matt.auth.api_keys import APIKey, api_key_required
import secrets

@api.post("/api-keys")
@jwt_required
async def create_api_key(request, data: APIKeyCreateRequest):
    """Create a new API key."""
    user = request.user

    # Generate key
    key = f"dm_{secrets.token_urlsafe(32)}"

    # Store hashed key
    api_key = await APIKey.objects.acreate(
        user=user,
        name=data.name,
        key_hash=hash_key(key),
        scopes=data.scopes or ["read"],
        expires_at=data.expires_at,
    )

    # Return key only once
    return {
        "id": api_key.id,
        "key": key,  # Only shown once!
        "name": api_key.name,
        "scopes": api_key.scopes,
    }


@api.get("/internal/data")
@api_key_required(scopes=["read"])
async def get_internal_data(request):
    """Access with API key only."""
    return {"data": "..."}


@api.post("/internal/webhook")
@api_key_required(scopes=["write"])
async def receive_webhook(request, data: WebhookData):
    """Write access with API key."""
    ...
```

## Impersonation for Admin

```python
@api.post("/admin/impersonate/{user_id}")
@jwt_required
@admin_required
async def start_impersonation(request, user_id: int):
    """Admin impersonates another user."""
    admin = request.user

    target_user = await User.objects.aget(id=user_id)

    # Create impersonation token with admin context
    token = create_access_token(
        target_user,
        extra_claims={
            "impersonator_id": admin.id,
            "impersonator_email": admin.email,
        },
    )

    # Log impersonation for audit
    await AuditLog.objects.acreate(
        actor=admin,
        action="impersonate_start",
        target_user=target_user,
    )

    return {"access_token": token}


@api.post("/admin/impersonate/stop")
@jwt_required
async def stop_impersonation(request):
    """Stop impersonation and return to admin."""
    impersonator_id = request.auth.get("impersonator_id")

    if not impersonator_id:
        raise BadRequestError("Not currently impersonating")

    admin = await User.objects.aget(id=impersonator_id)
    return create_token_pair(admin)
```

## Password Reset Flow

!!! warning "Not Built-In"
    django-matt does not include built-in `generate_reset_token` or `verify_reset_token`
    functions. The `AuthController` provides `change-password` (for authenticated users)
    but not a forgot-password/reset flow. The schemas `ResetPasswordRequest` and
    `ResetPasswordConfirmRequest` exist for you to build your own implementation.

Here is a recipe for implementing password reset yourself:

```python
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

@api.post("/auth/forgot-password")
@throttle(rate="3/hour")
async def forgot_password(request, data: ForgotPasswordRequest):
    """Request password reset email."""
    user = await User.objects.filter(email=data.email).afirst()

    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        # Send email using your preferred method
        await send_email(
            to=user.email,
            subject="Reset Your Password",
            template="password_reset",
            context={"reset_url": reset_url, "user": user},
        )

    # Always return success (don't reveal if email exists)
    return {"message": "If the email exists, a reset link has been sent"}


@api.post("/auth/reset-password")
async def reset_password(request, data: ResetPasswordRequest):
    """Reset password with token."""
    try:
        uid = force_str(urlsafe_base64_decode(data.uid))
        user = await User.objects.aget(pk=uid)
    except (TypeError, ValueError, User.DoesNotExist):
        raise UnauthorizedError("Invalid reset link")

    if not default_token_generator.check_token(user, data.token):
        raise UnauthorizedError("Invalid or expired reset token")

    user.set_password(data.new_password)
    await user.asave()

    return {"message": "Password reset successful"}
```
