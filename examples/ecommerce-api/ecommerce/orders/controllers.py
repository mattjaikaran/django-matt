"""API controllers for orders app."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import transaction

from django_matt.core import APIController
from django_matt.auth import jwt_required
from django_matt.permissions import IsAuthenticated
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from ecommerce.cart.models import Cart
from ecommerce.catalog.models import Inventory
from ecommerce.orders.models import Coupon, Order, OrderItem, OrderStatusHistory
from ecommerce.orders.schemas import (
    CheckoutRequest,
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    CouponValidationRequest,
    CouponValidationResponse,
    OrderCreateResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderListResponse,
    OrderStatusHistoryResponse,
    OrderStatusUpdate,
    ShippingRateResponse,
    ShippingRatesResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
)
from ecommerce.payments.services import create_payment_intent


# =============================================================================
# Order Controller
# =============================================================================


class OrderController(APIController):
    """Order management controller."""

    prefix = "/orders"
    tags = ["Orders"]
    permission_classes = [IsAuthenticated]

    @staticmethod
    @jwt_required
    async def checkout(request, data: CheckoutRequest) -> OrderCreateResponse:
        """Create order from cart."""
        # Get user's cart
        cart = await Cart.objects.filter(user=request.user).prefetch_related(
            "items__product", "items__variant"
        ).afirst()

        if not cart or cart.item_count == 0:
            raise ValidationAPIError("Cart is empty")

        # Prepare addresses
        billing_address = data.billing_address.model_dump()
        shipping_address = (
            data.shipping_address.model_dump()
            if data.shipping_address and not data.same_as_billing
            else billing_address
        )

        # Verify and reserve inventory
        for item in await cart.items.select_related("product", "variant").alist():
            if item.variant:
                inv = await Inventory.objects.filter(variant=item.variant).afirst()
            else:
                inv = await Inventory.objects.filter(
                    product=item.product, variant__isnull=True
                ).afirst()

            if not inv or not inv.reserve(item.quantity):
                raise ValidationAPIError(
                    f"Insufficient inventory for {item.product.name}"
                )

        # Apply coupon if provided
        coupon = None
        coupon_code = ""
        if data.coupon_code:
            coupon = await Coupon.objects.filter(code__iexact=data.coupon_code).afirst()
            if coupon and coupon.is_valid:
                cart.coupon = coupon
                coupon_code = coupon.code

        # Create order
        order = await Order.objects.acreate(
            user=request.user,
            email=data.email,
            phone=data.phone,
            billing_address=billing_address,
            shipping_address=shipping_address,
            subtotal=cart.subtotal,
            discount_amount=cart.discount_amount,
            tax_amount=cart.tax_amount,
            shipping_amount=cart.shipping_amount,
            total=cart.total,
            coupon=coupon,
            coupon_code=coupon_code,
            customer_notes=data.customer_notes,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        # Create order items
        for item in await cart.items.select_related("product", "variant").alist():
            await OrderItem.objects.acreate(
                order=order,
                product=item.product,
                variant=item.variant,
                product_name=item.product.name,
                variant_name=item.variant.name if item.variant else "",
                sku=item.variant.sku if item.variant else item.product.sku,
                unit_price=item.unit_price,
                quantity=item.quantity,
                total=item.line_total,
                product_snapshot={
                    "id": str(item.product.id),
                    "name": item.product.name,
                    "sku": item.product.sku,
                    "price": str(item.product.price),
                },
            )

        # Update coupon usage
        if coupon:
            coupon.times_used += 1
            await coupon.asave()

        # Create initial status history
        await OrderStatusHistory.objects.acreate(
            order=order,
            status=Order.Status.PENDING,
            notes="Order created",
        )

        # Clear cart
        await cart.items.all().adelete()
        cart.coupon = None
        await cart.asave()

        # Create payment intent
        payment_intent = await create_payment_intent(order)

        # Trigger order confirmation email (async)
        from ecommerce.orders.tasks import send_order_confirmation_email
        send_order_confirmation_email.delay(str(order.id))

        return OrderCreateResponse(
            order_id=order.id,
            order_number=order.order_number,
            total=order.total,
            payment_intent_client_secret=payment_intent.get("client_secret"),
        )

    @staticmethod
    @jwt_required
    async def list_orders(
        request,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List user's orders."""
        queryset = Order.objects.filter(user=request.user)

        if status:
            queryset = queryset.filter(status=status)

        total = await queryset.acount()
        pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size

        orders = queryset.order_by("-created_at")[offset : offset + page_size]

        items = []
        async for order in orders:
            item_count = await order.items.acount()
            items.append(
                OrderListResponse(
                    id=order.id,
                    order_number=order.order_number,
                    status=order.status,
                    item_count=item_count,
                    total=order.total,
                    created_at=order.created_at,
                )
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
        }

    @staticmethod
    @jwt_required
    async def get_order(request, order_id: UUID) -> OrderDetailResponse:
        """Get order details."""
        order = await Order.objects.filter(
            id=order_id, user=request.user
        ).prefetch_related("items").afirst()

        if not order:
            raise NotFoundAPIError("Order not found")

        items = [
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                variant_name=item.variant_name,
                sku=item.sku,
                unit_price=item.unit_price,
                quantity=item.quantity,
                discount_amount=item.discount_amount,
                total=item.total,
                line_total=item.line_total,
            )
            async for item in order.items.all()
        ]

        return OrderDetailResponse(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            billing_address=order.billing_address,
            shipping_address=order.shipping_address,
            email=order.email,
            phone=order.phone,
            items=items,
            subtotal=order.subtotal,
            discount_amount=order.discount_amount,
            tax_amount=order.tax_amount,
            shipping_amount=order.shipping_amount,
            total=order.total,
            coupon_code=order.coupon_code,
            shipping_method=order.shipping_method,
            tracking_number=order.tracking_number,
            shipped_at=order.shipped_at,
            delivered_at=order.delivered_at,
            customer_notes=order.customer_notes,
            currency=order.currency,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    @staticmethod
    @jwt_required
    async def get_order_history(request, order_id: UUID) -> list[OrderStatusHistoryResponse]:
        """Get order status history."""
        order = await Order.objects.filter(id=order_id, user=request.user).afirst()
        if not order:
            raise NotFoundAPIError("Order not found")

        history = OrderStatusHistory.objects.filter(order=order).select_related(
            "changed_by"
        ).order_by("-created_at")

        return [
            OrderStatusHistoryResponse(
                id=h.id,
                status=h.status,
                notes=h.notes,
                changed_by_email=h.changed_by.email if h.changed_by else None,
                created_at=h.created_at,
            )
            async for h in history
        ]

    @staticmethod
    @jwt_required
    async def cancel_order(request, order_id: UUID) -> OrderDetailResponse:
        """Cancel an order (only if pending)."""
        order = await Order.objects.filter(id=order_id, user=request.user).afirst()
        if not order:
            raise NotFoundAPIError("Order not found")

        if order.status not in [Order.Status.PENDING, Order.Status.CONFIRMED]:
            raise ValidationAPIError("Cannot cancel order in current status")

        # Release reserved inventory
        for item in await order.items.select_related("product", "variant").alist():
            if item.variant:
                inv = await Inventory.objects.filter(variant=item.variant).afirst()
            else:
                inv = await Inventory.objects.filter(
                    product=item.product, variant__isnull=True
                ).afirst()
            if inv:
                inv.release(item.quantity)

        order.cancel()

        # Record status change
        await OrderStatusHistory.objects.acreate(
            order=order,
            status=Order.Status.CANCELLED,
            notes="Cancelled by customer",
            changed_by=request.user,
        )

        return await OrderController.get_order(request, order_id)

    @staticmethod
    @jwt_required
    async def update_order_status(
        request, order_id: UUID, data: OrderStatusUpdate
    ) -> OrderDetailResponse:
        """Update order status (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        order = await Order.objects.filter(id=order_id).afirst()
        if not order:
            raise NotFoundAPIError("Order not found")

        old_status = order.status
        order.status = data.status

        if data.tracking_number:
            order.tracking_number = data.tracking_number

        if data.status == Order.Status.SHIPPED:
            order.ship(data.tracking_number or "")
        elif data.status == Order.Status.DELIVERED:
            order.deliver()
        else:
            await order.asave()

        # Record status change
        await OrderStatusHistory.objects.acreate(
            order=order,
            status=data.status,
            notes=data.notes or f"Status changed from {old_status} to {data.status}",
            changed_by=request.user,
        )

        # Trigger notifications
        from ecommerce.orders.tasks import send_order_status_update_email
        send_order_status_update_email.delay(str(order.id), data.status)

        return await OrderController.get_order(request, order_id)


# =============================================================================
# Coupon Controller
# =============================================================================


class CouponController(APIController):
    """Coupon management controller."""

    prefix = "/coupons"
    tags = ["Coupons"]

    @staticmethod
    async def validate_coupon(data: CouponValidationRequest) -> CouponValidationResponse:
        """Validate a coupon code."""
        coupon = await Coupon.objects.filter(code__iexact=data.code).afirst()

        if not coupon:
            return CouponValidationResponse(
                valid=False,
                message="Invalid coupon code",
            )

        if not coupon.is_valid:
            return CouponValidationResponse(
                valid=False,
                message="Coupon is expired or has reached its usage limit",
            )

        if data.subtotal < coupon.minimum_purchase:
            return CouponValidationResponse(
                valid=False,
                message=f"Minimum purchase of ${coupon.minimum_purchase} required",
            )

        discount_amount = coupon.calculate_discount(data.subtotal)

        return CouponValidationResponse(
            valid=True,
            message="Coupon is valid",
            discount_amount=discount_amount,
            coupon=CouponResponse.model_validate(coupon),
        )

    @staticmethod
    @jwt_required
    async def list_coupons(request) -> list[CouponResponse]:
        """List coupons (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        coupons = Coupon.objects.all().order_by("-created_at")
        return [CouponResponse.model_validate(c) async for c in coupons]

    @staticmethod
    @jwt_required
    async def create_coupon(request, data: CouponCreate) -> CouponResponse:
        """Create a coupon (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        # Check code uniqueness
        if await Coupon.objects.filter(code__iexact=data.code).aexists():
            raise ValidationAPIError("Coupon code already exists")

        coupon = await Coupon.objects.acreate(**data.model_dump())
        return CouponResponse.model_validate(coupon)

    @staticmethod
    @jwt_required
    async def update_coupon(
        request, coupon_id: UUID, data: CouponUpdate
    ) -> CouponResponse:
        """Update a coupon (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        coupon = await Coupon.objects.filter(id=coupon_id).afirst()
        if not coupon:
            raise NotFoundAPIError("Coupon not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(coupon, key, value)
        await coupon.asave()

        return CouponResponse.model_validate(coupon)

    @staticmethod
    @jwt_required
    async def delete_coupon(request, coupon_id: UUID) -> dict[str, str]:
        """Delete a coupon (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        deleted, _ = await Coupon.objects.filter(id=coupon_id).adelete()
        if not deleted:
            raise NotFoundAPIError("Coupon not found")

        return {"message": "Coupon deleted successfully"}


# =============================================================================
# Shipping & Tax Controllers
# =============================================================================


class ShippingController(APIController):
    """Shipping calculation controller."""

    prefix = "/shipping"
    tags = ["Shipping"]

    @staticmethod
    async def get_rates(subtotal: Decimal) -> ShippingRatesResponse:
        """Get available shipping rates."""
        free_threshold = Decimal(str(getattr(settings, "FREE_SHIPPING_THRESHOLD", 50.00)))
        flat_rate = Decimal(str(getattr(settings, "SHIPPING_FLAT_RATE", 5.99)))

        rates = [
            ShippingRateResponse(
                method="standard",
                name="Standard Shipping",
                description="5-7 business days",
                price=Decimal("0.00") if subtotal >= free_threshold else flat_rate,
                estimated_days=7,
            ),
            ShippingRateResponse(
                method="express",
                name="Express Shipping",
                description="2-3 business days",
                price=Decimal("12.99"),
                estimated_days=3,
            ),
            ShippingRateResponse(
                method="overnight",
                name="Overnight Shipping",
                description="Next business day",
                price=Decimal("24.99"),
                estimated_days=1,
            ),
        ]

        return ShippingRatesResponse(
            rates=rates,
            free_shipping_threshold=free_threshold,
            subtotal=subtotal,
            qualifies_for_free_shipping=subtotal >= free_threshold,
        )


class TaxController(APIController):
    """Tax calculation controller."""

    prefix = "/tax"
    tags = ["Tax"]

    @staticmethod
    async def calculate(data: TaxCalculationRequest) -> TaxCalculationResponse:
        """Calculate tax for an address."""
        # Placeholder - in production, integrate with a tax service
        tax_rate = Decimal(str(getattr(settings, "TAX_RATE_DEFAULT", 0.0875)))
        tax_amount = (data.subtotal * tax_rate).quantize(Decimal("0.01"))

        return TaxCalculationResponse(
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            subtotal=data.subtotal,
            total=data.subtotal + tax_amount,
            jurisdiction=f"{data.address.state}, {data.address.country}",
        )
