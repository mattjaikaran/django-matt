import orjson
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError

from apps.catalog.models import Product, Variant
from apps.catalog.schemas import VariantCreateSchema, VariantSchema, VariantUpdateSchema
from apps.stores.models import Store


async def _check_store_ownership(product: Product, user) -> None:
    """Verify the user owns the store that the product belongs to."""
    store = await Store.objects.filter(id=product.store_id).afirst()
    if store.owner_id != user.id:
        raise APIError(status_code=403, message="You do not own this store")


class VariantController(APIController):
    prefix = "/products/{product_id}/variants"
    tags = ["Variants"]

    @staticmethod
    async def list_variants(request, product_id: str) -> dict:
        """List variants for a product."""
        if not await Product.objects.filter(id=product_id).aexists():
            raise NotFoundAPIError("Product not found")

        qs = Variant.objects.filter(product_id=product_id).order_by("name")

        items = []
        async for variant in qs:
            items.append(
                VariantSchema(
                    id=str(variant.id),
                    product_id=str(variant.product_id),
                    name=variant.name,
                    sku=variant.sku,
                    price_override=variant.price_override,
                    is_active=variant.is_active,
                    created_at=variant.created_at,
                    updated_at=variant.updated_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_variant(request, product_id: str) -> dict:
        """Create a variant for a product. Must own the store."""
        product = await Product.objects.filter(id=product_id).afirst()
        if not product:
            raise NotFoundAPIError("Product not found")

        await _check_store_ownership(product, request.user)

        body = orjson.loads(request.body)
        data = VariantCreateSchema(**body)

        if await Variant.objects.filter(sku=data.sku).aexists():
            raise ValidationAPIError("A variant with this SKU already exists")

        variant = await Variant.objects.acreate(
            product_id=product_id,
            name=data.name,
            sku=data.sku,
            price_override=data.price_override,
        )

        return VariantSchema(
            id=str(variant.id),
            product_id=str(variant.product_id),
            name=variant.name,
            sku=variant.sku,
            price_override=variant.price_override,
            is_active=variant.is_active,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    async def get_variant(request, product_id: str, variant_id: str) -> dict:
        """Get a variant by ID."""
        variant = await Variant.objects.filter(
            id=variant_id, product_id=product_id
        ).afirst()
        if not variant:
            raise NotFoundAPIError("Variant not found")

        return VariantSchema(
            id=str(variant.id),
            product_id=str(variant.product_id),
            name=variant.name,
            sku=variant.sku,
            price_override=variant.price_override,
            is_active=variant.is_active,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_variant(request, product_id: str, variant_id: str) -> dict:
        """Update a variant. Must own the store."""
        variant = await Variant.objects.filter(
            id=variant_id, product_id=product_id
        ).afirst()
        if not variant:
            raise NotFoundAPIError("Variant not found")

        product = await Product.objects.filter(id=product_id).afirst()
        await _check_store_ownership(product, request.user)

        body = orjson.loads(request.body)
        data = VariantUpdateSchema(**body)
        updates = data.model_dump(exclude_unset=True)

        if "sku" in updates and updates["sku"] != variant.sku:
            if await Variant.objects.filter(sku=updates["sku"]).exclude(id=variant_id).aexists():
                raise ValidationAPIError("A variant with this SKU already exists")

        for field, value in updates.items():
            setattr(variant, field, value)
        await variant.asave()

        return VariantSchema(
            id=str(variant.id),
            product_id=str(variant.product_id),
            name=variant.name,
            sku=variant.sku,
            price_override=variant.price_override,
            is_active=variant.is_active,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_variant(request, product_id: str, variant_id: str) -> dict:
        """Delete a variant. Must own the store."""
        variant = await Variant.objects.filter(
            id=variant_id, product_id=product_id
        ).afirst()
        if not variant:
            raise NotFoundAPIError("Variant not found")

        product = await Product.objects.filter(id=product_id).afirst()
        await _check_store_ownership(product, request.user)

        await variant.adelete()
        return {"message": "Variant deleted"}
