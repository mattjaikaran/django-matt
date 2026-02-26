# BaseThirdPartyService

`BaseThirdPartyService` is an async HTTP client base class for integrating external APIs. It wraps `httpx.AsyncClient` with authentication headers, orjson serialization, structured error handling, and connection reuse.

## When to Use It

Use `BaseThirdPartyService` whenever you call an external HTTP API:

- Payment providers (Stripe, PayPal, Polar)
- Email delivery (Resend, SendGrid, Mailgun)
- SMS / messaging (Twilio, Vonage)
- Workspace tools (Slack, Discord)
- Any SaaS API with a REST interface

Do not use it for internal service-to-service calls within your Django application — use `CRUDService` for those.

## Import

```python
from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError
```

`httpx` must be installed:

```bash
uv add httpx
```

---

## Class Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `""` | Root URL prepended to every request path |
| `timeout` | `float` | `30.0` | Request timeout in seconds |

---

## Override Points

### _auth_headers()

```python
def _auth_headers(self) -> dict[str, str]
```

Return authentication headers. Called once when the client is constructed. Override in every subclass.

```python
def _auth_headers(self) -> dict:
    from django.conf import settings
    return {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"}
```

Common patterns:

```python
# Bearer token
{"Authorization": f"Bearer {settings.API_KEY}"}

# Basic auth
import base64
token = base64.b64encode(f"{user}:{password}".encode()).decode()
{"Authorization": f"Basic {token}"}

# API key header
{"X-API-Key": settings.SERVICE_API_KEY}

# Multiple headers
{"Authorization": f"Bearer {settings.TOKEN}", "X-Account-Id": settings.ACCOUNT_ID}
```

### _default_headers()

```python
def _default_headers(self) -> dict[str, str]
```

Return static headers sent with every request. The default implementation sends `Content-Type: application/json` and `Accept: application/json`. Override to add versioning headers, user agents, or service-specific requirements.

```python
def _default_headers(self) -> dict:
    return {
        **super()._default_headers(),
        "Stripe-Version": "2024-06-20",
        "User-Agent": "MyApp/1.0",
    }
```

### _on_error()

```python
def _on_error(self, status: int, body: dict) -> None
```

Called when the response status is non-2xx. The default implementation reads `body["message"]`, `body["error"]`, or `body["detail"]` and raises `ThirdPartyServiceError`.

Override to extract service-specific error structures:

```python
def _on_error(self, status: int, body: dict) -> None:
    # Stripe wraps errors under body["error"]
    error = body.get("error", {})
    msg = error.get("message", f"HTTP {status}")
    code = error.get("code", "unknown")
    raise ThirdPartyServiceError(status, msg, body)
```

---

## HTTP Request Helpers

All helpers are `async` and return a parsed `dict`. They raise `ThirdPartyServiceError` on non-2xx responses.

```python
async def _get(self, path: str, *, params: dict | None = None, **kw) -> dict
async def _post(self, path: str, body: dict | None = None, **kw) -> dict
async def _put(self, path: str, body: dict | None = None, **kw) -> dict
async def _patch(self, path: str, body: dict | None = None, **kw) -> dict
async def _delete(self, path: str, **kw) -> dict
```

`path` is relative to `base_url`. Query parameters go in `params`; request body goes as the positional `body` argument.

```python
# GET with query params
customers = await self._get("/customers", params={"limit": 100, "status": "active"})

# POST with JSON body
customer = await self._post("/customers", {"email": "alice@example.com", "name": "Alice"})

# PATCH
updated = await self._patch(f"/customers/{customer_id}", {"name": "Alice Smith"})

# DELETE
await self._delete(f"/customers/{customer_id}")
```

### extra_headers

Any helper accepts `extra_headers` to add or override headers for a single request:

```python
result = await self._post("/payments", body, extra_headers={"Idempotency-Key": str(uuid4())})
```

---

## Connection Management

The `httpx.AsyncClient` is created lazily on the first request and reused across subsequent calls.

### Explicit close

```python
service = StripeService()
result = await service.create_customer(email, name)
await service.close()  # release the connection pool
```

### Async context manager (recommended for short-lived usage)

```python
async with StripeService() as stripe:
    customer = await stripe.create_customer(email="alice@example.com", name="Alice")
    session = await stripe.create_checkout_session(price_id="price_xxx", success_url="https://...")
```

For long-lived usage (controller attribute, singleton), keep the service alive and let it reuse connections. Call `close()` during application shutdown.

---

## ThirdPartyServiceError

```python
class ThirdPartyServiceError(Exception):
    status: int     # HTTP status code (e.g. 402, 429, 500)
    message: str    # Human-readable error message
    body: dict      # Full parsed response body
```

