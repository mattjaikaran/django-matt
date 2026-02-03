"""API controllers for catalog app."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.db import models
from django.db.models import Avg, Count, F, Q

from django_matt.core import APIController
from django_matt.auth import jwt_required, jwt_optional
from django_matt.permissions import IsAuthenticated, IsAdmin
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from ecommerce.catalog.models import Category, Inventory, Product, ProductImage, ProductVariant
from ecommerce.catalog.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryTreeResponse,
    CategoryUpdate,
    InventoryResponse,
    PaginatedProductsResponse,
    ProductCreate,
    ProductDetailResponse,
    ProductListResponse,
    ProductSearchParams,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)


# =============================================================================
# Category Controller
# =============================================================================


class CategoryController(APIController):
    """Product category management controller."""

    prefix = "/categories"
    tags = ["Categories"]

    @staticmethod
    async def list_categories() -> list[CategoryResponse]:
        """List all active categories."""
        cache_key = "categories:all"
        cached = cache.get(cache_key)
        if cached:
            return cached

        categories = Category.objects.filter(is_active=True)
        result = [CategoryResponse.model_validate(c) async for c in categories]
        cache.set(cache_key, result, timeout=300)  # 5 minutes
        return result

    @staticmethod
    async def get_category_tree() -> list[CategoryTreeResponse]:
        """Get category tree structure."""
        cache_key = "categories:tree"
        cached = cache.get(cache_key)
        if cached:
            return cached

        def build_tree(categories, parent=None):
            """Recursively build category tree."""
            tree = []
            for cat in categories:
                if cat.parent_id == parent:
                    children = build_tree(categories, cat.id)
                    tree.append(
                        CategoryTreeResponse(
                            id=cat.id,
                            name=cat.name,
                            slug=cat.slug,
                            description=cat.description,
                            meta_title=cat.meta_title,
                            meta_description=cat.meta_description,
                            is_active=cat.is_active,
                            display_order=cat.display_order,
                            parent_id=cat.parent_id,
                            full_path=cat.full_path,
                            created_at=cat.created_at,
                            updated_at=cat.updated_at,
                            children=children,
                            product_count=getattr(cat, "product_count", 0),
                        )
                    )
            return tree

        categories = await Category.objects.filter(is_active=True).annotate(
            product_count=Count("products", filter=Q(products__status="active"))
        ).order_by("tree_id", "lft").alist()

        result = build_tree(list(categories))
        cache.set(cache_key, result, timeout=300)
        return result

    @staticmethod
    async def get_category(category_slug: str) -> CategoryResponse:
        """Get category by slug."""
        category = await Category.objects.filter(
            slug=category_slug, is_active=True
        ).afirst()
        if not category:
            raise NotFoundAPIError("Category not found")
        return CategoryResponse.model_validate(category)

    @staticmethod
    @jwt_required
    async def create_category(request, data: CategoryCreate) -> CategoryResponse:
        """Create a new category (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        parent = None
        if data.parent_id:
            parent = await Category.objects.filter(id=data.parent_id).afirst()
            if not parent:
                raise NotFoundAPIError("Parent category not found")

        category = await Category.objects.acreate(
            parent=parent,
            **data.model_dump(exclude={"parent_id"}),
        )
        cache.delete_many(["categories:all", "categories:tree"])
        return CategoryResponse.model_validate(category)

    @staticmethod
    @jwt_required
    async def update_category(
        request, category_id: UUID, data: CategoryUpdate
    ) -> CategoryResponse:
        """Update a category (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        category = await Category.objects.filter(id=category_id).afirst()
        if not category:
            raise NotFoundAPIError("Category not found")

        update_data = data.model_dump(exclude_unset=True)
        if "parent_id" in update_data:
            parent_id = update_data.pop("parent_id")
            if parent_id:
                parent = await Category.objects.filter(id=parent_id).afirst()
                if not parent:
                    raise NotFoundAPIError("Parent category not found")
                category.parent = parent
            else:
                category.parent = None

        for key, value in update_data.items():
            setattr(category, key, value)
        await category.asave()

        cache.delete_many(["categories:all", "categories:tree"])
        return CategoryResponse.model_validate(category)

    @staticmethod
    @jwt_required
    async def delete_category(request, category_id: UUID) -> dict[str, str]:
        """Delete a category (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        deleted, _ = await Category.objects.filter(id=category_id).adelete()
        if not deleted:
            raise NotFoundAPIError("Category not found")

        cache.delete_many(["categories:all", "categories:tree"])
        return {"message": "Category deleted successfully"}


# =============================================================================
# Product Controller
# =============================================================================


class ProductController(APIController):
    """Product management controller."""

    prefix = "/products"
    tags = ["Products"]

    @staticmethod
    async def list_products(
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        category_id: UUID | None = None,
        category_slug: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
        is_featured: bool | None = None,
        is_on_sale: bool | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedProductsResponse:
        """List products with filtering and search."""
        queryset = Product.objects.filter(status="active")

        # Full-text search
        if q:
            search_vector = SearchVector("name", weight="A") + SearchVector(
                "description", weight="B"
            )
            search_query = SearchQuery(q)
            queryset = (
                queryset.annotate(
                    search=search_vector, rank=SearchRank(search_vector, search_query)
                )
                .filter(search=search_query)
                .order_by("-rank")
            )

        # Category filter
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        elif category_slug:
            category = await Category.objects.filter(slug=category_slug).afirst()
            if category:
                # Include subcategories
                descendants = category.get_descendants(include_self=True)
                queryset = queryset.filter(category__in=descendants)

        # Price filter
        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)

        # Stock filter
        if in_stock is not None:
            if in_stock:
                queryset = queryset.filter(
                    inventory__quantity__gt=F("inventory__reserved_quantity")
                ).distinct()
            else:
                queryset = queryset.exclude(
                    inventory__quantity__gt=F("inventory__reserved_quantity")
                )

        # Featured filter
        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured)

        # On sale filter
        if is_on_sale is not None:
            if is_on_sale:
                queryset = queryset.filter(
                    compare_at_price__isnull=False, compare_at_price__gt=F("price")
                )

        # Sorting
        if not q:  # Don't override search ranking
            order_field = sort_by if sort_by in ["name", "price", "created_at"] else "created_at"
            if sort_order == "desc":
                order_field = f"-{order_field}"
            queryset = queryset.order_by(order_field)

        # Annotate with review stats
        queryset = queryset.annotate(
            rating_avg=Avg("reviews__rating", filter=Q(reviews__status="approved")),
            review_count_val=Count("reviews", filter=Q(reviews__status="approved")),
        )

        # Pagination
        total = await queryset.acount()
        pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size

        products = queryset.select_related("category").prefetch_related("images")[
            offset : offset + page_size
        ]

        items = []
        async for p in products:
            primary_image = await p.images.filter(is_primary=True).afirst()
            if not primary_image:
                primary_image = await p.images.afirst()

            items.append(
                ProductListResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    price=p.price,
                    compare_at_price=p.compare_at_price,
                    is_on_sale=p.is_on_sale,
                    discount_percentage=p.discount_percentage,
                    primary_image=primary_image.image.url if primary_image else None,
                    in_stock=p.in_stock,
                    category_name=p.category.name if p.category else None,
                    rating_average=getattr(p, "rating_avg", None),
                    review_count=getattr(p, "review_count_val", 0),
                )
            )

        return PaginatedProductsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )

    @staticmethod
    async def get_product(product_slug: str) -> ProductDetailResponse:
        """Get product details."""
        product = await Product.objects.filter(
            slug=product_slug, status="active"
        ).select_related("category").prefetch_related(
            "images", "variants", "inventory"
        ).afirst()

        if not product:
            raise NotFoundAPIError("Product not found")

        # Get images
        images = [img async for img in product.images.all()]

        # Get variants with inventory
        variants = []
        async for v in product.variants.filter(is_active=True):
            inv = await Inventory.objects.filter(variant=v).afirst()
            variants.append(
                ProductVariantResponse(
                    id=v.id,
                    product_id=product.id,
                    name=v.name,
                    sku=v.sku,
                    barcode=v.barcode,
                    options=v.options,
                    price=v.price,
                    weight=v.weight,
                    is_active=v.is_active,
                    effective_price=v.effective_price,
                    image=None,  # TODO: Include image
                    stock_quantity=inv.available_quantity if inv else 0,
                    created_at=v.created_at,
                    updated_at=v.updated_at,
                )
            )

        # Get review stats
        from ecommerce.reviews.models import Review
        review_stats = await Review.objects.filter(
            product=product, status="approved"
        ).aggregate(
            rating_avg=Avg("rating"),
            count=Count("id"),
        )

        return ProductDetailResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            description=product.description,
            short_description=product.short_description,
            price=product.price,
            compare_at_price=product.compare_at_price,
            cost_price=product.cost_price,
            sku=product.sku,
            barcode=product.barcode,
            weight=product.weight,
            weight_unit=product.weight_unit,
            dimensions=product.dimensions,
            status=product.status,
            is_featured=product.is_featured,
            meta_title=product.meta_title,
            meta_description=product.meta_description,
            attributes=product.attributes,
            tags=product.tags,
            category=(
                CategoryResponse.model_validate(product.category)
                if product.category
                else None
            ),
            is_on_sale=product.is_on_sale,
            discount_percentage=product.discount_percentage,
            in_stock=product.in_stock,
            stock_quantity=product.stock_quantity,
            images=[
                {
                    "id": img.id,
                    "image": img.image.url,
                    "alt_text": img.alt_text,
                    "is_primary": img.is_primary,
                    "display_order": img.display_order,
                }
                for img in images
            ],
            variants=variants,
            rating_average=review_stats.get("rating_avg"),
            review_count=review_stats.get("count", 0),
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    @staticmethod
    @jwt_required
    async def create_product(request, data: ProductCreate) -> ProductDetailResponse:
        """Create a new product (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        # Verify category
        category = None
        if data.category_id:
            category = await Category.objects.filter(id=data.category_id).afirst()
            if not category:
                raise NotFoundAPIError("Category not found")

        # Check SKU uniqueness
        if await Product.objects.filter(sku=data.sku).aexists():
            raise ValidationAPIError("SKU already exists")

        product = await Product.objects.acreate(
            category=category,
            **data.model_dump(exclude={"category_id"}),
        )

        # Create default inventory
        await Inventory.objects.acreate(product=product, location="default", quantity=0)

        return await ProductController.get_product(product.slug)

    @staticmethod
    @jwt_required
    async def update_product(
        request, product_id: UUID, data: ProductUpdate
    ) -> ProductDetailResponse:
        """Update a product (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        update_data = data.model_dump(exclude_unset=True)

        # Handle category update
        if "category_id" in update_data:
            category_id = update_data.pop("category_id")
            if category_id:
                category = await Category.objects.filter(id=category_id).afirst()
                if not category:
                    raise NotFoundAPIError("Category not found")
                product.category = category
            else:
                product.category = None

        # Check SKU uniqueness
        if "sku" in update_data:
            existing = await Product.objects.filter(sku=update_data["sku"]).exclude(
                id=product_id
            ).aexists()
            if existing:
                raise ValidationAPIError("SKU already exists")

        for key, value in update_data.items():
            setattr(product, key, value)
        await product.asave()

        return await ProductController.get_product(product.slug)

    @staticmethod
    @jwt_required
    async def delete_product(request, product_id: UUID) -> dict[str, str]:
        """Delete a product (admin only)."""
        if not request.user.is_staff:
            raise ValidationAPIError("Admin access required")

        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        # Soft delete - just archive
        product.status = "archived"
        await product.asave()

        return {"message": "Product archived successfully"}

    @staticmethod
    async def get_featured() -> list[ProductListResponse]:
        """Get featured products."""
        cache_key = "products:featured"
        cached = cache.get(cache_key)
        if cached:
            return cached

        queryset = Product.objects.filter(
            status="active", is_featured=True
        ).select_related("category").prefetch_related("images")[:12]

        items = []
        async for p in queryset:
            primary_image = await p.images.filter(is_primary=True).afirst()
            if not primary_image:
                primary_image = await p.images.afirst()

            items.append(
                ProductListResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    price=p.price,
                    compare_at_price=p.compare_at_price,
                    is_on_sale=p.is_on_sale,
                    discount_percentage=p.discount_percentage,
                    primary_image=primary_image.image.url if primary_image else None,
                    in_stock=p.in_stock,
                    category_name=p.category.name if p.category else None,
                )
            )

        cache.set(cache_key, items, timeout=300)
        return items

    @staticmethod
    async def get_on_sale() -> list[ProductListResponse]:
        """Get products on sale."""
        queryset = Product.objects.filter(
            status="active",
            compare_at_price__isnull=False,
            compare_at_price__gt=F("price"),
        ).select_related("category").prefetch_related("images")[:20]

        items = []
        async for p in queryset:
            primary_image = await p.images.filter(is_primary=True).afirst()
            if not primary_image:
                primary_image = await p.images.afirst()

            items.append(
                ProductListResponse(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    price=p.price,
                    compare_at_price=p.compare_at_price,
                    is_on_sale=p.is_on_sale,
                    discount_percentage=p.discount_percentage,
                    primary_image=primary_image.image.url if primary_image else None,
                    in_stock=p.in_stock,
                    category_name=p.category.name if p.category else None,
                )
            )

        return items
