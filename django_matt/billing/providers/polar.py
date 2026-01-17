"""
Polar billing provider.

Polar is a developer-focused Merchant of Record platform.

Requires: pip install httpx

Documentation: https://polar.sh/docs
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from django_matt.billing.config import PolarConfig
from django_matt.billing.providers.base import (
    BillingProvider,
    BillingAPIError,
    BillingWebhookError,
    CustomerData,
    ProductData,
    PriceData,
    SubscriptionData,
    CheckoutSessionData,
    InvoiceData,
    WebhookEvent,
    PriceInterval,
    SubscriptionStatus,
)


class PolarProvider(BillingProvider[PolarConfig]):
    """Polar billing provider implementation."""

    provider_name = "polar"

    def __init__(self, config: PolarConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self):
        """Get or create httpx client."""
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=self.config.base_url,
                    timeout=30.0,
                    headers={
                        "Authorization": f"Bearer {self.config.access_token}",
                        "Content-Type": "application/json",
                    },
                )
            except ImportError:
                raise BillingAPIError(
                    "httpx package is not installed. Run: pip install httpx",
                    provider=self.provider_name,
                )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make authenticated request to Polar API."""
        client = await self._get_client()

        kwargs: dict[str, Any] = {}
        if data:
            kwargs["json"] = data
        if params:
            kwargs["params"] = params

        response = await client.request(method, path, **kwargs)

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}

            raise BillingAPIError(
                error_data.get("detail", f"Polar API error: {response.status_code}"),
                provider=self.provider_name,
                status_code=response.status_code,
                details=error_data,
            )

        if response.status_code == 204:
            return {}

        return response.json()

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _parse_customer(self, customer: dict) -> CustomerData:
        """Parse Polar customer to CustomerData."""
        return self._add_provider_tag(
            CustomerData(
                id=customer["id"],
                email=customer.get("email", ""),
                name=customer.get("name"),
                metadata=customer.get("metadata", {}),
                created_at=self._parse_datetime(customer.get("created_at")),
                raw_data=customer,
            )
        )

    def _parse_product(self, product: dict) -> ProductData:
        """Parse Polar product to ProductData."""
        return self._add_provider_tag(
            ProductData(
                id=product["id"],
                name=product["name"],
                description=product.get("description"),
                active=product.get("is_archived", False) is False,
                metadata=product.get("metadata", {}),
                created_at=self._parse_datetime(product.get("created_at")),
                raw_data=product,
            )
        )

    def _parse_price(self, price: dict, product_id: str = "") -> PriceData:
        """Parse Polar price to PriceData."""
        # Polar has prices embedded in products
        recurring = price.get("recurring_interval")
        interval = PriceInterval.ONE_TIME

        if recurring:
            interval_map = {
                "day": PriceInterval.DAY,
                "week": PriceInterval.WEEK,
                "month": PriceInterval.MONTH,
                "year": PriceInterval.YEAR,
            }
            interval = interval_map.get(recurring, PriceInterval.MONTH)

        amount = price.get("price_amount", 0)
        if isinstance(amount, str):
            amount = int(float(amount) * 100)

        return self._add_provider_tag(
            PriceData(
                id=price.get("id", ""),
                product_id=product_id,
                currency=price.get("price_currency", "usd").lower(),
                unit_amount=amount,
                interval=interval,
                interval_count=1,
                trial_period_days=None,
                active=True,
                metadata={},
                raw_data=price,
            )
        )

    def _parse_subscription(self, sub: dict) -> SubscriptionData:
        """Parse Polar subscription to SubscriptionData."""
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "unpaid": SubscriptionStatus.UNPAID,
        }

        return self._add_provider_tag(
            SubscriptionData(
                id=sub["id"],
                customer_id=sub.get("customer_id", ""),
                status=status_map.get(sub.get("status", "active"), SubscriptionStatus.ACTIVE),
                price_id=sub.get("price_id"),
                product_id=sub.get("product_id"),
                quantity=1,
                current_period_start=self._parse_datetime(sub.get("current_period_start")),
                current_period_end=self._parse_datetime(sub.get("current_period_end")),
                cancel_at_period_end=sub.get("cancel_at_period_end", False),
                canceled_at=self._parse_datetime(sub.get("canceled_at")),
                trial_start=None,
                trial_end=self._parse_datetime(sub.get("trial_end")),
                metadata=sub.get("metadata", {}),
                created_at=self._parse_datetime(sub.get("created_at")),
                raw_data=sub,
            )
        )

    def _parse_order(self, order: dict) -> InvoiceData:
        """Parse Polar order to InvoiceData."""
        amount = order.get("amount", 0)
        if isinstance(amount, str):
            amount = int(float(amount) * 100)

        return self._add_provider_tag(
            InvoiceData(
                id=order["id"],
                customer_id=order.get("customer_id", ""),
                subscription_id=order.get("subscription_id"),
                status="paid" if order.get("paid_at") else "open",
                currency=order.get("currency", "usd").lower(),
                amount_due=amount,
                amount_paid=amount if order.get("paid_at") else 0,
                amount_remaining=0 if order.get("paid_at") else amount,
                invoice_pdf=order.get("invoice_url"),
                paid_at=self._parse_datetime(order.get("paid_at")),
                created_at=self._parse_datetime(order.get("created_at")),
                raw_data=order,
            )
        )

    # -------------------------------------------------------------------------
    # Customer Management
    # -------------------------------------------------------------------------

    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        data: dict[str, Any] = {"email": email}
        if name:
            data["name"] = name
        if metadata:
            data["metadata"] = metadata
        if self.config.organization_id:
            data["organization_id"] = self.config.organization_id

        result = await self._request("POST", "/v1/customers/", data=data)
        return self._parse_customer(result)

    async def get_customer(self, customer_id: str) -> CustomerData | None:
        try:
            result = await self._request("GET", f"/v1/customers/{customer_id}")
            return self._parse_customer(result)
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def update_customer(
        self,
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        data: dict[str, Any] = {}
        if email is not None:
            data["email"] = email
        if name is not None:
            data["name"] = name
        if metadata is not None:
            data["metadata"] = metadata

        result = await self._request("PATCH", f"/v1/customers/{customer_id}", data=data)
        return self._parse_customer(result)

    async def delete_customer(self, customer_id: str) -> bool:
        try:
            await self._request("DELETE", f"/v1/customers/{customer_id}")
            return True
        except BillingAPIError:
            return False

    async def list_customers(
        self,
        email: str | None = None,
        limit: int = 10,
        starting_after: str | None = None,
    ) -> list[CustomerData]:
        params: dict[str, Any] = {"limit": limit}
        if email:
            params["email"] = email
        if self.config.organization_id:
            params["organization_id"] = self.config.organization_id

        result = await self._request("GET", "/v1/customers/", params=params)
        items = result.get("items", result.get("result", []))
        return [self._parse_customer(c) for c in items]

    # -------------------------------------------------------------------------
    # Product Management
    # -------------------------------------------------------------------------

    async def create_product(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        data: dict[str, Any] = {"name": name}
        if description:
            data["description"] = description
        if metadata:
            data["metadata"] = metadata
        if self.config.organization_id:
            data["organization_id"] = self.config.organization_id

        result = await self._request("POST", "/v1/products/", data=data)
        return self._parse_product(result)

    async def get_product(self, product_id: str) -> ProductData | None:
        try:
            result = await self._request("GET", f"/v1/products/{product_id}")
            return self._parse_product(result)
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def update_product(
        self,
        product_id: str,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if active is not None:
            data["is_archived"] = not active
        if metadata is not None:
            data["metadata"] = metadata

        result = await self._request("PATCH", f"/v1/products/{product_id}", data=data)
        return self._parse_product(result)

    async def list_products(
        self,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[ProductData]:
        params: dict[str, Any] = {"limit": limit}
        if active is not None:
            params["is_archived"] = not active
        if self.config.organization_id:
            params["organization_id"] = self.config.organization_id

        result = await self._request("GET", "/v1/products/", params=params)
        items = result.get("items", result.get("result", []))
        return [self._parse_product(p) for p in items]

    # -------------------------------------------------------------------------
    # Price Management (Polar prices are part of products)
    # -------------------------------------------------------------------------

    async def create_price(
        self,
        product_id: str,
        unit_amount: int,
        currency: str = "usd",
        interval: PriceInterval = PriceInterval.MONTH,
        interval_count: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PriceData:
        """
        Create a price by updating the product's price.
        Polar handles pricing at the product level.
        """
        interval_map = {
            PriceInterval.DAY: "day",
            PriceInterval.WEEK: "week",
            PriceInterval.MONTH: "month",
            PriceInterval.YEAR: "year",
            PriceInterval.ONE_TIME: None,
        }

        price_data: dict[str, Any] = {
            "price_amount": unit_amount,
            "price_currency": currency.upper(),
        }

        if interval != PriceInterval.ONE_TIME:
            price_data["recurring_interval"] = interval_map[interval]

        # Update the product with the new price
        result = await self._request(
            "PATCH",
            f"/v1/products/{product_id}",
            data={"prices": [price_data]},
        )

        # Return the price from the updated product
        prices = result.get("prices", [])
        if prices:
            return self._parse_price(prices[0], product_id)

        return PriceData(
            id=f"{product_id}_price",
            product_id=product_id,
            currency=currency,
            unit_amount=unit_amount,
            interval=interval,
            interval_count=interval_count,
            provider=self.provider_name,
        )

    async def get_price(self, price_id: str) -> PriceData | None:
        """Get price by fetching the product."""
        # Polar prices are embedded in products
        # price_id might be product_id or product_id_price
        product_id = price_id.replace("_price", "")

        product = await self.get_product(product_id)
        if not product:
            return None

        prices = product.raw_data.get("prices", [])
        if prices:
            return self._parse_price(prices[0], product_id)

        return None

    async def list_prices(
        self,
        product_id: str | None = None,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[PriceData]:
        """List prices by fetching products."""
        products = await self.list_products(active=active, limit=limit)

        prices = []
        for product in products:
            if product_id and product.id != product_id:
                continue

            product_prices = product.raw_data.get("prices", [])
            for price in product_prices:
                prices.append(self._parse_price(price, product.id))

        return prices

    # -------------------------------------------------------------------------
    # Subscription Management
    # -------------------------------------------------------------------------

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionData:
        """
        Create a subscription.
        Note: Polar typically creates subscriptions through checkout.
        """
        # Get product from price_id
        product_id = price_id.replace("_price", "")

        data: dict[str, Any] = {
            "customer_id": customer_id,
            "product_id": product_id,
        }
        if metadata:
            data["metadata"] = metadata

        result = await self._request("POST", "/v1/subscriptions/", data=data)
        return self._parse_subscription(result)

    async def get_subscription(self, subscription_id: str) -> SubscriptionData | None:
        try:
            result = await self._request("GET", f"/v1/subscriptions/{subscription_id}")
            return self._parse_subscription(result)
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: str | None = None,
        quantity: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionData:
        data: dict[str, Any] = {}

        if price_id:
            product_id = price_id.replace("_price", "")
            data["product_id"] = product_id

        if metadata:
            data["metadata"] = metadata

        result = await self._request("PATCH", f"/v1/subscriptions/{subscription_id}", data=data)
        return self._parse_subscription(result)

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True,
    ) -> SubscriptionData:
        if cancel_at_period_end:
            result = await self._request(
                "PATCH",
                f"/v1/subscriptions/{subscription_id}",
                data={"cancel_at_period_end": True},
            )
        else:
            result = await self._request("DELETE", f"/v1/subscriptions/{subscription_id}")

        return self._parse_subscription(result)

    async def resume_subscription(self, subscription_id: str) -> SubscriptionData:
        result = await self._request(
            "PATCH",
            f"/v1/subscriptions/{subscription_id}",
            data={"cancel_at_period_end": False},
        )
        return self._parse_subscription(result)

    async def list_subscriptions(
        self,
        customer_id: str | None = None,
        status: SubscriptionStatus | None = None,
        limit: int = 10,
    ) -> list[SubscriptionData]:
        params: dict[str, Any] = {"limit": limit}
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status.value
        if self.config.organization_id:
            params["organization_id"] = self.config.organization_id

        result = await self._request("GET", "/v1/subscriptions/", params=params)
        items = result.get("items", result.get("result", []))
        return [self._parse_subscription(s) for s in items]

    # -------------------------------------------------------------------------
    # Checkout / Payment
    # -------------------------------------------------------------------------

    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: str | None = None,
        customer_email: str | None = None,
        mode: str = "subscription",
        quantity: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSessionData:
        """Create a Polar checkout session."""
        product_id = price_id.replace("_price", "")

        data: dict[str, Any] = {
            "product_id": product_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        if customer_id:
            data["customer_id"] = customer_id
        if customer_email:
            data["customer_email"] = customer_email
        if metadata:
            data["metadata"] = metadata

        result = await self._request("POST", "/v1/checkouts/", data=data)

        return self._add_provider_tag(
            CheckoutSessionData(
                id=result["id"],
                url=result.get("url", result.get("checkout_url", "")),
                customer_id=customer_id,
                subscription_id=result.get("subscription_id"),
                status=result.get("status", "open"),
                mode=mode,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {},
                expires_at=self._parse_datetime(result.get("expires_at")),
                raw_data=result,
            )
        )

    async def get_checkout_session(self, session_id: str) -> CheckoutSessionData | None:
        try:
            result = await self._request("GET", f"/v1/checkouts/{session_id}")
            return self._add_provider_tag(
                CheckoutSessionData(
                    id=result["id"],
                    url=result.get("url", result.get("checkout_url", "")),
                    customer_id=result.get("customer_id"),
                    subscription_id=result.get("subscription_id"),
                    status=result.get("status", "open"),
                    mode="subscription",
                    raw_data=result,
                )
            )
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """Create a customer portal session."""
        result = await self._request(
            "POST",
            "/v1/customer-portal/sessions/",
            data={
                "customer_id": customer_id,
                "return_url": return_url,
            },
        )
        return result.get("url", "")

    # -------------------------------------------------------------------------
    # Invoice/Order Management
    # -------------------------------------------------------------------------

    async def get_invoice(self, invoice_id: str) -> InvoiceData | None:
        """Get order/invoice by ID."""
        try:
            result = await self._request("GET", f"/v1/orders/{invoice_id}")
            return self._parse_order(result)
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_invoices(
        self,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[InvoiceData]:
        """List orders/invoices."""
        params: dict[str, Any] = {"limit": limit}
        if customer_id:
            params["customer_id"] = customer_id
        if subscription_id:
            params["subscription_id"] = subscription_id
        if self.config.organization_id:
            params["organization_id"] = self.config.organization_id

        result = await self._request("GET", "/v1/orders/", params=params)
        items = result.get("items", result.get("result", []))
        return [self._parse_order(o) for o in items]

    # -------------------------------------------------------------------------
    # Webhook Handling
    # -------------------------------------------------------------------------

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """
        Verify Polar webhook signature.

        Polar uses HMAC-SHA256 for webhook signatures.
        The signature header is typically: sha256=<signature>
        """
        try:
            # Extract signature
            if signature.startswith("sha256="):
                signature = signature[7:]

            # Compute expected signature
            expected = hmac.new(
                self.config.webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison
            if not hmac.compare_digest(expected, signature):
                raise BillingWebhookError("Invalid webhook signature")

            data = json.loads(payload)

            return WebhookEvent(
                id=data.get("id", ""),
                type=data.get("type", data.get("event", "")),
                provider=self.provider_name,
                data=data.get("data", data.get("payload", {})),
                created_at=self._parse_datetime(data.get("created_at")),
                raw_payload=payload,
            )
        except json.JSONDecodeError as e:
            raise BillingWebhookError(f"Invalid JSON payload: {e}")
        except BillingWebhookError:
            raise
        except Exception as e:
            raise BillingWebhookError(f"Webhook verification failed: {e}")

    def normalize_webhook_type(self, provider_type: str) -> str:
        """Normalize Polar webhook types to common format."""
        mapping = {
            "subscription.created": "subscription.created",
            "subscription.updated": "subscription.updated",
            "subscription.canceled": "subscription.canceled",
            "subscription.active": "subscription.resumed",
            "order.created": "invoice.created",
            "order.paid": "invoice.paid",
            "order.refunded": "invoice.refunded",
            "checkout.created": "checkout.created",
            "checkout.updated": "checkout.completed",
            "customer.created": "customer.created",
            "customer.updated": "customer.updated",
            "customer.deleted": "customer.deleted",
            "customer.state_changed": "customer.updated",
        }
        return mapping.get(provider_type, provider_type)
