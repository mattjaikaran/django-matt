from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

import pytest

from django_matt.exceptions import default_registry
from django_matt.exceptions.builtins import (
    DatabaseExceptionFilter,
    NotFoundExceptionFilter,
    PermissionExceptionFilter,
    ThrottleExceptionFilter,
    ValidationExceptionFilter,
)
from django_matt.exceptions.decorators import (
    catch,
    catch_all,
    exception_filter,
    register_global_filter,
)
from django_matt.exceptions.filters import (
    ExceptionFilter,
    ExceptionFilterChain,
    FunctionExceptionFilter,
)
from django_matt.exceptions.registry import ExceptionFilterRegistry


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def request_(rf):
    return rf.get("/api/test")


@pytest.fixture
def registry():
    return ExceptionFilterRegistry()


# ---------------------------------------------------------------------------
# ExceptionFilter base
# ---------------------------------------------------------------------------


class DummyFilter(ExceptionFilter):
    exception_types = (ValueError,)
    order = 0

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        return HttpResponse(f"caught: {exc}", status=400)


class HighPriorityFilter(ExceptionFilter):
    exception_types = (ValueError,)
    order = -10

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        return HttpResponse("high priority", status=400)


class TypeErrorFilter(ExceptionFilter):
    exception_types = (TypeError,)
    order = 0

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        return HttpResponse("type error caught", status=400)


class BrokenFilter(ExceptionFilter):
    exception_types = (ValueError,)
    order = 5

    async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        raise RuntimeError("filter broke")


@pytest.mark.asyncio
async def test_filter_can_handle():
    f = DummyFilter()
    assert f.can_handle(ValueError("x"))
    assert not f.can_handle(TypeError("x"))


@pytest.mark.asyncio
async def test_filter_catch(request_):
    f = DummyFilter()
    resp = await f.catch(ValueError("boom"), request_)
    assert resp.status_code == 400
    assert b"caught: boom" in resp.content


# ---------------------------------------------------------------------------
# ExceptionFilterChain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_handles_matching_exception(request_):
    chain = ExceptionFilterChain([DummyFilter()])
    resp = await chain.handle(ValueError("test"), request_)
    assert resp is not None
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_chain_returns_none_for_unmatched(request_):
    chain = ExceptionFilterChain([DummyFilter()])
    resp = await chain.handle(TypeError("test"), request_)
    assert resp is None


@pytest.mark.asyncio
async def test_chain_respects_order(request_):
    chain = ExceptionFilterChain([DummyFilter(), HighPriorityFilter()])
    resp = await chain.handle(ValueError("test"), request_)
    assert resp is not None
    assert b"high priority" in resp.content


@pytest.mark.asyncio
async def test_chain_skips_broken_filter(request_):
    chain = ExceptionFilterChain([BrokenFilter(), DummyFilter()])
    resp = await chain.handle(ValueError("test"), request_)
    assert resp is not None
    assert b"caught: test" in resp.content


@pytest.mark.asyncio
async def test_chain_add_and_remove(request_):
    chain = ExceptionFilterChain()
    chain.add(DummyFilter())
    assert len(chain.filters) == 1
    chain.remove(DummyFilter)
    assert len(chain.filters) == 0


# ---------------------------------------------------------------------------
# FunctionExceptionFilter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_function_filter_sync_handler(request_):
    def handler(exc: Exception, request: HttpRequest) -> HttpResponse:
        return HttpResponse(f"sync: {exc}", status=422)

    f = FunctionExceptionFilter(exception_types=(ValueError,), handler=handler, order=0)
    assert f.can_handle(ValueError("x"))
    resp = await f.catch(ValueError("bad"), request_)
    assert resp.status_code == 422
    assert b"sync: bad" in resp.content


@pytest.mark.asyncio
async def test_function_filter_async_handler(request_):
    async def handler(exc: Exception, request: HttpRequest) -> HttpResponse:
        return HttpResponse(f"async: {exc}", status=418)

    f = FunctionExceptionFilter(exception_types=(TypeError,), handler=handler, order=0)
    resp = await f.catch(TypeError("tea"), request_)
    assert resp.status_code == 418
    assert b"async: tea" in resp.content


