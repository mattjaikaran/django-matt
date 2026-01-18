"""
Session management controller.

Provides REST API endpoints for session-based authentication.
"""

from typing import TYPE_CHECKING

from django.contrib.auth import authenticate, get_user_model
from django.http import JsonResponse

from .schemas import (
    SessionLoginSchema,
    SessionInfoSchema,
    SessionListSchema,
    SessionStatusSchema,
    SessionUserSchema,
    CSRFTokenSchema,
    LogoutResponseSchema,
    RevokeSessionSchema,
    RevokeAllSessionsSchema,
    RevokeSessionsResponseSchema,
)
from .utils import (
    login_session,
    logout_session,
    get_session_info,
    is_session_authenticated,
)
from .csrf import get_csrf_token, ensure_csrf_cookie
from .backend import get_user_sessions, delete_session, delete_other_sessions
from .decorators import session_required, csrf_protect

if TYPE_CHECKING:
    from django.http import HttpRequest


class SessionController:
    """
    Session authentication controller.

    Provides endpoints for:
    - Login/logout via session
    - Session status and info
    - CSRF token retrieval
    - Session management (list, revoke)

    Usage:
        from django_matt.auth.session import SessionController

        api.register_controller(SessionController, prefix="/auth/session")

    Endpoints:
        POST /login - Login with email/password
        POST /logout - Logout current session
        GET /status - Get authentication status
        GET /csrf - Get CSRF token
        GET /sessions - List all user sessions
        DELETE /sessions/{key} - Revoke specific session
        DELETE /sessions - Revoke all other sessions
    """

    tags = ["Session Auth"]

    def __init__(self, api=None):
        """Initialize controller and register routes."""
        self.api = api
        if api:
            self._register_routes(api)

    def _register_routes(self, api):
        """Register all routes with the API."""
        # Login
        api.post("/login", tags=self.tags)(self.login)

        # Logout
        api.post("/logout", tags=self.tags)(self.logout)

        # Status
        api.get("/status", tags=self.tags)(self.status)

        # CSRF
        api.get("/csrf", tags=self.tags)(self.csrf_token)

        # Sessions management
        api.get("/sessions", tags=self.tags)(self.list_sessions)
        api.delete("/sessions/{session_key}", tags=self.tags)(self.revoke_session)
        api.delete("/sessions", tags=self.tags)(self.revoke_all_sessions)

    async def login(
        self,
        request: "HttpRequest",
        data: SessionLoginSchema,
    ) -> JsonResponse:
        """
        Login with email and password.

        Creates a new session for the authenticated user.
        Returns user info and sets session cookie.
        """
        User = get_user_model()

        # Authenticate user
        user = authenticate(
            request,
            username=data.email,
            password=data.password,
        )

        if user is None:
            return JsonResponse(
                {"detail": "Invalid email or password"},
                status=401,
            )

        if not user.is_active:
            return JsonResponse(
                {"detail": "Account is disabled"},
                status=403,
            )

        # Create session
        from asgiref.sync import sync_to_async

        await sync_to_async(login_session)(request, user)

        # Extend session if remember_me
        if data.remember_me:
            # Set longer session expiry (30 days)
            request.session.set_expiry(86400 * 30)

        # Build response
        user_data = SessionUserSchema(
            id=user.pk,
            email=user.email,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            is_active=user.is_active,
            is_staff=getattr(user, "is_staff", False),
            date_joined=getattr(user, "date_joined", None),
            last_login=getattr(user, "last_login", None),
        )

        session_data = get_session_info(request)
        csrf_token = get_csrf_token(request)

        return JsonResponse({
            "user": user_data.model_dump(),
            "session": session_data,
            "csrf_token": csrf_token,
        })

    async def logout(self, request: "HttpRequest") -> JsonResponse:
        """
        Logout current session.

        Clears session data and invalidates the session.
        """
        from asgiref.sync import sync_to_async

        await sync_to_async(logout_session)(request)

        response = JsonResponse(
            LogoutResponseSchema().model_dump()
        )

        # Clear session cookie
        from .config import get_session_config

        config = get_session_config()
        response.delete_cookie(config.cookie_name)

        return response

    async def status(self, request: "HttpRequest") -> JsonResponse:
        """
        Get current authentication status.

        Returns whether user is authenticated and session info.
        """
        authenticated = is_session_authenticated(request)
        csrf_token = get_csrf_token(request)

        if authenticated and request.user.is_authenticated:
            user = request.user
            user_data = SessionUserSchema(
                id=user.pk,
                email=user.email,
                username=getattr(user, "username", None),
                first_name=getattr(user, "first_name", None),
                last_name=getattr(user, "last_name", None),
                is_active=user.is_active,
                is_staff=getattr(user, "is_staff", False),
                date_joined=getattr(user, "date_joined", None),
                last_login=getattr(user, "last_login", None),
            )
            session_info = get_session_info(request)

            return JsonResponse(
                SessionStatusSchema(
                    authenticated=True,
                    user=user_data,
                    session=SessionInfoSchema(**session_info),
                    csrf_token=csrf_token,
                ).model_dump()
            )

        return JsonResponse(
            SessionStatusSchema(
                authenticated=False,
                user=None,
                session=None,
                csrf_token=csrf_token,
            ).model_dump()
        )

    async def csrf_token(self, request: "HttpRequest") -> JsonResponse:
        """
        Get a CSRF token.

        Returns a fresh CSRF token for use in form submissions.
        The token is also set as a cookie.
        """
        token = get_csrf_token(request)

        response = JsonResponse(
            CSRFTokenSchema(csrf_token=token).model_dump()
        )

        # Set CSRF cookie
        from .config import get_session_config

        config = get_session_config()
        response.set_cookie(
            config.csrf_cookie_name,
            token,
            max_age=config.csrf_cookie_age,
            path="/",
            secure=config.csrf_cookie_secure,
            httponly=config.csrf_cookie_httponly,
            samesite=config.csrf_cookie_samesite,
        )

        return response

    @session_required
    async def list_sessions(self, request: "HttpRequest") -> JsonResponse:
        """
        List all active sessions for the current user.

        Returns a list of sessions with device info.
        """
        from asgiref.sync import sync_to_async

        sessions = await sync_to_async(get_user_sessions)(request.user)

        current_key = request.session.session_key

        session_list = [
            SessionInfoSchema(
                session_key=s["session_key"],
                created=s.get("created"),
                last_activity=s.get("last_activity"),
                ip_address=s.get("ip_address"),
                user_agent=s.get("user_agent"),
                expires=s.get("expires"),
                is_current=s["session_key"] == current_key,
            )
            for s in sessions
        ]

        return JsonResponse(
            SessionListSchema(
                sessions=[s.model_dump() for s in session_list],
                total=len(session_list),
            ).model_dump()
        )

    @session_required
    async def revoke_session(
        self,
        request: "HttpRequest",
        session_key: str,
    ) -> JsonResponse:
        """
        Revoke a specific session.

        Cannot revoke the current session through this endpoint.
        """
        # Prevent revoking current session
        if session_key == request.session.session_key:
            return JsonResponse(
                {"detail": "Cannot revoke current session. Use logout instead."},
                status=400,
            )

        # Verify session belongs to user
        from asgiref.sync import sync_to_async

        sessions = await sync_to_async(get_user_sessions)(request.user)
        session_keys = [s["session_key"] for s in sessions]

        if session_key not in session_keys:
            return JsonResponse(
                {"detail": "Session not found"},
                status=404,
            )

        # Delete the session
        await sync_to_async(delete_session)(session_key)

        return JsonResponse(
            RevokeSessionsResponseSchema(
                revoked_count=1,
                message="Session revoked successfully",
            ).model_dump()
        )

    @session_required
    async def revoke_all_sessions(
        self,
        request: "HttpRequest",
        data: RevokeAllSessionsSchema = None,
    ) -> JsonResponse:
        """
        Revoke all other sessions.

        By default keeps the current session active.
        """
        from asgiref.sync import sync_to_async

        keep_current = data.keep_current if data else True
        current_key = request.session.session_key if keep_current else None

        count = await sync_to_async(delete_other_sessions)(
            request.user,
            current_key,
        )

        return JsonResponse(
            RevokeSessionsResponseSchema(
                revoked_count=count,
                message=f"Revoked {count} session(s)",
            ).model_dump()
        )


# Standalone view functions for use without controller registration
async def session_login_view(
    request: "HttpRequest",
    data: SessionLoginSchema,
) -> JsonResponse:
    """Standalone login view."""
    controller = SessionController()
    return await controller.login(request, data)


async def session_logout_view(request: "HttpRequest") -> JsonResponse:
    """Standalone logout view."""
    controller = SessionController()
    return await controller.logout(request)


async def session_status_view(request: "HttpRequest") -> JsonResponse:
    """Standalone status view."""
    controller = SessionController()
    return await controller.status(request)


async def csrf_token_view(request: "HttpRequest") -> JsonResponse:
    """Standalone CSRF token view."""
    controller = SessionController()
    return await controller.csrf_token(request)
