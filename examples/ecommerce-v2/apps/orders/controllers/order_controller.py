from __future__ import annotations

from decimal import Decimal

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError
from django_matt.events import Event, get_event_bus

from apps.catalog.models import Inventory, Product, Variant
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.orders.schemas import (
    OrderCreateSchema,
    OrderItemSchema,
    OrderUpdateSchema,
)
from apps.orders.schemas.order_schema import OrderItemProductSchema
from apps.stores.models import Store

# Valid status transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [OrderStatus.REFUNDED],
    OrderStatus.CANCELLED: [],
    OrderStatus.REFUNDED: [],
}


async def _get_inventory(variant: Variant) -> Inventory | None:
    """Get inventory for a variant, or None if not tracked."""
    try:
        return await Inventory.objects.aget(variant=variant)
    except Inventory.DoesNotExist:
        return None


def _item_product_schema(product: Product) -> OrderItemProductSchema:
    return OrderItemProductSchema(
        id=str(product.id),
        name=product.name,
        slug=product.slug,
        price=str(product.price),
        image_url=product.image_url,
    )


class OrderController(APIController):
    prefix = "orders"
    tags = ["Orders"]

    @jwt_required
    async def list_orders(self, request):
        """GET /orders — List user's orders, filterable by ?status."""
        queryset = Order.objects.filter(user=request.user).select_related("store")

        # Filter by status
        status = request.GET.get("status")
        if status:
            if status not in OrderStatus.values:
                raise ValidationAPIError(f"Invalid status: {status}")
            queryset = queryset.filter(status=status)

        # Simple pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        offset = (page - 1) * page_size

        orders = []
        async for order in queryset[offset : offset + page_size]:
            items = []
            async for item in order.items.select_related("product").all():
                items.append(
                    OrderItemSchema(
                        id=str(item.id),
                        product_id=str(item.product_id),
                        variant_id=str(item.variant_id) if item.variant_id else None,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        total_price=item.total_price,
                        product=_item_product_schema(item.product),
                    ).model_dump()
                )

            orders.append(
                {
                    "id": str(order.id),
                    "user_id": str(order.user_id),
                    "store_id": str(order.store_id),
                    "status": order.status,
                    "subtotal": str(order.subtotal),
                    "tax": str(order.tax),
                    "shipping_cost": str(order.shipping_cost),
                    "total": str(order.total),
                    "shipping_address": order.shipping_address,
                    "billing_address": order.billing_address,
                    "notes": order.notes,
                    "stripe_payment_intent_id": order.stripe_payment_intent_id,
                    "items": items,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                }
            )

        total = await queryset.acount()
        return {"items": orders, "total": total, "page": page, "page_size": page_size}

    @jwt_required
    async def create_order(self, request, body: OrderCreateSchema):
        """POST /orders — Create order from schema, calculate prices, validate stock."""
        if not body.items:
            raise ValidationAPIError("Order must have at least one item")

        # Validate store
        try:
            store = await Store.objects.aget(id=body.store_id, is_active=True)
        except Store.DoesNotExist:
            raise NotFoundAPIError("Store not found")

        # Validate items and calculate prices
        subtotal = Decimal("0")
        order_items_data = []

        for item_data in body.items:
            try:
                product = await Product.objects.aget(
                    id=item_data.product_id, store=store, is_active=True
                )
            except Product.DoesNotExist:
                raise NotFoundAPIError(f"Product {item_data.product_id} not found in store")

            variant = None
            inventory = None
            if item_data.variant_id:
                try:
                    variant = await Variant.objects.aget(
                        id=item_data.variant_id, product=product, is_active=True
                    )
                except Variant.DoesNotExist:
                    raise NotFoundAPIError(f"Variant {item_data.variant_id} not found")

                # Check stock via Inventory
                inventory = await _get_inventory(variant)
                if inventory is not None and inventory.quantity < item_data.quantity:
                    raise APIError(
                        message=f"Insufficient stock for {product.name} ({variant.name}). "
                        f"Available: {inventory.quantity}",
                        status_code=400,
                    )

            # Price: use variant price_override if set, otherwise product price
            unit_price = (
                variant.price_override if variant and variant.price_override else product.price
            )
            total_price = unit_price * item_data.quantity
            subtotal += total_price

            order_items_data.append(
                {
                    "product": product,
                    "variant": variant,
                    "inventory": inventory,
                    "quantity": item_data.quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                }
            )

        # Create order
        total = subtotal  # Tax and shipping can be calculated separately
        order = await Order.objects.acreate(
            user=request.user,
            store=store,
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            tax=Decimal("0"),
            shipping_cost=Decimal("0"),
            total=total,
            shipping_address=body.shipping_address,
            billing_address=body.billing_address,
            notes=body.notes,
        )

        # Create order items and decrement stock
        items = []
        for item_data in order_items_data:
            order_item = await OrderItem.objects.acreate(
                order=order,
                product=item_data["product"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            )

            # Decrement inventory stock
            if item_data["inventory"] is not None:
                item_data["inventory"].quantity -= item_data["quantity"]
                await item_data["inventory"].asave()

            items.append(
                OrderItemSchema(
                    id=str(order_item.id),
                    product_id=str(order_item.product_id),
                    variant_id=str(order_item.variant_id) if order_item.variant_id else None,
                    quantity=order_item.quantity,
                    unit_price=order_item.unit_price,
                    total_price=order_item.total_price,
                    product=_item_product_schema(item_data["product"]),
                ).model_dump()
            )

        # Emit order created event
        bus = get_event_bus()
        await bus.emit(
            Event(
                name="order.created",
                data={
                    "order_id": str(order.id),
                    "user_id": str(request.user.id),
                    "total": str(total),
                },
            )
        )

        return {
            "id": str(order.id),
            "user_id": str(order.user_id),
            "store_id": str(order.store_id),
            "status": order.status,
            "subtotal": str(order.subtotal),
            "tax": str(order.tax),
            "shipping_cost": str(order.shipping_cost),
            "total": str(order.total),
            "shipping_address": order.shipping_address,
            "billing_address": order.billing_address,
            "notes": order.notes,
            "stripe_payment_intent_id": order.stripe_payment_intent_id,
            "items": items,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }

    @jwt_required
    async def get_order(self, request, order_id: str):
        """GET /orders/{order_id} — Get order with items."""
        try:
            order = await Order.objects.select_related("store").aget(id=order_id, user=request.user)
        except Order.DoesNotExist:
            raise NotFoundAPIError("Order not found")

        items = []
        async for item in order.items.select_related("product", "variant").all():
            items.append(
                OrderItemSchema(
                    id=str(item.id),
                    product_id=str(item.product_id),
                    variant_id=str(item.variant_id) if item.variant_id else None,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price,
                    product=_item_product_schema(item.product),
                ).model_dump()
            )

        return {
            "id": str(order.id),
            "user_id": str(order.user_id),
            "store_id": str(order.store_id),
            "status": order.status,
            "subtotal": str(order.subtotal),
            "tax": str(order.tax),
            "shipping_cost": str(order.shipping_cost),
            "total": str(order.total),
            "shipping_address": order.shipping_address,
            "billing_address": order.billing_address,
            "notes": order.notes,
            "stripe_payment_intent_id": order.stripe_payment_intent_id,
            "items": items,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }

    @jwt_required
    async def update_order_status(self, request, order_id: str, body: OrderUpdateSchema):
        """PATCH /orders/{order_id} — Update order status with transition validation."""
        try:
            order = await Order.objects.aget(id=order_id, user=request.user)
        except Order.DoesNotExist:
            raise NotFoundAPIError("Order not found")

        if body.status is not None:
            if body.status not in OrderStatus.values:
                raise ValidationAPIError(f"Invalid status: {body.status}")

            allowed = VALID_TRANSITIONS.get(order.status, [])
            if body.status not in allowed:
                raise APIError(
                    message=f"Cannot transition from '{order.status}' to '{body.status}'. "
                    f"Allowed: {allowed}",
                    status_code=400,
                )
            order.status = body.status

        if body.notes is not None:
            order.notes = body.notes

        await order.asave()

        return {
            "id": str(order.id),
            "status": order.status,
            "notes": order.notes,
            "updated_at": order.updated_at.isoformat(),
        }

    @jwt_required
    async def cancel_order(self, request, order_id: str):
        """POST /orders/{order_id}/cancel — Cancel if PENDING or CONFIRMED."""
        try:
            order = await Order.objects.aget(id=order_id, user=request.user)
        except Order.DoesNotExist:
            raise NotFoundAPIError("Order not found")

        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise APIError(
                message=f"Cannot cancel order with status '{order.status}'. "
                f"Only pending or confirmed orders can be cancelled.",
                status_code=400,
            )

        order.status = OrderStatus.CANCELLED
        await order.asave()

        # Emit order cancelled event
        bus = get_event_bus()
        await bus.emit(
            Event(
                name="order.cancelled",
                data={"order_id": str(order.id), "user_id": str(request.user.id)},
            )
        )

        # Restore inventory stock
        async for item in order.items.select_related("variant").all():
            if item.variant_id:
                inventory = await _get_inventory(item.variant)
                if inventory is not None:
                    inventory.quantity += item.quantity
                    await inventory.asave()

        return {
            "id": str(order.id),
            "status": order.status,
            "detail": "Order cancelled. Stock restored.",
        }
