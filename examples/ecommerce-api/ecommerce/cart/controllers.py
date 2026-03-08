"""API controllers for cart app."""

from decimal import Decimal
from uuid import UUID

from django_matt.auth import jwt_optional
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from ecommerce.cart.models import Cart, CartItem
from ecommerce.cart.schemas import (
    ApplyCouponRequest,
    ApplyCouponResponse,
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartNotesUpdate,
    CartResponse,
    CartSummaryResponse,
)
from ecommerce.catalog.models import Inventory, Product, ProductVariant
from ecommerce.orders.models import Coupon


class CartController(APIController):
    """Shopping cart management controller."""

    prefix = "/cart"
    tags = ["Cart"]

    @staticmethod
    async def _get_or_create_cart(request) -> Cart:
        """Get or create cart for user or session."""
        if request.user and request.user.is_authenticated:
            cart, _ = await Cart.objects.aget_or_create(user=request.user)
            # Merge session cart if exists
            session_key = request.session.session_key
            if session_key:
                session_cart = await Cart.objects.filter(
                    session_key=session_key, user__isnull=True
                ).afirst()
                if session_cart:
                    await cart.amerge(session_cart)
        else:
            if not request.session.session_key:
                request.session.create()
            cart, _ = await Cart.objects.aget_or_create(
                session_key=request.session.session_key, user__isnull=True
            )
        return cart

    @staticmethod
    async def _build_cart_response(cart: Cart) -> CartResponse:
        """Build cart response with items."""
        items = []
        async for item in cart.items.select_related("product", "variant").all():
            # Get inventory
            if item.variant:
                inv = await Inventory.objects.filter(variant=item.variant).afirst()
            else:
                inv = await Inventory.objects.filter(
                    product=item.product, variant__isnull=True
                ).afirst()

            primary_image = await item.product.images.filter(is_primary=True).afirst()
            if not primary_image:
                primary_image = await item.product.images.afirst()

            items.append(
                CartItemResponse(
                    id=item.id,
                    product_id=item.product.id,
                    product_name=item.product.name,
                    product_slug=item.product.slug,
                    product_image=primary_image.image.url if primary_image else None,
                    variant_id=item.variant.id if item.variant else None,
                    variant_name=item.variant.name if item.variant else None,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                    price_at_add=item.price_at_add,
                    price_changed=item.price_changed,
                    in_stock=item.product.in_stock,
                    available_quantity=inv.available_quantity if inv else 0,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        return CartResponse(
            id=cart.id,
            items=items,
            item_count=cart.item_count,
            subtotal=cart.subtotal,
            discount_amount=cart.discount_amount,
            tax_amount=cart.tax_amount,
            shipping_amount=cart.shipping_amount,
            total=cart.total,
            coupon_code=cart.coupon.code if cart.coupon else None,
            notes=cart.notes,
            created_at=cart.created_at,
            updated_at=cart.updated_at,
        )

    @staticmethod
    @jwt_optional
    async def get_cart(request) -> CartResponse:
        """Get current cart."""
        cart = await CartController._get_or_create_cart(request)
        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def get_cart_summary(request) -> CartSummaryResponse:
        """Get cart summary (lightweight)."""
        cart = await CartController._get_or_create_cart(request)
        return CartSummaryResponse(
            id=cart.id,
            item_count=cart.item_count,
            subtotal=cart.subtotal,
            total=cart.total,
        )

    @staticmethod
    @jwt_optional
    async def add_item(request, data: CartItemCreate) -> CartResponse:
        """Add item to cart."""
        cart = await CartController._get_or_create_cart(request)

        # Get product
        product = await Product.objects.filter(
            id=data.product_id, status="active"
        ).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        # Get variant if specified
        variant = None
        if data.variant_id:
            variant = await ProductVariant.objects.filter(
                id=data.variant_id, product=product, is_active=True
            ).afirst()
            if not variant:
                raise NotFoundAPIError("Product variant not found")

        # Check inventory
        if variant:
            inv = await Inventory.objects.filter(variant=variant).afirst()
        else:
            inv = await Inventory.objects.filter(
                product=product, variant__isnull=True
            ).afirst()

        if not inv or inv.available_quantity < data.quantity:
            raise ValidationAPIError("Insufficient inventory")

        # Check if already in cart
        existing = await CartItem.objects.filter(
            cart=cart, product=product, variant=variant
        ).afirst()

        if existing:
            new_quantity = existing.quantity + data.quantity
            if inv and new_quantity > inv.available_quantity:
                raise ValidationAPIError(
                    f"Only {inv.available_quantity} items available"
                )
            existing.quantity = new_quantity
            await existing.asave()
        else:
            await CartItem.objects.acreate(
                cart=cart,
                product=product,
                variant=variant,
                quantity=data.quantity,
            )

        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def update_item(
        request, item_id: UUID, data: CartItemUpdate
    ) -> CartResponse:
        """Update cart item quantity."""
        cart = await CartController._get_or_create_cart(request)

        item = await CartItem.objects.filter(id=item_id, cart=cart).select_related(
            "product", "variant"
        ).afirst()
        if not item:
            raise NotFoundAPIError("Cart item not found")

        # Check inventory
        if item.variant:
            inv = await Inventory.objects.filter(variant=item.variant).afirst()
        else:
            inv = await Inventory.objects.filter(
                product=item.product, variant__isnull=True
            ).afirst()

        if inv and data.quantity > inv.available_quantity:
            raise ValidationAPIError(
                f"Only {inv.available_quantity} items available"
            )

        item.quantity = data.quantity
        await item.asave()

        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def remove_item(request, item_id: UUID) -> CartResponse:
        """Remove item from cart."""
        cart = await CartController._get_or_create_cart(request)

        deleted, _ = await CartItem.objects.filter(id=item_id, cart=cart).adelete()
        if not deleted:
            raise NotFoundAPIError("Cart item not found")

        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def clear_cart(request) -> CartResponse:
        """Clear all items from cart."""
        cart = await CartController._get_or_create_cart(request)
        await cart.items.all().adelete()
        cart.coupon = None
        await cart.asave()
        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def apply_coupon(request, data: ApplyCouponRequest) -> ApplyCouponResponse:
        """Apply coupon to cart."""
        cart = await CartController._get_or_create_cart(request)

        coupon = await Coupon.objects.filter(code__iexact=data.code).afirst()
        if not coupon:
            return ApplyCouponResponse(
                success=False,
                message="Invalid coupon code",
                discount_amount=Decimal("0.00"),
                new_total=cart.total,
            )

        if not coupon.is_valid:
            return ApplyCouponResponse(
                success=False,
                message="Coupon is expired or has reached its usage limit",
                discount_amount=Decimal("0.00"),
                new_total=cart.total,
            )

        subtotal = cart.subtotal
        if subtotal < coupon.minimum_purchase:
            return ApplyCouponResponse(
                success=False,
                message=f"Minimum purchase of ${coupon.minimum_purchase} required",
                discount_amount=Decimal("0.00"),
                new_total=cart.total,
            )

        cart.coupon = coupon
        await cart.asave()

        return ApplyCouponResponse(
            success=True,
            message="Coupon applied successfully",
            discount_amount=cart.discount_amount,
            new_total=cart.total,
        )

    @staticmethod
    @jwt_optional
    async def remove_coupon(request) -> CartResponse:
        """Remove coupon from cart."""
        cart = await CartController._get_or_create_cart(request)
        cart.coupon = None
        await cart.asave()
        return await CartController._build_cart_response(cart)

    @staticmethod
    @jwt_optional
    async def update_notes(request, data: CartNotesUpdate) -> CartResponse:
        """Update cart notes."""
        cart = await CartController._get_or_create_cart(request)
        cart.notes = data.notes
        await cart.asave()
        return await CartController._build_cart_response(cart)
