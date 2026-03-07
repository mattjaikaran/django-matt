"""
Authentication controllers for Django Matt.

Provides ready-to-use authentication endpoints using the controller pattern.
All request/response handling uses Pydantic v2 schemas.

Usage:
    from django_matt.auth.controllers import AuthController
    from django_matt import MattAPI

    api = MattAPI()
    api.register_controller(AuthController)

    # Or with custom prefix:
    api.register_controller(AuthController, prefix="api/v1/auth")
"""

from django.contrib.auth import authenticate, get_user_model
from django.http import HttpRequest, JsonResponse

import orjson
from asgiref.sync import sync_to_async

from django_matt.audit.context import extract_client_ip, extract_user_agent
from django_matt.audit.enums import AuditAction, AuditSeverity
from django_matt.audit.models import AuditLog
from django_matt.auth.decorators import jwt_optional, jwt_required
from django_matt.auth.jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
    acreate_token_pair,
    async_refresh_tokens,
)
from django_matt.auth.magic_link import (
    averify_magic_link_token,
    create_magic_link_url,
    magic_link_config,
    send_magic_link_async,
)
from django_matt.auth.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginWithUsernameRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    UserResponse,
)
from django_matt.core.controller import APIController
from django_matt.core.router import get, post

User = get_user_model()


def _user_metadata(user) -> dict:
    """Build rich user metadata for audit logs."""
    return {
        "user_id": str(user.pk),
        "email": getattr(user, "email", ""),
        "username": getattr(user, "username", ""),
        "full_name": user.get_full_name() if hasattr(user, "get_full_name") else "",
        "is_staff": getattr(user, "is_staff", False),
        "is_superuser": getattr(user, "is_superuser", False),
    }


def _request_context(request: HttpRequest) -> dict:
    """Extract IP, user agent, method, and path from request."""
    return {
        "ip_address": extract_client_ip(request),
        "user_agent": extract_user_agent(request),
        "request_method": request.method or "",
        "request_path": request.path or "",
    }


