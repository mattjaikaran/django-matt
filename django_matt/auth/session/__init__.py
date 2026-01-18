"""
Session authentication module.

Provides cookie-based session authentication with CSRF protection.

Usage:
    # In settings.py
    MIDDLEWARE = [
        ...
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django_matt.auth.session.SessionAuthMiddleware',
        'django_matt.auth.session.CSRFMiddleware',
    ]

    DJANGO_MATT_SESSION = {
        "COOKIE_NAME": "sessionid",
        "COOKIE_AGE": 86400 * 14,  # 14 days
        "COOKIE_SECURE": True,
        "COOKIE_HTTPONLY": True,
        "COOKIE_SAMESITE": "Lax",
        "CSRF_ENABLED": True,
        "CSRF_COOKIE_NAME": "csrftoken",
    }

    # In views
    from django_matt.auth.session import session_required, csrf_protect

    @api.post("/login")
    async def login(request, data: LoginSchema):
        user = authenticate(data.email, data.password)
        login_session(request, user)
        return {"success": True}

    @api.get("/protected")
    @session_required
    async def protected(request):
        return {"user": request.user.email}

    # Register session management endpoints
    from django_matt.auth.session import SessionController
    api.register_controller(SessionController, prefix="/auth/session")
"""

from .config import SessionConfig, get_session_config
from .backend import (
    SessionStore,
    create_session,
    get_session,
    delete_session,
    refresh_session,
    get_user_sessions,
    delete_user_sessions,
    delete_other_sessions,
)
from .middleware import (
    SessionAuthMiddleware,
    CSRFMiddleware,
    AsyncSessionAuthMiddleware,
    AsyncCSRFMiddleware,
)
from .csrf import (
    get_csrf_token,
    verify_csrf_token,
    rotate_csrf_token,
    csrf_exempt,
    csrf_protect,
    ensure_csrf_cookie,
)
from .decorators import (
    session_required,
    session_optional,
    login_required,
    fresh_session_required,
)
from .utils import (
    login_session,
    logout_session,
    get_session_user,
    is_session_authenticated,
    get_session_data,
    set_session_data,
    flash_message,
    get_flash_messages,
)
from .controllers import SessionController
from .schemas import (
    SessionLoginSchema,
    SessionInfoSchema,
    SessionListSchema,
    CSRFTokenSchema,
)

__all__ = [
    # Config
    "SessionConfig",
    "get_session_config",
    # Backend
    "SessionStore",
    "create_session",
    "get_session",
    "delete_session",
    "refresh_session",
    "get_user_sessions",
    "delete_user_sessions",
    "delete_other_sessions",
    # Middleware
    "SessionAuthMiddleware",
    "CSRFMiddleware",
    "AsyncSessionAuthMiddleware",
    "AsyncCSRFMiddleware",
    # CSRF
    "get_csrf_token",
    "verify_csrf_token",
    "rotate_csrf_token",
    "csrf_exempt",
    "csrf_protect",
    "ensure_csrf_cookie",
    # Decorators
    "session_required",
    "session_optional",
    "login_required",
    "fresh_session_required",
    # Utils
    "login_session",
    "logout_session",
    "get_session_user",
    "is_session_authenticated",
    "get_session_data",
    "set_session_data",
    "flash_message",
    "get_flash_messages",
    # Controller
    "SessionController",
    # Schemas
    "SessionLoginSchema",
    "SessionInfoSchema",
    "SessionListSchema",
    "CSRFTokenSchema",
]