# ---------------------------------------------------------------------------
# ExceptionFilterRegistry — scoped resolution
# ---------------------------------------------------------------------------


class _Controller:
    pass


@pytest.mark.asyncio
async def test_registry_global_scope(registry, request_):
    registry.register_global_filter(DummyFilter())
    resp = await registry.handle(ValueError("global"), request_)
    assert resp is not None
    assert b"caught: global" in resp.content


@pytest.mark.asyncio
async def test_registry_controller_scope(registry, request_):
    registry.register_controller_filter(_Controller, DummyFilter())
    resp = await registry.handle(ValueError("ctrl"), request_, controller_cls=_Controller)
    assert resp is not None
    assert b"caught: ctrl" in resp.content


@pytest.mark.asyncio
async def test_registry_route_scope(registry, request_):
    registry.register_route_filter("GET:/api/test", DummyFilter())
    resp = await registry.handle(ValueError("route"), request_, route_key="GET:/api/test")
    assert resp is not None
    assert b"caught: route" in resp.content


@pytest.mark.asyncio
async def test_registry_route_takes_precedence(registry, request_):
    """route scope should win over controller and global."""

    class RouteFilter(ExceptionFilter):
        exception_types = (ValueError,)

        async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
            return HttpResponse("route wins", status=200)

    class GlobalFilter(ExceptionFilter):
        exception_types = (ValueError,)

        async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
            return HttpResponse("global wins", status=200)

    registry.register_global_filter(GlobalFilter())
    registry.register_route_filter("GET:/api/x", RouteFilter())

    resp = await registry.handle(ValueError("x"), request_, route_key="GET:/api/x")
    assert b"route wins" in resp.content


@pytest.mark.asyncio
async def test_registry_controller_before_global(registry, request_):
    class CtrlFilter(ExceptionFilter):
        exception_types = (ValueError,)

        async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
            return HttpResponse("ctrl wins", status=200)

    class GlobalFilter(ExceptionFilter):
        exception_types = (ValueError,)

        async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
            return HttpResponse("global wins", status=200)

    registry.register_global_filter(GlobalFilter())
    registry.register_controller_filter(_Controller, CtrlFilter())

    resp = await registry.handle(ValueError("x"), request_, controller_cls=_Controller)
    assert b"ctrl wins" in resp.content


@pytest.mark.asyncio
async def test_registry_fallthrough_to_global(registry, request_):
    """If route/controller don't handle it, global should."""
    registry.register_route_filter("GET:/api/x", TypeErrorFilter())
    registry.register_global_filter(DummyFilter())

    resp = await registry.handle(ValueError("fallthrough"), request_, route_key="GET:/api/x")
    assert b"caught: fallthrough" in resp.content


@pytest.mark.asyncio
async def test_registry_returns_none_if_unhandled(registry, request_):
    resp = await registry.handle(ValueError("nope"), request_)
    assert resp is None


