"""Payment services for Stripe integration."""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from ecommerce.orders.models import Order
from ecommerce.payments.models import Payment, Refund


async def create_payment_intent(
    order: Order,
    payment_method: str = "card",
) -> dict[str, Any]:
    """Create a Stripe PaymentIntent for an order."""
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Convert to cents
    amount_cents = int(order.total * 100)

    # Create PaymentIntent
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=order.currency.lower(),
        metadata={
            "order_id": str(order.id),
            "order_number": order.order_number,
        },
        automatic_payment_methods={"enabled": True},
    )

    # Create Payment record
    payment = await Payment.objects.acreate(
        order=order,
        payment_method=payment_method,
        amount=order.total,
        currency=order.currency,
        stripe_payment_intent_id=intent.id,
    )

    return {
        "payment_id": payment.id,
        "client_secret": intent.client_secret,
        "amount": order.total,
        "currency": order.currency,
    }


async def create_checkout_session(
    order: Order,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session."""
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Build line items
    line_items = []
    for item in await order.items.alist():
        line_items.append({
            "price_data": {
                "currency": order.currency.lower(),
                "product_data": {
                    "name": item.product_name,
                    "description": item.variant_name or None,
                },
                "unit_amount": int(item.unit_price * 100),
            },
            "quantity": item.quantity,
        })

    # Add shipping as line item if applicable
    if order.shipping_amount > 0:
        line_items.append({
            "price_data": {
                "currency": order.currency.lower(),
                "product_data": {
                    "name": "Shipping",
                },
                "unit_amount": int(order.shipping_amount * 100),
            },
            "quantity": 1,
        })

    # Create checkout session
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url,
        metadata={
            "order_id": str(order.id),
            "order_number": order.order_number,
        },
        customer_email=order.email,
    )

    return {
        "session_id": session.id,
        "url": session.url,
    }


async def create_refund(
    payment: Payment,
    amount: Decimal,
    reason: str,
    notes: str = "",
    created_by=None,
) -> Refund:
    """Create a Stripe refund."""
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Create Stripe refund
    stripe_refund = stripe.Refund.create(
        payment_intent=payment.stripe_payment_intent_id,
        amount=int(amount * 100),
        reason=_map_refund_reason(reason),
    )

    # Create refund record
    refund = await Refund.objects.acreate(
        payment=payment,
        order=payment.order,
        amount=amount,
        reason=reason,
        notes=notes,
        stripe_refund_id=stripe_refund.id,
        status=Refund.Status.SUCCEEDED if stripe_refund.status == "succeeded" else Refund.Status.PENDING,
        created_by=created_by,
        refunded_at=timezone.now() if stripe_refund.status == "succeeded" else None,
    )

    # Update payment status if fully refunded
    total_refunded = await Refund.objects.filter(
        payment=payment, status=Refund.Status.SUCCEEDED
    ).aggregate(total=models.Sum("amount"))

    if (total_refunded.get("total") or Decimal("0.00")) >= payment.amount:
        payment.status = Payment.Status.REFUNDED
    else:
        payment.status = Payment.Status.PARTIALLY_REFUNDED
    await payment.asave()

    return refund


def _map_refund_reason(reason: str) -> str:
    """Map internal reason to Stripe reason."""
    mapping = {
        "requested_by_customer": "requested_by_customer",
        "duplicate": "duplicate",
        "fraudulent": "fraudulent",
    }
    return mapping.get(reason, "requested_by_customer")


async def process_stripe_webhook(event) -> None:
    """Process a Stripe webhook event."""
    event_type = event.type
    data = event.data.object

    if event_type == "payment_intent.succeeded":
        await _handle_payment_succeeded(data)
    elif event_type == "payment_intent.payment_failed":
        await _handle_payment_failed(data)
    elif event_type == "charge.refunded":
        await _handle_charge_refunded(data)
    elif event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)


async def _handle_payment_succeeded(data) -> None:
    """Handle successful payment."""
    payment_intent_id = data.id

    payment = await Payment.objects.filter(
        stripe_payment_intent_id=payment_intent_id
    ).select_related("order").afirst()

    if not payment:
        return

    # Update payment
    payment.status = Payment.Status.SUCCEEDED
    payment.paid_at = timezone.now()

    # Store card details if available
    if data.charges and data.charges.data:
        charge = data.charges.data[0]
        payment.stripe_charge_id = charge.id
        if charge.payment_method_details and charge.payment_method_details.card:
            card = charge.payment_method_details.card
            payment.card_brand = card.brand
            payment.card_last4 = card.last4
            payment.card_exp_month = card.exp_month
            payment.card_exp_year = card.exp_year

    await payment.asave()

    # Update order status
    order = payment.order
    order.status = Order.Status.CONFIRMED
    await order.asave()

    # Commit inventory
    for item in await order.items.select_related("product", "variant").alist():
        from ecommerce.catalog.models import Inventory
        if item.variant:
            inv = await Inventory.objects.filter(variant=item.variant).afirst()
        else:
            inv = await Inventory.objects.filter(
                product=item.product, variant__isnull=True
            ).afirst()
        if inv:
            inv.commit(item.quantity)

    # Send confirmation email
    from ecommerce.orders.tasks import send_order_confirmation_email
    send_order_confirmation_email.delay(str(order.id))


async def _handle_payment_failed(data) -> None:
    """Handle failed payment."""
    payment_intent_id = data.id

    payment = await Payment.objects.filter(
        stripe_payment_intent_id=payment_intent_id
    ).afirst()

    if not payment:
        return

    # Update payment
    payment.status = Payment.Status.FAILED
    if data.last_payment_error:
        payment.error_code = data.last_payment_error.code or ""
        payment.error_message = data.last_payment_error.message or ""
    await payment.asave()

    # Release reserved inventory
    order = await Order.objects.filter(id=payment.order_id).afirst()
    if order:
        for item in await order.items.select_related("product", "variant").alist():
            from ecommerce.catalog.models import Inventory
            if item.variant:
                inv = await Inventory.objects.filter(variant=item.variant).afirst()
            else:
                inv = await Inventory.objects.filter(
                    product=item.product, variant__isnull=True
                ).afirst()
            if inv:
                inv.release(item.quantity)


async def _handle_charge_refunded(data) -> None:
    """Handle refund webhook."""
    # Refunds are typically created via API, so just log
    pass


async def _handle_checkout_completed(data) -> None:
    """Handle checkout session completion."""
    order_id = data.metadata.get("order_id")
    if not order_id:
        return

    order = await Order.objects.filter(id=order_id).afirst()
    if not order:
        return

    # Create payment record from checkout session
    await Payment.objects.acreate(
        order=order,
        payment_method="card",
        amount=Decimal(data.amount_total) / 100,
        currency=data.currency.upper(),
        status=Payment.Status.SUCCEEDED,
        paid_at=timezone.now(),
    )

    # Update order
    order.status = Order.Status.CONFIRMED
    await order.asave()

