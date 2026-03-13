from decimal import Decimal

from django.db.models import Q
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError

from apps.catalog.models import Product
from apps.catalog.schemas import ProductCreateSchema, ProductSchema, ProductUpdateSchema
from apps.stores.models import Store


class ProductController(APIController):
    prefix = "/products"
    tags = ["Products"]

    @staticmethod
    async def list_products(request) -> dict:
        """List products with filtering and pagination."""
        params = request.GET

        qs = Product.objects.filter(is_active=True).select_related("store", "category")

        # Filters
        if category_id := params.get("category"):
            qs = qs.filter(category_id=category_id)
        if store_id := params.get("store"):
            qs = qs.filter(store_id=store_id)
        if min_price := params.get("min_price"):
            qs = qs.filter(price__gte=Decimal(min_price))
        if max_price := params.get("max_price"):
            qs = qs.filter(price__lte=Decimal(max_price))
        if search := params.get("search"):
            qs = qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        # Pagination
        total = await qs.acount()
        limit = min(int(params.get("limit", "20")), 100)
        offset = int(params.get("offset", "0"))
        qs = qs.order_by("-created_at")[offset : offset + limit]

        items = []
        async for product in qs:
            items.append(
                ProductSchema(
                    id=str(product.id),
                    store_id=str(product.store_id),
                    category_id=str(product.category_id) if product.category_id else None,
                    name=product.name,
                    slug=product.slug,
                    description=product.description,
                    price=product.price,
                    compare_at_price=product.compare_at_price,
                    is_active=product.is_active,
                    image_url=product.image_url,
                    created_at=product.created_at,
                    updated_at=product.updated_at,
                ).model_dump(mode="json")
            )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    @jwt_required
    async def create_product(request) -> dict:
        """Create a product. Must own the store."""
        body = request.json
        data = ProductCreateSchema(**body)

        # Verify store ownership
        store = await Store.objects.filter(id=data.store_id).afirst()
        if not store:
            raise NotFoundAPIError("Store not found")
        if store.owner_id != request.user.id:
            raise APIError(status_code=403, message="You do not own this store")

        # Check slug uniqueness
        if await Product.objects.filter(slug=data.slug).aexists():
            raise ValidationAPIError("A product with this slug already exists")

        # Validate category if provided
        if data.category_id:
            from apps.catalog.models import Category
            if not await Category.objects.filter(id=data.category_id).aexists():
                raise NotFoundAPIError("Category not found")

        product = await Product.objects.acreate(
            store_id=data.store_id,
            category_id=data.category_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            price=data.price,
            compare_at_price=data.compare_at_price,
            image_url=data.image_url,
        )

        return ProductSchema(
            id=str(product.id),
            store_id=str(product.store_id),
            category_id=str(product.category_id) if product.category_id else None,
            name=product.name,
            slug=product.slug,
            description=product.description,
            price=product.price,
            compare_at_price=product.compare_at_price,
            is_active=product.is_active,
            image_url=product.image_url,
            created_at=product.created_at,
            updated_at=product.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    async def get_product(request, product_id: str) -> dict:
        """Get a product by ID."""
        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        return ProductSchema(
            id=str(product.id),
            store_id=str(product.store_id),
            category_id=str(product.category_id) if product.category_id else None,
            name=product.name,
            slug=product.slug,
            description=product.description,
            price=product.price,
            compare_at_price=product.compare_at_price,
            is_active=product.is_active,
            image_url=product.image_url,
            created_at=product.created_at,
            updated_at=product.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_product(request, product_id: str) -> dict:
        """Update a product. Must own the store."""
        product = await Product.objects.select_related("store").filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        store = await Store.objects.filter(id=product.store_id).afirst()
        if store.owner_id != request.user.id:
            raise APIError(status_code=403, message="You do not own this store")

        body = request.json
        data = ProductUpdateSchema(**body)
        updates = data.model_dump(exclude_unset=True)

        if "slug" in updates and updates["slug"] != product.slug:
            if await Product.objects.filter(slug=updates["slug"]).exclude(id=product_id).aexists():
                raise ValidationAPIError("A product with this slug already exists")

        if "category_id" in updates and updates["category_id"]:
            from apps.catalog.models import Category
            if not await Category.objects.filter(id=updates["category_id"]).aexists():
                raise NotFoundAPIError("Category not found")

        for field, value in updates.items():
            setattr(product, field, value)
        await product.asave()

        return ProductSchema(
            id=str(product.id),
            store_id=str(product.store_id),
            category_id=str(product.category_id) if product.category_id else None,
            name=product.name,
            slug=product.slug,
            description=product.description,
            price=product.price,
            compare_at_price=product.compare_at_price,
            is_active=product.is_active,
            image_url=product.image_url,
            created_at=product.created_at,
            updated_at=product.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_product(request, product_id: str) -> dict:
        """Delete a product. Must own the store."""
        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        store = await Store.objects.filter(id=product.store_id).afirst()
        if store.owner_id != request.user.id:
            raise APIError(status_code=403, message="You do not own this store")

        await product.adelete()
        return {"message": "Product deleted"}
