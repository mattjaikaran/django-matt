# django-matt-stripe-webhooks

Stripe webhook integration for django-matt. Auto-registers a webhook endpoint,
verifies Stripe signatures, and emits framework events for downstream handlers.

## Installation

```bash
uv add django-matt-stripe-webhooks
```

## Configuration

```python
# settings.py
MATT_STRIPE = {
    "WEBHOOK_SECRET": "whsec_...",
    "API_KEY": "sk_...",
    "WEBHOOK_PATH": "/webhooks/stripe",  # optional, default shown
    "WEBHOOK_TOLERANCE": 300,            # optional, signature tolerance in seconds
}
```

## Usage

```python
from django_matt_stripe_webhooks.handlers import on_stripe_event

@on_stripe_event("checkout.session.completed")
async def handle_checkout(event_data: dict) -> None:
    session = event_data["data"]["object"]
    # process completed checkout...

@on_stripe_event("invoice.paid")
async def handle_invoice_paid(event_data: dict) -> None:
    invoice = event_data["data"]["object"]
    # process paid invoice...

# Wildcard patterns
@on_stripe_event("customer.*")
async def handle_customer_events(event_data: dict) -> None:
    ...
```

The plugin automatically:
- Registers a POST endpoint at the configured webhook path
- Verifies the Stripe signature header
- Dispatches to registered handlers by event type
- Emits `stripe.*` events on the django-matt event bus
