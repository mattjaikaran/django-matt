"""Pydantic schemas for catalog app."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Category Schemas
# =============================================================================


class CategoryBase(BaseModel):
    """Base category schema."""

    name: str
    slug: str | None = None
    description: str = ""
    meta_title: str = ""
    meta_description: str = ""
    is_active: bool = True
    display_order: int = 0


class CategoryCreate(CategoryBase):
    """Category creation schema."""

    parent_id: UUID | None = None


class CategoryUpdate(BaseModel):
    """Category update schema."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class CategoryResponse(CategoryBase):
    """Category response schema."""

    id: UUID
    parent_id: UUID | None = None
    full_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryTreeResponse(CategoryResponse):
    """Category tree response with children."""

    children: list["CategoryTreeResponse"] = []
    product_count: int = 0


# =============================================================================
# Product Image Schemas
# =============================================================================


class ProductImageResponse(BaseModel):
    """Product image response schema."""

    id: UUID
    image: str
    alt_text: str
    is_primary: bool
    display_order: int

    class Config:
        from_attributes = True


# =============================================================================
# Product Variant Schemas
# =============================================================================


class ProductVariantBase(BaseModel):
    """Base product variant schema."""

    name: str
    sku: str
    barcode: str = ""
    options: dict[str, Any] = {}
    price: Decimal | None = None
    weight: Decimal | None = None
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    """Product variant creation schema."""

    image_id: UUID | None = None


class ProductVariantUpdate(BaseModel):
    """Product variant update schema."""

    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    options: dict[str, Any] | None = None
    price: Decimal | None = None
    weight: Decimal | None = None
    is_active: bool | None = None
    image_id: UUID | None = None


class ProductVariantResponse(ProductVariantBase):
    """Product variant response schema."""

    id: UUID
    product_id: UUID
    effective_price: Decimal
    image: ProductImageResponse | None = None
    stock_quantity: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Inventory Schemas
# =============================================================================


class InventoryResponse(BaseModel):
    """Inventory response schema."""

    id: UUID
    location: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    reorder_level: int
    needs_reorder: bool
    last_restocked_at: datetime | None = None

    class Config:
        from_attributes = True


# =============================================================================
# Product Schemas
# =============================================================================


class ProductBase(BaseModel):
    """Base product schema."""

    name: str
    slug: str | None = None
    description: str = ""
    short_description: str = ""
    price: Decimal = Field(gt=0)
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    sku: str
    barcode: str = ""
    weight: Decimal | None = None
    weight_unit: str = "kg"
    dimensions: dict[str, Any] = {}
    status: str = "draft"
    is_featured: bool = False
    meta_title: str = ""
    meta_description: str = ""
    attributes: dict[str, Any] = {}
    tags: list[str] = []


class ProductCreate(ProductBase):
    """Product creation schema."""

    category_id: UUID | None = None


class ProductUpdate(BaseModel):
    """Product update schema."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    short_description: str | None = None
    category_id: UUID | None = None
    price: Decimal | None = None
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    sku: str | None = None
    barcode: str | None = None
    weight: Decimal | None = None
    weight_unit: str | None = None
    dimensions: dict[str, Any] | None = None
    status: str | None = None
    is_featured: bool | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    attributes: dict[str, Any] | None = None
    tags: list[str] | None = None


class ProductListResponse(BaseModel):
    """Product list response schema (minimal)."""

    id: UUID
    name: str
    slug: str
    price: Decimal
    compare_at_price: Decimal | None = None
    is_on_sale: bool
    discount_percentage: int
    primary_image: str | None = None
    in_stock: bool
    category_name: str | None = None
    rating_average: float | None = None
    review_count: int = 0

    class Config:
        from_attributes = True


class ProductDetailResponse(ProductBase):
    """Product detail response schema (full)."""

    id: UUID
    category: CategoryResponse | None = None
    is_on_sale: bool
    discount_percentage: int
    in_stock: bool
    stock_quantity: int
    images: list[ProductImageResponse] = []
    variants: list[ProductVariantResponse] = []
    rating_average: float | None = None
    review_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Search and Filter Schemas
# =============================================================================


class ProductSearchParams(BaseModel):
    """Product search parameters."""

    q: str | None = None  # Search query
    category_id: UUID | None = None
    category_slug: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None
    is_featured: bool | None = None
    is_on_sale: bool | None = None
    status: str | None = None
    attributes: dict[str, Any] | None = None
    tags: list[str] | None = None
    sort_by: str = "created_at"  # name, price, created_at, rating
    sort_order: str = "desc"  # asc, desc


class PaginatedProductsResponse(BaseModel):
    """Paginated products response."""

    items: list[ProductListResponse]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool
    next_cursor: str | None = None  # For cursor-based pagination
