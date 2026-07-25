"""Controllers for {{ project_name }}."""

from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_matt.auth import jwt_required

from .models import Product, Review, Store
from .schemas import (
    ProductCreate,
    ProductSchema,
    ReviewCreate,
    ReviewSchema,
    StoreCreate,
    StoreSchema,
)


async def health(request) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
async def list_products(request) -> JsonResponse:
    """Public product listing with optional search."""
    q = request.GET.get("q", "")
    qs = Product.objects.filter(is_active=True)
    if q:
        qs = qs.filter(title__icontains=q)
    products = [
        ProductSchema.model_validate(p).model_dump(mode="json")
        async for p in qs.select_related("store")
    ]
    return JsonResponse({"products": products})


@require_http_methods(["GET"])
async def get_product(request, product_id: int) -> JsonResponse:
    try:
        product = await Product.objects.select_related("store").aget(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    avg_rating = await Review.objects.filter(product=product).aaggregate(
        avg=Avg("rating")
    )
    data = ProductSchema.model_validate(product).model_dump(mode="json")
    data["avg_rating"] = avg_rating.get("avg")
    return JsonResponse(data)


@require_http_methods(["POST"])
@jwt_required
async def create_store(request) -> JsonResponse:
    import orjson

    data = StoreCreate.model_validate(orjson.loads(request.body))
    store = await Store.objects.acreate(
        owner=request.user,
        name=data.name,
        slug=data.slug,
        description=data.description,
    )
    return JsonResponse(
        StoreSchema.model_validate(store).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["POST"])
@jwt_required
async def create_product(request, store_slug: str) -> JsonResponse:
    import orjson

    try:
        store = await Store.objects.aget(slug=store_slug, owner=request.user)
    except Store.DoesNotExist:
        return JsonResponse({"error": "Store not found"}, status=404)

    data = ProductCreate.model_validate(orjson.loads(request.body))
    product = await Product.objects.acreate(
        store=store,
        title=data.title,
        description=data.description,
        price=data.price,
        image_url=data.image_url,
    )
    return JsonResponse(
        ProductSchema.model_validate(product).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["POST"])
@jwt_required
async def create_review(request, product_id: int) -> JsonResponse:
    import orjson

    try:
        product = await Product.objects.aget(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)

    data = ReviewCreate.model_validate(orjson.loads(request.body))
    review = await Review.objects.acreate(
        product=product,
        user=request.user,
        rating=data.rating,
        comment=data.comment,
    )
    return JsonResponse(
        ReviewSchema.model_validate(review).model_dump(mode="json"),
        status=201,
    )


@require_http_methods(["GET"])
async def list_reviews(request, product_id: int) -> JsonResponse:
    reviews = [
        ReviewSchema.model_validate(r).model_dump(mode="json")
        async for r in Review.objects.filter(product_id=product_id)
    ]
    return JsonResponse({"reviews": reviews})
