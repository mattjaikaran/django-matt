"""
Authentication API controllers.

Includes:
- Login/logout
- Registration
- JWT token refresh
- OAuth flows
- Magic link authentication
- Password reset
"""

import contextlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import delete, get, patch, post

from core.models import AuditLog, MagicLinkToken, User
from core.schemas import (
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    OAuthCallbackRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)


class AuthController(APIController):
    prefix = "/auth"
    tags = ["Auth"]

    @staticmethod
    def create_tokens(user: User) -> dict:
        """Create JWT access and refresh tokens for a user."""
        from django_matt.auth.jwt import create_access_token, create_refresh_token

        jwt_settings = settings.MATT_JWT
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": jwt_settings.get("ACCESS_TOKEN_LIFETIME", 900),
        }

    # =========================================================================
    # Basic Auth
    # =========================================================================

    @post("/login")
    async def login(self, request, data: LoginRequest) -> dict:
        """Authenticate user with email and password."""
        try:
            user = await User.objects.aget(email=data.email.lower())
        except User.DoesNotExist:
            return {"error": "Invalid credentials"}, 401

        if not user.check_password(data.password):
            return {"error": "Invalid credentials"}, 401

        if not user.is_active:
            return {"error": "Account is disabled"}, 403

        # Update last login
        user.last_login_at = timezone.now()
        await user.asave(update_fields=["last_login_at"])

        # Create audit log
        await AuditLog.objects.acreate(
            user=user,
            action="user.login",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        tokens = self.create_tokens(user)
        return {
            **tokens,
            "user": UserResponse.model_validate(user),
        }

    @post("/register")
    async def register(self, request, data: RegisterRequest) -> dict:
        """Register a new user account."""
        # Check if email already exists
        if await User.objects.filter(email=data.email.lower()).aexists():
            return {"error": "Email already registered"}, 400

        # Create user
        user = await User.objects.acreate(
            email=data.email.lower(),
            first_name=data.first_name,
            last_name=data.last_name,
        )
        user.set_password(data.password)
        await user.asave()

        # Create audit log
        await AuditLog.objects.acreate(
            user=user,
            action="user.registered",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return {
            "user": UserResponse.model_validate(user),
            "message": "Registration successful. Please verify your email.",
        }

    @post("/refresh")
    async def refresh_token(self, request, data: RefreshRequest) -> dict:
        """Refresh access token using refresh token."""
        from django_matt.auth.jwt import create_access_token, decode_token

        try:
            payload = decode_token(data.refresh_token, token_type="refresh")
            user = await User.objects.aget(id=payload["sub"])

            if not user.is_active:
                return {"error": "Account is disabled"}, 403

            access_token = create_access_token(user)
            jwt_settings = settings.MATT_JWT

            return {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": jwt_settings.get("ACCESS_TOKEN_LIFETIME", 900),
            }
        except Exception:
            return {"error": "Invalid refresh token"}, 401

    @post("/logout")
    @jwt_required
    async def logout(self, request) -> dict:
        """Logout current user."""
        await AuditLog.objects.acreate(
            user=request.user,
            action="user.logout",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return {"message": "Logged out successfully"}

    # =========================================================================
    # Current User
    # =========================================================================

    @get("/me")
    @jwt_required
    async def get_current_user(self, request) -> dict:
        """Get current authenticated user profile."""
        return UserProfileResponse.model_validate(request.user)

    @patch("/me")
    @jwt_required
    async def update_current_user(self, request, data: UserUpdate) -> dict:
        """Update current user profile."""
        user = request.user

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        await user.asave()

        return UserProfileResponse.model_validate(user)

    # =========================================================================
    # Magic Link
    # =========================================================================

    @post("/magic-link")
    async def request_magic_link(self, request, data: MagicLinkRequest) -> dict:
        """Request a magic link for passwordless login."""
        # Always return success to prevent email enumeration
        try:
            user = await User.objects.aget(email=data.email.lower())

            # Create magic link token
            magic_settings = settings.MATT_MAGIC_LINK
            token = secrets.token_urlsafe(32)
            expires_at = timezone.now() + timedelta(
                seconds=magic_settings.get("TOKEN_LIFETIME", 900)
            )

            await MagicLinkToken.objects.acreate(
                email=user.email,
                token=token,
                expires_at=expires_at,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            # TODO: Send email with magic link
            # send_magic_link_email.delay(user.email, token)

        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        return {"message": "If the email exists, a magic link has been sent."}

    @post("/magic-link/verify")
    async def verify_magic_link(self, request, data: MagicLinkVerifyRequest) -> dict:
        """Verify magic link token and login."""
        try:
            token = await MagicLinkToken.objects.select_related().aget(
                token=data.token,
                is_used=False,
            )

            if not token.is_valid:
                return {"error": "Invalid or expired token"}, 400

            user = await User.objects.aget(email=token.email)

            # Mark token as used
            token.is_used = True
            token.used_at = timezone.now()
            await token.asave()

            # Update user last login
            user.last_login_at = timezone.now()
            if not user.is_verified:
                user.is_verified = True
            await user.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=user,
                action="user.magic_link_login",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            tokens = self.create_tokens(user)
            return {
                **tokens,
                "user": UserResponse.model_validate(user),
            }

        except MagicLinkToken.DoesNotExist:
            return {"error": "Invalid token"}, 400

    # =========================================================================
    # Password Reset
    # =========================================================================

    @post("/password/reset")
    async def request_password_reset(self, request, data: PasswordResetRequest) -> dict:
        """Request password reset email."""
        # Always return success to prevent email enumeration
        with contextlib.suppress(User.DoesNotExist):
            await User.objects.aget(email=data.email.lower())
            # TODO: Send password reset email
            # send_password_reset_email.delay(user.id)

        return {"message": "If the email exists, a password reset link has been sent."}

    @post("/password/reset/confirm")
    async def confirm_password_reset(self, request, data: PasswordResetConfirmRequest) -> dict:
        """Confirm password reset with token."""
        # TODO: Implement token verification and password reset
        return {"message": "Password has been reset successfully."}

    @post("/password/change")
    @jwt_required
    async def change_password(self, request, data: PasswordChangeRequest) -> dict:
        """Change password for authenticated user."""
        user = request.user

        if not user.check_password(data.current_password):
            return {"error": "Current password is incorrect"}, 400

        user.set_password(data.new_password)
        await user.asave()

        await AuditLog.objects.acreate(
            user=user,
            action="user.password_changed",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return {"message": "Password changed successfully"}

    # =========================================================================
    # OAuth
    # =========================================================================

    @get("/oauth/<str:provider>/authorize")
    async def oauth_authorize(self, request, provider: str) -> dict:
        """Get OAuth authorization URL for provider."""
        oauth_settings = settings.MATT_OAUTH.get(provider.upper())
        if not oauth_settings:
            return {"error": f"Unknown provider: {provider}"}, 400

        state = request.GET.get("state", "")

        # Build authorization URL based on provider
        if provider == "google":
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={oauth_settings['CLIENT_ID']}"
                f"&redirect_uri={oauth_settings['REDIRECT_URI']}"
                f"&response_type=code"
                f"&scope=email profile"
                f"&state={state}"
            )
        elif provider == "github":
            auth_url = (
                f"https://github.com/login/oauth/authorize"
                f"?client_id={oauth_settings['CLIENT_ID']}"
                f"&redirect_uri={oauth_settings['REDIRECT_URI']}"
                f"&scope=user:email"
                f"&state={state}"
            )
        else:
            return {"error": f"Provider not implemented: {provider}"}, 400

        return {"authorization_url": auth_url}

    @post("/oauth/<str:provider>/callback")
    async def oauth_callback(self, request, provider: str, data: OAuthCallbackRequest) -> dict:
        """Handle OAuth callback and exchange code for tokens."""
        # TODO: Implement OAuth token exchange and user creation/login
        return {"error": "OAuth callback not implemented"}, 501

    @get("/oauth/connections")
    @jwt_required
    async def list_oauth_connections(self, request) -> dict:
        """List OAuth connections for current user."""
        user = request.user
        connections = []

        if user.google_id:
            connections.append({"provider": "google", "connected": True})
        else:
            connections.append({"provider": "google", "connected": False})

        if user.github_id:
            connections.append({"provider": "github", "connected": True})
        else:
            connections.append({"provider": "github", "connected": False})

        return {"connections": connections}

    @delete("/oauth/<str:provider>")
    @jwt_required
    async def disconnect_oauth(self, request, provider: str) -> dict:
        """Disconnect OAuth provider from current user."""
        user = request.user

        if provider == "google":
            user.google_id = None
        elif provider == "github":
            user.github_id = None
        else:
            return {"error": f"Unknown provider: {provider}"}, 400

        await user.asave()

        return {"message": f"Disconnected from {provider}"}
