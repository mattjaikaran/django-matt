from uuid import UUID

from django.db.models import Q
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError, ValidationAPIError

from apps.stores.models import Store
from apps.stores.schemas import StoreCreateSchema, StoreSchema, StoreUpdateSchema


class StoreController(APIController):
    prefix = "/stores"
    tags = ["Stores"]

    @staticmethod
    async def list_stores(request) -> dict:
        """List stores with optional search and pagination."""
        params = request.GET
        search = params.get("search")
        limit = min(int(params.get("limit", "20")), 100)
        offset = int(params.get("offset", "0"))

        qs = Store.objects.filter(is_active=True)

        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        total = await qs.acount()
        stores = qs.order_by("-created_at")[offset : offset + limit]

        items = []
        async for store in stores:
            items.append(
                StoreSchema(
                    id=str(store.id),
                    name=store.name,
                    slug=store.slug,
                    description=store.description,
                    logo_url=store.logo_url,
                    is_active=store.is_active,
                    rating=store.rating,
                    owner_id=store.owner_id,
                    created_at=store.created_at,
                    updated_at=store.updated_at,
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
    async def create_store(request, body: StoreCreateSchema) -> dict:
        """Create a new store. Owner is set to the authenticated user."""
        # Check slug uniqueness
        if await Store.objects.filter(slug=body.slug).aexists():
            raise ValidationAPIError("A store with this slug already exists")

        store = await Store.objects.acreate(
            owner=request.user,
            name=body.name,
            slug=body.slug,
            description=body.description,
            logo_url=body.logo_url,
        )

        return StoreSchema(
            id=str(store.id),
            name=store.name,
            slug=store.slug,
            description=store.description,
            logo_url=store.logo_url,
            is_active=store.is_active,
            rating=store.rating,
            owner_id=store.owner_id,
            created_at=store.created_at,
            updated_at=store.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    async def get_store(request, store_id: str) -> dict:
        """Get a store by slug or UUID."""
        # Try UUID first, fall back to slug
        try:
            UUID(store_id)
            store = await Store.objects.filter(id=store_id, is_active=True).afirst()
        except ValueError:
            store = await Store.objects.filter(slug=store_id, is_active=True).afirst()

        if not store:
            raise NotFoundAPIError("Store not found")

        return StoreSchema(
            id=str(store.id),
            name=store.name,
            slug=store.slug,
            description=store.description,
            logo_url=store.logo_url,
            is_active=store.is_active,
            rating=store.rating,
            owner_id=store.owner_id,
            created_at=store.created_at,
            updated_at=store.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_store(request, store_id: str, body: StoreUpdateSchema) -> dict:
        """Update a store. Must be owner."""
        store = await Store.objects.filter(id=store_id).afirst()
        if not store:
            raise NotFoundAPIError("Store not found")

        if store.owner_id != request.user.id:
            raise APIError(status_code=403, message="You do not own this store")

        updates = body.model_dump(exclude_unset=True)

        # Check slug uniqueness if changing
        if "slug" in updates and updates["slug"] != store.slug:
            if await Store.objects.filter(slug=updates["slug"]).exclude(id=store_id).aexists():
                raise ValidationAPIError("A store with this slug already exists")

        for field, value in updates.items():
            setattr(store, field, value)
        await store.asave()

        return StoreSchema(
            id=str(store.id),
            name=store.name,
            slug=store.slug,
            description=store.description,
            logo_url=store.logo_url,
            is_active=store.is_active,
            rating=store.rating,
            owner_id=store.owner_id,
            created_at=store.created_at,
            updated_at=store.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_store(request, store_id: str) -> dict:
        """Delete a store. Must be owner."""
        store = await Store.objects.filter(id=store_id).afirst()
        if not store:
            raise NotFoundAPIError("Store not found")

        if store.owner_id != request.user.id:
            raise APIError(status_code=403, message="You do not own this store")

        await store.adelete()
        return {"message": "Store deleted"}
