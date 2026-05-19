from __future__ import annotations

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError

from apps.cart.models import Cart, CartItem
from apps.cart.schemas import (
    AddToCartSchema,
    CartItemProductSchema,
    CartItemSchema,
    UpdateCartItemSchema,
)
from apps.catalog.models import Product, Variant


async def _get_available_stock(variant: Variant | None) -> int | None:
    """Get available stock from Inventory. Returns None if no inventory tracking."""
    if variant is None:
        return None
    try:
        inventory = await variant.inventory.aget() if hasattr(variant, "inventory") else None
    except Exception:
        inventory = None
    if inventory is None:
        # Try fetching via queryset
        from apps.catalog.models import Inventory

        try:
            inventory = await Inventory.objects.aget(variant=variant)
        except Inventory.DoesNotExist:
            return None
    return inventory.quantity


class CartController(APIController):
    prefix = "cart"
    tags = ["Cart"]

    @jwt_required
    async def get_cart(self, request):
        """GET /cart — Get or create the user's cart with items."""
        cart, _ = await Cart.objects.aget_or_create(user=request.user)

        items = []
        async for item in cart.items.select_related("product", "variant").all():
            product_data = None
            if item.product:
                product_data = CartItemProductSchema(
                    id=str(item.product.id),
                    store_id=str(item.product.store_id),
                    name=item.product.name,
                    price=str(item.product.price),
                    image_url=item.product.image_url,
                    slug=item.product.slug,
                )
            items.append(
                CartItemSchema(
                    id=str(item.id),
                    product_id=str(item.product_id),
                    variant_id=str(item.variant_id) if item.variant_id else None,
                    quantity=item.quantity,
                    created_at=item.created_at,
                    product=product_data,
                ).model_dump()
            )

        return {
            "id": str(cart.id),
            "items": items,
            "item_count": len(items),
            "created_at": cart.created_at.isoformat(),
        }

    @jwt_required
    async def add_to_cart(self, request, body: AddToCartSchema):
        """POST /cart/items — Add item to cart (create or increment quantity)."""
        cart, _ = await Cart.objects.aget_or_create(user=request.user)

        # Validate product exists
        try:
            product = await Product.objects.aget(id=body.product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundAPIError("Product not found")

        # Validate variant if provided
        variant = None
        if body.variant_id:
            try:
                variant = await Variant.objects.aget(
                    id=body.variant_id, product=product, is_active=True
                )
            except Variant.DoesNotExist:
                raise NotFoundAPIError("Variant not found")

        # Check stock via Inventory if variant exists
        if variant:
            available_stock = await _get_available_stock(variant)
            if available_stock is not None and available_stock < body.quantity:
                raise APIError(
                    message=f"Insufficient stock. Available: {available_stock}",
                    status_code=400,
                )

        # Create or update cart item
        try:
            item = await CartItem.objects.aget(
                cart=cart, product=product, variant=variant
            )
            item.quantity += body.quantity
            # Re-check stock for total quantity
            if variant:
                available_stock = await _get_available_stock(variant)
                if available_stock is not None and available_stock < item.quantity:
                    raise APIError(
                        message=f"Insufficient stock. Available: {available_stock}",
                        status_code=400,
                    )
            await item.asave()
        except CartItem.DoesNotExist:
            item = await CartItem.objects.acreate(
                cart=cart,
                product=product,
                variant=variant,
                quantity=body.quantity,
            )

        return {
            "id": str(item.id),
            "product_id": str(item.product_id),
            "variant_id": str(item.variant_id) if item.variant_id else None,
            "quantity": item.quantity,
            "created_at": item.created_at.isoformat(),
        }

    @jwt_required
    async def update_cart_item(self, request, item_id: str, body: UpdateCartItemSchema):
        """PATCH /cart/items/{item_id} — Update quantity (delete if 0)."""
        try:
            item = await CartItem.objects.select_related("cart", "product", "variant").aget(
                id=item_id, cart__user=request.user
            )
        except CartItem.DoesNotExist:
            raise NotFoundAPIError("Cart item not found")

        if body.quantity == 0:
            await item.adelete()
            return {"detail": "Item removed from cart"}

        # Check stock via Inventory
        if item.variant_id:
            available_stock = await _get_available_stock(item.variant)
            if available_stock is not None and available_stock < body.quantity:
                raise APIError(
                    message=f"Insufficient stock. Available: {available_stock}",
                    status_code=400,
                )

        item.quantity = body.quantity
        await item.asave()

        return {
            "id": str(item.id),
            "product_id": str(item.product_id),
            "variant_id": str(item.variant_id) if item.variant_id else None,
            "quantity": item.quantity,
            "created_at": item.created_at.isoformat(),
        }

    @jwt_required
    async def remove_cart_item(self, request, item_id: str):
        """DELETE /cart/items/{item_id} — Remove item from cart."""
        try:
            item = await CartItem.objects.aget(
                id=item_id, cart__user=request.user
            )
        except CartItem.DoesNotExist:
            raise NotFoundAPIError("Cart item not found")

        await item.adelete()
        return {"detail": "Item removed from cart"}

    @jwt_required
    async def clear_cart(self, request):
        """DELETE /cart — Clear all items from cart."""
        try:
            cart = await Cart.objects.aget(user=request.user)
        except Cart.DoesNotExist:
            raise NotFoundAPIError("Cart not found")

        deleted_count, _ = await cart.items.all().adelete()
        return {"detail": f"Cart cleared. {deleted_count} items removed."}