```python
from django_matt.services import ThirdPartyServiceError

try:
    customer = await stripe.create_customer(email, name)
except ThirdPartyServiceError as exc:
    if exc.status == 402:
        raise HttpError(402, "Payment required")
    if exc.status == 429:
        raise HttpError(429, "Rate limit exceeded — retry later")
    raise HttpError(500, f"Stripe error: {exc.message}")
```

---

## Real Examples

### StripeService

```python
# billing/stripe_service.py
from django.conf import settings
from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError

class StripeService(BaseThirdPartyService):
    base_url = "https://api.stripe.com/v1"

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"}

    def _default_headers(self) -> dict:
        return {
            **super()._default_headers(),
            "Stripe-Version": "2024-06-20",
        }

    def _on_error(self, status: int, body: dict) -> None:
        error = body.get("error", {})
        msg = error.get("message", f"Stripe error {status}")
        raise ThirdPartyServiceError(status, msg, body)

    async def create_customer(self, email: str, name: str) -> dict:
        return await self._post("/customers", {"email": email, "name": name})

    async def get_customer(self, customer_id: str) -> dict:
        return await self._get(f"/customers/{customer_id}")

    async def create_checkout_session(
        self, price_id: str, customer_id: str, success_url: str, cancel_url: str
    ) -> dict:
        return await self._post("/checkout/sessions", {
            "mode": "subscription",
            "customer": customer_id,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": 1,
            "success_url": success_url,
            "cancel_url": cancel_url,
        })

    async def cancel_subscription(self, subscription_id: str) -> dict:
        return await self._delete(f"/subscriptions/{subscription_id}")

    async def list_invoices(self, customer_id: str) -> list[dict]:
        result = await self._get("/invoices", params={"customer": customer_id, "limit": 100})
        return result.get("data", [])
```

### ResendService

```python
# email/resend_service.py
from django.conf import settings
from django_matt.services import BaseThirdPartyService

class ResendService(BaseThirdPartyService):
    base_url = "https://api.resend.com"

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        html: str,
        from_address: str = "noreply@example.com",
        reply_to: str | None = None,
    ) -> dict:
        body = {
            "from": from_address,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
        }
        if reply_to:
            body["reply_to"] = reply_to
        return await self._post("/emails", body)

    async def get_email(self, email_id: str) -> dict:
        return await self._get(f"/emails/{email_id}")
```

### SlackService

```python
# integrations/slack_service.py
from django.conf import settings
from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError

class SlackService(BaseThirdPartyService):
    base_url = "https://slack.com/api"

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}

    def _on_error(self, status: int, body: dict) -> None:
        # Slack returns 200 even on errors; check body["ok"]
        if not body.get("ok"):
            msg = body.get("error", f"Slack error {status}")
            raise ThirdPartyServiceError(status, msg, body)

    async def _slack_request(self, path: str, body: dict) -> dict:
        result = await self._post(path, body)
        if not result.get("ok"):
            self._on_error(200, result)
        return result

    async def post_message(self, channel: str, text: str) -> dict:
        return await self._slack_request("/chat.postMessage", {
            "channel": channel,
            "text": text,
        })

    async def post_blocks(self, channel: str, blocks: list[dict]) -> dict:
        return await self._slack_request("/chat.postMessage", {
            "channel": channel,
            "blocks": blocks,
        })

    async def lookup_user_by_email(self, email: str) -> dict:
        result = await self._get("/users.lookupByEmail", params={"email": email})
        if not result.get("ok"):
            self._on_error(200, result)
        return result["user"]
```

---

## Injecting into a Controller

```python
# billing/controllers.py
from django_matt.core import APIController
from django_matt.services import ThirdPartyServiceError
from .stripe_service import StripeService
from .internal_service import BillingService

@api.controller("/billing", tags=["Billing"])
class BillingController(APIController):
    def __init__(self):
        self.billing = BillingService()   # internal CRUD service
        self.stripe = StripeService()     # external HTTP service
        super().__init__()

    @api.post("/checkout")
    async def create_checkout(self, request, data: CheckoutSchema):
        customer = await self.billing.get_or_create_customer(request.user)
        try:
            session = await self.stripe.create_checkout_session(
                price_id=data.price_id,
                customer_id=customer.stripe_id,
                success_url=data.success_url,
                cancel_url=data.cancel_url,
            )
        except ThirdPartyServiceError as exc:
            raise HttpError(exc.status, exc.message)
        return {"url": session["url"]}
```

---

## See Also

- [Service Layer Overview](./index.md)
- [CRUDService API Reference](./crud-service.md)
- [Service Patterns](./patterns.md)
- [Billing module](../../django_matt/billing/) — production Stripe/PayPal/Polar integrations
- [Email module](../../django_matt/email/) — production email provider integrations
