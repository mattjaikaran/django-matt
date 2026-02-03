"""
Billing API controllers.

Includes:
- Subscription management
- Checkout sessions
- Invoice retrieval
- Payment methods
- Billing portal
- Webhook handling
"""

from typing import Optional
from uuid import UUID
from django.conf import settings
import stripe

from django_matt.core import APIController, api_controller
from django_matt.auth import jwt_required
from django_matt.permissions import IsAuthenticated, AllowAny

from core.models import Organization, Membership, AuditLog
from billing.models import Subscription, Invoice, PaymentMethod, UsageRecord
from billing.schemas import (
    SubscriptionResponse, SubscriptionDetailResponse,
    SubscriptionUpdateRequest, SubscriptionCancelRequest,
    InvoiceResponse, InvoiceDetailResponse, InvoiceListResponse,
    PaymentMethodResponse, PaymentMethodCreateRequest, PaymentMethodSetDefaultRequest,
    CheckoutSessionRequest, CheckoutSessionResponse,
    BillingPortalRequest, BillingPortalResponse,
    BillingOverviewResponse, PlanResponse, PlansListResponse,
    UsageSummaryResponse, CouponApplyRequest, CouponApplyResponse,
)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@api_controller("/organizations/{org_slug}/billing", tags=["Billing"])
class BillingController(APIController):
    """Billing and subscription management endpoints."""

    async def get_org_and_check_billing_access(self, request, org_slug: str):
        """Helper to get organization and check billing permission."""
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return None, None, ({"error": "Organization not found"}, 404)

        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership:
            return None, None, ({"error": "Not a member of this organization"}, 403)

        if not membership.has_permission("billing"):
            return None, None, ({"error": "Billing permission required"}, 403)

        return org, membership, None

    # =========================================================================
    # Plans
    # =========================================================================

    @APIController.get("/plans", response=PlansListResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def list_plans(self, request, org_slug: str):
        """
        List available subscription plans.
        """
        plans = []
        for plan_id, plan_data in settings.BILLING_PRODUCTS.items():
            plans.append(PlanResponse(
                id=plan_id,
                name=plan_data["name"],
                price_monthly=0,  # Would come from Stripe
                price_yearly=0,
                limits=plan_data.get("limits", {}),
                features=plan_data.get("features", []),
                is_popular=plan_id == "pro",
            ))

        return PlansListResponse(plans=plans)

    # =========================================================================
    # Subscription
    # =========================================================================

    @APIController.get("/subscription", response=SubscriptionDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_subscription(self, request, org_slug: str):
        """
        Get current subscription details.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            subscription = await Subscription.objects.select_related("organization").aget(
                organization=org
            )
            return SubscriptionDetailResponse.model_validate(subscription)
        except Subscription.DoesNotExist:
            return {"error": "No active subscription"}, 404

    @APIController.patch("/subscription", response=SubscriptionDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def update_subscription(self, request, org_slug: str, data: SubscriptionUpdateRequest):
        """
        Update subscription (change plan).
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            subscription = await Subscription.objects.aget(organization=org)

            # Update in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    "id": subscription.stripe_subscription_id,
                    "price": data.plan_id,
                }],
                proration_behavior="create_prorations",
            )

            # Update local record
            subscription.stripe_price_id = data.plan_id
            if data.quantity:
                subscription.quantity = data.quantity
            await subscription.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="subscription.updated",
                data={"plan_id": data.plan_id},
            )

            return SubscriptionDetailResponse.model_validate(subscription)

        except Subscription.DoesNotExist:
            return {"error": "No active subscription"}, 404
        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    @APIController.post("/subscription/cancel", permissions=[IsAuthenticated])
    @jwt_required
    async def cancel_subscription(self, request, org_slug: str, data: SubscriptionCancelRequest):
        """
        Cancel subscription.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            subscription = await Subscription.objects.aget(organization=org)

            # Cancel in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=data.cancel_at_period_end,
            )

            # Update local record
            subscription.cancel_at_period_end = data.cancel_at_period_end
            subscription.cancellation_reason = data.reason
            await subscription.asave()

            # Create audit log
            await AuditLog.objects.acreate(
                user=request.user,
                organization=org,
                action="subscription.cancelled",
                data={"reason": data.reason, "cancel_at_period_end": data.cancel_at_period_end},
            )

            return {"message": "Subscription will be cancelled at period end" if data.cancel_at_period_end else "Subscription cancelled"}

        except Subscription.DoesNotExist:
            return {"error": "No active subscription"}, 404
        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    @APIController.post("/subscription/reactivate", permissions=[IsAuthenticated])
    @jwt_required
    async def reactivate_subscription(self, request, org_slug: str):
        """
        Reactivate a cancelled subscription (before period ends).
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            subscription = await Subscription.objects.aget(organization=org)

            if not subscription.cancel_at_period_end:
                return {"error": "Subscription is not scheduled for cancellation"}, 400

            # Reactivate in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
            )

            # Update local record
            subscription.cancel_at_period_end = False
            subscription.cancellation_reason = ""
            await subscription.asave()

            return {"message": "Subscription reactivated"}

        except Subscription.DoesNotExist:
            return {"error": "No subscription found"}, 404
        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    # =========================================================================
    # Checkout
    # =========================================================================

    @APIController.post("/checkout", response=CheckoutSessionResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def create_checkout_session(self, request, org_slug: str, data: CheckoutSessionRequest):
        """
        Create a Stripe Checkout session for new subscription.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            # Create or get Stripe customer
            if not org.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={
                        "organization_id": str(org.id),
                        "organization_slug": org.slug,
                    },
                )
                org.stripe_customer_id = customer.id
                await org.asave(update_fields=["stripe_customer_id"])
            else:
                customer = stripe.Customer.retrieve(org.stripe_customer_id)

            # Create checkout session
            session_params = {
                "customer": org.stripe_customer_id,
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": data.price_id,
                    "quantity": data.quantity,
                }],
                "mode": "subscription",
                "success_url": data.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                "cancel_url": data.cancel_url,
                "metadata": {
                    "organization_id": str(org.id),
                },
            }

            # Add trial if specified
            if data.trial_days:
                session_params["subscription_data"] = {
                    "trial_period_days": data.trial_days,
                }

            # Add coupon if specified
            if data.coupon_code:
                session_params["discounts"] = [{"coupon": data.coupon_code}]

            session = stripe.checkout.Session.create(**session_params)

            return CheckoutSessionResponse(
                session_id=session.id,
                checkout_url=session.url,
            )

        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    # =========================================================================
    # Billing Portal
    # =========================================================================

    @APIController.post("/portal", response=BillingPortalResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def create_billing_portal_session(self, request, org_slug: str, data: BillingPortalRequest):
        """
        Create a Stripe Billing Portal session.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        if not org.stripe_customer_id:
            return {"error": "No billing account found"}, 400

        try:
            session = stripe.billing_portal.Session.create(
                customer=org.stripe_customer_id,
                return_url=data.return_url,
            )

            return BillingPortalResponse(portal_url=session.url)

        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    # =========================================================================
    # Invoices
    # =========================================================================

    @APIController.get("/invoices", response=InvoiceListResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def list_invoices(self, request, org_slug: str, page: int = 1, page_size: int = 20):
        """
        List invoices for the organization.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        invoices = Invoice.objects.filter(organization=org)
        total = await invoices.acount()

        offset = (page - 1) * page_size
        invoices = invoices.order_by("-invoice_date")[offset:offset + page_size]

        items = []
        async for invoice in invoices:
            items.append(InvoiceResponse.model_validate(invoice))

        return InvoiceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @APIController.get("/invoices/{invoice_id}", response=InvoiceDetailResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_invoice(self, request, org_slug: str, invoice_id: UUID):
        """
        Get invoice details.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            invoice = await Invoice.objects.aget(id=invoice_id, organization=org)
            return InvoiceDetailResponse.model_validate(invoice)
        except Invoice.DoesNotExist:
            return {"error": "Invoice not found"}, 404

    # =========================================================================
    # Payment Methods
    # =========================================================================

    @APIController.get("/payment-methods", response=list[PaymentMethodResponse], permissions=[IsAuthenticated])
    @jwt_required
    async def list_payment_methods(self, request, org_slug: str):
        """
        List payment methods for the organization.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        methods = PaymentMethod.objects.filter(organization=org).order_by("-is_default", "-created_at")

        result = []
        async for method in methods:
            result.append(PaymentMethodResponse.model_validate(method))

        return result

    @APIController.post("/payment-methods", response=PaymentMethodResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def add_payment_method(self, request, org_slug: str, data: PaymentMethodCreateRequest):
        """
        Add a new payment method.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                data.payment_method_id,
                customer=org.stripe_customer_id,
            )

            # Get payment method details
            pm = stripe.PaymentMethod.retrieve(data.payment_method_id)

            # Check if this is the first payment method
            is_first = not await PaymentMethod.objects.filter(organization=org).aexists()

            # Save to database
            payment_method = await PaymentMethod.objects.acreate(
                organization=org,
                stripe_payment_method_id=pm.id,
                type=pm.type,
                card_brand=pm.card.brand if pm.card else "",
                card_last4=pm.card.last4 if pm.card else "",
                card_exp_month=pm.card.exp_month if pm.card else None,
                card_exp_year=pm.card.exp_year if pm.card else None,
                is_default=is_first,
            )

            # Set as default in Stripe if first
            if is_first:
                stripe.Customer.modify(
                    org.stripe_customer_id,
                    invoice_settings={"default_payment_method": pm.id},
                )

            return PaymentMethodResponse.model_validate(payment_method)

        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    @APIController.post("/payment-methods/default", permissions=[IsAuthenticated])
    @jwt_required
    async def set_default_payment_method(self, request, org_slug: str, data: PaymentMethodSetDefaultRequest):
        """
        Set default payment method.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            payment_method = await PaymentMethod.objects.aget(
                id=data.payment_method_id,
                organization=org,
            )

            # Set in Stripe
            stripe.Customer.modify(
                org.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method.stripe_payment_method_id},
            )

            # Update local records
            await PaymentMethod.objects.filter(organization=org).aupdate(is_default=False)
            payment_method.is_default = True
            await payment_method.asave()

            return {"message": "Default payment method updated"}

        except PaymentMethod.DoesNotExist:
            return {"error": "Payment method not found"}, 404
        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    @APIController.delete("/payment-methods/{method_id}", permissions=[IsAuthenticated])
    @jwt_required
    async def delete_payment_method(self, request, org_slug: str, method_id: UUID):
        """
        Delete a payment method.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        try:
            payment_method = await PaymentMethod.objects.aget(
                id=method_id,
                organization=org,
            )

            if payment_method.is_default:
                return {"error": "Cannot delete default payment method"}, 400

            # Detach from Stripe
            stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)

            # Delete local record
            await payment_method.adelete()

            return {"message": "Payment method deleted"}

        except PaymentMethod.DoesNotExist:
            return {"error": "Payment method not found"}, 404
        except stripe.error.StripeError as e:
            return {"error": str(e)}, 400

    # =========================================================================
    # Overview
    # =========================================================================

    @APIController.get("/overview", response=BillingOverviewResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_billing_overview(self, request, org_slug: str):
        """
        Get complete billing overview for the organization.
        """
        org, membership, error = await self.get_org_and_check_billing_access(request, org_slug)
        if error:
            return error

        # Get subscription
        subscription = None
        try:
            sub = await Subscription.objects.aget(organization=org)
            subscription = SubscriptionResponse.model_validate(sub)
        except Subscription.DoesNotExist:
            pass

        # Get default payment method
        default_method = None
        try:
            pm = await PaymentMethod.objects.aget(organization=org, is_default=True)
            default_method = PaymentMethodResponse.model_validate(pm)
        except PaymentMethod.DoesNotExist:
            pass

        # Get recent invoices
        recent_invoices = []
        async for invoice in Invoice.objects.filter(organization=org).order_by("-invoice_date")[:5]:
            recent_invoices.append(InvoiceResponse.model_validate(invoice))

        # Get usage summaries
        usage = []
        # TODO: Aggregate usage records

        return BillingOverviewResponse(
            subscription=subscription,
            upcoming_invoice=None,  # Would fetch from Stripe
            default_payment_method=default_method,
            usage=usage,
            recent_invoices=recent_invoices,
        )


# =========================================================================
# Webhooks (separate controller for security)
# =========================================================================

@api_controller("/webhooks", tags=["Webhooks"])
class WebhookController(APIController):
    """Webhook handlers for external services."""

    @APIController.post("/stripe", permissions=[AllowAny])
    async def stripe_webhook(self, request):
        """
        Handle Stripe webhook events.
        """
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return {"error": "Invalid payload"}, 400
        except stripe.error.SignatureVerificationError:
            return {"error": "Invalid signature"}, 400

        # Handle the event
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(data)
        elif event_type == "invoice.paid":
            await self._handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            await self._handle_payment_failed(data)

        return {"received": True}

    async def _handle_checkout_completed(self, data):
        """Handle successful checkout."""
        org_id = data.get("metadata", {}).get("organization_id")
        if not org_id:
            return

        try:
            org = await Organization.objects.aget(id=org_id)

            # Get subscription from Stripe
            stripe_sub = stripe.Subscription.retrieve(data["subscription"])

            # Create local subscription record
            await Subscription.objects.acreate(
                organization=org,
                stripe_subscription_id=stripe_sub.id,
                stripe_price_id=stripe_sub["items"]["data"][0]["price"]["id"],
                plan_name=stripe_sub["items"]["data"][0]["price"]["nickname"] or "Pro",
                status=stripe_sub.status,
                current_period_start=stripe_sub.current_period_start,
                current_period_end=stripe_sub.current_period_end,
                quantity=stripe_sub["items"]["data"][0]["quantity"],
            )

            # Update organization plan
            org.plan = "pro"  # Determine from price
            await org.asave()

        except Organization.DoesNotExist:
            pass

    async def _handle_subscription_updated(self, data):
        """Handle subscription updates."""
        try:
            sub = await Subscription.objects.aget(stripe_subscription_id=data["id"])
            sub.status = data["status"]
            sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
            await sub.asave()
        except Subscription.DoesNotExist:
            pass

    async def _handle_subscription_deleted(self, data):
        """Handle subscription cancellation."""
        try:
            sub = await Subscription.objects.select_related("organization").aget(
                stripe_subscription_id=data["id"]
            )
            sub.status = "canceled"
            await sub.asave()

            # Downgrade organization to free
            org = sub.organization
            org.plan = "free"
            org.plan_limits = settings.BILLING_PRODUCTS.get("free", {}).get("limits", {})
            await org.asave()
        except Subscription.DoesNotExist:
            pass

    async def _handle_invoice_paid(self, data):
        """Handle successful invoice payment."""
        try:
            org = await Organization.objects.aget(stripe_customer_id=data["customer"])

            await Invoice.objects.acreate(
                organization=org,
                stripe_invoice_id=data["id"],
                number=data.get("number", ""),
                status="paid",
                subtotal=data["subtotal"],
                tax=data.get("tax", 0),
                total=data["total"],
                amount_paid=data["amount_paid"],
                amount_due=data["amount_due"],
                invoice_date=data["created"],
                paid_at=data.get("status_transitions", {}).get("paid_at"),
                invoice_pdf_url=data.get("invoice_pdf", ""),
                hosted_invoice_url=data.get("hosted_invoice_url", ""),
            )
        except Organization.DoesNotExist:
            pass

    async def _handle_payment_failed(self, data):
        """Handle failed payment."""
        try:
            org = await Organization.objects.aget(stripe_customer_id=data["customer"])

            # Create notification
            from notifications.models import Notification, NotificationType

            owner = org.owner
            if owner:
                await Notification.objects.acreate(
                    user=owner,
                    organization=org,
                    type=NotificationType.BILLING_PAYMENT_FAILED,
                    title="Payment Failed",
                    message="Your payment could not be processed. Please update your payment method.",
                    action_url=f"/organizations/{org.slug}/settings/billing",
                )

        except Organization.DoesNotExist:
            pass
