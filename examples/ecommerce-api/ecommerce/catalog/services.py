"""
Service layer for the catalog app.

Encapsulates all business logic for Category, Product, ProductVariant,
and Inventory, keeping controllers as thin HTTP adapters.
"""

from __future__ import annotations

from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q
from django_matt.services import CRUDService, NotFoundError, ValidationError

from .models import Category, Inventory, Product, ProductVariant

# =============================================================================
# Category Service
# =============================================================================


class CategoryService(CRUDService["Category"]):
    """Service for category CRUD and tree operations."""

    model = Category

    def get_queryset(self):
        return super().get_queryset().order_by("tree_id", "lft")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def get_active(self) -> list[Category]:
        """Return all active categories."""
        return [c async for c in self.get_queryset().filter(is_active=True)]

    async def get_tree(self) -> list[Category]:
        """
        Return active categories annotated with product_count, ordered for
        tree reconstruction (tree_id, lft).
        """
        qs = (
            self.get_queryset()
            .filter(is_active=True)
            .annotate(product_count=Count("products", filter=Q(products__status="active")))
        )
        return [c async for c in qs]

    async def get_by_slug(self, slug: str) -> Category:
        """Fetch an active category by slug. Raises NotFoundError if missing."""
        try:
            return await self.get_queryset().aget(slug=slug, is_active=True)
        except Category.DoesNotExist:
            raise NotFoundError(f"Category '{slug}' not found")

    def invalidate_cache(self) -> None:
        """Invalidate the category list and tree caches."""
        cache.delete_many(["categories:all", "categories:tree"])


# =============================================================================
# Product Service
# =============================================================================


class ProductService(CRUDService["Product"]):
    """Service for product CRUD, search, and filtering."""

    model = Product

    def get_queryset(self):
        return (
            super().get_queryset().select_related("category").prefetch_related("images", "variants")
        )

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def list_active(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        **filters: Any,
    ) -> tuple[list[Product], int]:
        """Paginated list of active (status=active) products."""
        return await self.list(
            page=page, page_size=page_size, status=Product.Status.ACTIVE, **filters
        )

    async def search(
        self,
        query: str | None,
        *,
        category_id=None,
        category_slug: str | None = None,
        min_price=None,
        max_price=None,
        in_stock: bool | None = None,
        is_featured: bool | None = None,
        is_on_sale: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        """
        Full-text + filter search over active products.

        Supports keyword search via PostgreSQL search vectors plus optional
        price range, stock, featured, and on-sale filters.
        """
        qs = self.get_queryset().filter(status=Product.Status.ACTIVE)

        if query:
            search_vector = SearchVector("name", weight="A") + SearchVector(
                "description", weight="B"
            )
            search_query = SearchQuery(query)
            qs = (
                qs.annotate(
                    rank=SearchRank(search_vector, search_query),
                )
                .filter(
                    Q(search_vector=search_query)
                    | Q(name__icontains=query)
                    | Q(description__icontains=query)
                )
                .order_by("-rank", "-created_at")
            )

        if category_id is not None:
            qs = qs.filter(category_id=category_id)
        if category_slug is not None:
            qs = qs.filter(category__slug=category_slug)
        if min_price is not None:
            qs = qs.filter(price__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price__lte=max_price)
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured)
        if is_on_sale is True:
            qs = qs.filter(compare_at_price__isnull=False).filter(compare_at_price__gt=F("price"))

        total = await qs.acount()
        offset = (page - 1) * page_size
        items = [p async for p in qs[offset : offset + page_size]]
        return items, total

    async def get_featured(self) -> list[Product]:
        """Return all active featured products."""
        return [
            p
            async for p in self.get_queryset().filter(
                status=Product.Status.ACTIVE, is_featured=True
            )
        ]

    async def get_on_sale(self) -> list[Product]:
        """Return active products where compare_at_price > price."""
        return [
            p
            async for p in self.get_queryset()
            .filter(status=Product.Status.ACTIVE, compare_at_price__isnull=False)
            .filter(compare_at_price__gt=F("price"))
        ]

    async def get_with_details(self, pk) -> Product:
        """
        Fetch a single product with all related data pre-loaded.
        Raises NotFoundError if not found.
        """
        qs = (
            self.model.objects.select_related("category")
            .prefetch_related("images", "variants", "inventory")
            .filter(pk=pk)
        )
        try:
            return await qs.aget()
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {pk} not found")


# =============================================================================
# ProductVariant Service
# =============================================================================


class ProductVariantService(CRUDService["ProductVariant"]):
    """Service for product variant CRUD."""

    model = ProductVariant

    def get_queryset(self):
        return super().get_queryset().select_related("product", "image")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_product(self, product_id) -> list[ProductVariant]:
        """Return all active variants for a given product."""
        return [
            v
            async for v in self.get_queryset()
            .filter(product_id=product_id, is_active=True)
            .order_by("name")
        ]


# =============================================================================
# Inventory Service
# =============================================================================


class InventoryService(CRUDService["Inventory"]):
    """Service for inventory CRUD and reservation logic."""

    model = Inventory

    def get_queryset(self):
        return super().get_queryset().select_related("product", "variant")

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def for_product(self, product_id) -> list[Inventory]:
        """Return all inventory records for a given product."""
        return [i async for i in self.get_queryset().filter(product_id=product_id)]

    async def reserve(self, pk, qty: int) -> Inventory:
        """
        Reserve ``qty`` units in an inventory record.

        Raises ValidationError when insufficient available stock.
        """
        inv = await self.get(pk)
        available = inv.quantity - inv.reserved_quantity
        if available < qty:
            raise ValidationError(
                f"Insufficient stock: {available} available, {qty} requested",
                field="quantity",
            )
        async with transaction.atomic():
            inv.reserved_quantity += qty
            await inv.asave(update_fields=["reserved_quantity", "updated_at"])
        self._log.info("reserved %d units for inventory pk=%s", qty, pk)
        return inv

    async def release(self, pk, qty: int) -> Inventory:
        """
        Release ``qty`` previously reserved units back to available stock.
        """
        inv = await self.get(pk)
        async with transaction.atomic():
            inv.reserved_quantity = max(0, inv.reserved_quantity - qty)
            await inv.asave(update_fields=["reserved_quantity", "updated_at"])
        self._log.info("released %d units for inventory pk=%s", qty, pk)
        return inv
