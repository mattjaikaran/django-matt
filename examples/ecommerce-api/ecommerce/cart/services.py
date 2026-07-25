"""
Service layer for the cart app.

All business logic for Cart and CartItem lives here.
Controllers are thin HTTP adapters that delegate to CartService.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django_matt.services import BaseService, NotFoundError, ValidationError

from ecommerce.catalog.models import Product, ProductVariant

from .models import Cart, CartItem


class CartService(BaseService["Cart"]):
    """
    Domain service for shopping cart operations.

    Inherits from BaseService (read helpers) and provides full cart
    management including item CRUD, coupon application, and summary
    computation. Cart creation/retrieval is handled here rather than
    in CRUDService because carts are never listed in bulk.
    """

    model = Cart

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                "items__product",
                "items__variant",
                "coupon",
            )
        )

    # ------------------------------------------------------------------
    # Cart retrieval / creation
    # ------------------------------------------------------------------

    async def get_or_create_for_user(self, user) -> Cart:
        """
        Return the cart belonging to ``user``, creating one if needed.
        """
        cart, _ = await Cart.objects.aget_or_create(user=user)
        return cart

    async def get_or_create_for_session(self, session_key: str) -> Cart:
        """
        Return the anonymous cart for ``session_key``, creating one if needed.
        """
        cart, _ = await Cart.objects.aget_or_create(session_key=session_key, user=None)
        return cart

    # ------------------------------------------------------------------
    # Item management
    # ------------------------------------------------------------------

    async def add_item(
        self,
        cart: Cart,
        product_id,
        qty: int,
        variant_id=None,
    ) -> CartItem:
        """
        Add ``qty`` units of a product (and optional variant) to the cart.

        If the item already exists the quantity is incremented. The price
        snapshot is set on first add and never overwritten.
        """
        if qty <= 0:
            raise ValidationError("Quantity must be positive", field="quantity")

        try:
            product = await Product.objects.aget(pk=product_id)
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {product_id} not found")

        variant: ProductVariant | None = None
        if variant_id is not None:
            try:
                variant = await ProductVariant.objects.aget(pk=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                raise NotFoundError(f"ProductVariant {variant_id} not found")

        async with transaction.atomic():
            item, created = await CartItem.objects.aget_or_create(
                cart=cart,
                product=product,
                variant=variant,
                defaults={"quantity": qty},
            )
            if not created:
                item.quantity += qty
                await item.asave(update_fields=["quantity", "updated_at"])

        self._log.info(
            "cart pk=%s: added product=%s variant=%s qty=%d",
            cart.pk,
            product_id,
            variant_id,
            qty,
        )
        return item

    async def update_item(self, cart_item_id, qty: int) -> CartItem:
        """
        Set the quantity of a cart item to ``qty``.

        Pass qty=0 to remove the item. Raises NotFoundError if the item
        does not exist.
        """
        try:
            item = await CartItem.objects.aget(pk=cart_item_id)
        except CartItem.DoesNotExist:
            raise NotFoundError(f"CartItem {cart_item_id} not found")

        if qty <= 0:
            await item.adelete()
            self._log.info("cart item pk=%s removed (qty=0)", cart_item_id)
            return item

        item.quantity = qty
        await item.asave(update_fields=["quantity", "updated_at"])
        return item

    async def remove_item(self, cart_item_id) -> bool:
        """
        Remove a cart item by primary key.

        Returns True if a row was deleted, False if it was not found.
        """
        deleted, _ = await CartItem.objects.filter(pk=cart_item_id).adelete()
        return deleted > 0

    async def clear(self, cart: Cart) -> None:
        """Remove all items from ``cart`` and detach any applied coupon."""
        async with transaction.atomic():
            await CartItem.objects.filter(cart=cart).adelete()
            cart.coupon = None
            await cart.asave(update_fields=["coupon", "updated_at"])
        self._log.info("cart pk=%s cleared", cart.pk)

    # ------------------------------------------------------------------
    # Coupon
    # ------------------------------------------------------------------

    async def apply_coupon(self, cart: Cart, code: str) -> Cart:
        """
        Look up and apply a coupon by ``code`` to the cart.

        Raises ValidationError when the coupon is invalid or inactive.
        """
        from ecommerce.orders.models import Coupon  # local import to avoid circular

        try:
            coupon = await Coupon.objects.aget(code=code, is_active=True)
        except Coupon.DoesNotExist:
            raise ValidationError(f"Coupon '{code}' is invalid or expired", field="code")

        cart.coupon = coupon
        await cart.asave(update_fields=["coupon", "updated_at"])
        self._log.info("cart pk=%s: applied coupon '%s'", cart.pk, code)
        return cart

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def get_summary(self, cart: Cart) -> dict[str, Any]:
        """
        Compute and return a cart summary dict with totals.

        Reloads the cart with items prefetched so callers do not need to
        worry about prefetch state.
        """
        # Reload with all related data so property calculations work
        fresh = await Cart.objects.prefetch_related(
            "items__product",
            "items__variant",
            "coupon",
        ).aget(pk=cart.pk)

        items_data = []
        async for item in fresh.items.select_related("product", "variant").all():
            items_data.append(
                {
                    "id": item.pk,
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "variant_id": item.variant_id,
                    "variant_name": item.variant.name if item.variant else None,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                    "price_changed": item.price_changed,
                }
            )

        subtotal: Decimal = sum((Decimal(i["line_total"]) for i in items_data), Decimal("0.00"))
        coupon_code = fresh.coupon.code if fresh.coupon else None
        discount = fresh.coupon.calculate_discount(subtotal) if fresh.coupon else Decimal("0.00")
        tax_rate = Decimal("0.0875")  # placeholder — real apps read from settings
        tax = ((subtotal - discount) * tax_rate).quantize(Decimal("0.01"))
        free_shipping_threshold = Decimal("50.00")
        shipping_flat = Decimal("5.99")
        shipping = (
            Decimal("0.00") if (subtotal - discount) >= free_shipping_threshold else shipping_flat
        )
        total = subtotal - discount + tax + shipping

        return {
            "item_count": sum(int(i["quantity"]) for i in items_data),
            "items": items_data,
            "subtotal": str(subtotal),
            "coupon_code": coupon_code,
            "discount_amount": str(discount),
            "tax_amount": str(tax),
            "shipping_amount": str(shipping),
            "total": str(total),
        }