class AuthController(APIController):
    """
    Complete authentication controller with login, register, refresh, and me endpoints.

    Endpoints:
        POST /auth/login - Login with email/password
        POST /auth/register - Register new user
        POST /auth/refresh - Refresh access token
        POST /auth/logout - Logout (client-side token removal)
        GET  /auth/me - Get current user
        PUT  /auth/me - Update current user profile
        POST /auth/change-password - Change password

    Example:
        from django_matt import MattAPI
        from django_matt.auth.controllers import AuthController

        api = MattAPI()
        api.register_controller(AuthController)
    """

    prefix = "auth"
    tags = ["Authentication"]
    auto_error_handling = True

    @post("login")
    async def login(self, request: HttpRequest) -> JsonResponse:
        """
        Authenticate user and return JWT tokens.

        Request body:
            - email: User email address
            - password: User password

        Returns:
            - access_token: JWT access token
            - refresh_token: JWT refresh token
            - expires_in: Access token lifetime in seconds
        """
        # Parse request body
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = LoginRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        ctx = _request_context(request)

        # Find user by email
        try:
            user = await User.objects.aget(email=data.email)
        except User.DoesNotExist:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description=f"Failed login attempt for {data.email} — user not found",
                severity=AuditSeverity.WARNING,
                metadata={"email": data.email, "reason": "user_not_found"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )

        # Check password
        if not user.check_password(data.password):
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                user=user,
                obj=user,
                description=f"Failed login for {user.email} — wrong password",
                severity=AuditSeverity.WARNING,
                metadata={**_user_metadata(user), "reason": "invalid_password"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )

        # Check if user is active
        if not user.is_active:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                user=user,
                obj=user,
                description=f"Login blocked for {user.email} — account inactive",
                severity=AuditSeverity.WARNING,
                metadata={**_user_metadata(user), "reason": "account_inactive"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Account is inactive", "code": "account_inactive"},
                status=401,
            )

        # Generate tokens
        tokens = await acreate_token_pair(user)

        await AuditLog.alog(
            action=AuditAction.LOGIN,
            user=user,
            obj=user,
            description=f"{user.get_full_name() or user.email} logged in",
            metadata={**_user_metadata(user), "auth_method": "email_password"},
            **ctx,
        )

        return JsonResponse(tokens.model_dump())

    @post("login/username")
    async def login_with_username(self, request: HttpRequest) -> JsonResponse:
        """
        Authenticate user with username and password.

        Alternative login endpoint for username-based authentication.
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = LoginWithUsernameRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        ctx = _request_context(request)

        # Use Django's authenticate (sync, must wrap for async)
        user = await sync_to_async(authenticate)(username=data.username, password=data.password)

        if user is None:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description=f"Failed login attempt for username '{data.username}'",
                severity=AuditSeverity.WARNING,
                metadata={"username": data.username, "reason": "invalid_credentials"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )

        if not user.is_active:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                user=user,
                obj=user,
                description=f"Login blocked for {user.username} — account inactive",
                severity=AuditSeverity.WARNING,
                metadata={**_user_metadata(user), "reason": "account_inactive"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Account is inactive", "code": "account_inactive"},
                status=401,
            )

        tokens = await acreate_token_pair(user)

        await AuditLog.alog(
            action=AuditAction.LOGIN,
            user=user,
            obj=user,
            description=f"{user.get_full_name() or user.username} logged in",
            metadata={**_user_metadata(user), "auth_method": "username_password"},
            **ctx,
        )

        return JsonResponse(tokens.model_dump())

    @post("register")
    async def register(self, request: HttpRequest) -> JsonResponse:
        """
        Register a new user account.

        Request body:
            - email: User email address
            - password: User password (min 8 chars)
            - password_confirm: Password confirmation
            - username: Optional username
            - first_name: Optional first name
            - last_name: Optional last name

        Returns:
            - user: User details
            - tokens: JWT token pair
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = RegisterRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        # Check if email already exists
        if await User.objects.filter(email=data.email).aexists():
            return JsonResponse(
                {"detail": "Email already registered", "code": "email_exists"},
                status=400,
            )

        # Check if username already exists (if provided)
        if data.username and await User.objects.filter(username=data.username).aexists():
            return JsonResponse(
                {"detail": "Username already taken", "code": "username_exists"},
                status=400,
            )

        # Create user
        user_data = {
            "email": data.email,
            "is_active": True,
        }

        if data.username:
            user_data["username"] = data.username
        else:
            # Use email as username if not provided
            user_data["username"] = data.email.split("@")[0]

        if data.first_name:
            user_data["first_name"] = data.first_name
        if data.last_name:
            user_data["last_name"] = data.last_name

        user = User(**user_data)
        user.set_password(data.password)
        await user.asave()

        # Generate tokens
        tokens = await acreate_token_pair(user)

        ctx = _request_context(request)
        await AuditLog.alog(
            action=AuditAction.CREATE,
            user=user,
            obj=user,
            description=f"New user registered: {user.email}",
            metadata={**_user_metadata(user), "auth_method": "email_password"},
            **ctx,
        )

        # Build response
        response = AuthResponse(
            user=await UserResponse.afrom_user(user),
            tokens=tokens,
        )

        return JsonResponse(response.model_dump(), status=201)

    @post("refresh")
    async def refresh(self, request: HttpRequest) -> JsonResponse:
        """
        Refresh access token using refresh token.

        Request body:
            - refresh_token: JWT refresh token

        Returns:
            - access_token: New JWT access token
            - refresh_token: New JWT refresh token (if rotation enabled)
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = RefreshTokenRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        ctx = _request_context(request)

        try:
            tokens = await async_refresh_tokens(data.refresh_token)

            await AuditLog.alog(
                action=AuditAction.TOKEN_REFRESH,
                description="Token refreshed",
                **ctx,
            )

            return JsonResponse(tokens.model_dump())
        except ExpiredSignatureError:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description="Token refresh failed — expired",
                severity=AuditSeverity.WARNING,
                metadata={"reason": "token_expired"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Refresh token has expired", "code": "token_expired"},
                status=401,
            )
        except InvalidTokenError as e:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description=f"Token refresh failed — invalid: {e}",
                severity=AuditSeverity.WARNING,
                metadata={"reason": "token_invalid"},
                **ctx,
            )
            return JsonResponse(
                {"detail": f"Invalid refresh token: {e}", "code": "token_invalid"},
                status=401,
            )

    @post("logout")
    async def logout(self, request: HttpRequest) -> JsonResponse:
        """
        Logout user and blacklist tokens if blacklisting is enabled.

        Blacklists the current access token (from request) and optionally
        the refresh token (from request body). Falls back gracefully if
        blacklisting is not configured or errors occur.
        """
        user = getattr(request, "user", None)
        ctx = _request_context(request)

        # Blacklist current access token if blacklisting is enabled
        token_payload = getattr(request, "token_payload", None)
        if token_payload and getattr(token_payload, "jti", None):
            from django_matt.auth.blacklist.core import ablacklist_token

            try:
                await ablacklist_token(token_payload.jti, token_payload.exp)
            except Exception:
                pass  # Best effort - don't fail logout if blacklist errors

        # Also blacklist refresh token from body if provided
        try:
            body = orjson.loads(request.body) if request.body else {}
            refresh = body.get("refresh_token")
            if refresh:
                from django_matt.auth.blacklist.core import ablacklist_token as _abl
                from django_matt.auth.jwt import verify_refresh_token as _verify_refresh

                try:
                    rpayload = _verify_refresh(refresh)
                    if rpayload.jti:
                        await _abl(rpayload.jti, rpayload.exp)
                except Exception:
                    pass
        except Exception:
            pass

        if user and user.is_authenticated:
            await AuditLog.alog(
                action=AuditAction.LOGOUT,
                user=user,
                obj=user,
                description=f"{user.get_full_name() or user.email} logged out",
                metadata=_user_metadata(user),
                **ctx,
            )

        return JsonResponse(MessageResponse(message="Logged out successfully").model_dump())

    @get("me")
    @jwt_required
    async def me(self, request: HttpRequest) -> JsonResponse:
        """
        Get current authenticated user's profile.

        Requires: Valid JWT access token in Authorization header.

        Returns:
            - User profile data
        """
        user = request.user
        return JsonResponse((await UserResponse.afrom_user(user)).model_dump())

    @post("me")
    @jwt_required
    async def update_me(self, request: HttpRequest) -> JsonResponse:
        """
        Update current user's profile.

        Request body (all optional):
            - username: New username
            - first_name: New first name
            - last_name: New last name
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )

        user = request.user

        # Update allowed fields
        if body.get("username"):
            # Check if username is taken
            exists = (
                await User.objects.filter(username=body["username"]).exclude(pk=user.pk).aexists()
            )
            if exists:
                return JsonResponse(
                    {"detail": "Username already taken", "code": "username_exists"},
                    status=400,
                )
            user.username = body["username"]

        if "first_name" in body:
            user.first_name = body["first_name"] or ""

        if "last_name" in body:
            user.last_name = body["last_name"] or ""

        await user.asave()

        return JsonResponse((await UserResponse.afrom_user(user)).model_dump())

    @post("change-password")
    @jwt_required
    async def change_password(self, request: HttpRequest) -> JsonResponse:
        """
        Change authenticated user's password.

        Request body:
            - current_password: Current password
            - new_password: New password (min 8 chars)
            - new_password_confirm: New password confirmation
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = ChangePasswordRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        user = request.user

        ctx = _request_context(request)

        # Verify current password
        if not user.check_password(data.current_password):
            await AuditLog.alog(
                action=AuditAction.PASSWORD_CHANGE,
                user=user,
                obj=user,
                description=f"Failed password change for {user.email} — wrong current password",
                severity=AuditSeverity.WARNING,
                metadata={**_user_metadata(user), "reason": "invalid_current_password"},
                **ctx,
            )
            return JsonResponse(
                {"detail": "Current password is incorrect", "code": "invalid_password"},
                status=400,
            )

        # Set new password
        user.set_password(data.new_password)
        await user.asave()

        # Generate new tokens (old tokens should be invalidated)
        tokens = await acreate_token_pair(user)

        await AuditLog.alog(
            action=AuditAction.PASSWORD_CHANGE,
            user=user,
            obj=user,
            description=f"{user.get_full_name() or user.email} changed password",
            metadata=_user_metadata(user),
            **ctx,
        )

        return JsonResponse(
            {
                "message": "Password changed successfully",
                "tokens": tokens.model_dump(),
            }
        )

    # =========================================================================
    # Password Reset
    # =========================================================================

    @post("password-reset")
    async def request_password_reset(self, request: HttpRequest) -> JsonResponse:
        """Request password reset. Always returns 200 to prevent email enumeration."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            from django_matt.auth.schemas import ResetPasswordRequest

            data = ResetPasswordRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        # Always return success to prevent email enumeration
        try:
            user = await User.objects.aget(email=data.email)
            from django_matt.auth.password_reset import (
                create_password_reset_token,
                get_reset_url,
                password_reset_config,
            )

            token = create_password_reset_token(user)
            reset_url = get_reset_url(token)

            # Call email callback if configured
            email_callback = password_reset_config.email_callback
            if email_callback:
                try:
                    import inspect

                    if inspect.iscoroutinefunction(email_callback):
                        await email_callback(user.email, reset_url, token)
                    else:
                        email_callback(user.email, reset_url, token)
                except Exception:
                    pass  # Best effort
        except User.DoesNotExist:
            pass  # Silent — prevent enumeration

        return JsonResponse(
            MessageResponse(
                message="If an account exists with this email, a password reset link has been sent."
            ).model_dump()
        )

    @post("password-reset/confirm")
    async def confirm_password_reset(self, request: HttpRequest) -> JsonResponse:
        """Confirm password reset with token and new password."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            from django_matt.auth.schemas import ResetPasswordConfirmRequest

            data = ResetPasswordConfirmRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        from django_matt.auth.password_reset import averify_password_reset_token

        result = await averify_password_reset_token(data.token)

        if not result.valid:
            ctx = _request_context(request)
            await AuditLog.alog(
                action=AuditAction.PASSWORD_CHANGE,
                description=f"Password reset failed: {result.error}",
                severity=AuditSeverity.WARNING,
                metadata={"email": result.email, "reason": result.error},
                **ctx,
            )
            return JsonResponse(
                {
                    "detail": result.error or "Invalid or expired token",
                    "code": "invalid_token",
                },
                status=401,
            )

        user = result.user
        user.set_password(data.new_password)
        await user.asave()

        # Generate new tokens
        tokens = await acreate_token_pair(user)

        ctx = _request_context(request)
        await AuditLog.alog(
            action=AuditAction.PASSWORD_CHANGE,
            user=user,
            obj=user,
            description=f"{user.get_full_name() or user.email} reset password",
            metadata=_user_metadata(user),
            **ctx,
        )

        return JsonResponse(
            {
                "message": "Password reset successfully",
                "tokens": tokens.model_dump(),
            }
        )

    @get("verify")
    @jwt_optional
    async def verify_token(self, request: HttpRequest) -> JsonResponse:
        """
        Verify if the current access token is valid.

        Returns:
            - valid: Whether the token is valid
            - user: User data if valid
        """
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            return JsonResponse(
                {
                    "valid": True,
                    "user": (await UserResponse.afrom_user(user)).model_dump(),
                }
            )

        return JsonResponse(
            {
                "valid": False,
                "user": None,
            }
        )

    # =========================================================================
    # Magic Link Passwordless Authentication
    # =========================================================================

    @post("magic-link/request")
    async def request_magic_link(self, request: HttpRequest) -> JsonResponse:
        """
        Request a magic link for passwordless login.

        Sends an email with a one-time login link to the user.

        Request body:
            - email: User email address

        Returns:
            - message: Success message (always returns success to prevent email enumeration)
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = MagicLinkRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        # Check if user exists (but don't reveal this to prevent enumeration)
        user_exists = await User.objects.filter(email=data.email).aexists()

        # Only send email if user exists (or if registration is allowed)
        if user_exists or magic_link_config.allow_registration:
            try:
                # Generate magic link URL
                # Use request to build base URL if not configured
                if magic_link_config.base_url:
                    base_url = magic_link_config.base_url
                else:
                    scheme = "https" if request.is_secure() else "http"
                    base_url = f"{scheme}://{request.get_host()}"

                magic_link_url = create_magic_link_url(
                    email=data.email,
                    base_url=base_url,
                )

                # Send email asynchronously
                await send_magic_link_async(
                    email=data.email,
                    magic_link_url=magic_link_url,
                )
            except Exception:
                # Log error but don't expose to user
                pass

        # Always return success to prevent email enumeration
        return JsonResponse(
            MessageResponse(
                message="If an account exists with this email, a login link has been sent."
            ).model_dump()
        )

    @post("magic-link/verify")
    async def verify_magic_link(self, request: HttpRequest) -> JsonResponse:
        """
        Verify a magic link token and login the user.

        Request body:
            - token: Magic link token from email

        Returns:
            - user: User profile
            - tokens: JWT token pair
            - user_created: Whether a new account was created
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = MagicLinkVerifyRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )

        ctx = _request_context(request)

        # Verify the magic link token (async — uses native async ORM)
        result = await averify_magic_link_token(data.token, create_user=True)

        if not result.valid:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description=f"Magic link verification failed: {result.error}",
                severity=AuditSeverity.WARNING,
                metadata={"reason": "invalid_magic_link", "error": result.error},
                **ctx,
            )
            return JsonResponse(
                {"detail": result.error or "Invalid or expired link", "code": "invalid_token"},
                status=401,
            )

        if not result.user:
            return JsonResponse(
                {"detail": "User not found", "code": "user_not_found"},
                status=401,
            )

        # Generate JWT tokens for the user
        tokens = await acreate_token_pair(result.user)

        await AuditLog.alog(
            action=AuditAction.LOGIN,
            user=result.user,
            obj=result.user,
            description=f"{result.user.get_full_name() or result.user.email} logged in via magic link",
            metadata={
                **_user_metadata(result.user),
                "auth_method": "magic_link",
                "user_created": result.user_created,
            },
            **ctx,
        )

        # Build response
        return JsonResponse(
            {
                "user": (await UserResponse.afrom_user(result.user)).model_dump(),
                "tokens": tokens.model_dump(),
                "user_created": result.user_created,
            },
            status=200 if not result.user_created else 201,
        )

    @get("magic-link/check")
    async def check_magic_link(self, request: HttpRequest) -> JsonResponse:
        """
        Check if a magic link token is valid without consuming it.

        Query params:
            - token: Magic link token to check

        Returns:
            - valid: Whether the token is valid
            - email: Email from the token (if valid)
            - error: Error message (if invalid)
        """
        token = request.GET.get("token")

        if not token:
            return JsonResponse(
                {"valid": False, "email": None, "error": "Token required"},
                status=400,
            )

        # Verify without creating user (async — uses native async ORM)
        result = await averify_magic_link_token(token, create_user=False)

        return JsonResponse(
            {
                "valid": result.valid,
                "email": result.email,
                "error": result.error,
            }
        )


class MinimalAuthController(APIController):
    """
    Minimal authentication controller with just login and me endpoints.

    Use this if you don't need registration or password management.
    """

    prefix = "auth"
    tags = ["Authentication"]

    @post("login")
    async def login(self, request: HttpRequest) -> JsonResponse:
        """Login with email/password."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = LoginRequest.model_validate(body)
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=422)

        ctx = _request_context(request)

        try:
            user = await User.objects.aget(email=data.email)
        except User.DoesNotExist:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                description=f"Failed login attempt for {data.email}",
                severity=AuditSeverity.WARNING,
                metadata={"email": data.email, "reason": "user_not_found"},
                **ctx,
            )
            return JsonResponse({"detail": "Invalid credentials"}, status=401)

        if not user.check_password(data.password) or not user.is_active:
            await AuditLog.alog(
                action=AuditAction.LOGIN_FAILED,
                user=user,
                obj=user,
                description=f"Failed login for {user.email}",
                severity=AuditSeverity.WARNING,
                metadata={**_user_metadata(user), "reason": "invalid_credentials"},
                **ctx,
            )
            return JsonResponse({"detail": "Invalid credentials"}, status=401)

        tokens = await acreate_token_pair(user)

        await AuditLog.alog(
            action=AuditAction.LOGIN,
            user=user,
            obj=user,
            description=f"{user.get_full_name() or user.email} logged in",
            metadata={**_user_metadata(user), "auth_method": "email_password"},
            **ctx,
        )

        return JsonResponse(tokens.model_dump())

    @post("refresh")
    async def refresh(self, request: HttpRequest) -> JsonResponse:
        """Refresh access token."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = RefreshTokenRequest.model_validate(body)
            tokens = await async_refresh_tokens(data.refresh_token)
            return JsonResponse(tokens.model_dump())
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=401)

    @post("password-reset")
    async def request_password_reset(self, request: HttpRequest) -> JsonResponse:
        """Request password reset. Always returns 200 to prevent email enumeration."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            from django_matt.auth.schemas import ResetPasswordRequest

            data = ResetPasswordRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=422)

        try:
            user = await User.objects.aget(email=data.email)
            from django_matt.auth.password_reset import (
                create_password_reset_token,
                get_reset_url,
                password_reset_config,
            )

            token = create_password_reset_token(user)
            reset_url = get_reset_url(token)

            email_callback = password_reset_config.email_callback
            if email_callback:
                try:
                    import inspect

                    if inspect.iscoroutinefunction(email_callback):
                        await email_callback(user.email, reset_url, token)
                    else:
                        email_callback(user.email, reset_url, token)
                except Exception:
                    pass
        except User.DoesNotExist:
            pass

        return JsonResponse(
            MessageResponse(
                message="If an account exists with this email, a password reset link has been sent."
            ).model_dump()
        )

    @post("password-reset/confirm")
    async def confirm_password_reset(self, request: HttpRequest) -> JsonResponse:
        """Confirm password reset with token and new password."""
        try:
            body = orjson.loads(request.body) if request.body else {}
            from django_matt.auth.schemas import ResetPasswordConfirmRequest

            data = ResetPasswordConfirmRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=422)

        from django_matt.auth.password_reset import averify_password_reset_token

        result = await averify_password_reset_token(data.token)

        if not result.valid:
            return JsonResponse(
                {"detail": result.error or "Invalid or expired token"},
                status=401,
            )

        user = result.user
        user.set_password(data.new_password)
        await user.asave()

        tokens = await acreate_token_pair(user)

        return JsonResponse(
            {
                "message": "Password reset successfully",
                "tokens": tokens.model_dump(),
            }
        )

    @get("me")
    @jwt_required
    async def me(self, request: HttpRequest) -> JsonResponse:
        """Get current user."""
        return JsonResponse((await UserResponse.afrom_user(request.user)).model_dump())


__all__ = [
    "AuthController",
    "MinimalAuthController",
]
