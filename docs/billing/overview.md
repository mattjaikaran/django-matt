# Billing Overview

Subscription and payment management with Stripe, PayPal, and Polar.

## Quick Start

```python
from django_matt.billing import BillingController, WebhookController

api.register_controller(BillingController, prefix="/billing")
api.register_controller(WebhookController, prefix="/billing/webhooks")
```

## Providers

| Provider | Use Case |
|----------|----------|
| **Stripe** | Full-featured payment processing |
| **PayPal** | Global payment support |
| **Polar** | Open source monetization |

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "BILLING": {
        "DEFAULT_PROVIDER": "stripe",
        "STRIPE": {
            "SECRET_KEY": os.environ["STRIPE_SECRET_KEY"],
            "WEBHOOK_SECRET": os.environ["STRIPE_WEBHOOK_SECRET"],
        },
    },
}
```

## Usage

```python
from django_matt.billing import get_provider

provider = get_provider("stripe")

# Create checkout session
checkout = await provider.create_checkout_session(
    price_id="price_xxx",
    success_url="https://myapp.com/success",
    cancel_url="https://myapp.com/cancel",
)

# Manage subscription
subscription = await provider.get_subscription("sub_xxx")
await provider.cancel_subscription("sub_xxx")
```

## See Also

- [Stripe](stripe.md)
- [PayPal](paypal.md)
- [Polar](polar.md)
