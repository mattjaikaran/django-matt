from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from django_matt_stripe_webhooks.config import StripeConfig
from django_matt_stripe_webhooks.handlers import (
    clear_handlers,
    dispatch_event,
    get_handlers_for,
    list_registered_events,
    on_stripe_event,
)
from django_matt_stripe_webhooks.plugin import StripeWebhooksPlugin
from django_matt_stripe_webhooks.schemas import (
    StripeWebhookEvent,
    WebhookErrorResponse,
    WebhookResponse,
)


class TestStripeConfig:
    def test_default_config(self) -> None:
        config = StripeConfig()
        assert config.webhook_path == "/webhooks/stripe"
        assert config.webhook_tolerance == 300

    def test_config_validation_missing_secret(self) -> None:
        config = StripeConfig(api_key="sk_test_123")
        errors = config.validate()
        assert len(errors) == 1
        assert "WEBHOOK_SECRET" in errors[0]

    def test_config_validation_missing_api_key(self) -> None:
        config = StripeConfig(webhook_secret="whsec_test")
        errors = config.validate()
        assert len(errors) == 1
        assert "API_KEY" in errors[0]

    def test_config_validation_passes(self) -> None:
        config = StripeConfig(webhook_secret="whsec_test", api_key="sk_test_123")
        assert config.validate() == []


class TestHandlerRegistration:
    def setup_method(self) -> None:
        clear_handlers()

    def teardown_method(self) -> None:
        clear_handlers()

    def test_register_handler(self) -> None:
        @on_stripe_event("checkout.session.completed")
        async def handler(event_data: dict) -> None:
            pass

        assert "checkout.session.completed" in list_registered_events()
        assert handler._stripe_event_type == "checkout.session.completed"

    def test_sync_handler_rejected(self) -> None:
        with pytest.raises(TypeError, match="must be async"):

            @on_stripe_event("invoice.paid")
            def bad_handler(event_data: dict) -> None:
                pass

    def test_get_handlers_exact_match(self) -> None:
        @on_stripe_event("invoice.paid")
        async def handler(event_data: dict) -> None:
            pass

        handlers = get_handlers_for("invoice.paid")
        assert len(handlers) == 1
        assert handlers[0] is handler

    def test_get_handlers_wildcard(self) -> None:
        @on_stripe_event("customer.*")
        async def handler(event_data: dict) -> None:
            pass

        handlers = get_handlers_for("customer.created")
        assert len(handlers) == 1

        handlers = get_handlers_for("invoice.paid")
        assert len(handlers) == 0

    def test_multiple_handlers(self) -> None:
        @on_stripe_event("checkout.session.completed")
        async def handler1(event_data: dict) -> None:
            pass

        @on_stripe_event("checkout.session.completed")
        async def handler2(event_data: dict) -> None:
            pass

        handlers = get_handlers_for("checkout.session.completed")
        assert len(handlers) == 2


class TestEventDispatch:
    def setup_method(self) -> None:
        clear_handlers()

    def teardown_method(self) -> None:
        clear_handlers()

    @pytest.mark.asyncio
    async def test_dispatch_invokes_handler(self) -> None:
        mock = AsyncMock()

        @on_stripe_event("payment_intent.succeeded")
        async def handler(event_data: dict) -> None:
            await mock(event_data)

        event_data = {"type": "payment_intent.succeeded", "data": {"object": {}}}
        count = await dispatch_event("payment_intent.succeeded", event_data)
        assert count == 1
        mock.assert_awaited_once_with(event_data)

    @pytest.mark.asyncio
    async def test_dispatch_no_handlers(self) -> None:
        count = await dispatch_event("unknown.event", {})
        assert count == 0

    @pytest.mark.asyncio
    async def test_dispatch_handler_error_does_not_propagate(self) -> None:
        @on_stripe_event("test.error")
        async def bad_handler(event_data: dict) -> None:
            raise ValueError("boom")

        count = await dispatch_event("test.error", {})
        assert count == 1  # handler was still invoked


class TestSchemas:
    def test_webhook_event_schema(self) -> None:
        event = StripeWebhookEvent(
            id="evt_123",
            type="checkout.session.completed",
            data={"object": {"id": "cs_123"}},
        )
        assert event.id == "evt_123"
        assert event.type == "checkout.session.completed"

    def test_webhook_response(self) -> None:
        resp = WebhookResponse(event_id="evt_123", event_type="invoice.paid")
        assert resp.status == "ok"

    def test_webhook_error_response(self) -> None:
        resp = WebhookErrorResponse(detail="bad signature")
        assert resp.status == "error"


class TestPluginMeta:
    def test_plugin_name(self) -> None:
        plugin = StripeWebhooksPlugin()
        assert plugin.name == "stripe_webhooks"

    def test_plugin_version(self) -> None:
        plugin = StripeWebhooksPlugin()
        assert plugin.version == "0.1.0"

    def test_settings_schema(self) -> None:
        plugin = StripeWebhooksPlugin()
        schema = plugin.get_settings_schema()
        assert "WEBHOOK_SECRET" in schema["properties"]
        assert "API_KEY" in schema["properties"]
        assert "WEBHOOK_SECRET" in schema["required"]
