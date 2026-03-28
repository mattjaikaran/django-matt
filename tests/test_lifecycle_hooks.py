"""
Tests for MattAPI lifecycle hooks (@api.on_startup / @api.on_shutdown).

Tests cover:
- Registering sync and async startup/shutdown handlers
- Execution order (FIFO)
- Idempotency (calling startup/shutdown twice only runs handlers once)
- Error propagation from handlers
- Decorator return value (handler is returned unmodified)
- Sync handlers wrapped via sync_to_async
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from django_matt.api import MattAPI


@pytest.fixture()
def api() -> MattAPI:
    return MattAPI(title="Test API")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestRegistration:
    def test_on_startup_registers_handler(self, api: MattAPI) -> None:
        @api.on_startup
        async def handler() -> None:
            pass

        assert handler in api._startup_handlers
        assert len(api._startup_handlers) == 1

    def test_on_shutdown_registers_handler(self, api: MattAPI) -> None:
        @api.on_shutdown
        async def handler() -> None:
            pass

        assert handler in api._shutdown_handlers
        assert len(api._shutdown_handlers) == 1

    def test_decorator_returns_original_function(self, api: MattAPI) -> None:
        async def my_func() -> None:
            pass

        result = api.on_startup(my_func)
        assert result is my_func

    def test_multiple_handlers_registered(self, api: MattAPI) -> None:
        @api.on_startup
        async def first() -> None:
            pass

        @api.on_startup
        async def second() -> None:
            pass

        assert len(api._startup_handlers) == 2
        assert api._startup_handlers[0] is first
        assert api._startup_handlers[1] is second


# ------------------------------------------------------------------
# Execution
# ------------------------------------------------------------------


class TestStartup:
    @pytest.mark.asyncio
    async def test_async_handler_called(self, api: MattAPI) -> None:
        mock = AsyncMock()
        api.on_startup(mock)
        await api.startup()
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_handler_called(self, api: MattAPI) -> None:
        mock = MagicMock()
        api.on_startup(mock)
        await api.startup()
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_order(self, api: MattAPI) -> None:
        order: list[int] = []

        @api.on_startup
        async def first() -> None:
            order.append(1)

        @api.on_startup
        async def second() -> None:
            order.append(2)

        @api.on_startup
        async def third() -> None:
            order.append(3)

        await api.startup()
        assert order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_idempotent(self, api: MattAPI) -> None:
        mock = AsyncMock()
        api.on_startup(mock)
        await api.startup()
        await api.startup()
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_propagates(self, api: MattAPI) -> None:
        @api.on_startup
        async def bad_handler() -> None:
            raise RuntimeError("init failed")

        with pytest.raises(RuntimeError, match="init failed"):
            await api.startup()


class TestShutdown:
    @pytest.mark.asyncio
    async def test_async_handler_called(self, api: MattAPI) -> None:
        mock = AsyncMock()
        api.on_shutdown(mock)
        await api.shutdown()
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_handler_called(self, api: MattAPI) -> None:
        mock = MagicMock()
        api.on_shutdown(mock)
        await api.shutdown()
        mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent(self, api: MattAPI) -> None:
        mock = AsyncMock()
        api.on_shutdown(mock)
        await api.shutdown()
        await api.shutdown()
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error_propagates(self, api: MattAPI) -> None:
        @api.on_shutdown
        async def bad_handler() -> None:
            raise RuntimeError("cleanup failed")

        with pytest.raises(RuntimeError, match="cleanup failed"):
            await api.shutdown()


# ------------------------------------------------------------------
# Mixed sync + async
# ------------------------------------------------------------------


class TestMixedHandlers:
    @pytest.mark.asyncio
    async def test_mixed_startup(self, api: MattAPI) -> None:
        order: list[str] = []

        @api.on_startup
        async def async_handler() -> None:
            order.append("async")

        @api.on_startup
        def sync_handler() -> None:
            order.append("sync")

        await api.startup()
        assert order == ["async", "sync"]

    @pytest.mark.asyncio
    async def test_mixed_shutdown(self, api: MattAPI) -> None:
        order: list[str] = []

        @api.on_shutdown
        def sync_handler() -> None:
            order.append("sync")

        @api.on_shutdown
        async def async_handler() -> None:
            order.append("async")

        await api.shutdown()
        assert order == ["sync", "async"]


# ------------------------------------------------------------------
# State flags
# ------------------------------------------------------------------


class TestStateFlags:
    def test_initial_state(self, api: MattAPI) -> None:
        assert api._startup_complete is False
        assert api._shutdown_complete is False

    @pytest.mark.asyncio
    async def test_startup_sets_flag(self, api: MattAPI) -> None:
        await api.startup()
        assert api._startup_complete is True

    @pytest.mark.asyncio
    async def test_shutdown_sets_flag(self, api: MattAPI) -> None:
        await api.shutdown()
        assert api._shutdown_complete is True

    @pytest.mark.asyncio
    async def test_failed_startup_does_not_set_flag(self, api: MattAPI) -> None:
        @api.on_startup
        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await api.startup()
        assert api._startup_complete is False
