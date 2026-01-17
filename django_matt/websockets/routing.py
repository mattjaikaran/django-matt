"""
WebSocket routing utilities.

Provides helpers for setting up WebSocket URL routing.

Usage:
    # routing.py
    from django_matt.websockets import WebSocketRouter, AuthMiddlewareStack

    router = WebSocketRouter()
    router.route("ws/chat/", ChatConsumer)
    router.route("ws/chat/<str:room_name>/", RoomConsumer)
    router.route("ws/notifications/", NotificationConsumer, auth_required=True)

    # Get the ASGI application
    websocket_application = router.get_application()

    # Or in asgi.py
    from channels.routing import ProtocolTypeRouter

    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": websocket_application,
    })
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Type

from django_matt.websockets.consumers import BaseConsumer
from django_matt.websockets.auth import AuthMiddlewareStack


logger = logging.getLogger(__name__)


@dataclass
class WebSocketRoute:
    """Represents a WebSocket route."""
    path: str
    consumer: Type[BaseConsumer]
    name: str | None = None
    auth_required: bool = False
    kwargs: dict[str, Any] = field(default_factory=dict)


class WebSocketRouter:
    """
    Router for WebSocket URL patterns.

    Provides a clean API for defining WebSocket routes.

    Usage:
        router = WebSocketRouter()

        # Basic route
        router.route("ws/chat/", ChatConsumer)

        # Route with path parameters
        router.route("ws/chat/<str:room_name>/", RoomConsumer)

        # Route with authentication required
        router.route("ws/private/", PrivateConsumer, auth_required=True)

        # Get URLRouter for use in ASGI
        application = router.get_application()
    """

    def __init__(self, auth_middleware: Callable | None = None):
        """
        Initialize router.

        Args:
            auth_middleware: Custom auth middleware. Defaults to AuthMiddlewareStack.
        """
        self.routes: list[WebSocketRoute] = []
        self.auth_middleware = auth_middleware or AuthMiddlewareStack

    def route(
        self,
        path: str,
        consumer: Type[BaseConsumer],
        name: str | None = None,
        auth_required: bool = False,
        **kwargs,
    ) -> "WebSocketRouter":
        """
        Add a route.

        Args:
            path: URL path pattern (e.g., "ws/chat/<str:room>/")
            consumer: Consumer class to handle connections
            name: Optional name for the route
            auth_required: Whether authentication is required
            **kwargs: Additional kwargs to pass to consumer

        Returns:
            Self for chaining
        """
        self.routes.append(WebSocketRoute(
            path=path,
            consumer=consumer,
            name=name,
            auth_required=auth_required,
            kwargs=kwargs,
        ))
        return self

    def add_route(
        self,
        path: str,
        consumer: Type[BaseConsumer],
        **kwargs,
    ) -> "WebSocketRouter":
        """Alias for route()."""
        return self.route(path, consumer, **kwargs)

    def include(self, router: "WebSocketRouter", prefix: str = "") -> "WebSocketRouter":
        """
        Include routes from another router.

        Args:
            router: Router to include
            prefix: URL prefix to add to included routes

        Returns:
            Self for chaining
        """
        for route in router.routes:
            self.routes.append(WebSocketRoute(
                path=f"{prefix}{route.path}",
                consumer=route.consumer,
                name=route.name,
                auth_required=route.auth_required,
                kwargs=route.kwargs,
            ))
        return self

    def get_urlpatterns(self) -> list:
        """
        Get Django URL patterns for the routes.

        Returns:
            List of path() patterns for use with URLRouter
        """
        try:
            from django.urls import path, re_path
        except ImportError:
            from django.conf.urls import url as re_path
            path = re_path

        patterns = []

        for route in self.routes:
            # Wrap consumer with auth if required
            consumer = route.consumer
            if route.auth_required:
                consumer.auth_required = True

            patterns.append(
                path(route.path, consumer.as_asgi(), name=route.name, kwargs=route.kwargs)
            )

        return patterns

    def get_application(self, include_auth: bool = True) -> Any:
        """
        Get the ASGI application for these routes.

        Args:
            include_auth: Whether to wrap with auth middleware

        Returns:
            URLRouter wrapped with auth middleware
        """
        try:
            from channels.routing import URLRouter
        except ImportError:
            raise ImportError(
                "channels is not installed. Install with: pip install channels"
            )

        urlpatterns = self.get_urlpatterns()
        app = URLRouter(urlpatterns)

        if include_auth and self.auth_middleware:
            app = self.auth_middleware(app)

        return app

    def as_asgi(self) -> Any:
        """Get ASGI application (alias for get_application)."""
        return self.get_application()


def websocket_route(
    path: str,
    name: str | None = None,
    auth_required: bool = False,
):
    """
    Decorator to mark a consumer class as a WebSocket route.

    Usage:
        @websocket_route("ws/chat/")
        class ChatConsumer(JsonConsumer):
            async def handle_message(self, data):
                ...

        # Then collect routes
        router = WebSocketRouter()
        router.route("ws/chat/", ChatConsumer)
    """

    def decorator(cls: Type[BaseConsumer]) -> Type[BaseConsumer]:
        cls._websocket_path = path
        cls._websocket_name = name
        cls._websocket_auth_required = auth_required
        return cls

    return decorator


def collect_routes(*consumers: Type[BaseConsumer]) -> WebSocketRouter:
    """
    Collect routes from decorated consumer classes.

    Usage:
        @websocket_route("ws/chat/")
        class ChatConsumer(JsonConsumer):
            ...

        @websocket_route("ws/notifications/", auth_required=True)
        class NotificationConsumer(JsonConsumer):
            ...

        router = collect_routes(ChatConsumer, NotificationConsumer)
        application = router.get_application()
    """
    router = WebSocketRouter()

    for consumer in consumers:
        path = getattr(consumer, "_websocket_path", None)
        if path:
            router.route(
                path=path,
                consumer=consumer,
                name=getattr(consumer, "_websocket_name", None),
                auth_required=getattr(consumer, "_websocket_auth_required", False),
            )

    return router


def create_asgi_application(
    websocket_router: WebSocketRouter,
    http_application: Any | None = None,
) -> Any:
    """
    Create a complete ASGI application with HTTP and WebSocket support.

    Usage:
        # asgi.py
        from django_matt.websockets import create_asgi_application, WebSocketRouter

        router = WebSocketRouter()
        router.route("ws/chat/", ChatConsumer)

        application = create_asgi_application(router)
    """
    try:
        from channels.routing import ProtocolTypeRouter
    except ImportError:
        raise ImportError(
            "channels is not installed. Install with: pip install channels"
        )

    if http_application is None:
        from django.core.asgi import get_asgi_application
        http_application = get_asgi_application()

    return ProtocolTypeRouter({
        "http": http_application,
        "websocket": websocket_router.get_application(),
    })
