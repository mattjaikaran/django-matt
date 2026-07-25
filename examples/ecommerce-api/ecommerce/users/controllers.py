"""API controllers for users app."""

from uuid import UUID

from django.db import models
from django_matt.auth import create_token_pair, jwt_required, refresh_tokens
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError
from django_matt.permissions import IsAuthenticated

from ecommerce.catalog.models import Product
from ecommerce.users.models import Address, User, Wishlist, WishlistItem
from ecommerce.users.schemas import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
    WishlistCreate,
    WishlistDetailResponse,
    WishlistItemCreate,
    WishlistItemResponse,
    WishlistResponse,
    WishlistUpdate,
)

# =============================================================================
# Auth Controller
# =============================================================================


class AuthController(APIController):
    """Authentication controller."""

    prefix = "/auth"
    tags = ["Authentication"]

    @staticmethod
    async def register(data: UserCreate) -> UserResponse:
        """Register a new user."""
        # Check if email exists
        if await User.objects.filter(email=data.email).aexists():
            raise ValidationAPIError("Email already registered")

        user = await User.objects.acreate(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        user.set_password(data.password)
        await user.asave()

        return UserResponse.model_validate(user)

    @staticmethod
    async def login(data: LoginRequest) -> LoginResponse:
        """Login and get access tokens."""
        user = await User.objects.filter(email=data.email).afirst()
        if not user or not user.check_password(data.password):
            raise ValidationAPIError("Invalid email or password")

        if not user.is_active:
            raise ValidationAPIError("Account is disabled")

        tokens = create_token_pair(user)
        return LoginResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def refresh(data: RefreshTokenRequest) -> TokenResponse:
        """Refresh access token."""
        try:
            tokens = refresh_tokens(data.refresh_token)
            return TokenResponse(access_token=tokens.access_token)
        except Exception:
            raise ValidationAPIError("Invalid refresh token")

    @staticmethod
    @jwt_required
    async def me(request) -> UserProfileResponse:
        """Get current user profile."""
        user = request.user
        return UserProfileResponse.model_validate(user)

    @staticmethod
    @jwt_required
    async def update_profile(request, data: UserUpdate) -> UserProfileResponse:
        """Update current user profile."""
        user = request.user
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(user, key, value)
        await user.asave()

        return UserProfileResponse.model_validate(user)

    @staticmethod
    @jwt_required
    async def change_password(request, data: PasswordChangeRequest) -> dict[str, str]:
        """Change user password."""
        user = request.user
        if not user.check_password(data.current_password):
            raise ValidationAPIError("Current password is incorrect")

        user.set_password(data.new_password)
        await user.asave()

        return {"message": "Password changed successfully"}


# =============================================================================
# Address Controller
# =============================================================================


class AddressController(APIController):
    """User address management controller."""

    prefix = "/addresses"
    tags = ["Addresses"]
    permission_classes = [IsAuthenticated]

    @staticmethod
    @jwt_required
    async def list_addresses(request) -> list[AddressResponse]:
        """List user addresses."""
        addresses = Address.objects.filter(user=request.user)
        return [AddressResponse.model_validate(a) async for a in addresses]

    @staticmethod
    @jwt_required
    async def create_address(request, data: AddressCreate) -> AddressResponse:
        """Create a new address."""
        address = await Address.objects.acreate(
            user=request.user,
            **data.model_dump(),
        )
        return AddressResponse.model_validate(address)

    @staticmethod
    @jwt_required
    async def get_address(request, address_id: UUID) -> AddressResponse:
        """Get a specific address."""
        address = await Address.objects.filter(id=address_id, user=request.user).afirst()
        if not address:
            raise NotFoundAPIError("Address not found")
        return AddressResponse.model_validate(address)

    @staticmethod
    @jwt_required
    async def update_address(request, address_id: UUID, data: AddressUpdate) -> AddressResponse:
        """Update an address."""
        address = await Address.objects.filter(id=address_id, user=request.user).afirst()
        if not address:
            raise NotFoundAPIError("Address not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(address, key, value)
        await address.asave()

        return AddressResponse.model_validate(address)

    @staticmethod
    @jwt_required
    async def delete_address(request, address_id: UUID) -> dict[str, str]:
        """Delete an address."""
        deleted, _ = await Address.objects.filter(id=address_id, user=request.user).adelete()
        if not deleted:
            raise NotFoundAPIError("Address not found")
        return {"message": "Address deleted successfully"}

    @staticmethod
    @jwt_required
    async def set_default(request, address_id: UUID) -> AddressResponse:
        """Set an address as default."""
        address = await Address.objects.filter(id=address_id, user=request.user).afirst()
        if not address:
            raise NotFoundAPIError("Address not found")

        address.is_default = True
        await address.asave()

        return AddressResponse.model_validate(address)


# =============================================================================
# Wishlist Controller
# =============================================================================


class WishlistController(APIController):
    """Wishlist management controller."""

    prefix = "/wishlists"
    tags = ["Wishlists"]
    permission_classes = [IsAuthenticated]

    @staticmethod
    @jwt_required
    async def list_wishlists(request) -> list[WishlistResponse]:
        """List user wishlists."""
        wishlists = Wishlist.objects.filter(user=request.user).annotate(
            item_count_val=models.Count("items")
        )
        result = []
        async for wl in wishlists:
            response = WishlistResponse.model_validate(wl)
            response.item_count = getattr(wl, "item_count_val", 0)
            result.append(response)
        return result

    @staticmethod
    @jwt_required
    async def create_wishlist(request, data: WishlistCreate) -> WishlistResponse:
        """Create a new wishlist."""
        wishlist = await Wishlist.objects.acreate(
            user=request.user,
            **data.model_dump(),
        )
        response = WishlistResponse.model_validate(wishlist)
        response.item_count = 0
        return response

    @staticmethod
    @jwt_required
    async def get_wishlist(request, wishlist_id: UUID) -> WishlistDetailResponse:
        """Get wishlist with items."""
        wishlist = (
            await Wishlist.objects.filter(id=wishlist_id, user=request.user)
            .prefetch_related("items__product")
            .afirst()
        )
        if not wishlist:
            raise NotFoundAPIError("Wishlist not found")

        items = []
        async for item in wishlist.items.select_related("product").all():
            items.append(
                WishlistItemResponse(
                    id=item.id,
                    product_id=item.product.id,
                    product_name=item.product.name,
                    product_price=float(item.product.price),
                    product_image=(
                        item.product.primary_image.image.url if item.product.primary_image else None
                    ),
                    notes=item.notes,
                    priority=item.priority,
                    added_at=item.added_at,
                )
            )

        return WishlistDetailResponse(
            id=wishlist.id,
            name=wishlist.name,
            is_public=wishlist.is_public,
            item_count=len(items),
            items=items,
            created_at=wishlist.created_at,
            updated_at=wishlist.updated_at,
        )

    @staticmethod
    @jwt_required
    async def update_wishlist(request, wishlist_id: UUID, data: WishlistUpdate) -> WishlistResponse:
        """Update a wishlist."""
        wishlist = await Wishlist.objects.filter(id=wishlist_id, user=request.user).afirst()
        if not wishlist:
            raise NotFoundAPIError("Wishlist not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(wishlist, key, value)
        await wishlist.asave()

        item_count = await wishlist.items.acount()
        response = WishlistResponse.model_validate(wishlist)
        response.item_count = item_count
        return response

    @staticmethod
    @jwt_required
    async def delete_wishlist(request, wishlist_id: UUID) -> dict[str, str]:
        """Delete a wishlist."""
        deleted, _ = await Wishlist.objects.filter(id=wishlist_id, user=request.user).adelete()
        if not deleted:
            raise NotFoundAPIError("Wishlist not found")
        return {"message": "Wishlist deleted successfully"}

    @staticmethod
    @jwt_required
    async def add_item(
        request, wishlist_id: UUID, data: WishlistItemCreate
    ) -> WishlistItemResponse:
        """Add item to wishlist."""
        wishlist = await Wishlist.objects.filter(id=wishlist_id, user=request.user).afirst()
        if not wishlist:
            raise NotFoundAPIError("Wishlist not found")

        product = await Product.objects.filter(id=data.product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        # Check if already in wishlist
        existing = await WishlistItem.objects.filter(wishlist=wishlist, product=product).afirst()
        if existing:
            raise ValidationAPIError("Product already in wishlist")

        item = await WishlistItem.objects.acreate(
            wishlist=wishlist,
            product=product,
            notes=data.notes,
            priority=data.priority,
        )

        return WishlistItemResponse(
            id=item.id,
            product_id=product.id,
            product_name=product.name,
            product_price=float(product.price),
            product_image=(product.primary_image.image.url if product.primary_image else None),
            notes=item.notes,
            priority=item.priority,
            added_at=item.added_at,
        )

    @staticmethod
    @jwt_required
    async def remove_item(request, wishlist_id: UUID, item_id: UUID) -> dict[str, str]:
        """Remove item from wishlist."""
        deleted, _ = await WishlistItem.objects.filter(
            id=item_id, wishlist_id=wishlist_id, wishlist__user=request.user
        ).adelete()
        if not deleted:
            raise NotFoundAPIError("Wishlist item not found")
        return {"message": "Item removed from wishlist"}
