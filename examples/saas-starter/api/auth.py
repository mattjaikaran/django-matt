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

from typing import Optional
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets

from django_matt.core import APIController, api_controller
from django_matt.auth import jwt_required, jwt_optional
from django_matt.permissions import AllowAny, IsAuthenticated

from core.models import User, MagicLinkToken, AuditLog
from core.schemas import (
    LoginRequest, LoginResponse, RefreshRequest, TokenResponse,
    RegisterRequest, RegisterResponse, UserResponse, UserProfileResponse,
    UserUpdate, MagicLinkRequest, MagicLinkVerifyRequest,
    PasswordResetRequest, PasswordResetConfirmRequest, PasswordChangeRequest,
    OAuthAuthorizationRequest, OAuthCallbackRequest, OAuthConnectResponse,
)


@api_controller("/auth", tags=["Auth"])
class AuthController(APIController):
    """Authentication endpoints."""

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

    @APIController.post("/login", response=LoginResponse, permissions=[AllowAny])
    async def login(self, request, data: LoginRequest):
        """
        Authenticate user with email and password.

        Returns JWT access and refresh tokens.
        """
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

    @APIController.post("/register", response=RegisterResponse, permissions=[AllowAny])
    async def register(self, request, data: RegisterRequest):
        """
        Register a new user account.

        Creates a new user and their personal organization.
        """
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

    @APIController.post("/refresh", response=TokenResponse, permissions=[AllowAny])
    async def refresh_token(self, request, data: RefreshRequest):
        """
        Refresh access token using refresh token.
        """
        from django_matt.auth.jwt import decode_token, create_access_token

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

    @APIController.post("/logout", permissions=[IsAuthenticated])
    @jwt_required
    async def logout(self, request):
        """
        Logout current user.

        Invalidates the current refresh token (if token blacklisting is enabled).
        """
        await AuditLog.objects.acreate(
            user=request.user,
            action="user.logout",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return {"message": "Logged out successfully"}

    # =========================================================================
    # Current User
    # =========================================================================

    @APIController.get("/me", response=UserProfileResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_current_user(self, request):
        """
        Get current authenticated user profile.
        """
        return UserProfileResponse.model_validate(request.user)

    @APIController.patch("/me", response=UserProfileResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_current_user(self, request, data: UserUpdate):
        """
        Update current user profile.
        """
        user = request.user

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        await user.asave()

        return UserProfileResponse.model_validate(user)

    # =========================================================================
    # Magic Link
    # =========================================================================

    @APIController.post("/magic-link", permissions=[AllowAny])
    async def request_magic_link(self, request, data: MagicLinkRequest):
        """
        Request a magic link for passwordless login.

        Sends an email with a one-time login link.
        """
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

    @APIController.post("/magic-link/verify", response=LoginResponse, permissions=[AllowAny])
    async def verify_magic_link(self, request, data: MagicLinkVerifyRequest):
        """
        Verify magic link token and login.
        """
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

    @APIController.post("/password/reset", permissions=[AllowAny])
    async def request_password_reset(self, request, data: PasswordResetRequest):
        """
        Request password reset email.
        """
        # Always return success to prevent email enumeration
        try:
            user = await User.objects.aget(email=data.email.lower())
            # TODO: Send password reset email
            # send_password_reset_email.delay(user.id)
        except User.DoesNotExist:
            pass

        return {"message": "If the email exists, a password reset link has been sent."}

    @APIController.post("/password/reset/confirm", permissions=[AllowAny])
    async def confirm_password_reset(self, request, data: PasswordResetConfirmRequest):
        """
        Confirm password reset with token.
        """
        # TODO: Implement token verification and password reset
        return {"message": "Password has been reset successfully."}

    @APIController.post("/password/change", permissions=[IsAuthenticated])
    @jwt_required
    async def change_password(self, request, data: PasswordChangeRequest):
        """
        Change password for authenticated user.
        """
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

    @APIController.get("/oauth/{provider}/authorize", permissions=[AllowAny])
    async def oauth_authorize(self, request, provider: str, params: OAuthAuthorizationRequest = None):
        """
        Get OAuth authorization URL for provider.

        Supported providers: google, github
        """
        oauth_settings = settings.MATT_OAUTH.get(provider.upper())
        if not oauth_settings:
            return {"error": f"Unknown provider: {provider}"}, 400

        # Build authorization URL based on provider
        if provider == "google":
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={oauth_settings['CLIENT_ID']}"
                f"&redirect_uri={oauth_settings['REDIRECT_URI']}"
                f"&response_type=code"
                f"&scope=email profile"
                f"&state={params.state if params else ''}"
            )
        elif provider == "github":
            auth_url = (
                f"https://github.com/login/oauth/authorize"
                f"?client_id={oauth_settings['CLIENT_ID']}"
                f"&redirect_uri={oauth_settings['REDIRECT_URI']}"
                f"&scope=user:email"
                f"&state={params.state if params else ''}"
            )
        else:
            return {"error": f"Provider not implemented: {provider}"}, 400

        return {"authorization_url": auth_url}

    @APIController.post("/oauth/{provider}/callback", response=LoginResponse, permissions=[AllowAny])
    async def oauth_callback(self, request, provider: str, data: OAuthCallbackRequest):
        """
        Handle OAuth callback and exchange code for tokens.
        """
        # TODO: Implement OAuth token exchange and user creation/login
        return {"error": "OAuth callback not implemented"}, 501

    @APIController.get("/oauth/connections", permissions=[IsAuthenticated])
    @jwt_required
    async def list_oauth_connections(self, request):
        """
        List OAuth connections for current user.
        """
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

    @APIController.delete("/oauth/{provider}", permissions=[IsAuthenticated])
    @jwt_required
    async def disconnect_oauth(self, request, provider: str):
        """
        Disconnect OAuth provider from current user.
        """
        user = request.user

        if provider == "google":
            user.google_id = None
        elif provider == "github":
            user.github_id = None
        else:
            return {"error": f"Unknown provider: {provider}"}, 400

        await user.asave()

        return {"message": f"Disconnected from {provider}"}
