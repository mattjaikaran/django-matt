"""
WebSocket authentication middleware and utilities.

Supports:
- JWT token authentication (query param or first message)
- Session-based authentication
- Custom token authentication

Usage:
    # In routing.py
    from django_matt.websockets.auth import JWTAuthMiddleware

    application = ProtocolTypeRouter({
        "websocket": JWTAuthMiddleware(
            URLRouter([
                path("ws/chat/", ChatConsumer.as_asgi()),
            ])
        ),
    })

    # Or with query param token
    # Connect with: ws://example.com/ws/chat/?token=<jwt_token>
"""

import logging
from typing import Any, Callable
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections


logger = logging.getLogger(__name__)
User = get_user_model()


class AuthMiddlewareBase:
    """Base class for WebSocket authentication middleware."""

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """ASGI interface."""
        # Close old database connections
        close_old_connections()

        # Authenticate
        scope = dict(scope)
        scope["user"] = await self.authenticate(scope)

        await self.app(scope, receive, send)

    async def authenticate(self, scope: dict) -> Any:
        """
        Authenticate the connection.

        Override in subclasses.
        Returns user object or AnonymousUser.
        """
        return AnonymousUser()


class JWTAuthMiddleware(AuthMiddlewareBase):
    """
    JWT authentication middleware for WebSockets.

    Extracts JWT token from:
    1. Query parameter: ?token=<jwt_token>
    2. Subprotocol: Sec-WebSocket-Protocol header

    Usage:
        from django_matt.websockets.auth import JWTAuthMiddleware

        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddleware(
                URLRouter([...])
            ),
        })
    """

    token_query_param: str = "token"

    async def authenticate(self, scope: dict) -> Any:
        """Authenticate using JWT token."""
        token = self._get_token(scope)

        if not token:
            return AnonymousUser()

        try:
            user = await self._get_user_from_token(token)
            return user if user else AnonymousUser()
        except Exception as e:
            logger.warning(f"JWT authentication failed: {e}")
            return AnonymousUser()

    def _get_token(self, scope: dict) -> str | None:
        """Extract token from scope."""
        # Try query string first
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get(self.token_query_param, [])
        if token_list:
            return token_list[0]

        # Try subprotocols
        subprotocols = scope.get("subprotocols", [])
        for proto in subprotocols:
            if proto.startswith("bearer."):
                return proto[7:]  # Remove "bearer." prefix

        # Try headers (Authorization: Bearer <token>)
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        return None

    async def _get_user_from_token(self, token: str) -> Any:
        """Validate token and get user."""
        try:
            from django_matt.auth.jwt import get_user_from_token
            return await get_user_from_token(token)
        except ImportError:
            # django_matt.auth not available, try manual JWT decode
            return await self._decode_jwt_manually(token)

    async def _decode_jwt_manually(self, token: str) -> Any:
        """Manually decode JWT if django_matt.auth not available."""
        try:
            from django_matt.auth.jwt_builtin import decode_jwt, JWTError
            from django.conf import settings

            secret = getattr(settings, "SECRET_KEY", "")
            jwt_settings = getattr(settings, "DJANGO_MATT_JWT", {})
            algorithm = jwt_settings.get("ALGORITHM", "HS256")

            payload = decode_jwt(token, secret, algorithms=[algorithm])
            user_id = payload.get("sub") or payload.get("user_id")

            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    return await User.objects.aget(pk=user_id)
                except User.DoesNotExist:
                    return None

        except JWTError as e:
            logger.warning(f"Manual JWT decode failed: {e}")
        except Exception as e:
            logger.warning(f"Manual JWT decode failed: {e}")

        return None


