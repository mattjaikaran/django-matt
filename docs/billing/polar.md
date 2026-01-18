# Polar Integration

Open source monetization with Polar.

## Configuration

```python
# settings.py
DJANGO_MATT = {
    "BILLING": {
        "POLAR": {
            "ACCESS_TOKEN": os.environ["POLAR_ACCESS_TOKEN"],
        },
    },
}
```

## Usage

```python
from django_matt.billing import get_provider

polar = get_provider("polar")

# Create checkout
checkout = await polar.create_checkout_session(
    price_id="...",
    success_url="https://myapp.com/success",
    cancel_url="https://myapp.com/cancel",
)
```