@pytest.mark.asyncio
async def test_registry_clear(registry, request_):
    registry.register_global_filter(DummyFilter())
    registry.clear()
    resp = await registry.handle(ValueError("cleared"), request_)
    assert resp is None


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def test_exception_filter_decorator():
    @exception_filter(ValueError, TypeError, order=5)
    class MyFilter(ExceptionFilter):
        async def catch(self, exc: Exception, request: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

    assert MyFilter.exception_types == (ValueError, TypeError)
    assert MyFilter.order == 5


def test_catch_decorator_attaches_filters():
    def handler(exc, request):
        return HttpResponse("handled")

    @catch(ValueError, handler=handler)
    async def my_view(request):
        pass

    assert hasattr(my_view, "_exception_filters")
    assert len(my_view._exception_filters) == 1
    f = my_view._exception_filters[0]
    assert isinstance(f, FunctionExceptionFilter)
    assert f.exception_types == (ValueError,)


def test_catch_all_decorator():
    def handler(exc, request):
        return HttpResponse("caught all")

    @catch_all(handler)
    async def my_view(request):
        pass

    assert len(my_view._exception_filters) == 1
    assert my_view._exception_filters[0].exception_types == (Exception,)


# ---------------------------------------------------------------------------
# Built-in filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_exception_filter(request_):
    from pydantic import BaseModel, ValidationError

    class M(BaseModel):
        name: str
        age: int

    f = ValidationExceptionFilter()

    try:
        M(name=123, age="bad")  # type: ignore[arg-type]
    except ValidationError as exc:
        assert f.can_handle(exc)
        resp = await f.catch(exc, request_)
        assert resp.status_code == 422
        import orjson

        body = orjson.loads(resp.content)
        assert body["status"] == 422
        assert body["detail"] == "Validation error"
        assert isinstance(body["extra"], list)
        assert len(body["extra"]) > 0


@pytest.mark.asyncio
async def test_not_found_exception_filter(request_):
    from django.core.exceptions import ObjectDoesNotExist

    class MyDoesNotExist(ObjectDoesNotExist):
        pass

    f = NotFoundExceptionFilter()
    exc = MyDoesNotExist("User not found")
    assert f.can_handle(exc)
    resp = await f.catch(exc, request_)
    assert resp.status_code == 404
    import orjson

    body = orjson.loads(resp.content)
    assert body["status"] == 404


@pytest.mark.asyncio
async def test_permission_exception_filter(request_):
    from django.core.exceptions import PermissionDenied

    f = PermissionExceptionFilter()
    exc = PermissionDenied("nope")
    assert f.can_handle(exc)
    resp = await f.catch(exc, request_)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_permission_filter_handles_builtin_permission_error(request_):
    f = PermissionExceptionFilter()
    exc = PermissionError("os level")
    assert f.can_handle(exc)
    resp = await f.catch(exc, request_)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_database_exception_filter(request_):
    from django.db import IntegrityError

    f = DatabaseExceptionFilter()
    exc = IntegrityError("unique constraint")
    assert f.can_handle(exc)
    resp = await f.catch(exc, request_)
    assert resp.status_code == 409
    import orjson

    body = orjson.loads(resp.content)
    assert body["detail"] == "Database conflict"


@pytest.mark.asyncio
async def test_throttle_exception_filter(request_):
    from django_matt.core.errors import RateLimitAPIError

    f = ThrottleExceptionFilter()
    exc = RateLimitAPIError(retry_after=30)
    assert f.can_handle(exc)
    resp = await f.catch(exc, request_)
    assert resp.status_code == 429
    assert resp["Retry-After"] == "30"


# ---------------------------------------------------------------------------
# Integration: full registry with built-in filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_registry_with_builtins(request_):
    reg = ExceptionFilterRegistry()
    reg.register_global_filter(ValidationExceptionFilter())
    reg.register_global_filter(NotFoundExceptionFilter())
    reg.register_global_filter(PermissionExceptionFilter())
    reg.register_global_filter(DatabaseExceptionFilter())
    reg.register_global_filter(ThrottleExceptionFilter())

    from django.core.exceptions import ObjectDoesNotExist

    resp = await reg.handle(ObjectDoesNotExist("gone"), request_)
    assert resp is not None
    assert resp.status_code == 404

    from django.core.exceptions import PermissionDenied

    resp = await reg.handle(PermissionDenied("forbidden"), request_)
    assert resp is not None
    assert resp.status_code == 403

    from django.db import IntegrityError

    resp = await reg.handle(IntegrityError("dup"), request_)
    assert resp is not None
    assert resp.status_code == 409

    # unhandled exception falls through
    resp = await reg.handle(RuntimeError("unknown"), request_)
    assert resp is None


# ---------------------------------------------------------------------------
# register_global_filter helper
# ---------------------------------------------------------------------------


def test_register_global_filter_adds_to_default_registry():
    old_filters = default_registry.global_filters[:]
    try:
        f = DummyFilter()
        result = register_global_filter(f)
        assert result is f
        assert f in default_registry.global_filters
    finally:
        default_registry.clear()
        for old in old_filters:
            default_registry.register_global_filter(old)
