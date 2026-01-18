# PayPal Integration

Global payment support with PayPal.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "BILLING": {
        "PAYPAL": {
            "CLIENT_ID": os.environ["PAYPAL_CLIENT_ID"],
            "CLIENT_SECRET": os.environ["PAYPAL_CLIENT_SECRET"],
            "MODE": "live",  # or "sandbox"
        },
    },
}
```

## Usage

```python
from django_matt.billing import get_provider

paypal = get_provider("paypal")

# Create subscription
subscription = await paypal.create_subscription(
    plan_id="P-xxx",
    return_url="https://myapp.com/success",
    cancel_url="https://myapp.com/cancel",
)

# Redirect user to subscription.approve_url
```
