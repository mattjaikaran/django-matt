# file-length-max: 1100
"""
Stripe billing provider.

Requires: uv add stripe

Documentation: https://docs.stripe.com/api
"""

from datetime import UTC, datetime
from typing import Any

from django_matt.billing.config import StripeConfig
from django_matt.billing.providers.base import (
    AccountLinkData,
    BillingAPIError,
    BillingProvider,
    BillingWebhookError,
    CheckoutSessionData,
    ConnectAccountType,
    ConnectedAccountData,
    CustomerData,
    InvoiceData,
    OAuthLinkData,
    PriceData,
    PriceInterval,
    ProductData,
    SubscriptionData,
    SubscriptionStatus,
    TransferData,
    WebhookEvent,
)


class StripeProvider(BillingProvider[StripeConfig]):
    """Stripe billing provider implementation."""

    provider_name = "stripe"

    def __init__(self, config: StripeConfig):
        super().__init__(config)
        self._stripe = None

    @property
    def stripe(self):
        """Lazy-load stripe module."""
        if self._stripe is None:
            try:
                import stripe

                stripe.api_key = self.config.secret_key
                stripe.api_version = self.config.api_version
                self._stripe = stripe
            except ImportError:
                raise BillingAPIError(
                    "stripe package is not installed. Run: uv add stripe",
                    provider=self.provider_name,
                )
        return self._stripe

    def _handle_stripe_error(self, e: Exception) -> None:
        """Convert Stripe errors to BillingAPIError."""
        import stripe

        if isinstance(e, stripe.error.CardError):
            raise BillingAPIError(
                str(e.user_message or e),
                provider=self.provider_name,
                status_code=e.http_status,
                details={"code": e.code, "param": e.param},
            )
        if isinstance(e, stripe.error.InvalidRequestError):
            raise BillingAPIError(
                str(e),
                provider=self.provider_name,
                status_code=e.http_status,
                details={"param": e.param},
            )
        if isinstance(e, stripe.error.AuthenticationError):
            raise BillingAPIError(
                "Invalid Stripe API key",
                provider=self.provider_name,
                status_code=401,
            )
        if isinstance(e, stripe.error.StripeError):
            raise BillingAPIError(
                str(e),
                provider=self.provider_name,
                status_code=getattr(e, "http_status", None),
            )
        raise e

    def _timestamp_to_datetime(self, ts: int | None) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, tz=UTC)

    def _parse_customer(self, customer: Any) -> CustomerData:
        """Parse Stripe customer to CustomerData."""
        return self._add_provider_tag(
            CustomerData(
                id=customer.id,
                email=customer.email or "",
                name=customer.name,
                phone=customer.phone,
                metadata=dict(customer.metadata or {}),
                created_at=self._timestamp_to_datetime(customer.created),
                raw_data=customer.to_dict() if hasattr(customer, "to_dict") else {},
            )
        )

    def _parse_product(self, product: Any) -> ProductData:
        """Parse Stripe product to ProductData."""
        return self._add_provider_tag(
            ProductData(
                id=product.id,
                name=product.name,
                description=product.description,
                active=product.active,
                metadata=dict(product.metadata or {}),
                created_at=self._timestamp_to_datetime(product.created),
                raw_data=product.to_dict() if hasattr(product, "to_dict") else {},
            )
        )

    def _parse_price(self, price: Any) -> PriceData:
        """Parse Stripe price to PriceData."""
        interval = PriceInterval.ONE_TIME
        interval_count = 1

        if price.recurring:
            interval_map = {
                "day": PriceInterval.DAY,
                "week": PriceInterval.WEEK,
                "month": PriceInterval.MONTH,
                "year": PriceInterval.YEAR,
            }
            interval = interval_map.get(price.recurring.interval, PriceInterval.MONTH)
            interval_count = price.recurring.interval_count or 1

        return self._add_provider_tag(
            PriceData(
                id=price.id,
                product_id=price.product if isinstance(price.product, str) else price.product.id,
                currency=price.currency,
                unit_amount=price.unit_amount or 0,
                interval=interval,
                interval_count=interval_count,
                trial_period_days=price.recurring.trial_period_days if price.recurring else None,
                active=price.active,
                metadata=dict(price.metadata or {}),
                raw_data=price.to_dict() if hasattr(price, "to_dict") else {},
            )
        )

    def _parse_subscription(self, sub: Any) -> SubscriptionData:
        """Parse Stripe subscription to SubscriptionData."""
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.INCOMPLETE,
            "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
            "past_due": SubscriptionStatus.PAST_DUE,
            "paused": SubscriptionStatus.PAUSED,
            "trialing": SubscriptionStatus.TRIALING,
            "unpaid": SubscriptionStatus.UNPAID,
        }

        # Get price and product from first item
        price_id = None
        product_id = None
        quantity = 1
        if sub.items and sub.items.data:
            first_item = sub.items.data[0]
            price_id = first_item.price.id
            product_id = (
                first_item.price.product
                if isinstance(first_item.price.product, str)
                else first_item.price.product.id
            )
            quantity = first_item.quantity or 1

        return self._add_provider_tag(
            SubscriptionData(
                id=sub.id,
                customer_id=sub.customer if isinstance(sub.customer, str) else sub.customer.id,
                status=status_map.get(sub.status, SubscriptionStatus.ACTIVE),
                price_id=price_id,
                product_id=product_id,
                quantity=quantity,
                current_period_start=self._timestamp_to_datetime(sub.current_period_start),
                current_period_end=self._timestamp_to_datetime(sub.current_period_end),
                cancel_at_period_end=sub.cancel_at_period_end,
                canceled_at=self._timestamp_to_datetime(sub.canceled_at),
                trial_start=self._timestamp_to_datetime(sub.trial_start),
                trial_end=self._timestamp_to_datetime(sub.trial_end),
                metadata=dict(sub.metadata or {}),
                created_at=self._timestamp_to_datetime(sub.created),
                raw_data=sub.to_dict() if hasattr(sub, "to_dict") else {},
            )
        )

    def _parse_checkout_session(self, session: Any) -> CheckoutSessionData:
        """Parse Stripe checkout session to CheckoutSessionData."""
        return self._add_provider_tag(
            CheckoutSessionData(
                id=session.id,
                url=session.url or "",
                customer_id=session.customer
                if isinstance(session.customer, str)
                else (session.customer.id if session.customer else None),
                subscription_id=session.subscription
                if isinstance(session.subscription, str)
                else (session.subscription.id if session.subscription else None),
                status=session.status or "open",
                mode=session.mode or "subscription",
                success_url=session.success_url or "",
                cancel_url=session.cancel_url or "",
                metadata=dict(session.metadata or {}),
                expires_at=self._timestamp_to_datetime(session.expires_at),
                raw_data=session.to_dict() if hasattr(session, "to_dict") else {},
            )
        )

    def _parse_invoice(self, invoice: Any) -> InvoiceData:
        """Parse Stripe invoice to InvoiceData."""
        return self._add_provider_tag(
            InvoiceData(
                id=invoice.id,
                customer_id=invoice.customer
                if isinstance(invoice.customer, str)
                else invoice.customer.id,
                subscription_id=invoice.subscription
                if isinstance(invoice.subscription, str)
                else (invoice.subscription.id if invoice.subscription else None),
                status=invoice.status or "draft",
                currency=invoice.currency,
                amount_due=invoice.amount_due or 0,
                amount_paid=invoice.amount_paid or 0,
                amount_remaining=invoice.amount_remaining or 0,
                invoice_pdf=invoice.invoice_pdf,
                hosted_invoice_url=invoice.hosted_invoice_url,
                due_date=self._timestamp_to_datetime(invoice.due_date),
                paid_at=self._timestamp_to_datetime(
                    invoice.status_transitions.paid_at if invoice.status_transitions else None
                ),
                created_at=self._timestamp_to_datetime(invoice.created),
                raw_data=invoice.to_dict() if hasattr(invoice, "to_dict") else {},
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
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {},
            )
            return self._parse_customer(customer)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_customer(self, customer_id: str) -> CustomerData | None:
        try:
            customer = self.stripe.Customer.retrieve(customer_id)
            if customer.deleted:
                return None
            return self._parse_customer(customer)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def update_customer(
        self,
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        try:
            params: dict[str, Any] = {}
            if email is not None:
                params["email"] = email
            if name is not None:
                params["name"] = name
            if metadata is not None:
                params["metadata"] = metadata

            customer = self.stripe.Customer.modify(customer_id, **params)
            return self._parse_customer(customer)
        except Exception as e:
            self._handle_stripe_error(e)

    async def delete_customer(self, customer_id: str) -> bool:
        try:
            result = self.stripe.Customer.delete(customer_id)
            return result.deleted
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_customers(
        self,
        email: str | None = None,
        limit: int = 10,
        starting_after: str | None = None,
    ) -> list[CustomerData]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if email:
                params["email"] = email
            if starting_after:
                params["starting_after"] = starting_after

            customers = self.stripe.Customer.list(**params)
            return [self._parse_customer(c) for c in customers.data]
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Product Management
    # -------------------------------------------------------------------------

    async def create_product(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        try:
            product = self.stripe.Product.create(
                name=name,
                description=description,
                metadata=metadata or {},
            )
            return self._parse_product(product)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_product(self, product_id: str) -> ProductData | None:
        try:
            product = self.stripe.Product.retrieve(product_id)
            return self._parse_product(product)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def update_product(
        self,
        product_id: str,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        try:
            params: dict[str, Any] = {}
            if name is not None:
                params["name"] = name
            if description is not None:
                params["description"] = description
            if active is not None:
                params["active"] = active
            if metadata is not None:
                params["metadata"] = metadata

            product = self.stripe.Product.modify(product_id, **params)
            return self._parse_product(product)
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_products(
        self,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[ProductData]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if active is not None:
                params["active"] = active

            products = self.stripe.Product.list(**params)
            return [self._parse_product(p) for p in products.data]
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Price Management
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
        try:
            params: dict[str, Any] = {
                "product": product_id,
                "unit_amount": unit_amount,
                "currency": currency,
                "metadata": metadata or {},
            }

            if interval != PriceInterval.ONE_TIME:
                interval_map = {
                    PriceInterval.DAY: "day",
                    PriceInterval.WEEK: "week",
                    PriceInterval.MONTH: "month",
                    PriceInterval.YEAR: "year",
                }
                recurring: dict[str, Any] = {
                    "interval": interval_map[interval],
                    "interval_count": interval_count,
                }
                if trial_period_days:
                    recurring["trial_period_days"] = trial_period_days
                params["recurring"] = recurring

            price = self.stripe.Price.create(**params)
            return self._parse_price(price)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_price(self, price_id: str) -> PriceData | None:
        try:
            price = self.stripe.Price.retrieve(price_id)
            return self._parse_price(price)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_prices(
        self,
        product_id: str | None = None,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[PriceData]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if product_id:
                params["product"] = product_id
            if active is not None:
                params["active"] = active

            prices = self.stripe.Price.list(**params)
            return [self._parse_price(p) for p in prices.data]
        except Exception as e:
            self._handle_stripe_error(e)

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
        try:
            params: dict[str, Any] = {
                "customer": customer_id,
                "items": [{"price": price_id, "quantity": quantity}],
                "metadata": metadata or {},
            }
            if trial_period_days:
                params["trial_period_days"] = trial_period_days

            subscription = self.stripe.Subscription.create(**params)
            return self._parse_subscription(subscription)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_subscription(self, subscription_id: str) -> SubscriptionData | None:
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return self._parse_subscription(subscription)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: str | None = None,
        quantity: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionData:
        try:
            params: dict[str, Any] = {}

            if price_id is not None or quantity is not None:
                # Get current subscription to find item ID
                sub = self.stripe.Subscription.retrieve(subscription_id)
                if sub.items and sub.items.data:
                    item_id = sub.items.data[0].id
                    item_params: dict[str, Any] = {"id": item_id}
                    if price_id:
                        item_params["price"] = price_id
                    if quantity:
                        item_params["quantity"] = quantity
                    params["items"] = [item_params]

            if metadata is not None:
                params["metadata"] = metadata

            subscription = self.stripe.Subscription.modify(subscription_id, **params)
            return self._parse_subscription(subscription)
        except Exception as e:
            self._handle_stripe_error(e)

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True,
    ) -> SubscriptionData:
        try:
            if cancel_at_period_end:
                subscription = self.stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                subscription = self.stripe.Subscription.cancel(subscription_id)
            return self._parse_subscription(subscription)
        except Exception as e:
            self._handle_stripe_error(e)

    async def resume_subscription(self, subscription_id: str) -> SubscriptionData:
        try:
            subscription = self.stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False,
            )
            return self._parse_subscription(subscription)
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_subscriptions(
        self,
        customer_id: str | None = None,
        status: SubscriptionStatus | None = None,
        limit: int = 10,
    ) -> list[SubscriptionData]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if customer_id:
                params["customer"] = customer_id
            if status:
                params["status"] = status.value

            subscriptions = self.stripe.Subscription.list(**params)
            return [self._parse_subscription(s) for s in subscriptions.data]
        except Exception as e:
            self._handle_stripe_error(e)

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
        try:
            params: dict[str, Any] = {
                "line_items": [{"price": price_id, "quantity": quantity}],
                "mode": mode,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
            }

            if customer_id:
                params["customer"] = customer_id
            elif customer_email:
                params["customer_email"] = customer_email

            if trial_period_days and mode == "subscription":
                params["subscription_data"] = {"trial_period_days": trial_period_days}

            session = self.stripe.checkout.Session.create(**params)
            return self._parse_checkout_session(session)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_checkout_session(self, session_id: str) -> CheckoutSessionData | None:
        try:
            session = self.stripe.checkout.Session.retrieve(session_id)
            return self._parse_checkout_session(session)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        try:
            session = self.stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return session.url
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Invoice Management
    # -------------------------------------------------------------------------

    async def get_invoice(self, invoice_id: str) -> InvoiceData | None:
        try:
            invoice = self.stripe.Invoice.retrieve(invoice_id)
            return self._parse_invoice(invoice)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_invoices(
        self,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[InvoiceData]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if customer_id:
                params["customer"] = customer_id
            if subscription_id:
                params["subscription"] = subscription_id
            if status:
                params["status"] = status

            invoices = self.stripe.Invoice.list(**params)
            return [self._parse_invoice(i) for i in invoices.data]
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_upcoming_invoice(self, customer_id: str) -> InvoiceData | None:
        try:
            invoice = self.stripe.Invoice.upcoming(customer=customer_id)
            return self._parse_invoice(invoice)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Webhook Handling
    # -------------------------------------------------------------------------

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        try:
            event = self.stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.webhook_secret,
            )

            return WebhookEvent(
                id=event.id,
                type=event.type,
                provider=self.provider_name,
                data=event.data.object.to_dict()
                if hasattr(event.data.object, "to_dict")
                else dict(event.data.object),
                created_at=self._timestamp_to_datetime(event.created),
                raw_payload=payload,
            )
        except self.stripe.error.SignatureVerificationError as e:
            raise BillingWebhookError(f"Invalid webhook signature: {e}")
        except Exception as e:
            raise BillingWebhookError(f"Webhook verification failed: {e}")

    def normalize_webhook_type(self, provider_type: str) -> str:
        """Normalize Stripe webhook types to common format."""
        # Stripe uses dots: customer.subscription.created -> subscription.created
        mapping = {
            "customer.subscription.created": "subscription.created",
            "customer.subscription.updated": "subscription.updated",
            "customer.subscription.deleted": "subscription.canceled",
            "customer.subscription.paused": "subscription.paused",
            "customer.subscription.resumed": "subscription.resumed",
            "invoice.paid": "invoice.paid",
            "invoice.payment_failed": "invoice.payment_failed",
            "checkout.session.completed": "checkout.completed",
            "customer.created": "customer.created",
            "customer.updated": "customer.updated",
            "customer.deleted": "customer.deleted",
            "account.updated": "connect.account.updated",
            "account.application.deauthorized": "connect.account.deauthorized",
            "transfer.created": "connect.transfer.created",
            "transfer.updated": "connect.transfer.updated",
        }
        return mapping.get(provider_type, provider_type)

    # -------------------------------------------------------------------------
    # Stripe Connect — Account Management
    # -------------------------------------------------------------------------

    def _parse_connected_account(self, account: Any) -> ConnectedAccountData:
        """Parse Stripe account to ConnectedAccountData."""
        type_map = {
            "standard": ConnectAccountType.STANDARD,
            "express": ConnectAccountType.EXPRESS,
            "custom": ConnectAccountType.CUSTOM,
        }
        return ConnectedAccountData(
            id=account.id,
            type=type_map.get(account.type, ConnectAccountType.STANDARD),
            email=account.email or "",
            business_name=(
                account.business_profile.name
                if account.business_profile and account.business_profile.name
                else ""
            ),
            charges_enabled=account.charges_enabled,
            payouts_enabled=account.payouts_enabled,
            details_submitted=account.details_submitted,
            country=account.country or "",
            metadata=dict(account.metadata or {}),
            created_at=self._timestamp_to_datetime(account.created),
            raw_data=account.to_dict() if hasattr(account, "to_dict") else {},
        )

    def _parse_transfer(self, transfer: Any) -> TransferData:
        """Parse Stripe transfer to TransferData."""
        return TransferData(
            id=transfer.id,
            amount=transfer.amount,
            currency=transfer.currency,
            destination=transfer.destination
            if isinstance(transfer.destination, str)
            else transfer.destination.id,
            source_transaction=transfer.source_transaction or "",
            description=transfer.description or "",
            metadata=dict(transfer.metadata or {}),
            created_at=self._timestamp_to_datetime(transfer.created),
            raw_data=transfer.to_dict() if hasattr(transfer, "to_dict") else {},
        )

    async def create_connected_account(
        self,
        type: str = "standard",
        email: str | None = None,
        country: str | None = None,
        business_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConnectedAccountData:
        """Create a Stripe Connect account."""
        try:
            params: dict[str, Any] = {
                "type": type,
                "metadata": metadata or {},
            }
            if email:
                params["email"] = email
            if country:
                params["country"] = country
            if business_type:
                params["business_type"] = business_type

            # Express/Custom accounts need capabilities
            if type in ("express", "custom"):
                params["capabilities"] = {
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                }

            account = self.stripe.Account.create(**params)
            return self._parse_connected_account(account)
        except Exception as e:
            self._handle_stripe_error(e)

    async def get_connected_account(self, account_id: str) -> ConnectedAccountData | None:
        """Get a connected account by ID."""
        try:
            account = self.stripe.Account.retrieve(account_id)
            return self._parse_connected_account(account)
        except self.stripe.error.InvalidRequestError:
            return None
        except Exception as e:
            self._handle_stripe_error(e)

    async def update_connected_account(
        self,
        account_id: str,
        **params: Any,
    ) -> ConnectedAccountData:
        """Update a connected account."""
        try:
            account = self.stripe.Account.modify(account_id, **params)
            return self._parse_connected_account(account)
        except Exception as e:
            self._handle_stripe_error(e)

    async def delete_connected_account(self, account_id: str) -> bool:
        """Delete a connected account."""
        try:
            result = self.stripe.Account.delete(account_id)
            return result.deleted
        except Exception as e:
            self._handle_stripe_error(e)

    async def list_connected_accounts(
        self,
        limit: int = 10,
        starting_after: str | None = None,
    ) -> list[ConnectedAccountData]:
        """List connected accounts."""
        try:
            params: dict[str, Any] = {"limit": limit}
            if starting_after:
                params["starting_after"] = starting_after

            accounts = self.stripe.Account.list(**params)
            return [self._parse_connected_account(a) for a in accounts.data]
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Stripe Connect — Onboarding
    # -------------------------------------------------------------------------

    async def create_account_link(
        self,
        account_id: str,
        refresh_url: str,
        return_url: str,
    ) -> AccountLinkData:
        """Create an account link for Express onboarding."""
        try:
            link = self.stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )
            return AccountLinkData(
                url=link.url,
                expires_at=self._timestamp_to_datetime(link.expires_at),
            )
        except Exception as e:
            self._handle_stripe_error(e)

    def get_oauth_authorize_url(
        self,
        redirect_uri: str,
        state: str = "",
    ) -> OAuthLinkData:
        """
        Get OAuth authorize URL for Standard account onboarding.

        Uses Stripe's OAuth flow for Standard connected accounts.
        """
        import secrets
        from urllib.parse import urlencode

        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            "response_type": "code",
            "client_id": self.config.connect_client_id,
            "scope": "read_write",
            "redirect_uri": redirect_uri,
            "state": state,
        }

        url = f"https://connect.stripe.com/oauth/authorize?{urlencode(params)}"
        return OAuthLinkData(url=url, state=state)

    async def complete_oauth_connect(self, authorization_code: str) -> ConnectedAccountData:
        """Complete Standard OAuth flow with authorization code."""
        try:
            response = self.stripe.OAuth.token(
                grant_type="authorization_code",
                code=authorization_code,
            )
            account_id = response.stripe_user_id
            return await self.get_connected_account(account_id)
        except Exception as e:
            self._handle_stripe_error(e)

    async def deauthorize_connected_account(self, account_id: str) -> bool:
        """Deauthorize a Standard connected account."""
        try:
            self.stripe.OAuth.deauthorize(
                client_id=self.config.connect_client_id,
                stripe_user_id=account_id,
            )
            return True
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Stripe Connect — Payments & Transfers
    # -------------------------------------------------------------------------

    async def create_payment_intent_with_fee(
        self,
        amount: int,
        connected_account_id: str,
        application_fee_amount: int | None = None,
        currency: str = "usd",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a PaymentIntent with an application fee (destination charge).

        The payment goes directly to the connected account with a platform fee.
        """
        try:
            params: dict[str, Any] = {
                "amount": amount,
                "currency": currency,
                "metadata": metadata or {},
                "transfer_data": {
                    "destination": connected_account_id,
                },
            }

            if application_fee_amount is not None:
                params["application_fee_amount"] = application_fee_amount
            elif self.config.connect_application_fee_percent > 0:
                params["application_fee_amount"] = int(
                    amount * self.config.connect_application_fee_percent / 100
                )

            intent = self.stripe.PaymentIntent.create(**params)
            return intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
        except Exception as e:
            self._handle_stripe_error(e)

    async def create_transfer(
        self,
        amount: int,
        destination: str,
        currency: str = "usd",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TransferData:
        """Create a transfer to a connected account."""
        try:
            params: dict[str, Any] = {
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "metadata": metadata or {},
            }
            if description:
                params["description"] = description

            transfer = self.stripe.Transfer.create(**params)
            return self._parse_transfer(transfer)
        except Exception as e:
            self._handle_stripe_error(e)

    async def reverse_transfer(
        self,
        transfer_id: str,
        amount: int | None = None,
    ) -> dict[str, Any]:
        """Reverse a transfer (full or partial)."""
        try:
            params: dict[str, Any] = {}
            if amount is not None:
                params["amount"] = amount

            reversal = self.stripe.Transfer.create_reversal(transfer_id, **params)
            return reversal.to_dict() if hasattr(reversal, "to_dict") else dict(reversal)
        except Exception as e:
            self._handle_stripe_error(e)

    # -------------------------------------------------------------------------
    # Stripe Connect — Webhook Verification
    # -------------------------------------------------------------------------

    async def verify_connect_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """Verify and parse a Connect webhook event."""
        try:
            event = self.stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.connect_webhook_secret,
            )
            return WebhookEvent(
                id=event.id,
                type=event.type,
                provider=self.provider_name,
                data=event.data.object.to_dict()
                if hasattr(event.data.object, "to_dict")
                else dict(event.data.object),
                created_at=self._timestamp_to_datetime(event.created),
                raw_payload=payload,
            )
        except self.stripe.error.SignatureVerificationError as e:
            raise BillingWebhookError(f"Invalid Connect webhook signature: {e}")
        except Exception as e:
            raise BillingWebhookError(f"Connect webhook verification failed: {e}")
