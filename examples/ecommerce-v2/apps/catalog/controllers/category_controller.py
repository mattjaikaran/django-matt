from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError

from apps.catalog.models import Category
from apps.catalog.schemas import CategoryCreateSchema, CategorySchema, CategoryUpdateSchema


class CategoryController(APIController):
    prefix = "/categories"
    tags = ["Categories"]

    @staticmethod
    async def list_categories(request) -> dict:
        """List categories with optional parent filter."""
        params = request.GET
        parent_id = params.get("parent")

        qs = Category.objects.all()
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        elif parent_id is None and "parent" not in params:
            # Default: return all categories
            pass
        else:
            # ?parent= (empty) means root categories only
            qs = qs.filter(parent__isnull=True)

        items = []
        async for cat in qs.order_by("name"):
            items.append(
                CategorySchema(
                    id=str(cat.id),
                    name=cat.name,
                    slug=cat.slug,
                    description=cat.description,
                    parent_id=str(cat.parent_id) if cat.parent_id else None,
                    created_at=cat.created_at,
                    updated_at=cat.updated_at,
                ).model_dump(mode="json")
            )

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_category(request, body: CategoryCreateSchema) -> dict:
        """Create a new category."""
        if await Category.objects.filter(slug=body.slug).aexists():
            raise ValidationAPIError("A category with this slug already exists")

        if body.parent_id:
            if not await Category.objects.filter(id=body.parent_id).aexists():
                raise NotFoundAPIError("Parent category not found")

        cat = await Category.objects.acreate(
            name=body.name,
            slug=body.slug,
            description=body.description,
            parent_id=body.parent_id,
        )

        return CategorySchema(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            parent_id=str(cat.parent_id) if cat.parent_id else None,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    async def get_category(request, category_id: str) -> dict:
        """Get a category by ID."""
        cat = await Category.objects.filter(id=category_id).afirst()
        if not cat:
            raise NotFoundAPIError("Category not found")

        return CategorySchema(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            parent_id=str(cat.parent_id) if cat.parent_id else None,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def update_category(request, category_id: str, body: CategoryUpdateSchema) -> dict:
        """Update a category."""
        cat = await Category.objects.filter(id=category_id).afirst()
        if not cat:
            raise NotFoundAPIError("Category not found")

        updates = body.model_dump(exclude_unset=True)

        if "slug" in updates and updates["slug"] != cat.slug:
            if (
                await Category.objects.filter(slug=updates["slug"])
                .exclude(id=category_id)
                .aexists()
            ):
                raise ValidationAPIError("A category with this slug already exists")

        if "parent_id" in updates and updates["parent_id"]:
            if updates["parent_id"] == str(cat.id):
                raise ValidationAPIError("A category cannot be its own parent")
            if not await Category.objects.filter(id=updates["parent_id"]).aexists():
                raise NotFoundAPIError("Parent category not found")

        for field, value in updates.items():
            setattr(cat, field, value)
        await cat.asave()

        return CategorySchema(
            id=str(cat.id),
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            parent_id=str(cat.parent_id) if cat.parent_id else None,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        ).model_dump(mode="json")

    @staticmethod
    @jwt_required
    async def delete_category(request, category_id: str) -> dict:
        """Delete a category."""
        deleted, _ = await Category.objects.filter(id=category_id).adelete()
        if not deleted:
            raise NotFoundAPIError("Category not found")

        return {"message": "Category deleted"}
