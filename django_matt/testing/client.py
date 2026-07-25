# file-length-max: 650
"""
Test client with authentication helpers.

Both :class:`APITestClient` (sync) and :class:`AsyncAPITestClient` (async)
transparently patch ``request.auser`` so that ``await request.auser()``
returns the forced user in async Django 5.0+ endpoints.
"""

from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from django.http import HttpResponse
from django.test import AsyncClient, Client
from django.test.client import AsyncClientHandler, ClientHandler

import orjson

# ---------------------------------------------------------------------------
# auser() helpers
# ---------------------------------------------------------------------------


def _make_auser_callable(user: Any) -> Any:
    """Return an async callable that resolves to *user*.

    Mirrors Django ``AuthenticationMiddleware``'s contract where
    ``request.auser`` is set to ``partial(auser, request)``.
    """

    async def _auser() -> Any:
        return user

    return _auser


class _AuserClientHandler(ClientHandler):
    """WSGI test handler that patches ``request.auser`` when a user is forced."""

    _force_user: Any = None

    def get_response(self, request: Any) -> HttpResponse:
        if self._force_user is not None:
            request.auser = _make_auser_callable(self._force_user)  # type: ignore[attr-defined]
        return super().get_response(request)


class _AuserAsyncClientHandler(AsyncClientHandler):
    """ASGI test handler that patches ``request.auser`` when a user is forced."""

    _force_user: Any = None

    async def get_response_async(self, request: Any) -> HttpResponse:
        if self._force_user is not None:
            request.auser = _make_auser_callable(self._force_user)  # type: ignore[attr-defined]
        return await super().get_response_async(request)


# ---------------------------------------------------------------------------
# Sync test client
# ---------------------------------------------------------------------------


