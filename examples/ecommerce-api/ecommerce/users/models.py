"""User models for e-commerce."""

import uuid
from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

if TYPE_CHECKING:
    from ecommerce.catalog.models import Product


class UserManager(BaseUserManager):
    """Custom user manager."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create a regular user."""
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Create a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model with email as username."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # type: ignore
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)

    # Profile fields
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    # Marketing preferences
    accepts_marketing = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        """Return full name or email."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email


class Address(models.Model):
    """User address model."""

    class AddressType(models.TextChoices):
        BILLING = "billing", "Billing"
        SHIPPING = "shipping", "Shipping"
        BOTH = "both", "Both"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")

    # Address type
    address_type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.BOTH
    )
    is_default = models.BooleanField(default=False)

    # Address fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=200, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default="US")  # ISO 3166-1 alpha-2
    phone = models.CharField(max_length=20, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self) -> str:
        return f"{self.address_line_1}, {self.city}, {self.state} {self.postal_code}"

    def save(self, *args, **kwargs):
        """Ensure only one default address per type per user."""
        if self.is_default:
            # Unset other defaults for this user and type
            Address.objects.filter(
                user=self.user,
                address_type__in=[self.address_type, Address.AddressType.BOTH],
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Wishlist(models.Model):
    """User wishlist model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlists")
    name = models.CharField(max_length=100, default="My Wishlist")
    is_public = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.name}"


class WishlistItem(models.Model):
    """Wishlist item model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    product: models.ForeignKey["Product"] = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="wishlist_items"
    )

    # Optional notes
    notes = models.TextField(blank=True)

    # Priority
    priority = models.PositiveSmallIntegerField(default=0)

    # Timestamps
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"
        ordering = ["-priority", "-added_at"]
        unique_together = ["wishlist", "product"]

    def __str__(self) -> str:
        return f"{self.wishlist.name} - {self.product.name}"
