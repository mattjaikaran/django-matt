"""
Django views for Centrifugo proxy callbacks.

Centrifugo calls these endpoints to validate connections, subscriptions,
publications, and RPC requests.  Mount them in urls.py:

    from django_matt.websockets.centrifugo import get_centrifugo_urls

    urlpatterns += [path("centrifugo/", include(get_centrifugo_urls()))]

Then configure Centrifugo with:

    proxy_connect_endpoint: "http://django:8000/centrifugo/connect/"
    proxy_subscribe_endpoint: "http://django:8000/centrifugo/subscribe/"
    proxy_publish_endpoint: "http://django:8000/centrifugo/publish/"
    proxy_rpc_endpoint: "http://django:8000/centrifugo/rpc/"

Override individual proxy views to add custom validation logic.
"""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

import orjson

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class CentrifugoProxyView(View):
    """
    Base class for Centrifugo proxy views.

    Parses the orjson request body and returns a JsonResponse.
    Subclass and override the ``on_*`` method to add custom logic.
    """

    def _parse_body(self, request) -> dict:
        try:
            return orjson.loads(request.body) if request.body else {}
        except Exception:
            return {}

    def _ok(self, result: dict) -> JsonResponse:
        return JsonResponse({"result": result})

    def _error(self, code: int, message: str) -> JsonResponse:
        return JsonResponse({"error": {"code": code, "message": message}}, status=200)


class CentrifugoConnectProxy(CentrifugoProxyView):
    """
    Handle Centrifugo connect proxy calls.

    Centrifugo sends connection credentials here so Django can validate
    the user and return per-connection context.

    Override ``on_connect`` to implement custom validation::

        class MyConnectProxy(CentrifugoConnectProxy):
            async def on_connect(self, data: dict) -> dict:
                token = data.get("token")
                # validate token, fetch user …
                return {"user": "42", "channels": ["#personal:42"]}
    """

    async def post(self, request, *args, **kwargs) -> JsonResponse:
        data = self._parse_body(request)
        try:
            result = await self.on_connect(data)
            return self._ok(result)
        except Exception as exc:
            logger.exception("CentrifugoConnectProxy error: %s", exc)
            return self._error(500, str(exc))

    async def on_connect(self, data: dict) -> dict:
        """
        Called for each client connect request.

        Return a dict that Centrifugo merges into the connection context.
        Minimum required: ``{"user": "<user_id>"}`` (empty string = anonymous).
        """
        return {}


class CentrifugoSubscribeProxy(CentrifugoProxyView):
    """
    Handle Centrifugo subscribe proxy calls.

    Override ``on_subscribe`` to allow or deny channel subscriptions::

        class MySubscribeProxy(CentrifugoSubscribeProxy):
            async def on_subscribe(self, channel: str, data: dict) -> dict:
                if not user_can_subscribe(data.get("user"), channel):
                    raise PermissionError("not allowed")
                return {}
    """

    async def post(self, request, *args, **kwargs) -> JsonResponse:
        data = self._parse_body(request)
        channel = data.get("channel", "")
        try:
            result = await self.on_subscribe(channel, data)
            return self._ok(result)
        except PermissionError as exc:
            return self._error(403, str(exc))
        except Exception as exc:
            logger.exception("CentrifugoSubscribeProxy error: %s", exc)
            return self._error(500, str(exc))

    async def on_subscribe(self, channel: str, data: dict) -> dict:
        """
        Called for each client subscribe request.

        Return ``{}`` to allow, raise ``PermissionError`` to deny.
        """
        return {}


class CentrifugoPublishProxy(CentrifugoProxyView):
    """
    Handle Centrifugo publish proxy calls.

    Override ``on_publish`` to validate or transform messages before
    they are delivered::

        class MyPublishProxy(CentrifugoPublishProxy):
            async def on_publish(self, channel: str, data: dict, raw: dict) -> dict:
                # mutate data, add server-side fields, etc.
                return {"data": {**data, "server_ts": time.time()}}
    """

    async def post(self, request, *args, **kwargs) -> JsonResponse:
        raw = self._parse_body(request)
        channel = raw.get("channel", "")
        data = raw.get("data", {})
        try:
            result = await self.on_publish(channel, data, raw)
            return self._ok(result)
        except PermissionError as exc:
            return self._error(403, str(exc))
        except Exception as exc:
            logger.exception("CentrifugoPublishProxy error: %s", exc)
            return self._error(500, str(exc))

    async def on_publish(self, channel: str, data: dict, raw: dict) -> dict:
        """
        Called for each client publish request.

        Return ``{}`` to allow unmodified, or ``{"data": {...}}`` to
        replace the published payload.  Raise ``PermissionError`` to deny.
        """
        return {}


class CentrifugoRPCProxy(CentrifugoProxyView):
    """
    Handle Centrifugo RPC proxy calls.

    Allows clients to call arbitrary server-side methods::

        class MyRPCProxy(CentrifugoRPCProxy):
            async def on_rpc(self, method: str, data: dict, raw: dict) -> dict:
                if method == "ping":
                    return {"result": {"pong": True}}
                raise ValueError(f"Unknown method: {method}")
    """

    async def post(self, request, *args, **kwargs) -> JsonResponse:
        raw = self._parse_body(request)
        method = raw.get("method", "")
        data = raw.get("data", {})
        try:
            result = await self.on_rpc(method, data, raw)
            return self._ok(result)
        except PermissionError as exc:
            return self._error(403, str(exc))
        except Exception as exc:
            logger.exception("CentrifugoRPCProxy error: %s", exc)
            return self._error(500, str(exc))

    async def on_rpc(self, method: str, data: dict, raw: dict) -> dict:
        """
        Called for each RPC request from a client.

        Return ``{"result": {...}}`` with your response data.
        """
        return {}


def get_centrifugo_urls(
    connect_view: type[CentrifugoConnectProxy] | None = None,
    subscribe_view: type[CentrifugoSubscribeProxy] | None = None,
    publish_view: type[CentrifugoPublishProxy] | None = None,
    rpc_view: type[CentrifugoRPCProxy] | None = None,
) -> list:
    """
    Return URL patterns for Centrifugo proxy endpoints.

    Include in urls.py::

        from django_matt.websockets.centrifugo import get_centrifugo_urls
        from django.urls import path, include

        urlpatterns += [path("centrifugo/", include(get_centrifugo_urls()))]

    Pass custom view classes to override proxy behaviour::

        urlpatterns += [
            path("centrifugo/", include(
                get_centrifugo_urls(connect_view=MyConnectProxy)
            ))
        ]
    """
    from django_matt.websockets.centrifugo.config import get_centrifugo_config

    cfg = get_centrifugo_config()

    return [
        path(
            cfg.proxy_connect_path,
            (connect_view or CentrifugoConnectProxy).as_view(),
            name="centrifugo_connect",
        ),
        path(
            cfg.proxy_subscribe_path,
            (subscribe_view or CentrifugoSubscribeProxy).as_view(),
            name="centrifugo_subscribe",
        ),
        path(
            cfg.proxy_publish_path,
            (publish_view or CentrifugoPublishProxy).as_view(),
            name="centrifugo_publish",
        ),
        path(
            cfg.proxy_rpc_path,
            (rpc_view or CentrifugoRPCProxy).as_view(),
            name="centrifugo_rpc",
        ),
    ]
