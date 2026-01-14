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

import json
from typing import Any

from django.contrib.auth import get_user_model, authenticate
from django.http import HttpRequest, JsonResponse

from django_matt.core.controller import APIController
from django_matt.core.router import get, post, delete
from django_matt.auth.jwt import (
    create_token_pair,
    refresh_tokens,
    verify_refresh_token,
    get_token_from_request,
    InvalidTokenError,
    ExpiredSignatureError,
)
from django_matt.auth.decorators import jwt_required, jwt_optional
from django_matt.auth.schemas import (
    LoginRequest,
    LoginWithUsernameRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    TokenPair,
    UserResponse,
    AuthResponse,
    MessageResponse,
)
from django_matt.auth.magic_link import (
    create_magic_link_token,
    create_magic_link_url,
    verify_magic_link_token,
    send_magic_link_async,
    magic_link_config,
)


User = get_user_model()


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
            body = json.loads(request.body) if request.body else {}
            data = LoginRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )
        
        # Find user by email
        try:
            user = await User.objects.aget(email=data.email)
        except User.DoesNotExist:
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )
        
        # Check password
        if not user.check_password(data.password):
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )
        
        # Check if user is active
        if not user.is_active:
            return JsonResponse(
                {"detail": "Account is inactive", "code": "account_inactive"},
                status=401,
            )
        
        # Generate tokens
        tokens = create_token_pair(user)
        
        return JsonResponse(tokens.model_dump())
    
    @post("login/username")
    async def login_with_username(self, request: HttpRequest) -> JsonResponse:
        """
        Authenticate user with username and password.
        
        Alternative login endpoint for username-based authentication.
        """
        try:
            body = json.loads(request.body) if request.body else {}
            data = LoginWithUsernameRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )
        
        # Use Django's authenticate
        user = authenticate(username=data.username, password=data.password)
        
        if user is None:
            return JsonResponse(
                {"detail": "Invalid credentials", "code": "invalid_credentials"},
                status=401,
            )
        
        if not user.is_active:
            return JsonResponse(
                {"detail": "Account is inactive", "code": "account_inactive"},
                status=401,
            )
        
        tokens = create_token_pair(user)
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
            body = json.loads(request.body) if request.body else {}
            data = RegisterRequest.model_validate(body)
        except json.JSONDecodeError:
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
        tokens = create_token_pair(user)
        
        # Build response
        response = AuthResponse(
            user=UserResponse.from_user(user),
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
            body = json.loads(request.body) if request.body else {}
            data = RefreshTokenRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )
        
        try:
            tokens = refresh_tokens(data.refresh_token)
            return JsonResponse(tokens.model_dump())
        except ExpiredSignatureError:
            return JsonResponse(
                {"detail": "Refresh token has expired", "code": "token_expired"},
                status=401,
            )
        except InvalidTokenError as e:
            return JsonResponse(
                {"detail": f"Invalid refresh token: {e}", "code": "token_invalid"},
                status=401,
            )
    
    @post("logout")
    async def logout(self, request: HttpRequest) -> JsonResponse:
        """
        Logout user (client-side token removal).
        
        For stateless JWT, logout is handled client-side by removing tokens.
        This endpoint exists for API consistency and can be extended
        for token blacklisting if needed.
        """
        # For stateless JWT, just return success
        # In a real implementation, you might:
        # 1. Add the token to a blacklist
        # 2. Record logout time
        # 3. Clear session if using hybrid auth
        
        return JsonResponse(
            MessageResponse(message="Logged out successfully").model_dump()
        )
    
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
        return JsonResponse(UserResponse.from_user(user).model_dump())
    
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
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        
        user = request.user
        
        # Update allowed fields
        if "username" in body and body["username"]:
            # Check if username is taken
            exists = await User.objects.filter(username=body["username"]).exclude(pk=user.pk).aexists()
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
        
        return JsonResponse(UserResponse.from_user(user).model_dump())
    
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
            body = json.loads(request.body) if request.body else {}
            data = ChangePasswordRequest.model_validate(body)
        except json.JSONDecodeError:
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
        
        # Verify current password
        if not user.check_password(data.current_password):
            return JsonResponse(
                {"detail": "Current password is incorrect", "code": "invalid_password"},
                status=400,
            )
        
        # Set new password
        user.set_password(data.new_password)
        await user.asave()
        
        # Generate new tokens (old tokens should be invalidated)
        tokens = create_token_pair(user)
        
        return JsonResponse({
            "message": "Password changed successfully",
            "tokens": tokens.model_dump(),
        })
    
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
            return JsonResponse({
                "valid": True,
                "user": UserResponse.from_user(user).model_dump(),
            })
        
        return JsonResponse({
            "valid": False,
            "user": None,
        })
    
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
            body = json.loads(request.body) if request.body else {}
            data = MagicLinkRequest.model_validate(body)
        except json.JSONDecodeError:
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
            body = json.loads(request.body) if request.body else {}
            data = MagicLinkVerifyRequest.model_validate(body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON", "code": "invalid_json"},
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                {"detail": str(e), "code": "validation_error"},
                status=422,
            )
        
        # Verify the magic link token
        result = verify_magic_link_token(data.token, create_user=True)
        
        if not result.valid:
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
        tokens = create_token_pair(result.user)
        
        # Build response
        return JsonResponse({
            "user": UserResponse.from_user(result.user).model_dump(),
            "tokens": tokens.model_dump(),
            "user_created": result.user_created,
        }, status=200 if not result.user_created else 201)
    
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
        
        # Verify without creating user
        result = verify_magic_link_token(token, create_user=False)
        
        return JsonResponse({
            "valid": result.valid,
            "email": result.email,
            "error": result.error,
        })


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
            body = json.loads(request.body) if request.body else {}
            data = LoginRequest.model_validate(body)
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=422)
        
        try:
            user = await User.objects.aget(email=data.email)
        except User.DoesNotExist:
            return JsonResponse({"detail": "Invalid credentials"}, status=401)
        
        if not user.check_password(data.password) or not user.is_active:
            return JsonResponse({"detail": "Invalid credentials"}, status=401)
        
        tokens = create_token_pair(user)
        return JsonResponse(tokens.model_dump())
    
    @post("refresh")
    async def refresh(self, request: HttpRequest) -> JsonResponse:
        """Refresh access token."""
        try:
            body = json.loads(request.body) if request.body else {}
            data = RefreshTokenRequest.model_validate(body)
            tokens = refresh_tokens(data.refresh_token)
            return JsonResponse(tokens.model_dump())
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=401)
    
    @get("me")
    @jwt_required
    async def me(self, request: HttpRequest) -> JsonResponse:
        """Get current user."""
        return JsonResponse(UserResponse.from_user(request.user).model_dump())


__all__ = [
    "AuthController",
    "MinimalAuthController",
]
