from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse

from django_matt.serialization.groups import SerializationContext


class SerializationContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.role_to_groups: dict[str, list[str]] = {
            "admin": ["admin", "internal", "public"],
            "staff": ["internal", "public"],
        }
        self.default_groups: list[str] = ["public"]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        groups = self._resolve_groups(request)
        request.serialization_context = SerializationContext(  # type: ignore[attr-defined]
            groups=frozenset(groups),
        )
        return self.get_response(request)

    def _resolve_groups(self, request: HttpRequest) -> list[str]:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return list(self.default_groups)

        if getattr(user, "is_superuser", False):
            return ["admin", "internal", "public"]

        if getattr(user, "is_staff", False):
            return ["internal", "public"]

        role = getattr(user, "role", None)
        if role and role in self.role_to_groups:
            return list(self.role_to_groups[role])

        return list(self.default_groups)
