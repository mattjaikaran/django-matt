# Stripe Integration

Full-featured payment processing with Stripe.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "BILLING": {
        "STRIPE": {
            "SECRET_KEY": os.environ["STRIPE_SECRET_KEY"],
            "PUBLISHABLE_KEY": os.environ["STRIPE_PUBLISHABLE_KEY"],
            "WEBHOOK_SECRET": os.environ["STRIPE_WEBHOOK_SECRET"],
        },
    },
}
```

## Checkout

```python
from django_matt.billing import get_provider

stripe = get_provider("stripe")

# Create checkout session
checkout = await stripe.create_checkout_session(
    price_id="price_xxx",
    success_url="https://myapp.com/success?session_id={CHECKOUT_SESSION_ID}",
    cancel_url="https://myapp.com/cancel",
    customer_email="user@example.com",
    metadata={"user_id": str(user.id)},
)

# Redirect user to checkout.url
```

## Subscriptions

```python
# Get subscription
subscription = await stripe.get_subscription("sub_xxx")

# Cancel subscription
await stripe.cancel_subscription("sub_xxx", cancel_at_period_end=True)

# Update subscription
await stripe.update_subscription("sub_xxx", price_id="price_new")
```

## Billing Portal

```python
# Create portal session for customer self-service
portal_url = await stripe.create_billing_portal_session(
    customer_id="cus_xxx",
    return_url="https://myapp.com/account",
)
```

## Webhooks

```python
from django_matt.billing import WebhookController

api.register_controller(WebhookController)

# Configure webhook URL in Stripe Dashboard:
# https://myapp.com/billing/webhooks/stripe
```