class SessionAuthMiddleware(AuthMiddlewareBase):
    """
    Session-based authentication middleware for WebSockets.

    Uses Django's session framework to authenticate.
    Requires session cookie to be sent with WebSocket connection.

    Usage:
        from django_matt.websockets.auth import SessionAuthMiddleware

        application = ProtocolTypeRouter({
            "websocket": SessionAuthMiddleware(
                URLRouter([...])
            ),
        })
    """

    async def authenticate(self, scope: dict) -> Any:
        """Authenticate using Django session."""
        try:
            from channels.auth import get_user
            return await get_user(scope)
        except ImportError:
            # channels.auth not available
            return await self._get_user_from_session(scope)

    async def _get_user_from_session(self, scope: dict) -> Any:
        """Get user from session manually."""
        from django.contrib.sessions.backends.db import SessionStore

        # Get session ID from cookies
        cookies = self._parse_cookies(scope)
        session_key = cookies.get("sessionid")

        if not session_key:
            return AnonymousUser()

        try:
            session = SessionStore(session_key=session_key)
            user_id = session.get("_auth_user_id")

            if user_id:
                try:
                    return await User.objects.aget(pk=user_id)
                except User.DoesNotExist:
                    pass

        except Exception as e:
            logger.warning(f"Session authentication failed: {e}")

        return AnonymousUser()

    def _parse_cookies(self, scope: dict) -> dict[str, str]:
        """Parse cookies from scope headers."""
        cookies = {}
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()

        for item in cookie_header.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookies[key] = value

        return cookies


class TokenAuthMiddleware(AuthMiddlewareBase):
    """
    Custom token authentication middleware.

    Validates tokens against a custom token model.

    Usage:
        from django_matt.websockets.auth import TokenAuthMiddleware

        application = ProtocolTypeRouter({
            "websocket": TokenAuthMiddleware(
                URLRouter([...])
            ),
        })

        # Connect with: ws://example.com/ws/?token=<api_token>
    """

    token_query_param: str = "token"
    token_model: str = "auth.Token"  # app_label.ModelName

    async def authenticate(self, scope: dict) -> Any:
        """Authenticate using custom token."""
        token = self._get_token(scope)

        if not token:
            return AnonymousUser()

        try:
            user = await self._get_user_from_token(token)
            return user if user else AnonymousUser()
        except Exception as e:
            logger.warning(f"Token authentication failed: {e}")
            return AnonymousUser()

    def _get_token(self, scope: dict) -> str | None:
        """Extract token from query string."""
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get(self.token_query_param, [])
        return token_list[0] if token_list else None

    async def _get_user_from_token(self, token: str) -> Any:
        """Look up user from token model."""
        from django.apps import apps

        try:
            app_label, model_name = self.token_model.split(".")
            TokenModel = apps.get_model(app_label, model_name)

            token_obj = await TokenModel.objects.select_related("user").aget(key=token)
            return token_obj.user

        except Exception:
            return None


class CombinedAuthMiddleware(AuthMiddlewareBase):
    """
    Combined authentication middleware.

    Tries multiple authentication methods in order:
    1. JWT token
    2. Session
    3. Custom token

    Usage:
        from django_matt.websockets.auth import CombinedAuthMiddleware

        application = ProtocolTypeRouter({
            "websocket": CombinedAuthMiddleware(
                URLRouter([...])
            ),
        })
    """

    def __init__(self, app: Callable):
        super().__init__(app)
        self.jwt_auth = JWTAuthMiddleware(app)
        self.session_auth = SessionAuthMiddleware(app)

    async def authenticate(self, scope: dict) -> Any:
        """Try multiple authentication methods."""
        # Try JWT first
        user = await self.jwt_auth.authenticate(scope)
        if user and user.is_authenticated:
            return user

        # Try session
        user = await self.session_auth.authenticate(scope)
        if user and user.is_authenticated:
            return user

        return AnonymousUser()


# Aliases for common middleware stacks
def AuthMiddlewareStack(inner):
    """
    Standard authentication middleware stack.

    Combines session and JWT authentication.
    """
    return CombinedAuthMiddleware(inner)


def JWTAuthMiddlewareStack(inner):
    """JWT-only authentication middleware."""
    return JWTAuthMiddleware(inner)


def SessionAuthMiddlewareStack(inner):
    """Session-only authentication middleware."""
    return SessionAuthMiddleware(inner)
