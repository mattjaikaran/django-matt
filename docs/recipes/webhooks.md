# Webhooks

Outbound delivery with HMAC-SHA256 signatures and inbound signature verification.

---

## Outbound Webhooks

Outbound webhooks are delivered through the notification system's `WebhookDeliveryHandler`.

### Settings

```python
DJANGO_MATT_NOTIFICATIONS = {
    "WEBHOOK_SECRET": env("WEBHOOK_SECRET"),  # falls back to SECRET_KEY
}
```

### Signature scheme

Each outbound webhook request includes two headers:

```
X-Webhook-Timestamp: 1710000000        # Unix seconds
X-Webhook-Signature: abc123...         # HMAC-SHA256 hex digest
```

The signature is computed over `"{timestamp}.{json_body}"` where the JSON body uses sorted keys:

```python
import hmac, hashlib, time
import orjson

def sign_payload(secret: str, payload: dict) -> tuple[str, str]:
    timestamp = str(int(time.time()))
    body = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode()
    signature_input = f"{timestamp}.{body}"
    sig = hmac.new(
        secret.encode(),
        signature_input.encode(),
        hashlib.sha256,
    ).hexdigest()
    return timestamp, sig
```

### Sending a webhook

```python
from django_matt.notifications.models import Notification
from django_matt.notifications.services.delivery import DeliveryService

notification = await Notification.objects.acreate(
    recipient=user,
    notification_type="order.completed",
    title="Order shipped",
    message="Your order #1234 has shipped.",
    metadata={"order_id": 1234, "tracking": "1Z999AA1012345678"},
)

service = DeliveryService()
await service.deliver_notification(notification)
```

### Retry failed deliveries

```python
service = DeliveryService()
await service.retry_failed_deliveries(max_retries=3)
```

Delivery status (`PENDING → DELIVERED / FAILED`) is tracked in `NotificationDelivery`. `retry_count` and `next_retry_at` are updated on each attempt.

---

## Inbound Webhooks (Verification)

Verify that incoming webhooks actually came from the sender before processing.

### Generic verification helper

```python
import hmac
import hashlib
import time
import orjson

def verify_webhook_signature(
    payload_bytes: bytes,
    timestamp: str,
    signature: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    # Reject stale timestamps (replay protection)
    ts = int(timestamp)
    if abs(time.time() - ts) > tolerance_seconds:
        return False

    expected_input = f"{timestamp}.{payload_bytes.decode()}"
    expected_sig = hmac.new(
        secret.encode(),
        expected_input.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signature)
```

### Inbound endpoint

```python
from django_matt.core.controller import APIController
from django_matt.core.router import post
from django.http import HttpRequest

WEBHOOK_SECRET = env("WEBHOOK_SECRET")

class WebhookController(APIController):
    prefix = "/webhooks"

    @post("/stripe")
    async def stripe(self, request: HttpRequest):
        payload = await request.abody()
        timestamp = request.headers.get("Stripe-Signature", "").split(",")[0].replace("t=", "")
        signature = request.headers.get("X-Webhook-Signature", "")

        if not verify_webhook_signature(payload, timestamp, signature, WEBHOOK_SECRET):
            return self.error("Invalid signature", status=401)

        event = orjson.loads(payload)
        await process_event(event)
        return {"received": True}
```

### Stripe-style `t=,v1=` header

Stripe combines timestamp and signature in one header: `t=1710000000,v1=abc123...`

```python
def parse_stripe_signature_header(header: str) -> tuple[str, str]:
    parts = dict(item.split("=", 1) for item in header.split(","))
    return parts["t"], parts["v1"]

def verify_stripe_webhook(payload_bytes: bytes, sig_header: str, secret: str) -> bool:
    timestamp, signature = parse_stripe_signature_header(sig_header)
    signed_payload = f"{timestamp}.{payload_bytes.decode()}"
    expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

# In controller
@post("/stripe")
async def stripe(self, request: HttpRequest):
    payload = await request.abody()
    sig_header = request.headers.get("Stripe-Signature", "")
    if not verify_stripe_webhook(payload, sig_header, STRIPE_WEBHOOK_SECRET):
        return self.error("Invalid signature", status=400)
    event = orjson.loads(payload)
    await handle_stripe_event(event)
    return {"ok": True}
```

---

## Outbound Delivery Tracking

```python
from django_matt.notifications.models import NotificationDelivery

# Check delivery status for a notification
deliveries = NotificationDelivery.objects.filter(notification=notification)
for d in deliveries:
    print(d.channel, d.status, d.retry_count)

# Mark manually (e.g. from a confirmation callback)
await d.mark_delivered()
await d.mark_failed("connection timeout")
```

---

## Custom Webhook Handler

Register a custom delivery handler for a specific channel:

```python
from django_matt.notifications.services.delivery import DeliveryService, DeliveryHandler

class SlackWebhookHandler(DeliveryHandler):
    async def deliver(self, delivery):
        notification = delivery.notification
        await post_to_slack(
            webhook_url=env("SLACK_WEBHOOK_URL"),
            text=notification.message,
        )
        await delivery.mark_delivered()

service = DeliveryService()
service.register_handler("slack", SlackWebhookHandler())
```

---

## Notification Preferences

Users can opt in/out of webhook delivery per channel:

```python
from django_matt.notifications.models import NotificationPreferences

prefs = await NotificationPreferences.get_or_create_for_user(user)
prefs.in_app_enabled = True
prefs.email_enabled = False
await prefs.asave()
```
