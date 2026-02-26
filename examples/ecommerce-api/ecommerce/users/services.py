"""
Service layer for the users app.

Encapsulates business logic for User, Address, and Wishlist models,
keeping controllers as thin HTTP adapters.
"""

from __future__ import annotations

from django.db import transaction
from django_matt.services import CRUDService, NotFoundError, ValidationError

from .models import Address, User, Wishlist, WishlistItem

# =============================================================================
# User Service
# =============================================================================


class UserService(CRUDService["User"]):
    """Service for user CRUD and profile helpers."""

    model = User

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_by_email(self, email: str) -> User:
        """
        Fetch a user by email address.
        Raises NotFoundError if no matching user exists.
        """
        return await self.get_by(email=email)

    async def set_default_address(self, user: User, address_id) -> Address:
        """
        Mark the given address as the default for ``user``.

        Clears the existing default first, then sets the new one.
        Raises NotFoundError when the address does not belong to the user.
        """
        try:
            address = await Address.objects.aget(pk=address_id, user=user)
        except Address.DoesNotExist:
            raise NotFoundError(f"Address {address_id} not found for user {user.pk}")

        async with transaction.atomic():
            # Unset all current defaults for this user
            await Address.objects.filter(user=user, is_default=True).aupdate(
                is_default=False
            )
            address.is_default = True
            await address.asave(update_fields=["is_default", "updated_at"])

        return address


# =============================================================================
# Address Service
# =============================================================================


class AddressService(CRUDService["Address"]):
    """Service for address CRUD."""

    model = Address

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_user(self, user: User) -> list[Address]:
        """Return all addresses belonging to ``user``, default first."""
        return [
            a
            async for a in self.get_queryset()
            .filter(user=user)
            .order_by("-is_default", "-created_at")
        ]

    async def set_default(self, pk, user: User) -> Address:
        """
        Mark address ``pk`` as the default for ``user``.

        Raises ValidationError if the address belongs to a different user.
        Raises NotFoundError if the address does not exist.
        """
        address = await self.get(pk)
        if address.user_id != user.pk:
            raise ValidationError("Address does not belong to this user")

        async with transaction.atomic():
            await Address.objects.filter(user=user, is_default=True).aupdate(
                is_default=False
            )
            address.is_default = True
            await address.asave(update_fields=["is_default", "updated_at"])

        return address


# =============================================================================
# Wishlist Service
# =============================================================================


class WishlistService(CRUDService["Wishlist"]):
    """Service for wishlist CRUD and item management."""

    model = Wishlist

    def get_queryset(self):
        return super().get_queryset().prefetch_related("items__product")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_user(self, user: User) -> list[Wishlist]:
        """Return all wishlists owned by ``user``."""
        return [w async for w in self.get_queryset().filter(user=user)]

    async def add_item(self, wishlist_id, product_id) -> WishlistItem:
        """
        Add a product to the specified wishlist.

        If the product is already on the wishlist the existing item is returned
        (idempotent). Raises NotFoundError when the wishlist does not exist.
        """
        wishlist = await self.get(wishlist_id)
        item, _ = await WishlistItem.objects.aget_or_create(
            wishlist=wishlist,
            product_id=product_id,
        )
        return item

    async def remove_item(self, wishlist_id, item_id) -> bool:
        """
        Remove an item from a wishlist.

        Returns True if a row was deleted, False if the item was not found.
        """
        deleted, _ = await WishlistItem.objects.filter(
            pk=item_id, wishlist_id=wishlist_id
        ).adelete()
        return deleted > 0