class APITestClient(Client):
    """
    Extended Django test client with API testing helpers.

    Provides:
    - JWT authentication helpers
    - JSON request/response handling
    - Organization/tenant context
    - Cookie management helpers
    - ``request.auser()`` mock support (Django 5.0+)

    Example:
        client = APITestClient()
        client.force_authenticate(user)

        response = client.get("/api/users/")
        assert response.status_code == 200

        data = client.json(response)
        assert len(data["items"]) > 0
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._auth_token: str | None = None
        self._organization_id: str | None = None
        self._user: Any = None
        # Replace the default handler with our auser-aware variant
        self.handler = _AuserClientHandler(
            enforce_csrf_checks=self.handler.enforce_csrf_checks,
        )

    def force_authenticate(self, user: Any = None, token: str | None = None) -> None:
        """
        Force authentication for subsequent requests.

        Sets both ``request.user`` (via JWT header / session) and
        ``request.auser()`` (async callable) on every request.

        Args:
            user: User to authenticate as
            token: Optional JWT token (will be generated if not provided)
        """
        self._user = user
        self.handler._force_user = user

        if token:
            self._auth_token = token
        elif user:
            # Generate a token for the user.
            # Sync create_access_token is safe here: force_authenticate() is called
            # during test setup (not inside an async request handler) and APITestClient
            # is a synchronous client. There is no event loop to block.
            try:
                from django_matt.auth import create_access_token

                self._auth_token = create_access_token(user)
            except ImportError:
                # Fallback to session auth
                self.force_login(user)
                self._auth_token = None

    def logout(self) -> None:
        """Clear authentication."""
        self._auth_token = None
        self._user = None
        self.handler._force_user = None
        super().logout()

    def set_organization(self, organization: Any) -> None:
        """
        Set organization context for multi-tenant requests.

        Args:
            organization: Organization instance or ID
        """
        if hasattr(organization, "id"):
            self._organization_id = str(organization.id)
        else:
            self._organization_id = str(organization)

    def clear_organization(self) -> None:
        """Clear organization context."""
        self._organization_id = None

    # ------------------------------------------------------------------
    # Cookie helpers
    # ------------------------------------------------------------------

    def set_cookie(self, name: str, value: str, **kwargs: Any) -> None:
        """
        Set a cookie that will be sent with subsequent requests.

        Args:
            name: Cookie name.
            value: Cookie value.
            **kwargs: Additional cookie attributes (max_age, path, domain,
                      secure, httponly, samesite).
        """
        self.cookies[name] = value
        if kwargs:
            for attr, attr_val in kwargs.items():
                self.cookies[name][attr.replace("_", "-")] = attr_val

    def get_cookie(self, name: str) -> str | None:
        """
        Get a cookie value by name from the cookie jar.

        Args:
            name: Cookie name.

        Returns:
            The cookie value, or ``None`` if the cookie does not exist.
        """
        morsel = self.cookies.get(name)
        if morsel is None:
            return None
        # SimpleCookie stores values as Morsel objects; .value gives the
        # unquoted value, while .coded_value gives the possibly-quoted one.
        return morsel.value if hasattr(morsel, "value") else str(morsel)

    def delete_cookie(self, name: str) -> None:
        """
        Remove a cookie from the cookie jar.

        Args:
            name: Cookie name.
        """
        if name in self.cookies:
            del self.cookies[name]

    def clear_cookies(self) -> None:
        """Remove all cookies from the cookie jar."""
        self.cookies = SimpleCookie()

    # ------------------------------------------------------------------
    # Header helpers
    # ------------------------------------------------------------------

    def _get_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build headers including auth and organization."""
        headers: dict[str, str] = {}

        if self._auth_token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {self._auth_token}"

        if self._organization_id:
            headers["HTTP_X_ORGANIZATION_ID"] = self._organization_id

        if extra_headers:
            for key, value in extra_headers.items():
                # Convert to HTTP_ format if needed
                if not key.startswith("HTTP_"):
                    key = f"HTTP_{key.upper().replace('-', '_')}"
                headers[key] = value

        return headers

    def get(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make a GET request."""
        all_headers = self._get_headers(headers)
        return super().get(path, data=data, **all_headers, **kwargs)

    def post(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make a POST request with JSON body."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return super().post(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    def put(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make a PUT request with JSON body."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return super().put(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    def patch(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make a PATCH request with JSON body."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return super().patch(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make a DELETE request."""
        all_headers = self._get_headers(headers)
        return super().delete(path, **all_headers, **kwargs)

    @staticmethod
    def json(response: HttpResponse) -> Any:
        """
        Parse JSON response body.

        Args:
            response: HttpResponse object

        Returns:
            Parsed JSON data
        """
        return orjson.loads(response.content)

    def get_json(self, path: str, **kwargs: Any) -> tuple[HttpResponse, Any]:
        """
        Make a GET request and return (response, json_data) tuple.
        """
        response = self.get(path, **kwargs)
        data = self.json(response) if response.content else None
        return response, data

    def post_json(self, path: str, data: Any = None, **kwargs: Any) -> tuple[HttpResponse, Any]:
        """
        Make a POST request and return (response, json_data) tuple.
        """
        response = self.post(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data

    def put_json(self, path: str, data: Any = None, **kwargs: Any) -> tuple[HttpResponse, Any]:
        """
        Make a PUT request and return (response, json_data) tuple.
        """
        response = self.put(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data

    def patch_json(self, path: str, data: Any = None, **kwargs: Any) -> tuple[HttpResponse, Any]:
        """
        Make a PATCH request and return (response, json_data) tuple.
        """
        response = self.patch(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data


# ---------------------------------------------------------------------------
# Async test client
# ---------------------------------------------------------------------------


class AsyncAPITestClient(AsyncClient):
    """
    Async version of APITestClient.

    Supports ``await request.auser()`` in async endpoints when
    ``force_authenticate()`` has been called.

    Example:
        async def test_list_users():
            client = AsyncAPITestClient()
            await client.force_authenticate(user)

            response = await client.get("/api/users/")
            assert response.status_code == 200
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._auth_token: str | None = None
        self._organization_id: str | None = None
        self._user: Any = None
        # Replace the default handler with our auser-aware variant
        self.handler = _AuserAsyncClientHandler(
            enforce_csrf_checks=self.handler.enforce_csrf_checks,
        )

    async def force_authenticate(self, user: Any = None, token: str | None = None) -> None:
        """Force authentication for subsequent requests."""
        self._user = user
        self.handler._force_user = user

        if token:
            self._auth_token = token
        elif user:
            try:
                from django_matt.auth import acreate_access_token

                self._auth_token = await acreate_access_token(user)
            except ImportError:
                self._auth_token = None

    def logout(self) -> None:
        """Clear authentication state."""
        self._auth_token = None
        self._user = None
        self.handler._force_user = None

    def set_organization(self, organization: Any) -> None:
        """Set organization context."""
        if hasattr(organization, "id"):
            self._organization_id = str(organization.id)
        else:
            self._organization_id = str(organization)

    def clear_organization(self) -> None:
        """Clear organization context."""
        self._organization_id = None

    # ------------------------------------------------------------------
    # Cookie helpers
    # ------------------------------------------------------------------

    def set_cookie(self, name: str, value: str, **kwargs: Any) -> None:
        """
        Set a cookie that will be sent with subsequent requests.

        Args:
            name: Cookie name.
            value: Cookie value.
            **kwargs: Additional cookie attributes (max_age, path, domain,
                      secure, httponly, samesite).
        """
        self.cookies[name] = value
        if kwargs:
            for attr, attr_val in kwargs.items():
                self.cookies[name][attr.replace("_", "-")] = attr_val

    def get_cookie(self, name: str) -> str | None:
        """
        Get a cookie value by name from the cookie jar.

        Args:
            name: Cookie name.

        Returns:
            The cookie value, or ``None`` if the cookie does not exist.
        """
        morsel = self.cookies.get(name)
        if morsel is None:
            return None
        return morsel.value if hasattr(morsel, "value") else str(morsel)

    def delete_cookie(self, name: str) -> None:
        """
        Remove a cookie from the cookie jar.

        Args:
            name: Cookie name.
        """
        if name in self.cookies:
            del self.cookies[name]

    def clear_cookies(self) -> None:
        """Remove all cookies from the cookie jar."""
        self.cookies = SimpleCookie()

    # ------------------------------------------------------------------
    # Header helpers
    # ------------------------------------------------------------------

    def _get_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build headers including auth and organization."""
        headers: dict[str, str] = {}

        if self._auth_token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {self._auth_token}"

        if self._organization_id:
            headers["HTTP_X_ORGANIZATION_ID"] = self._organization_id

        if extra_headers:
            for key, value in extra_headers.items():
                if not key.startswith("HTTP_"):
                    key = f"HTTP_{key.upper().replace('-', '_')}"
                headers[key] = value

        return headers

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make an async GET request."""
        all_headers = self._get_headers(headers)
        return await super().get(path, data=data, **all_headers, **kwargs)

    async def post(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make an async POST request."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return await super().post(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    async def put(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make an async PUT request with JSON body."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return await super().put(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    async def patch(
        self,
        path: str,
        data: Any | None = None,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make an async PATCH request with JSON body."""
        all_headers = self._get_headers(headers)

        if data is not None and content_type == "application/json":
            data = orjson.dumps(data).decode()

        return await super().patch(
            path,
            data=data,
            content_type=content_type,
            **all_headers,
            **kwargs,
        )

    async def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make an async DELETE request."""
        all_headers = self._get_headers(headers)
        return await super().delete(path, **all_headers, **kwargs)

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    @staticmethod
    def json(response: HttpResponse) -> Any:
        """Parse JSON response body."""
        return orjson.loads(response.content)

    async def get_json(self, path: str, **kwargs: Any) -> tuple[HttpResponse, Any]:
        """Make an async GET request and return (response, json_data) tuple."""
        response = await self.get(path, **kwargs)
        data = self.json(response) if response.content else None
        return response, data

    async def post_json(
        self, path: str, data: Any = None, **kwargs: Any
    ) -> tuple[HttpResponse, Any]:
        """Make an async POST request and return (response, json_data) tuple."""
        response = await self.post(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data

    async def put_json(
        self, path: str, data: Any = None, **kwargs: Any
    ) -> tuple[HttpResponse, Any]:
        """Make an async PUT request and return (response, json_data) tuple."""
        response = await self.put(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data

    async def patch_json(
        self, path: str, data: Any = None, **kwargs: Any
    ) -> tuple[HttpResponse, Any]:
        """Make an async PATCH request and return (response, json_data) tuple."""
        response = await self.patch(path, data=data, **kwargs)
        resp_data = self.json(response) if response.content else None
        return response, resp_data
