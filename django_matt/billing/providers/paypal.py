"""
PayPal billing provider.

Requires: uv add httpx

Documentation: https://developer.paypal.com/docs/api/subscriptions/v1/
"""

import base64
import hashlib
import hmac
import zlib
from datetime import UTC, datetime
from typing import Any

import orjson

from django_matt.billing.config import PayPalConfig
from django_matt.billing.providers.base import (
    BillingAPIError,
    BillingProvider,
    BillingWebhookError,
    CheckoutSessionData,
    CustomerData,
    PriceData,
    PriceInterval,
    ProductData,
    SubscriptionData,
    SubscriptionStatus,
    WebhookEvent,
)


class PayPalProvider(BillingProvider[PayPalConfig]):
    """PayPal billing provider implementation."""

    provider_name = "paypal"

    def __init__(self, config: PayPalConfig):
        super().__init__(config)
        self._client = None
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._tracked_subscriptions: dict[str, set[str]] = {}

    async def _get_client(self):
        """Get or create httpx client."""
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=self.config.base_url,
                    timeout=30.0,
                )
            except ImportError:
                raise BillingAPIError(
                    "httpx package is not installed. Run: uv add httpx",
                    provider=self.provider_name,
                )
        return self._client

    async def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        now = datetime.now(UTC)

        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        client = await self._get_client()
        credentials = base64.b64encode(
            f"{self.config.client_id}:{self.config.client_secret}".encode()
        ).decode()

        response = await client.post(
            "/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )

        if response.status_code != 200:
            raise BillingAPIError(
                "Failed to get PayPal access token",
                provider=self.provider_name,
                status_code=response.status_code,
                details=response.json(),
            )

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = now.replace(second=now.second + expires_in - 60)

        return self._access_token

    async def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make authenticated request to PayPal API."""
        client = await self._get_client()
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        kwargs: dict[str, Any] = {"headers": headers}
        if data:
            kwargs["json"] = data
        if params:
            kwargs["params"] = params

        response = await client.request(method, path, **kwargs)

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"message": response.text}

            raise BillingAPIError(
                error_data.get("message", f"PayPal API error: {response.status_code}"),
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
            # Handle various PayPal datetime formats
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _parse_subscription(self, sub: dict) -> SubscriptionData:
        """Parse PayPal subscription to SubscriptionData."""
        status_map = {
            "ACTIVE": SubscriptionStatus.ACTIVE,
            "CANCELLED": SubscriptionStatus.CANCELED,
            "SUSPENDED": SubscriptionStatus.PAUSED,
            "EXPIRED": SubscriptionStatus.CANCELED,
            "APPROVAL_PENDING": SubscriptionStatus.INCOMPLETE,
        }

        billing_info = sub.get("billing_info", {})
        last_payment = billing_info.get("last_payment", {})

        return self._add_provider_tag(
            SubscriptionData(
                id=sub["id"],
                customer_id=sub.get("subscriber", {}).get("payer_id", ""),
                status=status_map.get(sub.get("status", ""), SubscriptionStatus.ACTIVE),
                price_id=sub.get("plan_id"),
                product_id=None,
                quantity=sub.get("quantity", 1),
                current_period_start=self._parse_datetime(
                    billing_info.get("cycle_executions", [{}])[0].get("start_date")
                    if billing_info.get("cycle_executions")
                    else None
                ),
                current_period_end=self._parse_datetime(billing_info.get("next_billing_time")),
                cancel_at_period_end=False,
                canceled_at=None,
                trial_start=None,
                trial_end=None,
                metadata=sub.get("custom_id", {}),
                created_at=self._parse_datetime(sub.get("create_time")),
                raw_data=sub,
            )
        )

    def _parse_product(self, product: dict) -> ProductData:
        """Parse PayPal product to ProductData."""
        return self._add_provider_tag(
            ProductData(
                id=product["id"],
                name=product["name"],
                description=product.get("description"),
                active=product.get("status") == "ACTIVE",
                metadata={},
                created_at=self._parse_datetime(product.get("create_time")),
                raw_data=product,
            )
        )

    def _parse_plan(self, plan: dict) -> PriceData:
        """Parse PayPal billing plan to PriceData."""
        billing_cycles = plan.get("billing_cycles", [])
        regular_cycle = next(
            (c for c in billing_cycles if c.get("tenure_type") == "REGULAR"),
            billing_cycles[0] if billing_cycles else {},
        )

        pricing = regular_cycle.get("pricing_scheme", {})
        frequency = regular_cycle.get("frequency", {})

        interval_map = {
            "DAY": PriceInterval.DAY,
            "WEEK": PriceInterval.WEEK,
            "MONTH": PriceInterval.MONTH,
            "YEAR": PriceInterval.YEAR,
        }

        amount = pricing.get("fixed_price", {})
        unit_amount = int(float(amount.get("value", "0")) * 100)

        # Check for trial
        trial_cycle = next(
            (c for c in billing_cycles if c.get("tenure_type") == "TRIAL"),
            None,
        )
        trial_days = None
        if trial_cycle:
            trial_freq = trial_cycle.get("frequency", {})
            trial_count = trial_cycle.get("total_cycles", 1)
            interval_days = {"DAY": 1, "WEEK": 7, "MONTH": 30, "YEAR": 365}
            trial_days = (
                trial_count
                * trial_freq.get("interval_count", 1)
                * interval_days.get(trial_freq.get("interval_unit", "MONTH"), 30)
            )

        return self._add_provider_tag(
            PriceData(
                id=plan["id"],
                product_id=plan.get("product_id", ""),
                currency=amount.get("currency_code", "USD").lower(),
                unit_amount=unit_amount,
                interval=interval_map.get(
                    frequency.get("interval_unit", "MONTH"), PriceInterval.MONTH
                ),
                interval_count=frequency.get("interval_count", 1),
                trial_period_days=trial_days,
                active=plan.get("status") == "ACTIVE",
                metadata={},
                raw_data=plan,
            )
        )

    # -------------------------------------------------------------------------
    # Customer Management (PayPal doesn't have traditional customers)
    # -------------------------------------------------------------------------

    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        """
        PayPal doesn't have a customer creation API.
        Customers are created when they make a purchase.
        We return a placeholder that uses email as ID.
        """
        return self._add_provider_tag(
            CustomerData(
                id=email,  # Use email as customer ID
                email=email,
                name=name,
                metadata=metadata or {},
                created_at=datetime.now(UTC),
            )
        )

    async def get_customer(self, customer_id: str) -> CustomerData | None:
        """PayPal customers are identified by email or payer_id from transactions."""
        return self._add_provider_tag(
            CustomerData(
                id=customer_id,
                email=customer_id if "@" in customer_id else "",
            )
        )

    async def update_customer(
        self,
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        """PayPal doesn't support customer updates."""
        return self._add_provider_tag(
            CustomerData(
                id=customer_id,
                email=email or customer_id,
                name=name,
                metadata=metadata or {},
            )
        )

    async def delete_customer(self, customer_id: str) -> bool:
        """PayPal doesn't support customer deletion."""
        return True

    # -------------------------------------------------------------------------
    # Product Management
    # -------------------------------------------------------------------------

    async def create_product(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        data = {
            "name": name,
            "type": "SERVICE",
        }
        if description:
            data["description"] = description

        result = await self._request("POST", "/v1/catalogs/products", data=data)
        return self._parse_product(result)

    async def get_product(self, product_id: str) -> ProductData | None:
        try:
            result = await self._request("GET", f"/v1/catalogs/products/{product_id}")
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
        patches = []
        if description is not None:
            patches.append(
                {
                    "op": "replace",
                    "path": "/description",
                    "value": description,
                }
            )

        if patches:
            await self._request("PATCH", f"/v1/catalogs/products/{product_id}", data=patches)

        return await self.get_product(product_id)

    async def list_products(
        self,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[ProductData]:
        params = {"page_size": limit}
        result = await self._request("GET", "/v1/catalogs/products", params=params)
        products = result.get("products", [])
        return [self._parse_product(p) for p in products]

    # -------------------------------------------------------------------------
    # Price Management (PayPal calls these "Billing Plans")
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
        interval_map = {
            PriceInterval.DAY: "DAY",
            PriceInterval.WEEK: "WEEK",
            PriceInterval.MONTH: "MONTH",
            PriceInterval.YEAR: "YEAR",
        }

        billing_cycles = []

        # Add trial if specified
        if trial_period_days:
            billing_cycles.append(
                {
                    "tenure_type": "TRIAL",
                    "sequence": 1,
                    "total_cycles": 1,
                    "frequency": {
                        "interval_unit": "DAY",
                        "interval_count": trial_period_days,
                    },
                    "pricing_scheme": {
                        "fixed_price": {
                            "value": "0",
                            "currency_code": currency.upper(),
                        },
                    },
                }
            )

        # Regular billing cycle
        billing_cycles.append(
            {
                "tenure_type": "REGULAR",
                "sequence": len(billing_cycles) + 1,
                "total_cycles": 0,  # Infinite
                "frequency": {
                    "interval_unit": interval_map.get(interval, "MONTH"),
                    "interval_count": interval_count,
                },
                "pricing_scheme": {
                    "fixed_price": {
                        "value": str(unit_amount / 100),
                        "currency_code": currency.upper(),
                    },
                },
            }
        )

        data = {
            "product_id": product_id,
            "name": f"Plan {unit_amount / 100} {currency.upper()}/{interval.value}",
            "billing_cycles": billing_cycles,
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "payment_failure_threshold": 3,
            },
        }

        result = await self._request("POST", "/v1/billing/plans", data=data)
        return self._parse_plan(result)

    async def get_price(self, price_id: str) -> PriceData | None:
        try:
            result = await self._request("GET", f"/v1/billing/plans/{price_id}")
            return self._parse_plan(result)
        except BillingAPIError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_prices(
        self,
        product_id: str | None = None,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[PriceData]:
        params: dict[str, Any] = {"page_size": limit}
        if product_id:
            params["product_id"] = product_id

        result = await self._request("GET", "/v1/billing/plans", params=params)
        plans = result.get("plans", [])
        return [self._parse_plan(p) for p in plans]

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
        Note: PayPal subscriptions require customer approval.
        This returns a subscription with approval URL.
        """
        data: dict[str, Any] = {
            "plan_id": price_id,
            "quantity": str(quantity),
            "application_context": {
                "return_url": "https://example.com/return",
                "cancel_url": "https://example.com/cancel",
            },
        }

        if "@" in customer_id:
            data["subscriber"] = {"email_address": customer_id}

        if metadata:
            data["custom_id"] = orjson.dumps(metadata).decode()

        result = await self._request("POST", "/v1/billing/subscriptions", data=data)
        return self._parse_subscription(result)

    async def get_subscription(self, subscription_id: str) -> SubscriptionData | None:
        try:
            result = await self._request("GET", f"/v1/billing/subscriptions/{subscription_id}")
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
        if price_id:
            # Plan changes require revision
            await self._request(
                "POST",
                f"/v1/billing/subscriptions/{subscription_id}/revise",
                data={"plan_id": price_id},
            )

        if quantity:
            await self._request(
                "POST",
                f"/v1/billing/subscriptions/{subscription_id}/revise",
                data={"quantity": str(quantity)},
            )

        return await self.get_subscription(subscription_id)

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True,
    ) -> SubscriptionData:
        if cancel_at_period_end:
            # PayPal doesn't have cancel_at_period_end, so we suspend instead
            await self._request(
                "POST",
                f"/v1/billing/subscriptions/{subscription_id}/suspend",
                data={"reason": "Customer requested cancellation at period end"},
            )
        else:
            await self._request(
                "POST",
                f"/v1/billing/subscriptions/{subscription_id}/cancel",
                data={"reason": "Customer requested immediate cancellation"},
            )

        return await self.get_subscription(subscription_id)

    async def resume_subscription(self, subscription_id: str) -> SubscriptionData:
        await self._request(
            "POST",
            f"/v1/billing/subscriptions/{subscription_id}/activate",
            data={"reason": "Reactivating subscription"},
        )
        return await self.get_subscription(subscription_id)

    async def list_subscriptions(
        self,
        customer_id: str | None = None,
        status: SubscriptionStatus | None = None,
        limit: int = 10,
    ) -> list[SubscriptionData]:
        """
        List subscriptions using locally tracked IDs.

        PayPal has no bulk subscription list endpoint. This method fetches
        subscriptions individually from IDs stored via ``track_subscription()``.
        Call ``track_subscription(customer_id, subscription_id)`` when creating
        subscriptions to enable listing.
        """
        status_map = {
            SubscriptionStatus.ACTIVE: "ACTIVE",
            SubscriptionStatus.CANCELED: "CANCELLED",
            SubscriptionStatus.PAUSED: "SUSPENDED",
        }
        target_status = status_map.get(status) if status else None

        # Get tracked IDs for this customer (or all if no customer_id)
        if customer_id:
            sub_ids = list(self._tracked_subscriptions.get(customer_id, []))
        else:
            sub_ids = [
                sid
                for sids in self._tracked_subscriptions.values()
                for sid in sids
            ]

        subscriptions: list[SubscriptionData] = []
        for sub_id in sub_ids:
            if len(subscriptions) >= limit:
                break
            sub = await self.get_subscription(sub_id)
            if sub is None:
                continue
            if target_status and sub.status.value != target_status.lower():
                continue
            subscriptions.append(sub)

        return subscriptions

    def track_subscription(self, customer_id: str, subscription_id: str) -> None:
        """
        Track a subscription ID for a customer.

        Call this after ``create_subscription()`` to enable
        ``list_subscriptions()`` lookups. For persistence across restarts,
        store subscription IDs in your database instead.
        """
        if customer_id not in self._tracked_subscriptions:
            self._tracked_subscriptions[customer_id] = set()
        self._tracked_subscriptions[customer_id].add(subscription_id)

    def untrack_subscription(self, customer_id: str, subscription_id: str) -> None:
        """Remove a tracked subscription ID."""
        if customer_id in self._tracked_subscriptions:
            self._tracked_subscriptions[customer_id].discard(subscription_id)

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
        """Create a PayPal subscription with approval links."""
        data: dict[str, Any] = {
            "plan_id": price_id,
            "quantity": str(quantity),
            "application_context": {
                "brand_name": "Your Brand",
                "return_url": success_url,
                "cancel_url": cancel_url,
                "user_action": "SUBSCRIBE_NOW",
            },
        }

        if customer_email:
            data["subscriber"] = {"email_address": customer_email}

        if metadata:
            data["custom_id"] = orjson.dumps(metadata).decode()

        result = await self._request("POST", "/v1/billing/subscriptions", data=data)

        # Find approval link
        approval_url = ""
        for link in result.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href", "")
                break

        return self._add_provider_tag(
            CheckoutSessionData(
                id=result["id"],
                url=approval_url,
                customer_id=customer_id or customer_email,
                subscription_id=result["id"],
                status=result.get("status", "APPROVAL_PENDING"),
                mode=mode,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {},
                raw_data=result,
            )
        )

    async def get_checkout_session(self, session_id: str) -> CheckoutSessionData | None:
        """PayPal checkout sessions are subscriptions."""
        sub = await self.get_subscription(session_id)
        if not sub:
            return None

        return self._add_provider_tag(
            CheckoutSessionData(
                id=sub.id,
                url="",
                customer_id=sub.customer_id,
                subscription_id=sub.id,
                status=sub.status.value,
                mode="subscription",
                raw_data=sub.raw_data,
            )
        )

    # -------------------------------------------------------------------------
    # Webhook Handling
    # -------------------------------------------------------------------------

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
        headers: dict[str, str] | None = None,
    ) -> WebhookEvent:
        """
        Verify PayPal webhook signature and parse the event.

        PayPal webhook verification uses a composed signature string:
        ``transmission_id|transmission_time|webhook_id|crc32(raw_body)``
        verified via HMAC-SHA256 using the client secret.

        Required headers (passed via ``headers`` dict):
        - PAYPAL-TRANSMISSION-ID
        - PAYPAL-TRANSMISSION-TIME
        - PAYPAL-TRANSMISSION-SIG

        Args:
            payload: Raw request body bytes
            signature: The PAYPAL-TRANSMISSION-SIG header value
            headers: Dict of PayPal webhook headers

        Raises:
            BillingWebhookError: If verification fails
        """
        if headers is None:
            headers = {}

        # Normalize header keys to uppercase
        norm_headers = {k.upper(): v for k, v in headers.items()}

        try:
            data = orjson.loads(payload)
        except orjson.JSONDecodeError as e:
            raise BillingWebhookError(f"Invalid JSON payload: {e}")

        try:
            # Extract required PayPal headers
            transmission_id = norm_headers.get("PAYPAL-TRANSMISSION-ID", "")
            transmission_time = norm_headers.get("PAYPAL-TRANSMISSION-TIME", "")
            transmission_sig = signature or norm_headers.get("PAYPAL-TRANSMISSION-SIG", "")

            # webhook_id must be configured
            webhook_id = self.config.webhook_id
            if not webhook_id:
                raise BillingWebhookError(
                    "PayPal webhook_id is not configured. "
                    "Set DJANGO_MATT_BILLING['PAYPAL']['WEBHOOK_ID'] in settings."
                )

            if not transmission_id or not transmission_time:
                raise BillingWebhookError(
                    "Missing required PayPal webhook headers: "
                    "PAYPAL-TRANSMISSION-ID and PAYPAL-TRANSMISSION-TIME are required."
                )

            if not transmission_sig:
                raise BillingWebhookError(
                    "Missing PayPal webhook signature (PAYPAL-TRANSMISSION-SIG header)."
                )

            # Compute CRC32 of the raw payload body
            crc = zlib.crc32(payload) & 0xFFFFFFFF

            # Build the expected signature message:
            # transmission_id|transmission_time|webhook_id|crc32
            expected_message = f"{transmission_id}|{transmission_time}|{webhook_id}|{crc}"

            # Compute HMAC-SHA256 using client_secret as key
            expected_sig = hmac.new(
                self.config.client_secret.encode("utf-8"),
                expected_message.encode("utf-8"),
                hashlib.sha256,
            ).digest()

            # PayPal sends the signature as base64-encoded
            try:
                received_sig = base64.b64decode(transmission_sig)
            except Exception:
                raise BillingWebhookError("Invalid base64 in PAYPAL-TRANSMISSION-SIG header.")

            if not hmac.compare_digest(expected_sig, received_sig):
                raise BillingWebhookError(
                    "PayPal webhook signature verification failed. "
                    "The payload may have been tampered with."
                )

            return WebhookEvent(
                id=data.get("id", ""),
                type=data.get("event_type", ""),
                provider=self.provider_name,
                data=data.get("resource", {}),
                created_at=self._parse_datetime(data.get("create_time")),
                raw_payload=payload,
            )
        except BillingWebhookError:
            raise
        except Exception as e:
            raise BillingWebhookError(f"Webhook verification failed: {e}")

    def normalize_webhook_type(self, provider_type: str) -> str:
        """Normalize PayPal webhook types to common format."""
        mapping = {
            "BILLING.SUBSCRIPTION.CREATED": "subscription.created",
            "BILLING.SUBSCRIPTION.UPDATED": "subscription.updated",
            "BILLING.SUBSCRIPTION.CANCELLED": "subscription.canceled",
            "BILLING.SUBSCRIPTION.SUSPENDED": "subscription.paused",
            "BILLING.SUBSCRIPTION.ACTIVATED": "subscription.resumed",
            "PAYMENT.SALE.COMPLETED": "invoice.paid",
            "PAYMENT.SALE.DENIED": "invoice.payment_failed",
            "CHECKOUT.ORDER.APPROVED": "checkout.completed",
        }
        return mapping.get(provider_type, provider_type.lower().replace(".", "_"))
