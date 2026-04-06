from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.interceptors.base import Interceptor


class InterceptorChain:
    """Manages an ordered pipeline of interceptors around a handler."""

    def __init__(self, interceptors: list[Interceptor] | None = None) -> None:
        self._interceptors: list[Interceptor] = []
        if interceptors:
            for i in interceptors:
                self.add(i)

    def add(self, interceptor: Interceptor) -> InterceptorChain:
        self._interceptors.append(interceptor)
        self._interceptors.sort(key=lambda i: i.order)
        return self

    @property
    def interceptors(self) -> list[Interceptor]:
        return list(self._interceptors)

    async def execute(
        self,
        request: HttpRequest,
        handler: Callable[..., Coroutine[Any, Any, HttpResponse]],
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        active = [i for i in self._interceptors if i.enabled(request)]

        # before_request phase
        for interceptor in active:
            result = await interceptor.before_request(request, **kwargs)
            if isinstance(result, HttpResponse):
                # short-circuit: run after_response in reverse for already-executed interceptors
                idx = active.index(interceptor)
                for prev in reversed(active[: idx + 1]):
                    result = await prev.after_response(request, result, **kwargs)
                return result

        # handler phase
        try:
            response = await handler(request, *args, **kwargs)
        except Exception as exc:
            # on_error phase (reverse order)
            for interceptor in reversed(active):
                error_response = await interceptor.on_error(request, exc, **kwargs)
                if error_response is not None:
                    # still run after_response for all active interceptors
                    for i in reversed(active):
                        error_response = await i.after_response(
                            request, error_response, **kwargs
                        )
                    return error_response
            raise

        # after_response phase (reverse order)
        for interceptor in reversed(active):
            response = await interceptor.after_response(request, response, **kwargs)

        return response

    def merge(self, other: InterceptorChain) -> InterceptorChain:
        combined = InterceptorChain(self._interceptors + other._interceptors)
        return combined

    def __len__(self) -> int:
        return len(self._interceptors)

    def __bool__(self) -> bool:
        return len(self._interceptors) > 0
