from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.exceptions.filters import ExceptionFilter, ExceptionFilterChain

logger = logging.getLogger("django_matt.exceptions")


class ExceptionFilterRegistry:
    def __init__(self) -> None:
        self._global_chain = ExceptionFilterChain()
        self._controller_chains: dict[type, ExceptionFilterChain] = {}
        self._route_chains: dict[str, ExceptionFilterChain] = {}

    # -- global --

    def register_global_filter(self, filter_: ExceptionFilter) -> None:
        self._global_chain.add(filter_)

    def remove_global_filter(self, filter_type: type[ExceptionFilter]) -> None:
        self._global_chain.remove(filter_type)

    @property
    def global_filters(self) -> list[ExceptionFilter]:
        return self._global_chain.filters

    # -- controller --

    def register_controller_filter(
        self, controller_cls: type, filter_: ExceptionFilter
    ) -> None:
        if controller_cls not in self._controller_chains:
            self._controller_chains[controller_cls] = ExceptionFilterChain()
        self._controller_chains[controller_cls].add(filter_)

    def get_controller_filters(self, controller_cls: type) -> list[ExceptionFilter]:
        chain = self._controller_chains.get(controller_cls)
        return chain.filters if chain else []

    # -- route --

    def register_route_filter(
        self, route_key: str, filter_: ExceptionFilter
    ) -> None:
        if route_key not in self._route_chains:
            self._route_chains[route_key] = ExceptionFilterChain()
        self._route_chains[route_key].add(filter_)

    def get_route_filters(self, route_key: str) -> list[ExceptionFilter]:
        chain = self._route_chains.get(route_key)
        return chain.filters if chain else []

    # -- resolution: route -> controller -> global --

    async def handle(
        self,
        exc: Exception,
        request: HttpRequest,
        *,
        route_key: str | None = None,
        controller_cls: type | None = None,
    ) -> HttpResponse | None:
        # 1. route scope
        if route_key and route_key in self._route_chains:
            result = await self._route_chains[route_key].handle(exc, request)
            if result is not None:
                return result

        # 2. controller scope
        if controller_cls and controller_cls in self._controller_chains:
            result = await self._controller_chains[controller_cls].handle(exc, request)
            if result is not None:
                return result

        # 3. global scope
        result = await self._global_chain.handle(exc, request)
        if result is not None:
            return result

        return None

    def clear(self) -> None:
        self._global_chain = ExceptionFilterChain()
        self._controller_chains.clear()
        self._route_chains.clear()


# singleton registry
default_registry = ExceptionFilterRegistry()
